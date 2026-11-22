from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import organization_for_user, user_can_manage_organization
from .models import PatientVisit, VisitHandoff
from .services import audit_workforce

Destination = VisitHandoff.Destination
Status = VisitHandoff.Status
RECEIVERS = {
    Destination.RECEPTION: {"receptionist", "records_officer"},
    Destination.NURSING: {"nurse"},
    Destination.LAB: {"lab_technician"},
    Destination.IMAGING: {"doctor", "lab_technician"},
    Destination.PHARMACY: {"pharmacist"},
    Destination.BILLING: {"cashier"},
    Destination.SPECIALIST: {"doctor"},
    Destination.WARD: {"nurse", "doctor"},
}
OPEN = (Status.REQUESTED, Status.ACCEPTED, Status.RETURNED)
CLOSED_VISITS = (PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED)
PROFESSIONALS = {"doctor", "nurse", "lab_technician", "pharmacist"}
STAFF = {role for roles in RECEIVERS.values() for role in roles} | {"hospital", "facility_manager", "admin"}


class NewHandoff(serializers.Serializer):
    visit = serializers.IntegerField(min_value=1)
    destination = serializers.ChoiceField(choices=Destination.choices)
    priority = serializers.ChoiceField(choices=PatientVisit.Priority.choices, default=PatientVisit.Priority.ROUTINE)
    instructions = serializers.CharField(max_length=1000)
    prescription = serializers.IntegerField(min_value=1, required=False)
    modality = serializers.ChoiceField(choices=["CT", "MR", "US", "CR", "DX", "NM", "MG", "OT"], required=False)
    body_site = serializers.CharField(max_length=120, required=False)
    receiving_facility = serializers.IntegerField(min_value=1, required=False)
    specialty = serializers.CharField(max_length=200, required=False)

    def validate(self, attrs):
        if attrs["destination"] == Destination.IMAGING and not (attrs.get("modality") and attrs.get("body_site")):
            raise serializers.ValidationError("Select a modality and enter the body site.")
        if attrs.get("receiving_facility") and (attrs["destination"] != Destination.SPECIALIST or not attrs.get("specialty")):
            raise serializers.ValidationError("Select a specialty for the receiving facility.")
        return attrs


class HandoffAction(serializers.Serializer):
    action = serializers.ChoiceField(choices=["accept", "return", "complete", "cancel", "resend"])
    outcome = serializers.CharField(max_length=1000, required=False, allow_blank=True)


def scoped_facility(request):
    from operations.access import organizations

    user = request.user
    scope = organizations(user)
    organization_id = request.query_params.get("organization")
    if organization_id and not organization_id.isdecimal():
        raise ValidationError({"organization": "Enter a valid facility ID."})
    facility = organization_for_user(user, organization_id)
    if facility and not scope.filter(pk=facility.pk).exists():
        raise PermissionDenied("An active assignment at this facility is required.")
    if user.role == "pharmacist" and facility and facility.parent_facility_id:
        facility = facility.parent_facility
    if user.role not in STAFF or not facility or not facility.active or facility.status != "verified" or facility.organization_type not in {"clinic", "hospital"}:
        raise PermissionDenied("An active clinic or hospital staff assignment is required.")
    if user.role in PROFESSIONALS and not user.is_verified:
        raise PermissionDenied("Professional verification is required.")
    return facility


def is_prescriber(user, visit):
    return user.role == "doctor" and visit.assigned_doctor_id == user.pk


def is_receiver(user, row):
    if user.role not in RECEIVERS[row.destination] or user.role == "doctor" and row.requested_by_id == user.pk:
        return False
    if user.role == "pharmacist" and row.pharmacy_order_id:
        from services.pharmacy_permissions import permits
        from services.views import provider_account_for

        pharmacy = provider_account_for(user, "pharmacy")
        return bool(pharmacy and pharmacy.pk == row.pharmacy_order.pharmacy_id and permits(user, pharmacy.pk, "rx-orders"))
    if user.role == "lab_technician" and row.lab_order_id:
        from services.views import provider_account_for

        lab = provider_account_for(user, "lab")
        return bool(lab and lab.pk == row.lab_order.lab_id)
    return True


