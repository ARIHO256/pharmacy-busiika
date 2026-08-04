from datetime import timedelta
import hashlib

from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import request_role
from enterprise.access import (
    active_organization, active_role, can_manage_operations, can_manage_platform,
    can_review_clinical_safety, can_review_compliance, can_view_system_health,
    is_platform_super_admin,
)
from governance.models import AuditEvent
from governance.services import audit

from .definitions import definition_for
from .page_data import page_operational_data
from .models import (
    GeneratedClinicalDocument, OperationalAction, ReleaseAcceptance,
    WorkflowCase, WorkflowComment,
)
from .serializers import (
    GeneratedClinicalDocumentSerializer, OperationalActionSerializer,
    ReleaseAcceptanceSerializer, WorkflowActionSerializer, WorkflowCaseSerializer,
    WorkflowCommentSerializer,
)
from .services import assert_page_access, create_case, perform_action, workflow_queryset


class PageDefinitionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        definition = assert_page_access(request.user, slug)
        return Response(definition)




class PageOperationalDataView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        assert_page_access(request.user, slug)
        return Response(page_operational_data(request, slug))


class PageCaseListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, slug):
        definition = assert_page_access(request.user, slug)
        qs = workflow_queryset(request.user, slug)
        status_value = request.query_params.get("status")
        priority = request.query_params.get("priority")
        patient_id = request.query_params.get("patient")
        assigned_to = request.query_params.get("assigned_to")
        q = request.query_params.get("q", "").strip()
        if status_value:
            qs = qs.filter(status=status_value)
        if priority:
            qs = qs.filter(priority=priority)
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if assigned_to == "me":
            qs = qs.filter(assigned_to=request.user)
        elif assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        if q:
            qs = qs.filter(Q(reference__icontains=q) | Q(title__icontains=q) | Q(summary__icontains=q) | Q(patient__first_name__icontains=q) | Q(patient__last_name__icontains=q) | Q(patient__email__icontains=q))
        try:
            limit = min(max(int(request.query_params.get("limit", 100)), 1), 250)
        except (TypeError, ValueError):
            limit = 100
        rows = qs[:limit]
        return Response({
            "definition": definition,
            "results": WorkflowCaseSerializer(rows, many=True, context={"request": request}).data,
            "counts": {row["status"]: row["count"] for row in qs.values("status").annotate(count=Count("id"))},
        })

    def post(self, request, slug):
        definition = assert_page_access(request.user, slug)
        if not definition.get("create_allowed", True):
            return Response(
                {"detail": "This page is read-only. Use the page's supported operational actions instead."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        case = create_case(user=request.user, slug=slug, payload=request.data, request=request)
        return Response(WorkflowCaseSerializer(case, context={"request": request}).data, status=status.HTTP_201_CREATED)


class WorkflowCaseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, request, public_id):
        return get_object_or_404(workflow_queryset(request.user), public_id=public_id)

    def get(self, request, public_id):
        case = self.get_object(request, public_id)
        return Response(WorkflowCaseSerializer(case, context={"request": request}).data)

    def patch(self, request, public_id):
        case = self.get_object(request, public_id)
        if case.status not in {"draft", "awaiting_information", "submitted"}:
            return Response({"detail": "Only draft or information-requested cases may be edited."}, status=409)
        if case.created_by_id != request.user.id and case.assigned_to_id != request.user.id and not is_platform_super_admin(request.user):
            return Response({"detail": "You cannot edit this case."}, status=403)
        allowed = {"title", "summary", "priority", "due_at", "assigned_to", "data"}
        for key in allowed:
            if key in request.data:
                if key in {"assigned_to"}:
                    setattr(case, f"{key}_id", request.data[key] or None)
                else:
                    setattr(case, key, request.data[key])
        case.updated_by = request.user
        case.version += 1
        case.save()
        return Response(WorkflowCaseSerializer(case, context={"request": request}).data)


class WorkflowCaseActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        case = get_object_or_404(workflow_queryset(request.user), public_id=public_id)
        serializer = WorkflowActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        action_code = values.pop("action")
        case = perform_action(case=case, user=request.user, action_code=action_code, payload=values, request=request)
        return Response(WorkflowCaseSerializer(case, context={"request": request}).data)


class WorkflowCommentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_object(self, request, public_id):
        return get_object_or_404(workflow_queryset(request.user), public_id=public_id)

    def get(self, request, public_id):
        case = self.get_object(request, public_id)
        qs = case.comments.select_related("author")
        if request_role(request) == "patient":
            qs = qs.filter(visibility=WorkflowComment.Visibility.PATIENT)
        return Response(WorkflowCommentSerializer(qs, many=True, context={"request": request}).data)

    def post(self, request, public_id):
        case = self.get_object(request, public_id)
        serializer = WorkflowCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visibility = serializer.validated_data.get("visibility", WorkflowComment.Visibility.CARE_TEAM)
        if request_role(request) == "patient":
            visibility = WorkflowComment.Visibility.PATIENT
        comment = serializer.save(case=case, author=request.user, visibility=visibility)
        audit(actor=request.user, patient=case.patient, action="workflow.comment.created", resource=case, purpose="workflow_collaboration", decision=AuditEvent.Decision.ALLOW, metadata={"comment_id": comment.id, "visibility": visibility}, request=request)
        return Response(WorkflowCommentSerializer(comment, context={"request": request}).data, status=status.HTTP_201_CREATED)


class WorkflowDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = workflow_queryset(request.user)
        now = timezone.now()
        status_counts = {row["status"]: row["count"] for row in qs.values("status").annotate(count=Count("id"))}
        category_counts = list(qs.values("category").annotate(count=Count("id")).order_by("-count")[:12])
        due_soon = qs.filter(due_at__gte=now, due_at__lte=now + timedelta(hours=24)).count()
        overdue = qs.filter(due_at__lt=now).exclude(status__in=["completed", "closed", "cancelled", "rejected"]).count()
        critical = qs.filter(priority="critical").exclude(status__in=["completed", "closed", "cancelled"]).count()
        assigned = qs.filter(assigned_to=request.user).exclude(status__in=["completed", "closed", "cancelled"]).count()
        return Response({
            "active_role": request_role(request),
            "organization": getattr(active_organization(request.user), "legal_name", None),
            "total": qs.count(),
            "open": qs.exclude(status__in=["completed", "closed", "cancelled", "rejected", "revoked"]).count(),
            "critical": critical,
            "overdue": overdue,
            "due_soon": due_soon,
            "assigned_to_me": assigned,
            "status_counts": status_counts,
            "category_counts": category_counts,
            "recent": WorkflowCaseSerializer(qs[:10], many=True, context={"request": request}).data,
        })


class GeneratedDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = GeneratedClinicalDocument.objects.select_related("patient", "signed_by", "organization")
        role = request_role(request)
        if role == "patient":
            qs = qs.filter(patient=request.user, status=GeneratedClinicalDocument.Status.SIGNED)
        elif not is_platform_super_admin(request.user):
            org = active_organization(request.user)
            qs = qs.filter(Q(created_by=request.user) | Q(signed_by=request.user) | Q(organization=org)).distinct()
        return Response(GeneratedClinicalDocumentSerializer(qs[:200], many=True, context={"request": request}).data)


class GeneratedDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        document = get_object_or_404(GeneratedClinicalDocument.objects.select_related("patient"), public_id=public_id)
        role = request_role(request)
        if role == "patient" and document.patient_id != request.user.id:
            return Response({"detail": "Not permitted."}, status=403)
        if role != "patient" and not is_platform_super_admin(request.user) and document.created_by_id != request.user.id and document.signed_by_id != request.user.id and document.organization_id != getattr(active_organization(request.user), "id", None):
            return Response({"detail": "Not permitted."}, status=403)
        if not document.file:
            return Response({"detail": "The document file has not been generated."}, status=404)
        audit(actor=request.user, patient=document.patient, action="clinical_document.downloaded", resource=document, purpose="care_document", decision=AuditEvent.Decision.ALLOW, request=request)
        return FileResponse(document.file.open("rb"), as_attachment=True, filename=f"{document.verification_code}.pdf")


class PublicDocumentVerificationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, code):
        document = get_object_or_404(GeneratedClinicalDocument.objects.select_related("patient", "signed_by", "organization"), verification_code=code)
        return Response({
            "valid": document.status == GeneratedClinicalDocument.Status.SIGNED,
            "status": document.status,
            "document_type": document.document_type,
            "title": document.title,
            "patient_name": document.patient.display_name,
            "organization": getattr(document.organization, "legal_name", None),
            "signed_by": getattr(document.signed_by, "display_name", None),
            "signed_at": document.signed_at,
            "revoked_at": document.revoked_at,
            "verification_code": document.verification_code,
        })


