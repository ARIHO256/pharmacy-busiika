from datetime import timedelta
import os
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import request_role
from enterprise.access import active_role, is_platform_super_admin
from accounts.roles import (
    BILLING_ROLES, CLINICAL_ROLES, DIAGNOSTIC_ROLES, FACILITY_MANAGEMENT_ROLES,
    FRONT_DESK_ROLES, NURSING_ROLES, PHARMACY_STAFF_ROLES, SUPPLY_CHAIN_ROLES,
)
from workforce.access import organization_for_user, user_can_manage_organization
from .models import (
    AccountSubscription, Admission, AdmissionTransfer, AmbulanceDispatch, Announcement, BedAllocation,
    ClinicalRound, Complaint, DischargeSummary, EmergencyCase, FacilityBed, ImagingOrder, ImagingReport,
    InventoryBatch, InventoryItem, LeaveRequest, MaternityEpisode, PrivacyRequest, PurchaseOrder,
    PurchaseOrderItem, QualityIncident, StaffShift, StockMovement, SubscriptionPlan, SupportTicket,
    SurgicalCase, SurgicalChecklist, Ward, WardTask,
)
from .serializers import (
    AccountSubscriptionSerializer, AdmissionSerializer, AmbulanceDispatchSerializer, AnnouncementSerializer,
    ClinicalRoundSerializer, ComplaintSerializer, DischargeSummarySerializer, EmergencyCaseSerializer, FacilityBedSerializer,
    ImagingOrderSerializer, ImagingReportSerializer, InventoryBatchSerializer, InventoryItemSerializer,
    LeaveRequestSerializer, MaternityEpisodeSerializer, PrivacyRequestSerializer, PurchaseOrderSerializer,
    QualityIncidentSerializer, StaffShiftSerializer, StockMovementSerializer, SubscriptionPlanSerializer,
    SupportTicketSerializer, SurgicalCaseSerializer, SurgicalChecklistSerializer, WardSerializer, WardTaskSerializer,
)

MANAGER_ROLES = FACILITY_MANAGEMENT_ROLES | {"hospital", "pharmacy", "lab"}
ADMISSION_CREATE_ROLES = MANAGER_ROLES | CLINICAL_ROLES | FRONT_DESK_ROLES
INPATIENT_ROLES = MANAGER_ROLES | CLINICAL_ROLES | NURSING_ROLES
IMAGING_ROLES = MANAGER_ROLES | CLINICAL_ROLES | DIAGNOSTIC_ROLES
INVENTORY_ROLES = MANAGER_ROLES | PHARMACY_STAFF_ROLES | SUPPLY_CHAIN_ROLES
FINANCE_ROLES = MANAGER_ROLES | BILLING_ROLES


def _org_for_request(request):
    org_id = request.query_params.get("organization_id") or request.data.get("organization_id")
    return organization_for_user(request.user, org_id)


def _is_admin(user):
    return is_platform_super_admin(user)


def _can_manage(user, org):
    return bool(org and (user_can_manage_organization(user, org) or active_role(user) in MANAGER_ROLES))


def _audit(request, action, resource, patient=None, metadata=None):
    try:
        from governance.services import audit
        audit(actor=request.user, action=action, resource=resource, patient=patient, metadata=metadata or {}, request=request)
    except Exception:
        pass
    try:
        from interoperability.services import emit_event
        emit_event(action, resource, metadata or {"id": resource.pk}, actor=request.user, patient=patient, request=request)
    except Exception:
        pass


def _notify(user, title, body, action_url=""):
    if not user:
        return
    try:
        from communication.services import notify
        notify(user, title, body, kind="operations", action_url=action_url)
    except Exception:
        pass


class OperationsSummaryView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        if request_role(request) == "patient":
            return Response({
                "active_admissions": Admission.objects.filter(patient=request.user, status__in=[Admission.Status.ADMITTED, Admission.Status.TRANSFERRED, Admission.Status.DISCHARGE_PENDING]).count(),
                "pending_imaging": ImagingOrder.objects.filter(patient=request.user).exclude(status__in=[ImagingOrder.Status.RELEASED, ImagingOrder.Status.CANCELLED]).count(),
                "open_tickets": SupportTicket.objects.filter(requester=request.user).exclude(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED]).count(),
                "active_subscription": AccountSubscription.objects.filter(user=request.user, status__in=[AccountSubscription.Status.TRIAL, AccountSubscription.Status.ACTIVE]).count(),
            })
        if not org and not _is_admin(request.user):
            return Response({"detail": "No active organization scope."}, status=403)
        org_filter = {} if _is_admin(request.user) and not org else {"organization": org}
        ward_filter = {} if _is_admin(request.user) and not org else {"ward__organization": org}
        return Response({
            "active_admissions": Admission.objects.filter(**org_filter, status__in=[Admission.Status.ADMITTED, Admission.Status.TRANSFERRED, Admission.Status.DISCHARGE_PENDING]).count(),
            "available_beds": FacilityBed.objects.filter(**ward_filter, status=FacilityBed.Status.AVAILABLE, active=True).count(),
            "occupied_beds": FacilityBed.objects.filter(**ward_filter, status=FacilityBed.Status.OCCUPIED, active=True).count(),
            "open_ward_tasks": WardTask.objects.filter(admission__organization=org).exclude(status__in=[WardTask.Status.COMPLETED, WardTask.Status.CANCELLED]).count() if org else WardTask.objects.exclude(status__in=[WardTask.Status.COMPLETED, WardTask.Status.CANCELLED]).count(),
            "pending_imaging": ImagingOrder.objects.filter(**org_filter).exclude(status__in=[ImagingOrder.Status.RELEASED, ImagingOrder.Status.CANCELLED]).count(),
            "low_stock_items": sum(1 for item in InventoryItem.objects.filter(**org_filter, active=True).prefetch_related("batches") if item.quantity_on_hand <= item.reorder_level),
            "open_purchase_orders": PurchaseOrder.objects.filter(**org_filter).exclude(status__in=[PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CANCELLED]).count(),
            "open_support_tickets": SupportTicket.objects.filter(organization=org).exclude(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED]).count() if org else SupportTicket.objects.exclude(status__in=[SupportTicket.Status.RESOLVED, SupportTicket.Status.CLOSED]).count(),
        })


class WardListCreateView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        qs = Ward.objects.all().select_related("organization", "location").prefetch_related("beds") if _is_admin(request.user) and not org else Ward.objects.filter(organization=org).select_related("organization", "location").prefetch_related("beds")
        return Response(WardSerializer(qs, many=True).data)

    def post(self, request):
        org = _org_for_request(request)
        if not _can_manage(request.user, org):
            return Response({"detail": "Not permitted to manage wards."}, status=403)
        serializer = WardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ward = serializer.save(organization=org)
        _audit(request, "ward.created", ward)
        return Response(WardSerializer(ward).data, status=201)


class BedListCreateView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        qs = FacilityBed.objects.select_related("ward")
        if not (_is_admin(request.user) and not org):
            qs = qs.filter(ward__organization=org)
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response(FacilityBedSerializer(qs, many=True).data)

    def post(self, request):
        org = _org_for_request(request)
        if not _can_manage(request.user, org):
            return Response({"detail": "Not permitted to manage beds."}, status=403)
        ward = Ward.objects.filter(pk=request.data.get("ward"), organization=org).first()
        if not ward:
            return Response({"ward": ["Ward not found in this organization."]}, status=400)
        serializer = FacilityBedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bed = serializer.save()
        _audit(request, "bed.created", bed)
        return Response(FacilityBedSerializer(bed).data, status=201)