def allowed_actions(user, row):
    sender = is_prescriber(user, row.visit)
    receiver = is_receiver(user, row)
    if row.status == Status.REQUESTED:
        if row.lab_order_id or row.imaging_order_id or row.referral_route_id:
            return []
        return (["accept"] if receiver else []) + (["cancel"] if sender else [])
    if row.status == Status.ACCEPTED:
        if row.lab_order_id or row.imaging_order_id or row.referral_route_id:
            return []
        actions = ["complete", "return"] if row.accepted_by_id == user.pk and receiver else []
        if sender and not row.pharmacy_order_id:
            actions.append("cancel")
        return actions
    if row.status == Status.RETURNED and sender:
        if row.lab_order_id or row.imaging_order_id or row.referral_route_id:
            return ["complete"]
        if row.pharmacy_order_id and row.pharmacy_order.status == "rejected":
            return ["cancel"]
        return ["complete", "resend", "cancel"]
    return []


def serialize_handoff(request, row):
    user = request.user
    detail = is_prescriber(user, row.visit) or is_receiver(user, row) or row.requested_by_id == user.pk
    return {
        "id": row.pk, "visit": row.visit_id, "visit_number": row.visit.visit_number,
        "patient": row.visit.patient.display_name, "destination": row.destination,
        "destination_label": row.get_destination_display(), "status": row.status, "priority": row.priority,
        "requested_by": row.requested_by.display_name,
        "accepted_by": row.accepted_by.display_name if row.accepted_by else None,
        "instructions": row.instructions if detail else "",
        "outcome": row.outcome if detail else "",
        "updated_at": row.updated_at, "actions": allowed_actions(user, row),
        "pharmacy_order": row.pharmacy_order_id if detail else None,
        "lab_order": row.lab_order_id if detail else None,
        "imaging_order": row.imaging_order_id if detail else None,
        "referral_route": row.referral_route_id if detail else None,
    }


class HandoffListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        facility = scoped_facility(request)
        user = request.user
        rows = VisitHandoff.objects.filter(visit__organization=facility).select_related(
            "visit__patient", "requested_by", "accepted_by", "pharmacy_order", "lab_order",
        )
        if not user_can_manage_organization(user, facility):
            destinations = [destination for destination, roles in RECEIVERS.items() if user.role in roles]
            scope = Q(destination__in=destinations)
            if user.role == "doctor":
                scope |= Q(visit__assigned_doctor=user) | Q(requested_by=user)
            elif user.role == "nurse":
                scope |= Q(visit__assigned_nurse=user)
            elif user.role in RECEIVERS[Destination.RECEPTION]:
                # The front desk coordinates arrivals and sees stage without clinical instructions.
                scope = Q()
            rows = rows.filter(scope)
        visit = request.query_params.get("visit")
        if visit:
            if not visit.isdecimal():
                raise ValidationError({"visit": "Enter a valid visit ID."})
            rows = rows.filter(visit_id=visit)
        else:
            rows = rows.filter(status__in=OPEN)
        return Response([
            serialize_handoff(request, row) for row in rows
            if user.role not in {"pharmacist", "lab_technician"} or is_receiver(user, row)
        ])

    @transaction.atomic
    def post(self, request):
        facility = scoped_facility(request)
        data = NewHandoff(data=request.data)
        data.is_valid(raise_exception=True)
        fields = dict(data.validated_data)
        visit = get_object_or_404(PatientVisit.objects.select_for_update(), pk=fields.pop("visit"), organization=facility)
        if not is_prescriber(request.user, visit):
            raise PermissionDenied("Only the assigned doctor can request a handoff.")
        if visit.status in CLOSED_VISITS:
            raise ValidationError("The visit is closed.")
        if fields["destination"] == Destination.WARD and facility.organization_type != "hospital":
            raise ValidationError("Inpatient handoffs require a hospital. Use a referral to send a patient to another facility.")
        prescription_id = fields.pop("prescription", None)
        modality = fields.pop("modality", None)
        body_site = fields.pop("body_site", None)
        receiving_facility = fields.pop("receiving_facility", None)
        specialty = fields.pop("specialty", None)
        if receiving_facility:
            fields["referral_route"] = route_referral(visit, request.user, receiving_facility, specialty, fields)
        if fields["destination"] == Destination.IMAGING:
            from operations.models import ImagingOrder
            from operations.services import event

            imaging = ImagingOrder.objects.create(
                organization=facility, patient=visit.patient, referring_doctor=request.user, created_by=request.user,
                modality=modality, body_site=body_site, indication=fields["instructions"],
            )
            fields["imaging_order"] = imaging
            event(imaging, request.user, "imaging.ordered")
        if fields["destination"] == Destination.PHARMACY:
            fields["pharmacy_order"] = route_prescription(visit, request.user, prescription_id)
        elif prescription_id:
            raise ValidationError({"prescription": "Select the pharmacy destination."})
        row = VisitHandoff.objects.create(visit=visit, requested_by=request.user, **fields)
        audit_workforce(request, "visit.handoff.requested", row, patient=visit.patient)
        return Response(serialize_handoff(request, row), status=201)