ACCEPTANCE_REVIEW_ROLES = {
    ReleaseAcceptance.Type.DOCTOR_WORKFLOW: {"doctor", "medical_director", "clinical_safety_admin"},
    ReleaseAcceptance.Type.NURSING_WORKFLOW: {"nurse", "midwife", "medical_director", "clinical_safety_admin"},
    ReleaseAcceptance.Type.LABORATORY_WORKFLOW: {"lab_technician", "medical_director", "clinical_safety_admin"},
    ReleaseAcceptance.Type.PHARMACY_WORKFLOW: {"pharmacist", "medical_director", "clinical_safety_admin"},
    ReleaseAcceptance.Type.FINANCE_WORKFLOW: {"accountant", "finance_manager", "operations_admin"},
    ReleaseAcceptance.Type.RECORDS_WORKFLOW: {"records_officer", "compliance_admin", "compliance_officer"},
    ReleaseAcceptance.Type.ADMIN_WORKFLOW: {"platform_super_admin", "operations_admin"},
    ReleaseAcceptance.Type.PRIVACY_LEGAL: {"compliance_admin", "compliance_officer"},
    ReleaseAcceptance.Type.CLINICAL_SAFETY: {"clinical_safety_admin", "medical_director"},
    ReleaseAcceptance.Type.SECURITY: {"platform_super_admin", "it_support", "compliance_admin"},
    ReleaseAcceptance.Type.BACKUP_RESTORE: {"platform_super_admin", "it_support", "operations_admin"},
    ReleaseAcceptance.Type.DISASTER_RECOVERY: {"platform_super_admin", "it_support", "operations_admin"},
}