class AdmissionListCreateView(APIView):
    def get(self, request):
        qs = Admission.objects.select_related("patient", "ward", "organization", "admitting_clinician", "attending_clinician").prefetch_related("bed_allocations__bed__ward", "tasks")
        if request_role(request) == "patient":
            qs = qs.filter(patient=request.user)
        else:
            org = _org_for_request(request)
            if not (_is_admin(request.user) and not org):
                qs = qs.filter(organization=org)
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        if request.query_params.get("patient_id"):
            qs = qs.filter(patient_id=request.query_params["patient_id"])
        return Response(AdmissionSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in ADMISSION_CREATE_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to admit patients."}, status=403)
        if not org:
            return Response({"detail": "Organization scope is required."}, status=400)
        ward = Ward.objects.filter(pk=request.data.get("ward"), organization=org, active=True).first()
        if not ward:
            return Response({"ward": ["Ward not found in this organization."]}, status=400)
        serializer = AdmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admission = serializer.save(
            organization=org,
            created_by=request.user,
            admitting_clinician=request.user if request_role(request) in CLINICAL_ROLES else serializer.validated_data.get("admitting_clinician"),
        )
        bed_id = request.data.get("bed_id")
        if bed_id:
            bed = FacilityBed.objects.select_for_update().filter(pk=bed_id, ward__organization=org, status=FacilityBed.Status.AVAILABLE).first()
            if not bed:
                raise ValueError("Selected bed is not available.")
            BedAllocation.objects.create(admission=admission, bed=bed, assigned_by=request.user)
            bed.status = FacilityBed.Status.OCCUPIED
            bed.save(update_fields=["status"])
        _audit(request, "admission.created", admission, admission.patient)
        _notify(admission.patient, "Hospital admission recorded", f"Your admission {admission.admission_number} has been recorded at {org.legal_name}.", "/patient/health")
        return Response(AdmissionSerializer(admission).data, status=201)


class AdmissionActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        admission = Admission.objects.select_for_update().select_related("organization", "patient", "ward").filter(pk=pk).first()
        if not admission:
            return Response({"detail": "Admission not found."}, status=404)
        if request_role(request) not in INPATIENT_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        org = admission.organization
        scoped = organization_for_user(request.user, org.id)
        if not scoped and not _is_admin(request.user):
            return Response({"detail": "Admission is outside your organization."}, status=403)
        action = request.data.get("action")
        if action == "allocate_bed":
            bed = FacilityBed.objects.select_for_update().filter(pk=request.data.get("bed_id"), ward__organization=org, status=FacilityBed.Status.AVAILABLE).first()
            if not bed:
                return Response({"detail": "Selected bed is not available."}, status=400)
            current = admission.bed_allocations.filter(released_at__isnull=True).select_related("bed").first()
            if current:
                current.released_at = timezone.now()
                current.release_reason = "Reallocated"
                current.save(update_fields=["released_at", "release_reason"])
                current.bed.status = FacilityBed.Status.CLEANING
                current.bed.save(update_fields=["status"])
            BedAllocation.objects.create(admission=admission, bed=bed, assigned_by=request.user)
            bed.status = FacilityBed.Status.OCCUPIED
            bed.save(update_fields=["status"])
        elif action == "release_bed":
            current = admission.bed_allocations.filter(released_at__isnull=True).select_related("bed").first()
            if not current:
                return Response({"detail": "No active bed allocation."}, status=400)
            current.released_at = timezone.now()
            current.release_reason = request.data.get("reason", "Released")
            current.save(update_fields=["released_at", "release_reason"])
            current.bed.status = FacilityBed.Status.CLEANING
            current.bed.save(update_fields=["status"])
        elif action == "mark_bed_available":
            bed = FacilityBed.objects.filter(pk=request.data.get("bed_id"), ward__organization=org).first()
            if not bed:
                return Response({"detail": "Bed not found."}, status=404)
            if BedAllocation.objects.filter(bed=bed, released_at__isnull=True).exists():
                return Response({"detail": "Bed still has an active allocation."}, status=400)
            bed.status = FacilityBed.Status.AVAILABLE
            bed.save(update_fields=["status"])
        elif action == "transfer":
            to_ward = Ward.objects.filter(pk=request.data.get("to_ward"), organization=org, active=True).first()
            if not to_ward:
                return Response({"detail": "Destination ward not found."}, status=400)
            AdmissionTransfer.objects.create(admission=admission, from_ward=admission.ward, to_ward=to_ward, reason=request.data.get("reason", "Clinical transfer"), requested_by=request.user)
            admission.ward = to_ward
            admission.status = Admission.Status.TRANSFERRED
            admission.save(update_fields=["ward", "status", "updated_at"])
        elif action == "discharge_pending":
            admission.status = Admission.Status.DISCHARGE_PENDING
            admission.save(update_fields=["status", "updated_at"])
        elif action == "cancel":
            admission.status = Admission.Status.CANCELLED
            admission.save(update_fields=["status", "updated_at"])
        else:
            return Response({"detail": "Unsupported admission action."}, status=400)
        _audit(request, f"admission.{action}", admission, admission.patient, {"action": action})
        return Response(AdmissionSerializer(admission).data)


class WardTaskListCreateView(APIView):
    def get(self, request):
        qs = WardTask.objects.select_related("admission__patient", "admission__organization", "assigned_to")
        if request_role(request) == "patient":
            qs = qs.filter(admission__patient=request.user)
        else:
            org = _org_for_request(request)
            if not (_is_admin(request.user) and not org):
                qs = qs.filter(admission__organization=org)
            if request.query_params.get("mine") == "1":
                qs = qs.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response(WardTaskSerializer(qs, many=True).data)

    def post(self, request):
        if request_role(request) not in INPATIENT_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        admission = Admission.objects.filter(pk=request.data.get("admission")).select_related("organization", "patient").first()
        if not admission or (not _is_admin(request.user) and not organization_for_user(request.user, admission.organization_id)):
            return Response({"admission": ["Admission not found in your organization."]}, status=400)
        serializer = WardTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(created_by=request.user)
        _audit(request, "ward_task.created", task, admission.patient)
        if task.assigned_to:
            _notify(task.assigned_to, "New ward task", f"{task.title} for {admission.patient.display_name}", "/nurse/ward")
        return Response(WardTaskSerializer(task).data, status=201)


class WardTaskActionView(APIView):
    def post(self, request, pk):
        task = WardTask.objects.select_related("admission__organization", "admission__patient").filter(pk=pk).first()
        if not task:
            return Response({"detail": "Task not found."}, status=404)
        if request_role(request) not in INPATIENT_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        action = request.data.get("action")
        if action not in {WardTask.Status.IN_PROGRESS, WardTask.Status.COMPLETED, WardTask.Status.OMITTED, WardTask.Status.CANCELLED, WardTask.Status.OPEN}:
            return Response({"detail": "Unsupported task action."}, status=400)
        task.status = action
        task.completion_notes = request.data.get("notes", task.completion_notes)
        if action in {WardTask.Status.COMPLETED, WardTask.Status.OMITTED}:
            task.completed_by = request.user
            task.completed_at = timezone.now()
        task.save()
        _audit(request, f"ward_task.{action}", task, task.admission.patient)
        return Response(WardTaskSerializer(task).data)


class ClinicalRoundListCreateView(APIView):
    def get(self, request):
        qs = ClinicalRound.objects.select_related("admission__patient", "admission__organization", "clinician")
        if request_role(request) == "patient":
            qs = qs.filter(admission__patient=request.user)
        else:
            org = _org_for_request(request)
            if not (_is_admin(request.user) and not org):
                qs = qs.filter(admission__organization=org)
        if request.query_params.get("admission_id"):
            qs = qs.filter(admission_id=request.query_params["admission_id"])
        return Response(ClinicalRoundSerializer(qs, many=True).data)

    def post(self, request):
        if request_role(request) not in CLINICAL_ROLES and not _is_admin(request.user):
            return Response({"detail": "Only clinical professionals can record rounds."}, status=403)
        admission = Admission.objects.filter(pk=request.data.get("admission")).select_related("organization", "patient").first()
        if not admission or (not _is_admin(request.user) and not organization_for_user(request.user, admission.organization_id)):
            return Response({"admission": ["Admission not found."]}, status=400)
        serializer = ClinicalRoundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save(clinician=request.user)
        _audit(request, "clinical_round.created", row, admission.patient)
        return Response(ClinicalRoundSerializer(row).data, status=201)


class DischargeSummaryView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, admission_id):
        admission = Admission.objects.filter(pk=admission_id).select_related("patient", "organization").first()
        if not admission:
            return Response({"detail": "Admission not found."}, status=404)
        if request.user != admission.patient and not _is_admin(request.user) and not organization_for_user(request.user, admission.organization_id):
            return Response({"detail": "Not permitted."}, status=403)
        summary = DischargeSummary.objects.filter(admission=admission).select_related("clinician").first()
        return Response(DischargeSummarySerializer(summary).data if summary else None)

    @transaction.atomic
    def post(self, request, admission_id):
        if request_role(request) not in CLINICAL_ROLES and not _is_admin(request.user):
            return Response({"detail": "Only clinical professionals can prepare discharge summaries."}, status=403)
        admission = Admission.objects.select_for_update().filter(pk=admission_id).select_related("organization", "patient").first()
        if not admission or (not _is_admin(request.user) and not organization_for_user(request.user, admission.organization_id)):
            return Response({"detail": "Admission not found."}, status=404)
        summary = DischargeSummary.objects.filter(admission=admission).first()
        serializer = DischargeSummarySerializer(summary, data=request.data, partial=bool(summary))
        serializer.is_valid(raise_exception=True)
        summary = serializer.save(admission=admission, clinician=request.user)
        if request.data.get("finalize"):
            summary.finalized_at = timezone.now()
            summary.save(update_fields=["finalized_at", "updated_at"])
            admission.status = Admission.Status.DISCHARGED
            admission.discharged_at = timezone.now()
            admission.discharge_disposition = request.data.get("disposition", "Home")
            admission.save(update_fields=["status", "discharged_at", "discharge_disposition", "updated_at"])
            allocation = admission.bed_allocations.filter(released_at__isnull=True).select_related("bed").first()
            if allocation:
                allocation.released_at = timezone.now()
                allocation.release_reason = "Patient discharged"
                allocation.save(update_fields=["released_at", "release_reason"])
                allocation.bed.status = FacilityBed.Status.CLEANING
                allocation.bed.save(update_fields=["status"])
            _notify(admission.patient, "Discharge summary ready", f"Your discharge summary for admission {admission.admission_number} is ready.", "/patient/health")
        _audit(request, "discharge_summary.finalized" if summary.finalized_at else "discharge_summary.saved", summary, admission.patient)
        return Response(DischargeSummarySerializer(summary).data)


