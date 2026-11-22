import uuid

from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import User
from communication.services import notify
from services.models import Medicine

from . import models as m, services
from .access import organizations, require_organization
from .pharmacy_views import PharmacyView
from .serializers import StrictSerializer, serializer_for
from .views import validated

PHARMACIST_ROLES = {"pharmacist"}
MAX_QUANTITY = 2147483647


class PharmacyOversightView(PharmacyView):
    def get_roles(self):
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            return self.roles | {"pharmacy"}
        return self.roles


def verify_return_witness(batch, actor, witness):
    if not batch.controlled:
        if witness:
            raise ValidationError("A witness is only recorded for controlled returns.")
        return
    if witness is None or witness.pk == actor.pk:
        raise ValidationError("Controlled returns require an independent witness.")
    require_organization(witness, batch.organization_id, {"pharmacist", "doctor"})



class ReturnedMedicineSerializer(serializer_for(m.PharmacyReturn, ("disposition", "disposition_note", "resolved_by", "disposition_witness"))):
    medicine_name = serializers.CharField(source="movement.batch.medicine.name", read_only=True)
    batch_number = serializers.CharField(source="movement.batch.batch_number", read_only=True)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)
    reason = serializers.CharField(max_length=2000)


class ReturnDisposition(StrictSerializer):
    disposition = serializers.ChoiceField(choices=("destroyed", "returned_to_supplier"))
    note = serializers.CharField(max_length=2000)
    witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)


class ReturnView(PharmacyOversightView):
    pharmacy_page = "safety"
    pharmacy_actions = {'create': 'safety_manage', 'resolve': 'safety_manage'}
    roles = PHARMACIST_ROLES
    model, serializer_class = m.PharmacyReturn, ReturnedMedicineSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("movement__batch__medicine")

    def create_record(self, serializer):
        values = serializer.validated_data
        movement = m.StockMovement.objects.select_for_update().get(pk=values["movement"].pk)
        if movement.batch.organization_id != values["organization"].pk or movement.kind != "dispensed":
            raise ValidationError("Select a dispensing movement from this pharmacy.")
        order = movement.order or movement.pharmacy_order
        if not order or not order.handed_over_at or order.status != "delivered" or hasattr(movement, "reversal"):
            raise ValidationError("Only a recorded handover can be used for this return.")
        verify_return_witness(movement.batch, self.request.user, values.get("intake_witness"))
        previously_returned = movement.patient_returns.aggregate(total=Sum("quantity"))["total"] or 0
        if values["quantity"] + previously_returned > -movement.quantity:
            raise ValidationError("Return quantity exceeds the quantity handed over.")
        # A patient return stays segregated and is never added to sellable inventory.
        return super().create_record(serializer)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def resolve(self, request, pk=None):
        row = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        data = validated(ReturnDisposition, request)
        if row.disposition != "segregated":
            raise ValidationError("This return has already been resolved.")
        verify_return_witness(row.movement.batch, request.user, data.get("witness"))
        row.disposition_witness = data.get("witness")
        row.disposition = data["disposition"]
        row.disposition_note = data["note"]
        row.resolved_by = request.user
        row.save()
        services.event(row, request.user, "pharmacy.patient_return_resolved", disposition=row.disposition)
        return Response(self.get_serializer(row).data)


class RecallContactSerializer(serializer_for(m.PharmacyRecallContact, (
    "organization", "batch", "patient", "status", "notes", "notified_at",
))):
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    medicine_name = serializers.CharField(source="batch.medicine.name", read_only=True)
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    recovered = serializers.SerializerMethodField()
    handed_over = serializers.SerializerMethodField()

    def get_handed_over(self, row):
        quantity = handed_over_movements(row.batch).filter(patient=row.patient).aggregate(total=Sum("quantity"))["total"]
        return -quantity if quantity else 0

    def get_recovered(self, row):
        return m.PharmacyReturn.objects.filter(movement__batch=row.batch, movement__patient=row.patient).aggregate(
            total=Sum("quantity"),
        )["total"] or 0


class RecallAction(StrictSerializer):
    action = serializers.ChoiceField(choices=("notify", "contacted", "resolved", "unreachable"))
    note = serializers.CharField(max_length=2000)


