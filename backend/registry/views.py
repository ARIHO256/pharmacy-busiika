from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsRole, request_role
from accounts.roles import CLINICAL_ROLES, PROFESSIONAL_ROLES, portal_path_for_role
from governance.models import AuditEvent
from governance.services import audit

from .models import CareRelationship, Organization, OrganizationLocation, PractitionerCredential, PractitionerRole
from .serializers import (
    CareRelationshipSerializer,
    OrganizationLocationSerializer,
    OrganizationSerializer,
    PractitionerCredentialSerializer,
    PractitionerRoleSerializer,
)

PROVIDER_ROLES = ["pharmacy", "lab", "hospital", "insurance", "doctor"]


class OrganizationListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        self.allowed_roles = PROVIDER_ROLES + ["admin"]
        return [IsRole()]

    def get(self, request):
        qs = Organization.objects.filter(status=Organization.Status.VERIFIED, active=True).prefetch_related("locations")
        org_type = request.query_params.get("type")
        search = request.query_params.get("search")
        if org_type:
            qs = qs.filter(organization_type=org_type)
        if search:
            from django.db.models import Q

            qs = qs.filter(Q(legal_name__icontains=search) | Q(trading_name__icontains=search) | Q(district__icontains=search))
        return Response(OrganizationSerializer(qs, many=True, context={"request": request}).data)

    @transaction.atomic
    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status_value = Organization.Status.VERIFIED if request_role(request) == User.Role.ADMIN else Organization.Status.PENDING
        organization = serializer.save(owner=request.user, status=status_value)
        audit(
            actor=request.user,
            action="registry.organization.created",
            resource=organization,
            purpose="provider_registry",
            decision=AuditEvent.Decision.ALLOW,
            request=request,
        )
        return Response(OrganizationSerializer(organization, context={"request": request}).data, status=201)


class MyOrganizationListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = PROVIDER_ROLES + ["admin"]

    def get(self, request):
        qs = Organization.objects.all() if request_role(request) == User.Role.ADMIN else Organization.objects.filter(owner=request.user)
        return Response(OrganizationSerializer(qs.prefetch_related("locations"), many=True, context={"request": request}).data)


class OrganizationDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        self.allowed_roles = PROVIDER_ROLES + ["admin"]
        return [IsRole()]

    def get_object(self, request, public_id):
        qs = Organization.objects.prefetch_related("locations")
        obj = get_object_or_404(qs, public_id=public_id)
        if request.method == "GET" and obj.status == Organization.Status.VERIFIED and obj.active:
            return obj
        if request.user.is_authenticated and (request_role(request) == User.Role.ADMIN or obj.owner_id == request.user.id):
            return obj
        return None

    def get(self, request, public_id):
        obj = self.get_object(request, public_id)
        if obj is None:
            return Response({"detail": "Organization not found."}, status=404)
        return Response(OrganizationSerializer(obj, context={"request": request}).data)

    def patch(self, request, public_id):
        obj = self.get_object(request, public_id)
        if obj is None:
            return Response({"detail": "Organization not found."}, status=404)
        serializer = OrganizationSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit(actor=request.user, action="registry.organization.updated", resource=obj, purpose="provider_registry", request=request)
        return Response(OrganizationSerializer(obj, context={"request": request}).data)


class OrganizationLocationListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = PROVIDER_ROLES + ["admin"]

    def _organization(self, request, public_id):
        qs = Organization.objects.all()
        if request_role(request) != User.Role.ADMIN:
            qs = qs.filter(owner=request.user)
        return get_object_or_404(qs, public_id=public_id)

    def get(self, request, public_id):
        organization = self._organization(request, public_id)
        return Response(OrganizationLocationSerializer(organization.locations.all(), many=True).data)

    def post(self, request, public_id):
        organization = self._organization(request, public_id)
        serializer = OrganizationLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save(organization=organization)
        audit(actor=request.user, action="registry.location.created", resource=location, purpose="provider_registry", request=request)
        return Response(OrganizationLocationSerializer(location).data, status=201)


class PractitionerCredentialListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(PROFESSIONAL_ROLES | {"admin"})

    def get(self, request):
        qs = PractitionerCredential.objects.select_related("practitioner", "verified_by")
        if request_role(request) != User.Role.ADMIN:
            qs = qs.filter(practitioner=request.user)
        practitioner_id = request.query_params.get("practitioner")
        if request_role(request) == User.Role.ADMIN and practitioner_id:
            qs = qs.filter(practitioner_id=practitioner_id)
        return Response(PractitionerCredentialSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request):
        practitioner = request.user
        if request_role(request) == User.Role.ADMIN:
            practitioner = get_object_or_404(User, pk=request.data.get("practitioner"), role__in=PROFESSIONAL_ROLES)
        serializer = PractitionerCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.save(practitioner=practitioner)
        audit(actor=request.user, action="registry.credential.submitted", resource=credential, purpose="credentialing", request=request)
        return Response(PractitionerCredentialSerializer(credential, context={"request": request}).data, status=201)


class PractitionerCredentialVerifyView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def post(self, request, pk):
        credential = get_object_or_404(PractitionerCredential, pk=pk)
        new_status = request.data.get("status")
        allowed = {
            PractitionerCredential.Status.VERIFIED,
            PractitionerCredential.Status.REJECTED,
            PractitionerCredential.Status.EXPIRED,
            PractitionerCredential.Status.REVOKED,
        }
        if new_status not in allowed:
            return Response({"detail": "Invalid credential status."}, status=400)
        reason = str(request.data.get("reason", "")).strip()
        if new_status in {PractitionerCredential.Status.REJECTED, PractitionerCredential.Status.EXPIRED, PractitionerCredential.Status.REVOKED} and not reason:
            return Response({"detail": "A reason is required for this credential decision."}, status=400)
        credential.status = new_status
        credential.verified_by = request.user
        credential.verified_at = timezone.now()
        credential.save(update_fields=["status", "verified_by", "verified_at"])
        practitioner = credential.practitioner
        profile = (
            getattr(practitioner, "doctor_profile", None)
            if practitioner.role == User.Role.DOCTOR
            else getattr(practitioner, "staff_profile", None)
        )
        profile_status = {
            PractitionerCredential.Status.VERIFIED: "verified",
            PractitionerCredential.Status.REJECTED: "rejected",
            PractitionerCredential.Status.EXPIRED: "expired",
            PractitionerCredential.Status.REVOKED: "revoked",
        }[new_status]
        if profile is not None:
            profile.status = profile_status
            if hasattr(profile, "verification_notes"):
                profile.verification_notes = reason
                profile.save(update_fields=["status", "verification_notes"])
            else:
                profile.save(update_fields=["status"])
        practitioner.is_verified = new_status == PractitionerCredential.Status.VERIFIED
        if new_status == PractitionerCredential.Status.REVOKED:
            practitioner.is_active = False
            practitioner.save(update_fields=["is_verified", "is_active"])
        elif new_status == PractitionerCredential.Status.VERIFIED:
            practitioner.is_active = True
            practitioner.save(update_fields=["is_verified", "is_active"])
        else:
            practitioner.save(update_fields=["is_verified"])
        audit(
            actor=request.user,
            action=f"registry.credential.{new_status}",
            resource=credential,
            purpose="credentialing",
            metadata={"reason": reason},
            request=request,
        )
        try:
            from communication.services import notify

            notify(
                practitioner,
                f"Credential {profile_status}",
                f"Your professional credential {credential.identifier} is now {profile_status}.",
                kind="verification",
                priority="high",
                action_url=portal_path_for_role(practitioner.role),
            )
        except Exception:
            pass
        return Response(PractitionerCredentialSerializer(credential, context={"request": request}).data)


class PractitionerRoleListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET" and self.request.query_params.get("public") == "1":
            return [AllowAny()]
        self.allowed_roles = sorted(PROFESSIONAL_ROLES | {"admin"})
        return [IsRole()]

    def get(self, request):
        qs = PractitionerRole.objects.select_related("practitioner", "organization", "location")
        if request.query_params.get("public") == "1":
            qs = qs.filter(active=True, organization__status=Organization.Status.VERIFIED, organization__active=True)
        elif request_role(request) != User.Role.ADMIN:
            qs = qs.filter(practitioner=request.user)
        return Response(PractitionerRoleSerializer(qs, many=True).data)

    def post(self, request):
        practitioner = request.user
        if request_role(request) == User.Role.ADMIN:
            practitioner = get_object_or_404(User, pk=request.data.get("practitioner"), role__in=PROFESSIONAL_ROLES)
        organization = get_object_or_404(Organization, pk=request.data.get("organization"))
        if request_role(request) != User.Role.ADMIN and organization.owner_id not in [request.user.id, None]:
            return Response({"detail": "An administrator or organization owner must approve this affiliation."}, status=403)
        serializer = PractitionerRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save(practitioner=practitioner)
        audit(actor=request.user, action="registry.practitioner_role.created", resource=role, purpose="provider_registry", request=request)
        return Response(PractitionerRoleSerializer(role).data, status=201)