class ImagingOrderListCreateView(APIView):
    def get(self, request):
        qs = ImagingOrder.objects.select_related("patient", "organization", "ordering_clinician", "radiographer", "radiologist").select_related("report")
        if request_role(request) == "patient":
            qs = qs.filter(patient=request.user, status=ImagingOrder.Status.RELEASED)
        else:
            org = _org_for_request(request)
            if not (_is_admin(request.user) and not org):
                qs = qs.filter(organization=org)
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response(ImagingOrderSerializer(qs, many=True).data)

    def post(self, request):
        if request_role(request) not in CLINICAL_ROLES and not _is_admin(request.user):
            return Response({"detail": "Only clinical professionals can order imaging."}, status=403)
        org = _org_for_request(request)
        if not org:
            return Response({"detail": "Organization scope is required."}, status=400)
        serializer = ImagingOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(organization=org, ordering_clinician=request.user)
        _audit(request, "imaging_order.created", order, order.patient)
        _notify(order.patient, "Imaging request created", f"{order.study_name} has been requested.", "/patient/health")
        return Response(ImagingOrderSerializer(order).data, status=201)


class ImagingOrderActionView(APIView):
    def post(self, request, pk):
        order = ImagingOrder.objects.select_related("organization", "patient").filter(pk=pk).first()
        if not order:
            return Response({"detail": "Imaging order not found."}, status=404)
        if request_role(request) not in IMAGING_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if not _is_admin(request.user) and not organization_for_user(request.user, order.organization_id):
            return Response({"detail": "Order is outside your organization."}, status=403)
        action = request.data.get("action")
        if action == "schedule":
            order.scheduled_at = request.data.get("scheduled_at") or order.scheduled_at
            order.status = ImagingOrder.Status.SCHEDULED
        elif action == "check_in":
            order.status = ImagingOrder.Status.CHECKED_IN
        elif action == "start":
            order.status = ImagingOrder.Status.IN_PROGRESS
            if request_role(request) == "radiographer":
                order.radiographer = request.user
        elif action == "perform":
            order.status = ImagingOrder.Status.PERFORMED
            order.performed_at = timezone.now()
            order.radiographer = request.user if request_role(request) == "radiographer" else order.radiographer
            order.image_reference = request.data.get("image_reference", order.image_reference)
        elif action == "assign_radiologist":
            order.radiologist_id = request.data.get("radiologist_id")
            order.status = ImagingOrder.Status.REPORTING
        elif action == "cancel":
            order.status = ImagingOrder.Status.CANCELLED
        else:
            return Response({"detail": "Unsupported imaging action."}, status=400)
        order.save()
        _audit(request, f"imaging_order.{action}", order, order.patient)
        return Response(ImagingOrderSerializer(order).data)


class ImagingReportView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request, order_id):
        order = ImagingOrder.objects.filter(pk=order_id).select_related("organization", "patient").first()
        if not order:
            return Response({"detail": "Imaging order not found."}, status=404)
        if request.user == order.patient and order.status != ImagingOrder.Status.RELEASED:
            return Response({"detail": "Report has not been released."}, status=403)
        report = ImagingReport.objects.filter(order=order).select_related("created_by", "verified_by").first()
        return Response(ImagingReportSerializer(report).data if report else None)

    @transaction.atomic
    def post(self, request, order_id):
        order = ImagingOrder.objects.select_for_update().filter(pk=order_id).select_related("organization", "patient").first()
        if not order:
            return Response({"detail": "Imaging order not found."}, status=404)
        if request_role(request) not in {"radiologist", "admin"} and request_role(request) not in FACILITY_MANAGEMENT_ROLES:
            return Response({"detail": "Only an authorized radiologist can report imaging."}, status=403)
        report = ImagingReport.objects.filter(order=order).first()
        serializer = ImagingReportSerializer(report, data=request.data, partial=bool(report))
        serializer.is_valid(raise_exception=True)
        report = serializer.save(order=order, created_by=report.created_by if report else request.user)
        action = request.data.get("action", "save")
        if action == "verify":
            report.status = ImagingReport.Status.VERIFIED
            report.verified_by = request.user
            report.verified_at = timezone.now()
            order.status = ImagingOrder.Status.VERIFIED
        elif action == "release":
            report.status = ImagingReport.Status.RELEASED
            report.verified_by = report.verified_by or request.user
            report.verified_at = report.verified_at or timezone.now()
            report.released_at = timezone.now()
            order.status = ImagingOrder.Status.RELEASED
            _notify(order.patient, "Imaging report available", f"Your {order.study_name} report is now available.", "/patient/health")
        elif action == "preliminary":
            report.status = ImagingReport.Status.PRELIMINARY
            order.status = ImagingOrder.Status.REPORTING
        report.save()
        order.save(update_fields=["status", "updated_at"])
        _audit(request, f"imaging_report.{action}", report, order.patient)
        return Response(ImagingReportSerializer(report).data)


class InventoryItemListCreateView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        qs = InventoryItem.objects.all().prefetch_related("batches") if _is_admin(request.user) and not org else InventoryItem.objects.filter(organization=org).prefetch_related("batches")
        if request.query_params.get("search"):
            search = request.query_params["search"]
            qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
        return Response(InventoryItemSerializer(qs, many=True).data)

    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in INVENTORY_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to manage inventory."}, status=403)
        serializer = InventoryItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(organization=org)
        _audit(request, "inventory_item.created", item)
        return Response(InventoryItemSerializer(item).data, status=201)