class HandoffTransition(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        facility = scoped_facility(request)
        data = HandoffAction(data=request.data)
        data.is_valid(raise_exception=True)
        visit_id = get_object_or_404(VisitHandoff.objects.only("visit_id"), pk=pk, visit__organization=facility).visit_id
        visit = PatientVisit.objects.select_for_update().get(pk=visit_id)
        row = get_object_or_404(VisitHandoff.objects.select_for_update(), pk=pk, visit=visit)
        action = data.validated_data["action"]
        reviewing_result = (row.lab_order_id or row.imaging_order_id or row.referral_route_id) and row.status == Status.RETURNED and action == "complete"
        if visit.status in CLOSED_VISITS and not reviewing_result:
            raise ValidationError("The visit is closed.")
        outcome = data.validated_data.get("outcome", "")
        if action not in allowed_actions(request.user, row):
            raise PermissionDenied("This action is unavailable for your role or the current handoff stage.")
        if row.lab_order_id and row.status != Status.RETURNED:
            raise ValidationError("Use the linked laboratory order to record specimen and result progress.")
        if action == "complete" and row.lab_order_id and row.lab_order.results.filter(
            interpretation="critical", released_at__isnull=False,
            replacement__isnull=True, acknowledgement__isnull=True,
        ).exists():
            raise ValidationError("Acknowledge the critical result in Laboratory Referrals first.")
        if action == "complete" and row.pharmacy_order_id and row.pharmacy_order.status != "delivered":
            raise ValidationError("Record dispensing and patient handover in the prescription queue first.")
        if action in {"cancel", "resend"} and row.pharmacy_order_id and row.pharmacy_order.status != "rejected":
            raise ValidationError("The linked prescription order must be resolved at the pharmacy.")
        if action == "complete" and row.destination == Destination.BILLING:
            invoices = row.visit.invoices.exclude(status="void")
            if not invoices.exists() or any(invoice.balance for invoice in invoices):
                raise ValidationError("Issue a visit invoice and settle the balance before completing billing.")
        if action == "complete" and row.destination == Destination.WARD and not row.visit.admissions.exists():
            raise ValidationError("Create an admission linked to this visit first.")
        if action != "accept" and not outcome:
            raise ValidationError({"outcome": "Document the outcome or reason."})
        row.status = {
            "accept": Status.ACCEPTED, "return": Status.RETURNED, "complete": Status.COMPLETED,
            "cancel": Status.CANCELLED, "resend": Status.REQUESTED,
        }[action]
        if action == "accept":
            row.accepted_by = request.user
        elif action == "resend":
            row.accepted_by = None
            row.instructions = outcome
            row.outcome = ""
        else:
            row.outcome = outcome
        row.save()
        audit_workforce(request, f"visit.handoff.{action}", row, patient=row.visit.patient)
        return Response(serialize_handoff(request, row))


def route_prescription(visit, doctor, prescription_id):
    from prescriptions.models import Prescription
    from services.models import PharmacyOrder

    pharmacies = list(visit.organization.embedded_pharmacies.filter(
        active=True, status="verified", owner__role="pharmacy", owner__is_active=True,
    ).values_list("owner_id", flat=True)[:2])
    if len(pharmacies) != 1:
        raise ValidationError("The facility needs one verified dispensing pharmacy to route this prescription.")
    prescription = Prescription.objects.select_for_update().filter(
        pk=prescription_id, doctor=doctor, patient=visit.patient, status=Prescription.Status.ISSUED,
        expires_at__gt=timezone.now(),
    )
    scope = Q(visit=visit)
    if visit.appointment_id:
        scope |= Q(visit__isnull=True, appointment_id=visit.appointment_id)
    prescription = prescription.filter(scope).first()
    if not prescription:
        raise ValidationError({"prescription": "Select an active signed prescription from this visit."})
    if PharmacyOrder.objects.filter(prescription_id=prescription.pk).exclude(status=PharmacyOrder.Status.REJECTED).exists():
        raise ValidationError("This prescription was already sent to a pharmacy.")
    return PharmacyOrder.objects.create(patient=visit.patient, pharmacy_id=pharmacies[0], prescription_id=prescription.pk)


class VisitPrescription(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        from prescriptions.models import Prescription
        from prescriptions.serializers import PrescriptionCreateSerializer, PrescriptionDetailSerializer

        facility = scoped_facility(request)
        visit = get_object_or_404(PatientVisit.objects.select_for_update(), pk=pk, organization=facility)
        if not is_prescriber(request.user, visit):
            raise PermissionDenied("Only the assigned doctor can sign a prescription.")
        if visit.status in CLOSED_VISITS:
            raise ValidationError("The visit is closed.")
        data = PrescriptionCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        prescription = Prescription.objects.create(
            visit=visit, appointment=visit.appointment, doctor=request.user, patient=visit.patient,
            notes=data.validated_data["notes"],
        )
        for item in data.validated_data["items"]:
            prescription.items.create(**item)
        audit_workforce(request, "visit.prescription.signed", prescription, patient=visit.patient)
        return Response(PrescriptionDetailSerializer(prescription).data, status=201)


def track_lab_order(order):
    if not order.visit_id:
        return
    VisitHandoff.objects.create(
        visit_id=order.visit_id, requested_by_id=order.referring_doctor_id,
        destination=Destination.LAB, priority="emergency" if order.priority == "stat" else order.priority,
        instructions=f"Laboratory order #{order.pk}",
        lab_order=order,
    )


def update_lab_handoff(order, actor):
    rows = VisitHandoff.objects.filter(lab_order=order)
    if order.result_released:
        rows.update(status=Status.RETURNED, outcome="Laboratory result released for clinician review.",
                    accepted_by=actor, updated_at=timezone.now())
    elif order.status == "cancelled":
        rows.update(status=Status.CANCELLED, outcome="Laboratory order cancelled.",
                    accepted_by=actor, updated_at=timezone.now())
    elif order.status in {"sample_collected", "sample_received", "processing", "awaiting_validation"}:
        rows.filter(status=Status.REQUESTED).update(status=Status.ACCEPTED, accepted_by=actor, updated_at=timezone.now())


def update_pharmacy_handoff(order):
    row = VisitHandoff.objects.filter(pharmacy_order=order).first()
    if not row:
        return
    if order.status == "delivered":
        VisitHandoff.objects.filter(pk=row.pk).update(
            status=Status.COMPLETED, outcome="Medication handed over.",
            accepted_by_id=row.accepted_by_id or order.handed_over_by_id, updated_at=timezone.now(),
        )
    elif order.status == "rejected":
        VisitHandoff.objects.filter(pk=row.pk).update(
            status=Status.RETURNED, outcome="The pharmacy declined this prescription order.", updated_at=timezone.now(),
        )


def update_imaging_handoff(order, actor):
    rows = VisitHandoff.objects.filter(imaging_order=order)
    if order.status == "reported":
        rows.update(status=Status.RETURNED, outcome="Imaging report available for clinician review.",
                    accepted_by=actor, updated_at=timezone.now())
    elif order.status == "cancelled":
        rows.update(status=Status.CANCELLED, outcome="Imaging order cancelled.",
                    accepted_by=actor, updated_at=timezone.now())
    elif order.status in {"scheduled", "acquired"}:
        rows.filter(status=Status.REQUESTED).update(status=Status.ACCEPTED, accepted_by=actor, updated_at=timezone.now())


def referral_facilities():
    from registry.models import Organization

    return Organization.objects.filter(active=True, status="verified", organization_type__in=["hospital", "clinic"])


class ReferralFacilityList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scoped_facility(request)
        if request.user.role != "doctor":
            raise PermissionDenied("Only a doctor can route a clinical referral.")
        options = referral_facilities().order_by("legal_name", "pk").values("id", "legal_name")
        return Response(list(options))


def route_referral(visit, actor, receiving_facility, specialty, fields):
    from clinical.models import Referral
    from operations.models import ReferralRoute
    from operations.services import event

    facility = get_object_or_404(referral_facilities(), pk=receiving_facility)
    referral = Referral.objects.create(
        patient=visit.patient, referring_provider=actor, target_specialty=specialty,
        target_facility=facility.legal_name, reason=fields["instructions"], priority=fields["priority"],
    )
    route = ReferralRoute.objects.create(organization=facility, referral=referral, created_by=actor)
    event(route, actor, "referral.routed")
    return route


def update_referral_handoff(route, actor, status):
    rows = VisitHandoff.objects.filter(referral_route=route)
    if status in {"declined", "completed"}:
        rows.update(status=Status.RETURNED, outcome=f"Referral {status}. Review the outcome in the referral worklist.",
                    accepted_by=actor, updated_at=timezone.now())
    elif status == "cancelled":
        rows.update(status=Status.CANCELLED, outcome="Referral cancelled.",
                    updated_at=timezone.now())
    elif status in {"accepted", "in_progress"}:
        rows.filter(status=Status.REQUESTED).update(status=Status.ACCEPTED, accepted_by=actor, updated_at=timezone.now())
