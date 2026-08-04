from datetime import timedelta
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsRole, request_role
from accounts.roles import CLINICAL_ROLES

from .models import AuditEvent, BreakGlassAccess, Consent
from .serializers import (
    AuditEventSerializer,
    BreakGlassReviewSerializer,
    BreakGlassSerializer,
    ConsentRevokeSerializer,
    ConsentSerializer,
)
from .services import audit


class ConsentListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient"]

    def get(self, request):
        qs = Consent.objects.filter(patient=request.user).select_related("granted_to")
        return Response(ConsentSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent = serializer.save(
            patient=request.user,
            source="patient_portal",
            status=Consent.Status.ACTIVE,
        )
        audit(
            actor=request.user,
            patient=request.user,
            action="consent.granted",
            resource=consent,
            purpose=consent.purpose,
            decision=AuditEvent.Decision.ALLOW,
            request=request,
        )
        try:
            from interoperability.services import emit_event

            emit_event(
                "consent.granted", consent,
                {"type": consent.consent_type, "purpose": consent.purpose, "granted_to": consent.granted_to_id},
                actor=request.user, patient=request.user, request=request,
            )
        except Exception:
            pass
        return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


class ConsentRevokeView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient"]

    def post(self, request, pk):
        consent = get_object_or_404(Consent, pk=pk, patient=request.user)
        serializer = ConsentRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        consent.revoke(serializer.validated_data.get("reason", ""))
        audit(
            actor=request.user,
            patient=request.user,
            action="consent.revoked",
            resource=consent,
            purpose=consent.purpose,
            request=request,
        )
        try:
            from interoperability.services import emit_event

            emit_event(
                "consent.revoked", consent,
                {"type": consent.consent_type, "purpose": consent.purpose, "reason": consent.revocation_reason},
                actor=request.user, patient=request.user, request=request,
            )
        except Exception:
            pass
        return Response(ConsentSerializer(consent).data)


class PatientConsentStatusView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [*sorted(CLINICAL_ROLES), "admin"]

    def get(self, request, patient_id):
        patient = get_object_or_404(User, pk=patient_id, role=User.Role.PATIENT)
        if request_role(request) in CLINICAL_ROLES:
            from appointments.models import Appointment

            related = Appointment.objects.filter(
                patient=patient, doctor=request.user
            ).exists()
            if not related:
                audit(
                    actor=request.user,
                    patient=patient,
                    action="consent.view",
                    resource_type="Consent",
                    purpose="treatment",
                    decision=AuditEvent.Decision.DENY,
                    request=request,
                )
                return Response({"detail": "No care relationship with this patient."}, status=403)
        qs = Consent.objects.filter(patient=patient).select_related("granted_to")
        audit(
            actor=request.user,
            patient=patient,
            action="consent.view",
            resource_type="Consent",
            purpose="treatment",
            decision=AuditEvent.Decision.ALLOW,
            request=request,
        )
        return Response(ConsentSerializer(qs, many=True).data)


class BreakGlassListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [*sorted(CLINICAL_ROLES), "admin"]

    def get(self, request):
        qs = BreakGlassAccess.objects.select_related("requester", "patient")
        if request_role(request) != User.Role.ADMIN:
            qs = qs.filter(requester=request.user)
        return Response(BreakGlassSerializer(qs, many=True).data)

    def post(self, request):
        if request_role(request) not in CLINICAL_ROLES:
            return Response({"detail": "Only clinicians can request emergency access."}, status=403)
        serializer = BreakGlassSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        patient = serializer.validated_data["patient"]
        access = serializer.save(requester=request.user)
        audit(
            actor=request.user,
            patient=patient,
            action="access.break_glass.started",
            resource=access,
            purpose="emergency",
            decision=AuditEvent.Decision.ALLOW,
            emergency_access=True,
            metadata={"reason": access.reason},
            request=request,
        )
        return Response(BreakGlassSerializer(access).data, status=status.HTTP_201_CREATED)


class BreakGlassEndView(APIView):
    permission_classes = [IsRole]
    allowed_roles = [*sorted(CLINICAL_ROLES), "admin"]

    def post(self, request, pk):
        qs = BreakGlassAccess.objects.all()
        if request_role(request) != User.Role.ADMIN:
            qs = qs.filter(requester=request.user)
        access = get_object_or_404(qs, pk=pk)
        access.end()
        audit(
            actor=request.user,
            patient=access.patient,
            action="access.break_glass.ended",
            resource=access,
            purpose="emergency",
            emergency_access=True,
            request=request,
        )
        return Response(BreakGlassSerializer(access).data)


class BreakGlassReviewView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin", "platform_super_admin", "compliance_admin", "clinical_safety_admin"]

    def post(self, request, pk):
        access = get_object_or_404(BreakGlassAccess, pk=pk)
        serializer = BreakGlassReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access.status = (
            BreakGlassAccess.Status.REVIEWED
            if serializer.validated_data["action"] == "approve"
            else BreakGlassAccess.Status.REJECTED
        )
        access.reviewed_by = request.user
        access.reviewed_at = timezone.now()
        access.review_notes = serializer.validated_data.get("notes", "")
        access.save(
            update_fields=["status", "reviewed_by", "reviewed_at", "review_notes"]
        )
        audit(
            actor=request.user,
            patient=access.patient,
            action=f"access.break_glass.{serializer.validated_data['action']}",
            resource=access,
            purpose="compliance_review",
            request=request,
        )
        return Response(BreakGlassSerializer(access).data)


class ComplianceOverviewView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin", "platform_super_admin", "compliance_admin", "compliance_officer"]

    def get(self, request):
        consent_status = {
            row["status"]: row["count"]
            for row in Consent.objects.values("status").annotate(count=Count("id"))
        }
        return Response(
            {
                "consents": consent_status,
                "active_break_glass": BreakGlassAccess.objects.filter(
                    status=BreakGlassAccess.Status.ACTIVE,
                    expires_at__gt=timezone.now(),
                ).count(),
                "unreviewed_break_glass": BreakGlassAccess.objects.filter(
                    status__in=[
                        BreakGlassAccess.Status.ACTIVE,
                        BreakGlassAccess.Status.ENDED,
                    ]
                ).count(),
                "audit_events_24h": AuditEvent.objects.filter(
                    created_at__gte=timezone.now() - timedelta(hours=24)
                ).count(),
                "denied_access_24h": AuditEvent.objects.filter(
                    decision=AuditEvent.Decision.DENY,
                    created_at__gte=timezone.now() - timedelta(hours=24),
                ).count(),
            }
        )


class AuditEventListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin", "platform_super_admin", "compliance_admin", "compliance_officer"]

    def get(self, request):
        qs = AuditEvent.objects.select_related("actor", "patient")
        action = request.query_params.get("action")
        patient_id = request.query_params.get("patient")
        decision = request.query_params.get("decision")
        if action:
            qs = qs.filter(action__icontains=action)
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if decision:
            qs = qs.filter(decision=decision)
        try:
            limit = min(max(int(request.query_params.get("limit", 200)), 1), 1000)
        except ValueError:
            limit = 200
        return Response(AuditEventSerializer(qs[:limit], many=True).data)


class PrivilegedAccessListCreateView(APIView):
    """Request and review controlled administrator access to a named patient."""

    permission_classes = [IsRole]
    allowed_roles = [
        "admin", "platform_super_admin", "operations_admin",
        "compliance_admin", "clinical_safety_admin",
    ]

    def get(self, request):
        from accounts.permissions import request_role
        from enterprise.access import can_review_compliance, can_review_clinical_safety, is_platform_super_admin
        from .models import PrivilegedAccessGrant
        from .serializers import PrivilegedAccessGrantSerializer

        qs = PrivilegedAccessGrant.objects.select_related("requester", "patient", "approved_by")
        if not (is_platform_super_admin(request.user) or can_review_compliance(request.user) or can_review_clinical_safety(request.user)):
            qs = qs.filter(requester=request.user)
        patient_id = request.query_params.get("patient")
        status_value = request.query_params.get("status")
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if status_value:
            qs = qs.filter(status=status_value)
        return Response(PrivilegedAccessGrantSerializer(qs[:250], many=True).data)

    def post(self, request):
        from accounts.permissions import request_role
        from enterprise.access import is_any_admin
        from .models import PrivilegedAccessGrant
        from .serializers import PrivilegedAccessGrantSerializer

        if not is_any_admin(request.user):
            return Response({"detail": "Only an administrator context can request privileged access."}, status=403)
        if not request.user.mfa_enabled:
            return Response({"detail": "MFA must be enabled before requesting clinical elevation."}, status=403)
        serializer = PrivilegedAccessGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant = serializer.save(
            requester=request.user,
            status=PrivilegedAccessGrant.Status.PENDING,
            mfa_verified_at=timezone.now(),
        )
        audit(
            actor=request.user,
            patient=grant.patient,
            action="access.privileged.requested",
            resource=grant,
            purpose=grant.purpose,
            decision=AuditEvent.Decision.ALLOW,
            metadata={"scopes": grant.scopes, "read_only": grant.read_only, "role": request_role(request)},
            request=request,
        )
        return Response(PrivilegedAccessGrantSerializer(grant).data, status=status.HTTP_201_CREATED)


class PrivilegedAccessDecisionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin", "platform_super_admin", "compliance_admin", "clinical_safety_admin"]

    def post(self, request, pk):
        from enterprise.access import can_review_compliance, can_review_clinical_safety, is_platform_super_admin
        from .models import PrivilegedAccessGrant
        from .serializers import PrivilegedAccessDecisionSerializer, PrivilegedAccessGrantSerializer

        grant = get_object_or_404(PrivilegedAccessGrant, pk=pk)
        serializer = PrivilegedAccessDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        notes = serializer.validated_data.get("notes", "")
        if action in {"approve", "reject"} and not (
            is_platform_super_admin(request.user)
            or can_review_compliance(request.user)
            or can_review_clinical_safety(request.user)
        ):
            return Response({"detail": "A compliance or clinical-safety administrator must decide this request."}, status=403)
        if request.user.id == grant.requester_id:
            return Response({"detail": "The requester cannot decide their own elevated-access request."}, status=403)
        now = timezone.now()
        if action == "approve":
            if grant.status != PrivilegedAccessGrant.Status.PENDING:
                return Response({"detail": "Only pending requests may be approved."}, status=409)
            grant.status = PrivilegedAccessGrant.Status.ACTIVE
            grant.approved_by = request.user
            grant.approved_at = now
            grant.expires_at = now + timedelta(minutes=serializer.validated_data["duration_minutes"])
        elif action == "reject":
            grant.status = PrivilegedAccessGrant.Status.REJECTED
            grant.reviewed_by = request.user
            grant.reviewed_at = now
            grant.review_notes = notes
        elif action == "revoke":
            if not (request.user.id == grant.requester_id or can_review_compliance(request.user) or is_platform_super_admin(request.user)):
                return Response({"detail": "Not allowed to revoke this grant."}, status=403)
            grant.status = PrivilegedAccessGrant.Status.REVOKED
            grant.revoked_at = now
            grant.reviewed_by = request.user
            grant.review_notes = notes
        else:
            grant.status = PrivilegedAccessGrant.Status.REVIEWED
            grant.reviewed_by = request.user
            grant.reviewed_at = now
            grant.review_notes = notes
        grant.save()
        audit(
            actor=request.user,
            patient=grant.patient,
            action=f"access.privileged.{action}",
            resource=grant,
            purpose=grant.purpose,
            decision=AuditEvent.Decision.ALLOW if action == "approve" else AuditEvent.Decision.NOT_APPLICABLE,
            metadata={"notes": notes, "scopes": grant.scopes},
            request=request,
        )
        return Response(PrivilegedAccessGrantSerializer(grant).data)