class InventoryBatchListCreateView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        qs = InventoryBatch.objects.select_related("item")
        if not (_is_admin(request.user) and not org):
            qs = qs.filter(item__organization=org)
        if request.query_params.get("item_id"):
            qs = qs.filter(item_id=request.query_params["item_id"])
        return Response(InventoryBatchSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in INVENTORY_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to receive stock."}, status=403)
        item = InventoryItem.objects.filter(pk=request.data.get("item"), organization=org).first()
        if not item:
            return Response({"item": ["Inventory item not found."]}, status=400)
        serializer = InventoryBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = serializer.save()
        if batch.quantity_available == 0 and batch.quantity_received:
            batch.quantity_available = batch.quantity_received
            batch.save(update_fields=["quantity_available"])
        StockMovement.objects.create(batch=batch, movement_type=StockMovement.Type.RECEIPT, quantity=batch.quantity_received, balance_after=batch.quantity_available, reason="Initial batch receipt", created_by=request.user)
        _audit(request, "inventory_batch.received", batch)
        return Response(InventoryBatchSerializer(batch).data, status=201)


class StockMovementListCreateView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        qs = StockMovement.objects.select_related("batch__item", "created_by")
        if not (_is_admin(request.user) and not org):
            qs = qs.filter(batch__item__organization=org)
        return Response(StockMovementSerializer(qs[:500], many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in INVENTORY_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to move stock."}, status=403)
        batch = InventoryBatch.objects.select_for_update().filter(pk=request.data.get("batch"), item__organization=org).first()
        if not batch:
            return Response({"batch": ["Batch not found."]}, status=400)
        try:
            quantity = int(request.data.get("quantity", 0))
        except (TypeError, ValueError):
            return Response({"quantity": ["A whole-number quantity is required."]}, status=400)
        movement_type = request.data.get("movement_type")
        inbound = movement_type in {StockMovement.Type.RECEIPT, StockMovement.Type.RETURN}
        delta = abs(quantity) if inbound else -abs(quantity)
        new_balance = batch.quantity_available + delta
        if new_balance < 0:
            return Response({"quantity": ["Movement would create negative stock."]}, status=400)
        if batch.recalled and movement_type in {StockMovement.Type.DISPENSE, StockMovement.Type.ISSUE}:
            return Response({"detail": "Recalled batches cannot be dispensed or issued."}, status=400)
        batch.quantity_available = new_balance
        batch.save(update_fields=["quantity_available"])
        row = StockMovement.objects.create(batch=batch, movement_type=movement_type, quantity=delta, balance_after=new_balance, reason=request.data.get("reason", ""), reference=request.data.get("reference", ""), created_by=request.user)
        _audit(request, "stock_movement.created", row, metadata={"quantity": delta, "balance": new_balance})
        return Response(StockMovementSerializer(row).data, status=201)


class PurchaseOrderListCreateView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        qs = PurchaseOrder.objects.prefetch_related("items").select_related("created_by", "approved_by")
        if not (_is_admin(request.user) and not org):
            qs = qs.filter(organization=org)
        return Response(PurchaseOrderSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in INVENTORY_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to create purchase orders."}, status=403)
        serializer = PurchaseOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save(organization=org, created_by=request.user)
        for item in request.data.get("items", []):
            PurchaseOrderItem.objects.create(
                purchase_order=order,
                inventory_item_id=item.get("inventory_item") or None,
                description=item.get("description", ""),
                quantity=int(item.get("quantity", 1)),
                unit_cost=int(item.get("unit_cost", 0)),
            )
        _audit(request, "purchase_order.created", order)
        return Response(PurchaseOrderSerializer(order).data, status=201)


class PurchaseOrderActionView(APIView):
    def post(self, request, pk):
        order = PurchaseOrder.objects.filter(pk=pk).select_related("organization").first()
        if not order:
            return Response({"detail": "Purchase order not found."}, status=404)
        if request_role(request) not in INVENTORY_ROLES | FACILITY_MANAGEMENT_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        action = request.data.get("action")
        transitions = {
            "submit": PurchaseOrder.Status.SUBMITTED,
            "approve": PurchaseOrder.Status.APPROVED,
            "order": PurchaseOrder.Status.ORDERED,
            "part_receive": PurchaseOrder.Status.PART_RECEIVED,
            "receive": PurchaseOrder.Status.RECEIVED,
            "cancel": PurchaseOrder.Status.CANCELLED,
        }
        if action not in transitions:
            return Response({"detail": "Unsupported action."}, status=400)
        order.status = transitions[action]
        if action == "approve":
            order.approved_by = request.user
            order.approved_at = timezone.now()
        order.save()
        _audit(request, f"purchase_order.{action}", order)
        return Response(PurchaseOrderSerializer(order).data)


class SubscriptionPlanView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = SubscriptionPlan.objects.filter(active=True)
        audience = request.query_params.get("audience")
        if audience:
            qs = qs.filter(audience=audience)
        return Response(SubscriptionPlanSerializer(qs, many=True).data)

    def post(self, request):
        if not request.user.is_authenticated or request_role(request) != "admin":
            return Response({"detail": "Administrator access required."}, status=403)
        serializer = SubscriptionPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(SubscriptionPlanSerializer(serializer.save()).data, status=201)


class AccountSubscriptionView(APIView):
    def get(self, request):
        if request_role(request) == "admin":
            qs = AccountSubscription.objects.select_related("user", "organization", "plan")
        else:
            org = _org_for_request(request)
            qs = AccountSubscription.objects.filter(Q(user=request.user) | Q(organization=org)).select_related("user", "organization", "plan")
        return Response(AccountSubscriptionSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        plan = SubscriptionPlan.objects.filter(pk=request.data.get("plan"), active=True).first()
        if not plan:
            return Response({"plan": ["Subscription plan not found."]}, status=400)
        org = _org_for_request(request) if plan.audience == SubscriptionPlan.Audience.ORGANIZATION else None
        if plan.audience == SubscriptionPlan.Audience.ORGANIZATION and not org:
            return Response({"detail": "Organization plan requires an organization account."}, status=400)
        method = "mobile_money"
        selected_gateway = None
        if plan.price > 0:
            # Paid plans are invoiced and activate only when payment confirms.
            method = str(request.data.get("method") or "mobile_money")
            requested_gateway = str(request.data.get("gateway") or "").strip().lower()
            gateway_by_method = {
                "mobile_money": {"mtn_momo", "airtel_money", "flutterwave", "mock"},
                "card": {"flutterwave", "paystack", "mock"},
            }
            if method not in gateway_by_method:
                return Response({"detail": "method must be one of mobile_money, card"}, status=400)
            from django.conf import settings as django_settings

            default_gateway = "mock" if django_settings.MOCK_PAYMENTS else os.getenv("PAYMENT_GATEWAY", "flutterwave")
            selected_gateway = requested_gateway or default_gateway
            if selected_gateway not in gateway_by_method[method]:
                return Response({"detail": f"Gateway {selected_gateway} is not available for {method}."}, status=400)
        AccountSubscription.objects.filter(
            Q(user=request.user) | Q(organization=org),
            status__in=[AccountSubscription.Status.TRIAL, AccountSubscription.Status.ACTIVE],
        ).update(status=AccountSubscription.Status.CANCELLED, cancelled_at=timezone.now(), auto_renew=False)
        cycle_days = {"monthly": 30, "quarterly": 90, "annual": 365}[plan.billing_cycle]
        row = AccountSubscription.objects.create(
            user=None if org else request.user,
            organization=org,
            plan=plan,
            status=AccountSubscription.Status.ACTIVE if plan.price == 0 else AccountSubscription.Status.TRIAL,
            ends_at=timezone.now() + timedelta(days=cycle_days),
            auto_renew=bool(request.data.get("auto_renew", True)),
        )
        _audit(request, "subscription.created", row)
        if plan.price == 0:
            return Response(AccountSubscriptionSerializer(row).data, status=201)

        from payments.models import Invoice, InvoiceItem
        from payments.gateways import get_gateway

        invoice = Invoice.objects.create(
            patient=request.user,
            gateway=selected_gateway,
            source_type=Invoice.SourceType.SUBSCRIPTION,
            source_id=str(row.id),
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            code=plan.code,
            description=f"{plan.name} subscription ({plan.get_billing_cycle_display()})",
            quantity=1,
            unit_price=plan.price,
            service_type="subscription",
            source_id=str(row.id),
        )
        invoice.recalculate_amount()
        gateway = get_gateway(invoice.gateway)
        try:
            result = gateway.initiate(invoice, phone=request.data.get("phone"))
        except Exception as exc:
            return Response(
                {"detail": f"{invoice.gateway} gateway could not be initialized: {exc}"}, status=503
            )
        invoice.gateway_ref = result["ref"]
        invoice.save(update_fields=["gateway_ref", "updated_at"])
        return Response(
            {
                **AccountSubscriptionSerializer(row).data,
                "invoice_number": invoice.number,
                "amount": invoice.amount,
                "ref": result["ref"],
                "checkout_url": result.get("checkout_url", ""),
                "instructions": result.get("instructions", ""),
                "gateway": invoice.gateway,
                "payment_status": result.get("status", "initiated"),
                "mock": invoice.gateway == "mock",
            },
            status=201,
        )


class AccountSubscriptionCancelView(APIView):
    def post(self, request, pk):
        row = AccountSubscription.objects.filter(pk=pk).select_related("organization").first()
        if not row:
            return Response({"detail": "Subscription not found."}, status=404)
        owner = row.user_id == request.user.id or (row.organization and user_can_manage_organization(request.user, row.organization)) or _is_admin(request.user)
        if not owner:
            return Response({"detail": "Not permitted."}, status=403)
        row.status = AccountSubscription.Status.CANCELLED
        row.cancelled_at = timezone.now()
        row.auto_renew = False
        row.save(update_fields=["status", "cancelled_at", "auto_renew"])
        _audit(request, "subscription.cancelled", row)
        return Response(AccountSubscriptionSerializer(row).data)


class SupportTicketListCreateView(APIView):
    def get(self, request):
        if request_role(request) == "admin":
            qs = SupportTicket.objects.select_related("requester", "organization", "assigned_to")
        else:
            qs = SupportTicket.objects.filter(requester=request.user).select_related("requester", "organization", "assigned_to")
        return Response(SupportTicketSerializer(qs, many=True).data)

    def post(self, request):
        serializer = SupportTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save(requester=request.user, organization=_org_for_request(request))
        _audit(request, "support_ticket.created", ticket)
        return Response(SupportTicketSerializer(ticket).data, status=201)


class SupportTicketActionView(APIView):
    def post(self, request, pk):
        ticket = SupportTicket.objects.filter(pk=pk).select_related("requester").first()
        if not ticket:
            return Response({"detail": "Ticket not found."}, status=404)
        if request_role(request) != "admin" and ticket.requester_id != request.user.id:
            return Response({"detail": "Not permitted."}, status=403)
        if request_role(request) == "admin":
            if request.data.get("status"):
                ticket.status = request.data["status"]
            if request.data.get("assigned_to"):
                ticket.assigned_to_id = request.data["assigned_to"]
            if "resolution" in request.data:
                ticket.resolution = request.data["resolution"]
        elif request.data.get("action") == "close":
            ticket.status = SupportTicket.Status.CLOSED
        ticket.save()
        _notify(ticket.requester, "Support ticket updated", f"Ticket {ticket.number} is now {ticket.get_status_display()}.", "/notification-settings")
        _audit(request, "support_ticket.updated", ticket)
        return Response(SupportTicketSerializer(ticket).data)


class ComplaintListCreateView(APIView):
    def get(self, request):
        if _is_admin(request.user):
            qs = Complaint.objects.select_related("complainant", "against_user", "handled_by")
        else:
            qs = Complaint.objects.filter(complainant=request.user).select_related("complainant", "against_user", "handled_by")
        return Response(ComplaintSerializer(qs, many=True).data)

    def post(self, request):
        serializer = ComplaintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        complaint = serializer.save(complainant=request.user)
        _audit(request, "complaint.created", complaint)
        return Response(ComplaintSerializer(complaint).data, status=201)


class ComplaintActionView(APIView):
    def post(self, request, pk):
        complaint = Complaint.objects.filter(pk=pk).select_related("complainant", "against_user").first()
        if not complaint:
            return Response({"detail": "Complaint not found."}, status=404)
        if not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        action = request.data.get("action")
        transitions = {
            "start_review": Complaint.Status.IN_REVIEW,
            "resolve": Complaint.Status.RESOLVED,
            "dismiss": Complaint.Status.DISMISSED,
        }
        if action not in transitions:
            return Response({"detail": "action must be start_review|resolve|dismiss"}, status=400)
        complaint.status = transitions[action]
        complaint.handled_by = request.user
        if "resolution_notes" in request.data:
            complaint.resolution_notes = request.data["resolution_notes"]
        complaint.save(update_fields=["status", "handled_by", "resolution_notes", "updated_at"])
        for recipient in {complaint.complainant, complaint.against_user}:
            _notify(
                recipient,
                "Complaint updated",
                f"A complaint you are involved in is now {complaint.get_status_display()}.",
                "/notification-settings",
            )
        _audit(request, f"complaint.{action}", complaint)
        return Response(ComplaintSerializer(complaint).data)


class AnnouncementListCreateView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def get(self, request):
        now = timezone.now()
        qs = Announcement.objects.filter(active=True, starts_at__lte=now).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=now)).select_related("organization")
        if request.user.is_authenticated:
            org = _org_for_request(request)
            qs = qs.filter(Q(organization__isnull=True) | Q(organization=org))
            audience_map = {
                "patient": [Announcement.Audience.ALL, Announcement.Audience.PATIENTS],
                "hospital": [Announcement.Audience.ALL, Announcement.Audience.ORGANIZATIONS],
                "pharmacy": [Announcement.Audience.ALL, Announcement.Audience.ORGANIZATIONS],
                "lab": [Announcement.Audience.ALL, Announcement.Audience.ORGANIZATIONS],
                "insurance": [Announcement.Audience.ALL, Announcement.Audience.ORGANIZATIONS],
            }
            audiences = audience_map.get(request_role(request), [Announcement.Audience.ALL, Announcement.Audience.PROFESSIONALS, Announcement.Audience.STAFF])
            qs = qs.filter(audience__in=audiences)
        else:
            qs = qs.filter(organization__isnull=True, audience=Announcement.Audience.ALL)
        return Response(AnnouncementSerializer(qs, many=True).data)

    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) != "admin" and not _can_manage(request.user, org):
            return Response({"detail": "Not permitted to publish announcements."}, status=403)
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save(organization=org if request_role(request) != "admin" else None, created_by=request.user)
        _audit(request, "announcement.created", row)
        return Response(AnnouncementSerializer(row).data, status=201)


EMERGENCY_ACCESS_ROLES = MANAGER_ROLES | CLINICAL_ROLES | NURSING_ROLES | FRONT_DESK_ROLES | {"ambulance_dispatcher", "paramedic"}
THEATRE_ACCESS_ROLES = MANAGER_ROLES | CLINICAL_ROLES | NURSING_ROLES | {"anaesthetist", "theatre_nurse"}
MATERNITY_ACCESS_ROLES = MANAGER_ROLES | CLINICAL_ROLES | NURSING_ROLES | {"midwife"}
WORKFORCE_SCHEDULING_ROLES = MANAGER_ROLES | {"hr_officer"}
QUALITY_ACCESS_ROLES = MANAGER_ROLES | {"quality_officer", "compliance_officer", "medical_director"}
PRIVACY_MANAGEMENT_ROLES = MANAGER_ROLES | {"compliance_officer"}


def _scoped_queryset(request, queryset, org_field="organization"):
    if request_role(request) == "patient":
        return queryset.filter(patient=request.user)
    org = _org_for_request(request)
    if _is_admin(request.user) and not org:
        return queryset
    if not org:
        return queryset.none()
    return queryset.filter(**{org_field: org})


class EmergencyCaseListCreateView(APIView):
    def get(self, request):
        qs = EmergencyCase.objects.select_related("organization", "patient", "assigned_clinician", "visit")
        qs = _scoped_queryset(request, qs)
        status_value = request.query_params.get("status")
        if status_value:
            qs = qs.filter(status=status_value)
        return Response(EmergencyCaseSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in EMERGENCY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to register emergency cases."}, status=403)
        if not org:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = EmergencyCaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = serializer.save(organization=org, created_by=request.user)
        _audit(request, "emergency_case.created", case, case.patient, {"acuity": case.acuity})
        _notify(case.patient, "Emergency case registered", f"Emergency case {case.case_number} was registered at {org.legal_name}.", "/patient/health")
        return Response(EmergencyCaseSerializer(case).data, status=201)


class EmergencyCaseActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        case = get_object_or_404(EmergencyCase.objects.select_for_update().select_related("organization", "patient"), pk=pk)
        if request_role(request) not in EMERGENCY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if not _is_admin(request.user) and not organization_for_user(request.user, case.organization_id):
            return Response({"detail": "Case is outside your organization."}, status=403)
        action = request.data.get("action")
        status_map = {
            "triage": EmergencyCase.Status.TRIAGED,
            "start_treatment": EmergencyCase.Status.IN_TREATMENT,
            "observe": EmergencyCase.Status.OBSERVATION,
            "refer": EmergencyCase.Status.REFERRED,
            "admit": EmergencyCase.Status.ADMITTED,
            "discharge": EmergencyCase.Status.DISCHARGED,
            "left": EmergencyCase.Status.LEFT,
            "deceased": EmergencyCase.Status.DECEASED,
        }
        if action not in status_map:
            return Response({"detail": "Unsupported emergency action."}, status=400)
        case.status = status_map[action]
        if request.data.get("acuity") in EmergencyCase.Acuity.values:
            case.acuity = request.data["acuity"]
        if request.data.get("triage_notes") is not None:
            case.triage_notes = request.data.get("triage_notes", "")
        if request.data.get("disposition") is not None:
            case.disposition = request.data.get("disposition", "")
        if request.data.get("assigned_clinician"):
            case.assigned_clinician_id = request.data["assigned_clinician"]
        elif action == "start_treatment" and request_role(request) in CLINICAL_ROLES:
            case.assigned_clinician = request.user
        if action == "start_treatment" and not case.treatment_started_at:
            case.treatment_started_at = timezone.now()
        if action in {"refer", "admit", "discharge", "left", "deceased"}:
            case.closed_at = timezone.now()
        case.save()
        _audit(request, f"emergency_case.{action}", case, case.patient, {"status": case.status})
        return Response(EmergencyCaseSerializer(case).data)


class AmbulanceDispatchListCreateView(APIView):
    def get(self, request):
        qs = AmbulanceDispatch.objects.select_related("organization", "patient", "dispatcher", "paramedic")
        if request_role(request) == "patient":
            qs = qs.filter(patient=request.user)
        else:
            org = _org_for_request(request)
            if not (_is_admin(request.user) and not org):
                qs = qs.filter(organization=org)
        return Response(AmbulanceDispatchSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in EMERGENCY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to create ambulance dispatches."}, status=403)
        if not org:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = AmbulanceDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dispatch = serializer.save(organization=org, dispatcher=request.user if request_role(request) == "ambulance_dispatcher" else None)
        _audit(request, "ambulance_dispatch.created", dispatch, dispatch.patient, {"priority": dispatch.priority})
        return Response(AmbulanceDispatchSerializer(dispatch).data, status=201)


class AmbulanceDispatchActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        dispatch = get_object_or_404(AmbulanceDispatch.objects.select_for_update().select_related("organization", "patient"), pk=pk)
        if request_role(request) not in EMERGENCY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if not _is_admin(request.user) and not organization_for_user(request.user, dispatch.organization_id):
            return Response({"detail": "Dispatch is outside your organization."}, status=403)
        action = request.data.get("action")
        mapping = {
            "assign": AmbulanceDispatch.Status.ASSIGNED,
            "depart": AmbulanceDispatch.Status.EN_ROUTE,
            "on_scene": AmbulanceDispatch.Status.ON_SCENE,
            "transport": AmbulanceDispatch.Status.TRANSPORTING,
            "arrive": AmbulanceDispatch.Status.ARRIVED,
            "complete": AmbulanceDispatch.Status.COMPLETED,
            "cancel": AmbulanceDispatch.Status.CANCELLED,
        }
        if action not in mapping:
            return Response({"detail": "Unsupported dispatch action."}, status=400)
        dispatch.status = mapping[action]
        if request.data.get("paramedic"):
            dispatch.paramedic_id = request.data["paramedic"]
        if request.data.get("ambulance_identifier") is not None:
            dispatch.ambulance_identifier = request.data.get("ambulance_identifier", "")
        if request.data.get("clinical_notes") is not None:
            dispatch.clinical_notes = request.data.get("clinical_notes", "")
        now = timezone.now()
        if action in {"assign", "depart"} and not dispatch.dispatched_at:
            dispatch.dispatched_at = now
        if action == "on_scene":
            dispatch.arrived_scene_at = now
        if action in {"complete", "cancel"}:
            dispatch.completed_at = now
        dispatch.save()
        _audit(request, f"ambulance_dispatch.{action}", dispatch, dispatch.patient, {"status": dispatch.status})
        return Response(AmbulanceDispatchSerializer(dispatch).data)


class SurgicalCaseListCreateView(APIView):
    def get(self, request):
        qs = SurgicalCase.objects.select_related("organization", "patient", "admission", "surgeon", "anaesthetist", "theatre_nurse").prefetch_related("checklist")
        qs = _scoped_queryset(request, qs)
        return Response(SurgicalCaseSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in THEATRE_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to create surgical cases."}, status=403)
        if not org:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = SurgicalCaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        starts = serializer.validated_data.get("scheduled_start")
        ends = serializer.validated_data.get("scheduled_end")
        theatre_name = serializer.validated_data.get("theatre_name", "")
        if starts and ends and ends <= starts:
            return Response({"scheduled_end": ["Scheduled end must be after the start time."]}, status=400)
        if starts and ends and theatre_name and SurgicalCase.objects.filter(
            organization=org,
            theatre_name__iexact=theatre_name,
            scheduled_start__lt=ends,
            scheduled_end__gt=starts,
        ).exclude(status__in=[SurgicalCase.Status.CANCELLED, SurgicalCase.Status.POSTPONED]).exists():
            return Response({"detail": "The selected theatre is already booked during this time window."}, status=409)
        case = serializer.save(organization=org, created_by=request.user)
        SurgicalChecklist.objects.get_or_create(surgical_case=case)
        _audit(request, "surgical_case.created", case, case.patient, {"procedure": case.procedure_name})
        _notify(case.patient, "Surgical case created", f"Case {case.case_number} has been created for {case.procedure_name}.", "/patient/health")
        return Response(SurgicalCaseSerializer(case).data, status=201)


class SurgicalCaseActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        case = get_object_or_404(SurgicalCase.objects.select_for_update().select_related("organization", "patient"), pk=pk)
        if request_role(request) not in THEATRE_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if not _is_admin(request.user) and not organization_for_user(request.user, case.organization_id):
            return Response({"detail": "Case is outside your organization."}, status=403)
        action = request.data.get("action")
        mapping = {
            "schedule": SurgicalCase.Status.SCHEDULED,
            "pre_op": SurgicalCase.Status.PRE_OP,
            "start": SurgicalCase.Status.IN_THEATRE,
            "recovery": SurgicalCase.Status.RECOVERY,
            "complete": SurgicalCase.Status.COMPLETED,
            "postpone": SurgicalCase.Status.POSTPONED,
            "cancel": SurgicalCase.Status.CANCELLED,
        }
        if action not in mapping:
            return Response({"detail": "Unsupported surgical action."}, status=400)
        case.status = mapping[action]
        editable = ["scheduled_start", "scheduled_end", "theatre_name", "operation_notes", "anaesthesia_notes", "complications", "postoperative_diagnosis"]
        for name in editable:
            if name in request.data:
                setattr(case, name, request.data[name])
        for name in ["surgeon", "anaesthetist", "theatre_nurse"]:
            if request.data.get(name):
                setattr(case, f"{name}_id", request.data[name])
        if "consent_obtained" in request.data:
            case.consent_obtained = bool(request.data["consent_obtained"])
        if case.scheduled_start and case.scheduled_end and case.scheduled_end <= case.scheduled_start:
            return Response({"scheduled_end": ["Scheduled end must be after the start time."]}, status=400)
        if action in {"schedule", "pre_op"} and case.scheduled_start and case.scheduled_end and case.theatre_name:
            conflict = SurgicalCase.objects.filter(
                organization=case.organization,
                theatre_name__iexact=case.theatre_name,
                scheduled_start__lt=case.scheduled_end,
                scheduled_end__gt=case.scheduled_start,
            ).exclude(pk=case.pk).exclude(status__in=[SurgicalCase.Status.CANCELLED, SurgicalCase.Status.POSTPONED]).exists()
            if conflict:
                return Response({"detail": "The selected theatre is already booked during this time window."}, status=409)
        checklist, _ = SurgicalChecklist.objects.get_or_create(surgical_case=case)
        now = timezone.now()
        if action == "start":
            required = {
                "patient identity": checklist.patient_identity_confirmed,
                "procedure": checklist.procedure_confirmed,
                "consent": checklist.consent_confirmed and case.consent_obtained,
                "allergies": checklist.allergies_reviewed,
                "anaesthesia safety": checklist.anaesthesia_safety_check,
                "team introduction": checklist.team_introduction_complete,
            }
            missing = [label for label, complete in required.items() if not complete]
            if missing:
                return Response({"detail": f"Theatre cannot start until these safety checks are complete: {', '.join(missing)}."}, status=409)
            case.actual_start = case.actual_start or now
        if action == "recovery":
            if not checklist.instrument_count_complete or not checklist.recovery_plan_confirmed:
                return Response({"detail": "Instrument count and recovery plan must be signed off before transfer to recovery."}, status=409)
        if action == "complete":
            if checklist.completion_percent < 100:
                return Response({"detail": "The surgical safety checklist must be 100% complete before the case is closed."}, status=409)
            case.actual_end = case.actual_end or now
        elif action == "cancel":
            case.actual_end = case.actual_end or now
        case.save()
        _audit(request, f"surgical_case.{action}", case, case.patient, {"status": case.status})
        return Response(SurgicalCaseSerializer(case).data)


class SurgicalChecklistView(APIView):
    def get(self, request, case_id):
        case = get_object_or_404(SurgicalCase.objects.select_related("organization", "patient"), pk=case_id)
        if request_role(request) == "patient" and case.patient_id != request.user.id:
            return Response({"detail": "Not permitted."}, status=403)
        checklist, _ = SurgicalChecklist.objects.get_or_create(surgical_case=case)
        return Response(SurgicalChecklistSerializer(checklist).data)

    @transaction.atomic
    def post(self, request, case_id):
        case = get_object_or_404(SurgicalCase.objects.select_related("organization", "patient"), pk=case_id)
        if request_role(request) not in THEATRE_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if not _is_admin(request.user) and not organization_for_user(request.user, case.organization_id):
            return Response({"detail": "Case is outside your organization."}, status=403)
        checklist, _ = SurgicalChecklist.objects.get_or_create(surgical_case=case)
        serializer = SurgicalChecklistSerializer(checklist, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        checklist = serializer.save(completed_by=request.user)
        _audit(request, "surgical_checklist.updated", checklist, case.patient, {"completion_percent": checklist.completion_percent})
        return Response(SurgicalChecklistSerializer(checklist).data)


class MaternityEpisodeListCreateView(APIView):
    def get(self, request):
        qs = MaternityEpisode.objects.select_related("organization", "patient", "admission", "assigned_midwife", "assigned_clinician")
        qs = _scoped_queryset(request, qs)
        return Response(MaternityEpisodeSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in MATERNITY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted to create maternity episodes."}, status=403)
        if not org:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = MaternityEpisodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        episode = serializer.save(organization=org, created_by=request.user)
        _audit(request, "maternity_episode.created", episode, episode.patient, {"risk": episode.risk_level})
        return Response(MaternityEpisodeSerializer(episode).data, status=201)


class MaternityEpisodeActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        episode = get_object_or_404(MaternityEpisode.objects.select_for_update().select_related("organization", "patient"), pk=pk)
        if request_role(request) not in MATERNITY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if not _is_admin(request.user) and not organization_for_user(request.user, episode.organization_id):
            return Response({"detail": "Episode is outside your organization."}, status=403)
        action = request.data.get("action")
        mapping = {
            "admit": MaternityEpisode.Status.ADMITTED,
            "start_labour": MaternityEpisode.Status.IN_LABOUR,
            "deliver": MaternityEpisode.Status.DELIVERED,
            "postnatal": MaternityEpisode.Status.POSTNATAL,
            "discharge": MaternityEpisode.Status.DISCHARGED,
            "refer": MaternityEpisode.Status.REFERRED,
        }
        if action not in mapping:
            return Response({"detail": "Unsupported maternity action."}, status=400)
        episode.status = mapping[action]
        editable = ["risk_level", "risk_notes", "delivery_method", "birth_outcome", "newborn_weight_grams", "apgar_one_minute", "apgar_five_minutes", "newborn_notes"]
        for name in editable:
            if name in request.data:
                setattr(episode, name, request.data[name])
        if request.data.get("assigned_midwife"):
            episode.assigned_midwife_id = request.data["assigned_midwife"]
        if request.data.get("assigned_clinician"):
            episode.assigned_clinician_id = request.data["assigned_clinician"]
        if action == "start_labour":
            if episode.status in {MaternityEpisode.Status.DELIVERED, MaternityEpisode.Status.POSTNATAL, MaternityEpisode.Status.DISCHARGED}:
                return Response({"detail": "Labour cannot be started after delivery."}, status=409)
            episode.labour_started_at = episode.labour_started_at or timezone.now()
        if action == "deliver":
            if not request.data.get("delivery_method") or not request.data.get("birth_outcome"):
                return Response({"detail": "Delivery method and birth outcome are required."}, status=400)
            for field in ("apgar_one_minute", "apgar_five_minutes"):
                value = request.data.get(field)
                if value is None or not 0 <= int(value) <= 10:
                    return Response({field: ["APGAR score must be between 0 and 10."]}, status=400)
            weight = int(request.data.get("newborn_weight_grams") or 0)
            if weight <= 0:
                return Response({"newborn_weight_grams": ["Record the newborn birth weight in grams."]}, status=400)
            episode.delivered_at = request.data.get("delivered_at") or timezone.now()
        episode.save()
        _audit(request, f"maternity_episode.{action}", episode, episode.patient, {"status": episode.status})
        return Response(MaternityEpisodeSerializer(episode).data)


class StaffShiftListCreateView(APIView):
    def get(self, request):
        qs = StaffShift.objects.select_related("organization", "staff", "department", "created_by")
        org = _org_for_request(request)
        if _is_admin(request.user) and not org:
            pass
        elif request_role(request) in WORKFORCE_SCHEDULING_ROLES or _can_manage(request.user, org):
            qs = qs.filter(organization=org)
        else:
            qs = qs.filter(staff=request.user)
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if start:
            qs = qs.filter(ends_at__gte=start)
        if end:
            qs = qs.filter(starts_at__lte=end)
        return Response(StaffShiftSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if request_role(request) not in WORKFORCE_SCHEDULING_ROLES and not _is_admin(request.user):
            return Response({"detail": "Only facility or HR managers can schedule shifts."}, status=403)
        if not org:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = StaffShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shift = serializer.save(organization=org, created_by=request.user)
        _audit(request, "staff_shift.created", shift, metadata={"staff_id": shift.staff_id})
        _notify(shift.staff, "New work shift", f"You have a {shift.shift_type} shift starting {shift.starts_at:%d %b %Y %H:%M}.", "/facility/schedule")
        return Response(StaffShiftSerializer(shift).data, status=201)


class StaffShiftActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        shift = get_object_or_404(StaffShift.objects.select_for_update().select_related("organization", "staff"), pk=pk)
        action = request.data.get("action")
        own_actions = {"confirm": StaffShift.Status.CONFIRMED, "start": StaffShift.Status.IN_PROGRESS, "complete": StaffShift.Status.COMPLETED}
        manager_actions = {**own_actions, "absent": StaffShift.Status.ABSENT, "cancel": StaffShift.Status.CANCELLED}
        allowed = manager_actions if request_role(request) in WORKFORCE_SCHEDULING_ROLES or _is_admin(request.user) else own_actions
        if request.user != shift.staff and request_role(request) not in WORKFORCE_SCHEDULING_ROLES and not _is_admin(request.user):
            return Response({"detail": "Not permitted."}, status=403)
        if action not in allowed:
            return Response({"detail": "Unsupported shift action."}, status=400)
        shift.status = allowed[action]
        shift.save(update_fields=["status", "updated_at"])
        _audit(request, f"staff_shift.{action}", shift, metadata={"staff_id": shift.staff_id})
        return Response(StaffShiftSerializer(shift).data)


class LeaveRequestListCreateView(APIView):
    def get(self, request):
        qs = LeaveRequest.objects.select_related("organization", "staff", "reviewed_by")
        org = _org_for_request(request)
        if _is_admin(request.user) and not org:
            pass
        elif request_role(request) in WORKFORCE_SCHEDULING_ROLES:
            qs = qs.filter(organization=org)
        else:
            qs = qs.filter(staff=request.user)
        return Response(LeaveRequestSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if not org:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = LeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = request.user
        if request_role(request) in WORKFORCE_SCHEDULING_ROLES and request.data.get("staff"):
            staff = serializer.validated_data.get("staff", request.user)
        leave = serializer.save(organization=org, staff=staff)
        _audit(request, "leave_request.created", leave, metadata={"staff_id": leave.staff_id})
        return Response(LeaveRequestSerializer(leave).data, status=201)


class LeaveRequestActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest.objects.select_for_update().select_related("organization", "staff"), pk=pk)
        action = request.data.get("action")
        if action == "cancel" and request.user == leave.staff:
            leave.status = LeaveRequest.Status.CANCELLED
        elif action in {"approve", "reject"} and (request_role(request) in WORKFORCE_SCHEDULING_ROLES or _is_admin(request.user)):
            leave.status = LeaveRequest.Status.APPROVED if action == "approve" else LeaveRequest.Status.REJECTED
            leave.reviewed_by = request.user
            leave.reviewed_at = timezone.now()
            leave.review_notes = request.data.get("review_notes", "")
        else:
            return Response({"detail": "Not permitted or unsupported action."}, status=403)
        leave.save()
        _audit(request, f"leave_request.{action}", leave, metadata={"staff_id": leave.staff_id})
        _notify(leave.staff, f"Leave request {leave.status}", f"Your leave request from {leave.starts_on} to {leave.ends_on} is {leave.status}.", "/facility/schedule")
        return Response(LeaveRequestSerializer(leave).data)


class QualityIncidentListCreateView(APIView):
    def get(self, request):
        qs = QualityIncident.objects.select_related("organization", "patient", "reported_by", "assigned_to")
        org = _org_for_request(request)
        if not (_is_admin(request.user) and not org):
            qs = qs.filter(organization=org)
        return Response(QualityIncidentSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        if not org and not _is_admin(request.user):
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = QualityIncidentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = serializer.save(organization=org, reported_by=request.user)
        _audit(request, "quality_incident.reported", incident, incident.patient, {"severity": incident.severity})
        return Response(QualityIncidentSerializer(incident).data, status=201)


class QualityIncidentActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        incident = get_object_or_404(QualityIncident.objects.select_for_update().select_related("organization", "patient"), pk=pk)
        if request_role(request) not in QUALITY_ACCESS_ROLES and not _is_admin(request.user):
            return Response({"detail": "Only quality or facility management can update incidents."}, status=403)
        action = request.data.get("action")
        mapping = {"investigate": QualityIncident.Status.INVESTIGATING, "action_required": QualityIncident.Status.ACTION_REQUIRED, "resolve": QualityIncident.Status.RESOLVED, "close": QualityIncident.Status.CLOSED, "reopen": QualityIncident.Status.OPEN}
        if action not in mapping:
            return Response({"detail": "Unsupported incident action."}, status=400)
        incident.status = mapping[action]
        for name in ["immediate_actions", "root_cause", "corrective_actions"]:
            if name in request.data:
                setattr(incident, name, request.data[name])
        if request.data.get("assigned_to"):
            incident.assigned_to_id = request.data["assigned_to"]
        incident.closed_at = timezone.now() if action == "close" else None
        incident.save()
        _audit(request, f"quality_incident.{action}", incident, incident.patient, {"status": incident.status})
        return Response(QualityIncidentSerializer(incident).data)


class PrivacyRequestListCreateView(APIView):
    def get(self, request):
        qs = PrivacyRequest.objects.select_related("organization", "requester", "assigned_to")
        if request_role(request) == "patient":
            qs = qs.filter(requester=request.user)
        elif request_role(request) in PRIVACY_MANAGEMENT_ROLES or _is_admin(request.user):
            org = _org_for_request(request)
            if not (_is_admin(request.user) and not org):
                qs = qs.filter(organization=org)
        else:
            qs = qs.filter(requester=request.user)
        return Response(PrivacyRequestSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        org = _org_for_request(request)
        serializer = PrivacyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(organization=org, requester=request.user, requester_email=request.user.email)
        _audit(request, "privacy_request.received", item, request.user if request_role(request) == "patient" else None, {"type": item.request_type})
        return Response(PrivacyRequestSerializer(item).data, status=201)


class PrivacyRequestActionView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        item = get_object_or_404(PrivacyRequest.objects.select_for_update().select_related("organization", "requester"), pk=pk)
        if request_role(request) not in PRIVACY_MANAGEMENT_ROLES and not _is_admin(request.user):
            return Response({"detail": "Only privacy and compliance personnel can process requests."}, status=403)
        action = request.data.get("action")
        mapping = {"verify": PrivacyRequest.Status.VERIFYING, "start": PrivacyRequest.Status.IN_PROGRESS, "wait": PrivacyRequest.Status.WAITING, "complete": PrivacyRequest.Status.COMPLETED, "decline": PrivacyRequest.Status.DECLINED}
        if action not in mapping:
            return Response({"detail": "Unsupported privacy action."}, status=400)
        item.status = mapping[action]
        if action == "verify":
            item.identity_verified = bool(request.data.get("identity_verified", True))
        if request.data.get("assigned_to"):
            item.assigned_to_id = request.data["assigned_to"]
        if request.data.get("resolution") is not None:
            item.resolution = request.data.get("resolution", "")
        if action in {"complete", "decline"}:
            item.completed_at = timezone.now()
        item.save()
        _audit(request, f"privacy_request.{action}", item, item.requester if item.requester and item.requester.role == "patient" else None, {"status": item.status})
        _notify(item.requester, f"Privacy request {item.status}", f"Privacy request {item.request_number} is now {item.status}.", "/patient/profile")
        return Response(PrivacyRequestSerializer(item).data)


class EnterpriseAnalyticsView(APIView):
    def get(self, request):
        org = _org_for_request(request)
        if not org and not _is_admin(request.user):
            return Response({"detail": "No organization is in scope."}, status=403)
        org_filter = {} if _is_admin(request.user) and not org else {"organization": org}
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        admissions = Admission.objects.filter(**org_filter)
        emergency = EmergencyCase.objects.filter(**org_filter)
        surgery = SurgicalCase.objects.filter(**org_filter)
        maternity = MaternityEpisode.objects.filter(**org_filter)
        incidents = QualityIncident.objects.filter(**org_filter)
        shifts = StaffShift.objects.filter(**org_filter)
        result = {
            "generated_at": now,
            "admissions": {"active": admissions.filter(status__in=[Admission.Status.ADMITTED, Admission.Status.TRANSFERRED, Admission.Status.DISCHARGE_PENDING]).count(), "month": admissions.filter(admitted_at__gte=month_start).count()},
            "emergency": {"open": emergency.exclude(status__in=[EmergencyCase.Status.DISCHARGED, EmergencyCase.Status.ADMITTED, EmergencyCase.Status.REFERRED, EmergencyCase.Status.LEFT, EmergencyCase.Status.DECEASED]).count(), "month": emergency.filter(arrival_at__gte=month_start).count(), "critical": emergency.filter(acuity__in=[EmergencyCase.Acuity.RESUSCITATION, EmergencyCase.Acuity.EMERGENT], arrival_at__gte=month_start).count()},
            "theatre": {"scheduled": surgery.filter(status__in=[SurgicalCase.Status.SCHEDULED, SurgicalCase.Status.PRE_OP]).count(), "month_completed": surgery.filter(status=SurgicalCase.Status.COMPLETED, actual_end__gte=month_start).count()},
            "maternity": {"active": maternity.exclude(status__in=[MaternityEpisode.Status.DISCHARGED, MaternityEpisode.Status.REFERRED]).count(), "month_deliveries": maternity.filter(delivered_at__gte=month_start).count()},
            "quality": {"open": incidents.exclude(status__in=[QualityIncident.Status.RESOLVED, QualityIncident.Status.CLOSED]).count(), "critical_open": incidents.filter(severity='critical').exclude(status=QualityIncident.Status.CLOSED).count()},
            "workforce": {"scheduled_next_7_days": shifts.filter(starts_at__gte=now, starts_at__lte=now + timedelta(days=7)).count(), "unfilled": shifts.filter(starts_at__gte=now, staff__isnull=True).count()},
        }
        try:
            from payments.models import Invoice, PaymentTransaction
            invoice_filter = {} if _is_admin(request.user) and not org else {"organization": org}
            result["finance"] = {
                "invoiced_month": Invoice.objects.filter(**invoice_filter, created_at__gte=month_start).aggregate(total=Sum("amount"))["total"] or 0,
                "collected_month": PaymentTransaction.objects.filter(invoice__created_at__gte=month_start, status=PaymentTransaction.Status.CONFIRMED, **({} if _is_admin(request.user) and not org else {"invoice__organization": org})).aggregate(total=Sum("amount"))["total"] or 0,
                "outstanding": sum(invoice.balance for invoice in Invoice.objects.filter(**invoice_filter).exclude(status__in=[Invoice.Status.PAID, Invoice.Status.VOID, Invoice.Status.REFUNDED])),
            }
        except Exception:
            result["finance"] = {"invoiced_month": 0, "collected_month": 0, "outstanding": 0}
        return Response(result)