class RecallContactView(PharmacyOversightView):
    pharmacy_page = "safety"
    pharmacy_actions = {'follow_up': 'safety_manage'}
    roles = PHARMACIST_ROLES
    model, serializer_class = m.PharmacyRecallContact, RecallContactSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().select_related("batch__medicine", "patient")

    def create(self, request, *args, **kwargs):
        from rest_framework.exceptions import MethodNotAllowed
        raise MethodNotAllowed("POST")

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def follow_up(self, request, pk=None):
        row = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        data = validated(RecallAction, request)
        if row.status == "resolved":
            raise ValidationError("This contact has already been resolved.")
        if data["action"] == "notify":
            if row.notified_at:
                return Response(self.get_serializer(row).data)
            notify(row.patient, "Medicine safety alert",
                   "A medicine you received was affected by a recall. Contact the dispensing pharmacy for instructions.",
                   kind="medicine_recall", priority="critical", action_url="/patient/store", channels=["in_app"])
            row.notified_at = timezone.now()
            if row.status == "pending":
                row.status = "notified"
        else:
            row.status = data["action"]
        row.notes = data["note"]
        row.save()
        services.event(row, request.user, f"pharmacy.recall_{data['action']}")
        return Response(self.get_serializer(row).data)


def handed_over_movements(batch):
    return batch.movements.filter(kind="dispensed", patient__isnull=False, reversal__isnull=True).filter(
        Q(order__status="delivered") | Q(pharmacy_order__status="delivered"),
    )


def create_recall_contacts(batch, actor):
    for patient_id in handed_over_movements(batch).values_list("patient_id", flat=True).distinct():
        m.PharmacyRecallContact.objects.get_or_create(
            organization=batch.organization, batch=batch, patient_id=patient_id, defaults={"created_by": actor},
        )


class SafetyReportSerializer(serializer_for(m.PharmacySafetyReport, ("state", "external_reference", "resolution"))):
    description = serializers.CharField(max_length=4000)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        movement = attrs.get("movement")
        if movement and movement.batch.organization_id != attrs["organization"].pk:
            raise ValidationError("Movement belongs to a different pharmacy.")
        return attrs


class SafetyReportResolution(StrictSerializer):
    state = serializers.ChoiceField(choices=("reported", "closed"))
    note = serializers.CharField(max_length=2000)
    external_reference = serializers.CharField(max_length=200, required=False, allow_blank=True)


class SafetyReportView(PharmacyOversightView):
    pharmacy_page = "safety"
    pharmacy_actions = {'create': 'safety_manage', 'resolve': 'safety_manage'}
    roles = PHARMACIST_ROLES
    model, serializer_class = m.PharmacySafetyReport, SafetyReportSerializer

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def resolve(self, request, pk=None):
        row = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        data = validated(SafetyReportResolution, request)
        if row.state == "closed" or row.state == data["state"]:
            raise ValidationError("This report cannot make that transition.")
        if data["state"] == "reported" and not data.get("external_reference"):
            raise ValidationError("Record the external report reference or reporting channel.")
        row.state = data["state"]
        row.resolution = data["note"]
        row.external_reference = data.get("external_reference") or row.external_reference
        row.save()
        services.event(row, request.user, f"pharmacy.safety_report_{row.state}")
        return Response(self.get_serializer(row).data)


class TransferSerializer(serializer_for(m.PharmacyTransfer, ("status", "dispatch", "receipt"))):
    medicine_name = serializers.CharField(source="source.medicine.name", read_only=True)
    destination_name = serializers.CharField(source="destination.organization.legal_name", read_only=True)
    destination_organization = serializers.IntegerField(source="destination.organization_id", read_only=True)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY)
    reason = serializers.CharField(max_length=2000)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        source, destination = attrs["source"], attrs["destination"]
        if source.organization_id != attrs["organization"].pk or source.organization_id == destination.organization_id:
            raise ValidationError("Select a source at this pharmacy and a batch at a different pharmacy.")
        require_organization(self.context["request"].user, destination.organization_id, PHARMACIST_ROLES)
        validate_transfer_batches(source, destination)
        return attrs