class OrganizationStatusView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    @transaction.atomic
    def post(self, request, public_id):
        organization = get_object_or_404(Organization, public_id=public_id)
        status_value = request.data.get("status")
        if status_value == "reactivate":
            status_value = Organization.Status.VERIFIED
        if status_value not in Organization.Status.values:
            return Response({"detail": "Invalid organization status."}, status=400)
        reason = str(request.data.get("reason", "")).strip()
        if status_value in {Organization.Status.REJECTED, Organization.Status.SUSPENDED, Organization.Status.INACTIVE} and not reason:
            return Response({"detail": "A reason is required for this status decision."}, status=400)
        organization.status = status_value
        organization.active = status_value == Organization.Status.VERIFIED
        organization.save(update_fields=["status", "active", "updated_at"])

        # The original portals still read ProviderProfile.status. Keep that
        # compatibility projection synchronized with the canonical registry.
        owner = organization.owner
        if owner and owner.role in {User.Role.PHARMACY, User.Role.LAB, User.Role.HOSPITAL, User.Role.INSURANCE}:
            profile = getattr(owner, "provider_profile", None)
            if profile and status_value in {
                Organization.Status.PENDING,
                Organization.Status.VERIFIED,
                Organization.Status.REJECTED,
                Organization.Status.SUSPENDED,
            }:
                profile.status = status_value
                profile.save(update_fields=["status"])
            owner.is_verified = status_value == Organization.Status.VERIFIED
            if status_value == Organization.Status.SUSPENDED:
                owner.is_active = False
                owner.save(update_fields=["is_verified", "is_active"])
            elif status_value == Organization.Status.VERIFIED:
                owner.is_active = True
                owner.save(update_fields=["is_verified", "is_active"])
            else:
                owner.save(update_fields=["is_verified"])

        audit(
            actor=request.user,
            action=f"registry.organization.{status_value}",
            resource=organization,
            purpose="provider_registry",
            metadata={"reason": reason},
            request=request,
        )
        if owner:
            try:
                from communication.services import notify
                notify(
                    owner,
                    f"Organization verification: {status_value}",
                    reason or f"{organization.legal_name} is now {status_value}.",
                    kind="verification",
                    priority="high",
                    action_url=portal_path_for_role(owner.role),
                )
            except Exception:
                pass
        return Response(OrganizationSerializer(organization, context={"request": request}).data)


class OrganizationLicenseDocumentView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["admin", "pharmacy", "lab", "hospital", "insurance"]

    def get(self, request, public_id):
        organization = get_object_or_404(Organization, public_id=public_id)
        if request_role(request) != User.Role.ADMIN and organization.owner_id != request.user.id:
            return Response({"detail": "You are not allowed to view this licence document."}, status=403)
        if not organization.license_document:
            return Response({"detail": "No licence document is available."}, status=404)
        audit(actor=request.user, action="registry.organization_license.viewed", resource=organization, purpose="credentialing", request=request)
        return FileResponse(organization.license_document.open("rb"), as_attachment=False, filename=organization.license_document.name.rsplit("/", 1)[-1])


class PractitionerCredentialDocumentView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(PROFESSIONAL_ROLES | {"admin"})

    def get(self, request, pk):
        credential = get_object_or_404(PractitionerCredential, pk=pk)
        if request_role(request) != User.Role.ADMIN and credential.practitioner_id != request.user.id:
            return Response({"detail": "You are not allowed to view this credential."}, status=403)
        if not credential.document:
            return Response({"detail": "No credential document is available."}, status=404)
        audit(actor=request.user, action="registry.credential_document.viewed", resource=credential, purpose="credentialing", request=request)
        return FileResponse(credential.document.open("rb"), as_attachment=False, filename=credential.document.name.rsplit("/", 1)[-1])


class CareRelationshipListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(CLINICAL_ROLES | {"patient", "admin"})

    def get(self, request):
        qs = CareRelationship.objects.select_related("patient", "practitioner", "organization", "appointment")
        if request_role(request) == User.Role.PATIENT:
            qs = qs.filter(patient=request.user)
        elif request_role(request) in CLINICAL_ROLES:
            qs = qs.filter(practitioner=request.user)
        patient_id = request.query_params.get("patient")
        if request_role(request) == User.Role.ADMIN and patient_id:
            qs = qs.filter(patient_id=patient_id)
        return Response(CareRelationshipSerializer(qs, many=True).data)