def _can_view_acceptance(user):
    role = active_role(user)
    qualified_reviewer = any(role in roles for roles in ACCEPTANCE_REVIEW_ROLES.values())
    return any((
        can_manage_platform(user), can_manage_operations(user),
        can_review_compliance(user), can_review_clinical_safety(user),
        can_view_system_health(user), qualified_reviewer,
    ))


def _can_review_acceptance(user, acceptance_type):
    return can_manage_platform(user) or active_role(user) in ACCEPTANCE_REVIEW_ROLES.get(acceptance_type, set())


def _evidence_hash(file_obj):
    if not file_obj:
        return ""
    digest = hashlib.sha256()
    for chunk in file_obj.chunks():
        digest.update(chunk)
    try:
        file_obj.seek(0)
    except Exception:
        pass
    return digest.hexdigest()


class OperationalActionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        case_ids = workflow_queryset(request.user).values("id")
        qs = OperationalAction.objects.select_related(
            "workflow_case", "patient", "created_by", "approved_by", "executed_by",
        ).filter(workflow_case_id__in=case_ids)
        if request.query_params.get("page_slug"):
            qs = qs.filter(page_slug=request.query_params["page_slug"])
        if request.query_params.get("state"):
            qs = qs.filter(state=request.query_params["state"])
        return Response(OperationalActionSerializer(qs[:500], many=True).data)


class ReleaseAcceptanceListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        if not _can_view_acceptance(request.user):
            return Response({"detail": "Release acceptance access is restricted."}, status=403)
        qs = ReleaseAcceptance.objects.select_related("reviewer")
        release_version = request.query_params.get("release_version")
        environment = request.query_params.get("environment")
        if release_version:
            qs = qs.filter(release_version=release_version)
        if environment:
            qs = qs.filter(environment=environment)
        return Response(ReleaseAcceptanceSerializer(qs, many=True, context={"request": request}).data)

    @transaction.atomic
    def post(self, request):
        acceptance_type = request.data.get("acceptance_type")
        if not _can_review_acceptance(request.user, acceptance_type):
            return Response({"detail": "Your active role cannot sign this acceptance gate."}, status=403)
        serializer = ReleaseAcceptanceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        status_value = serializer.validated_data.get("status", ReleaseAcceptance.Status.PENDING)
        obj = serializer.save(
            reviewer=request.user,
            signed_at=timezone.now() if status_value == ReleaseAcceptance.Status.ACCEPTED else None,
            evidence_hash=_evidence_hash(serializer.validated_data.get("evidence")),
        )
        audit(actor=request.user, action="release.acceptance.recorded", resource=obj, purpose="release_governance", decision=AuditEvent.Decision.ALLOW, metadata={"type": obj.acceptance_type, "status": obj.status, "release": obj.release_version}, request=request)
        return Response(ReleaseAcceptanceSerializer(obj, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ReleaseAcceptanceDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_object(self, request, pk):
        obj = get_object_or_404(ReleaseAcceptance.objects.select_related("reviewer"), pk=pk)
        if not _can_view_acceptance(request.user):
            raise PermissionError
        return obj

    def get(self, request, pk):
        try:
            obj = self.get_object(request, pk)
        except PermissionError:
            return Response({"detail": "Release acceptance access is restricted."}, status=403)
        return Response(ReleaseAcceptanceSerializer(obj, context={"request": request}).data)

    @transaction.atomic
    def patch(self, request, pk):
        try:
            obj = self.get_object(request, pk)
        except PermissionError:
            return Response({"detail": "Release acceptance access is restricted."}, status=403)
        if not _can_review_acceptance(request.user, obj.acceptance_type):
            return Response({"detail": "Your active role cannot update this acceptance gate."}, status=403)
        if obj.is_currently_accepted and not can_manage_platform(request.user):
            return Response({"detail": "A signed acceptance can only be superseded through a new release version."}, status=409)
        serializer = ReleaseAcceptanceSerializer(obj, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        status_value = serializer.validated_data.get("status", obj.status)
        evidence = serializer.validated_data.get("evidence")
        obj = serializer.save(
            reviewer=request.user,
            signed_at=timezone.now() if status_value == ReleaseAcceptance.Status.ACCEPTED else None,
            evidence_hash=_evidence_hash(evidence) if evidence else obj.evidence_hash,
        )
        audit(actor=request.user, action="release.acceptance.updated", resource=obj, purpose="release_governance", decision=AuditEvent.Decision.ALLOW, metadata={"type": obj.acceptance_type, "status": obj.status, "release": obj.release_version}, request=request)
        return Response(ReleaseAcceptanceSerializer(obj, context={"request": request}).data)


class ProductionReadinessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _can_view_acceptance(request.user):
            return Response({"detail": "Production-readiness access is restricted."}, status=403)
        release_version = request.query_params.get("release_version", "")
        environment = request.query_params.get("environment", "production")
        qs = ReleaseAcceptance.objects.filter(release_version=release_version, environment=environment) if release_version else ReleaseAcceptance.objects.none()
        by_type = {row.acceptance_type: row for row in qs}
        required = [choice[0] for choice in ReleaseAcceptance.Type.choices]
        gates = []
        for acceptance_type in required:
            row = by_type.get(acceptance_type)
            gates.append({
                "acceptance_type": acceptance_type,
                "label": dict(ReleaseAcceptance.Type.choices)[acceptance_type],
                "status": row.status if row else "missing",
                "accepted": bool(row and row.is_currently_accepted),
                "reviewer": row.reviewer_name if row else "",
                "signed_at": row.signed_at if row else None,
                "evidence_hash": row.evidence_hash if row else "",
            })
        ready = bool(release_version) and all(item["accepted"] for item in gates)
        return Response({
            "release_version": release_version, "environment": environment,
            "ready_for_promotion": ready, "gates": gates,
            "message": "All formal acceptance gates are current." if ready else "Production promotion is blocked until every gate is accepted with evidence.",
        })