def validate_transfer_batches(source, destination):
    if source.organization.organization_type != "pharmacy" or destination.organization.organization_type != "pharmacy":
        raise ValidationError("Transfers require two pharmacy organizations.")
    if (source.controlled or destination.controlled or source.medicine.sale_type in {"unclassified", "controlled"}
            or source.medicine.sale_type != destination.medicine.sale_type):
        raise ValidationError("Only equivalently classified non-controlled products can be transferred.")
    matching_fields = ("batch_number", "expires_on", "min_temperature", "max_temperature")
    if any(getattr(source, name) != getattr(destination, name) for name in matching_fields):
        raise ValidationError("Transfer batches must match by lot, expiry and storage conditions.")
    source_entry = m.PharmacyFormularyEntry.objects.filter(
        organization=source.organization, medicine=source.medicine, active=True, register_entry__isnull=False,
    ).first()
    destination_entry = m.PharmacyFormularyEntry.objects.filter(
        organization=destination.organization, medicine=destination.medicine, active=True, register_entry__isnull=False,
    ).first()
    if (not source_entry or not destination_entry
            or source_entry.register_entry_id != destination_entry.register_entry_id
            or source_entry.strength.strip().casefold() != destination_entry.strength.strip().casefold()
            or source_entry.dosage_form.strip().casefold() != destination_entry.dosage_form.strip().casefold()):
        raise ValidationError("Both branch products must link to the same active formulary reference.")
    if (source.status != "available" or destination.status != "available"
            or source.expires_on <= timezone.localdate()):
        raise ValidationError("Transfers require available, unexpired stock at both branches.")


class TransferAction(StrictSerializer):
    action = serializers.ChoiceField(choices=("dispatch", "receive", "cancel", "segregate"))
    note = serializers.CharField(max_length=1900)


class TransferView(PharmacyOversightView):
    pharmacy_page = "transfers"
    pharmacy_actions = {'create': 'transfer_manage', 'transition': 'transfer_manage'}
    roles = PHARMACIST_ROLES
    model, serializer_class = m.PharmacyTransfer, TransferSerializer

    def get_queryset(self):
        scope = self.organization_scope()
        rows = self.model.objects.filter(Q(organization__in=scope) | Q(destination__organization__in=scope))
        selected = self.request.query_params.get("organization")
        if selected:
            org = require_organization(self.request.user, selected)
            rows = rows.filter(Q(organization=org) | Q(destination__organization=org))
        return rows.select_related("source__medicine", "destination__organization").order_by("-pk")

    def get_object(self):
        from rest_framework.generics import get_object_or_404
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transition(self, request, pk=None):
        row = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        data = validated(TransferAction, request)
        step = data["action"]
        org_id = row.destination.organization_id if step in {"receive", "segregate"} else row.organization_id
        self.check_pharmacy_policy(require_organization(request.user, org_id, PHARMACIST_ROLES))
        target = {("requested", "dispatch"): "dispatched", ("requested", "cancel"): "cancelled",
                  ("dispatched", "receive"): "received", ("dispatched", "segregate"): "segregated"}.get((row.status, step))
        if not target:
            raise ValidationError("The transfer cannot make that transition.")
        if step in {"dispatch", "receive"}:
            list(Medicine.objects.select_for_update().filter(pk__in=[row.source.medicine_id, row.destination.medicine_id]).order_by("pk"))
            locked = {batch.pk: batch for batch in m.MedicineBatch.objects.select_for_update().filter(
                pk__in=[row.source_id, row.destination_id],
            ).order_by("pk")}
            source, destination = locked[row.source_id], locked[row.destination_id]
            validate_transfer_batches(source, destination)
            movement = services.move_stock(
                source if step == "dispatch" else destination, request.user,
                quantity=-row.quantity if step == "dispatch" else row.quantity,
                kind="adjusted" if step == "dispatch" else "received",
                reason=f"Transfer #{row.pk}. {data['note']}", reference=uuid.uuid4(),
            )
            if step == "dispatch":
                row.dispatch = movement
            else:
                row.receipt = movement
        row.status = target
        row.save()
        services.event(row, request.user, f"pharmacy.transfer_{target}", note=data["note"])
        return Response(self.get_serializer(row).data)
