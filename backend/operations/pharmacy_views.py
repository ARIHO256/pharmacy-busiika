import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import User
from interoperability.models import TerminologyConcept
from services.models import Medicine, Supplier

from . import models as m, services
from .access import require_organization
from .serializers import StrictSerializer, serializer_for
from .views import BaseView, validated

PHARMACY_ROLES = {"pharmacy", "pharmacist", "storekeeper", "facility_manager"}
REVIEW_ROLES = PHARMACY_ROLES - {"storekeeper"}


class PharmacyView(BaseView):
    roles = PHARMACY_ROLES

    def get_queryset(self):
        return super().get_queryset().filter(organization__organization_type="pharmacy")

    def create_record(self, serializer):
        org = serializer.validated_data["organization"]
        if org.organization_type != "pharmacy":
            raise ValidationError("Select a pharmacy organization.")
        return super().create_record(serializer)


class PurchaseReceiptSerializer(serializers.ModelSerializer):
    batch_number = serializers.CharField(source="movement.batch.batch_number")
    quantity = serializers.IntegerField(source="movement.quantity")
    reason = serializers.CharField(source="movement.reason")
    received_at = serializers.DateTimeField(source="movement.occurred_at")

    class Meta:
        model = m.PharmacyPurchaseReceipt
        fields = ("id", "batch_number", "quantity", "reason", "received_at")


class PurchaseLineSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    receipts = PurchaseReceiptSerializer(many=True, read_only=True)

    class Meta:
        model = m.PharmacyPurchaseLine
        fields = ("id", "medicine", "medicine_name", "ordered", "received", "unit_cost", "receipts")


class PurchaseSerializer(serializer_for(m.PharmacyPurchase, ("status", "status_reason"))):
    supplier_name = serializers.CharField(source="supplier.suppliername", read_only=True)
    qualified_until = serializers.DateField(source="supplier.qualified_until", read_only=True)
    lines = PurchaseLineSerializer(many=True, read_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["supplier"].pharmacy_id != attrs["organization"].owner_id:
            raise ValidationError("Supplier belongs to a different pharmacy.")
        return attrs


class AddLine(StrictSerializer):
    medicine = serializers.PrimaryKeyRelatedField(queryset=Medicine.objects.all())
    ordered = serializers.IntegerField(min_value=1, max_value=2147483647)
    unit_cost = serializers.IntegerField(min_value=0, max_value=2147483647)


class RemoveLine(StrictSerializer):
    line = serializers.IntegerField(min_value=1)


class PurchaseTransition(StrictSerializer):
    action = serializers.ChoiceField(choices=("approve", "close", "cancel"))
    reason = serializers.CharField(max_length=2000)


class ReceiptInput(StrictSerializer):
    packs = serializers.BooleanField(required=False, default=False)
    line = serializers.IntegerField(min_value=1)
    batch = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=2147483647)
    reference = serializers.UUIDField()
    reason = serializers.CharField(max_length=1900)
    witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)


class ProcurementView(PharmacyView):
    pharmacy_page = "procurement"
    pharmacy_actions = {'create': 'purchase_edit', 'add_line': 'purchase_edit', 'remove_line': 'purchase_edit', 'receive': 'purchase_receive', 'transition': 'purchase_approve'}
    model = m.PharmacyPurchase
    serializer_class = PurchaseSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("supplier").prefetch_related("lines__medicine", "lines__receipts__movement__batch")

    @action(detail=True, methods=["post"], url_path="add-line")
    @transaction.atomic
    def add_line(self, request, pk=None):
        purchase = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        values = validated(AddLine, request)
        if purchase.status != "draft" or values["medicine"].pharmacy_id != purchase.supplier.pharmacy_id:
            raise ValidationError("Only medicines from this pharmacy can be added to a draft order.")
        if purchase.lines.filter(medicine=values["medicine"]).exists():
            raise ValidationError("This medicine is already on the purchase order.")
        line = purchase.lines.create(**values)
        services.event(purchase, request.user, "procurement.line_added", line_id=line.pk)
        return Response(PurchaseLineSerializer(line).data, status=201)

    @action(detail=True, methods=["post"], url_path="remove-line")
    @transaction.atomic
    def remove_line(self, request, pk=None):
        purchase = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        values = validated(RemoveLine, request)
        line = purchase.lines.filter(pk=values["line"]).first()
        if purchase.status != "draft" or not line:
            raise ValidationError("Select a line from this draft order.")
        services.event(purchase, request.user, "procurement.line_removed", line_id=line.pk, medicine_id=line.medicine_id)
        line.delete()
        return Response(self.get_serializer(purchase).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transition(self, request, pk=None):
        purchase = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        require_organization(request.user, purchase.organization_id, REVIEW_ROLES)
        values = validated(PurchaseTransition, request)
        transition = (purchase.status, values["action"])
        targets = {
            ("draft", "approve"): "approved",
            ("draft", "cancel"): "cancelled",
            ("approved", "close"): "closed",
        }
        if transition not in targets:
            raise ValidationError("This action is unavailable for the current order status.")
        if values["action"] == "approve":
            if not purchase.lines.exists():
                raise ValidationError("Add at least one medicine before approval.")
            supplier = purchase.supplier
            if not supplier.qualification_reference or not supplier.qualified_until or supplier.qualified_until < timezone.localdate():
                raise ValidationError("Record a current supplier qualification before approving this order.")
        purchase.status = targets[transition]
        purchase.status_reason = values["reason"]
        purchase.save(update_fields=["status", "status_reason", "updated_at"])
        services.event(purchase, request.user, f"procurement.{purchase.status}", reason=values["reason"])
        return Response(self.get_serializer(purchase).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def receive(self, request, pk=None):
        purchase = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        values = validated(ReceiptInput, request)
        line = purchase.lines.filter(pk=values.pop("line")).first()
        batch = m.MedicineBatch.objects.filter(
            pk=values.pop("batch"), organization_id=purchase.organization_id, supplier_id=purchase.supplier_id,
        ).first()
        if not line or not batch or line.medicine_id != batch.medicine_id:
            raise ValidationError("Select a batch for this order line, pharmacy and supplier.")
        values["reason"] = f"Purchase order #{purchase.pk}, line #{line.pk}. {values['reason']}"
        # Use the same lock order as inventory, dispensing and checkout.
        medicine = Medicine.objects.select_for_update().get(pk=batch.medicine_id)
        if values.pop("packs"):
            values["quantity"] = services.pack_units(medicine, values["quantity"])
        batch = m.MedicineBatch.objects.select_for_update().get(pk=batch.pk)
        previous = m.StockMovement.objects.filter(reference=values["reference"]).first()
        already_received = previous is not None
        if already_received and not line.receipts.filter(movement=previous).exists():
            raise ValidationError("This reference belongs to a different stock movement.")
        if not already_received:
            if purchase.status != "approved" or line.received + values["quantity"] > line.ordered:
                raise ValidationError("The order must be approved and the receipt cannot exceed the outstanding quantity.")
            if batch.status != "available" or batch.expires_on <= timezone.localdate():
                raise ValidationError("A receipt requires an available, unexpired batch.")
        movement = services.move_stock(batch, request.user, kind="received", **values)
        if not already_received:
            line.receipts.create(movement=movement)
            line.received += movement.quantity
            line.save(update_fields=["received"])
            services.event(purchase, request.user, "procurement.received", line_id=line.pk, movement_id=movement.pk)
        return Response(self.get_serializer(purchase).data)


class StockCountSerializer(serializer_for(m.PharmacyStockCount, (
    "expected", "batch_updated_at", "status", "reviewed_by", "review_reason", "adjustment",
))):
    medicine_name = serializers.CharField(source="batch.medicine.name", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["batch"].organization_id != attrs["organization"].pk:
            raise ValidationError("Batch belongs to a different pharmacy.")
        return attrs


class CountReview(StrictSerializer):
    action = serializers.ChoiceField(choices=("approve", "reject"))
    reason = serializers.CharField(max_length=1900)
    witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False)


class StocktakeView(PharmacyView):
    pharmacy_page = "stocktake"
    pharmacy_actions = {'create': 'stock_count', 'review': 'stock_approve'}
    model = m.PharmacyStockCount
    serializer_class = StockCountSerializer

    def get_queryset(self):
        return super().get_queryset().select_related("batch__medicine")

    def create_record(self, serializer):
        batch = m.MedicineBatch.objects.select_for_update().get(pk=serializer.validated_data["batch"].pk)
        return serializer.save(
            created_by=self.request.user, expected=batch.quantity, batch_updated_at=batch.updated_at,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def review(self, request, pk=None):
        count = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        require_organization(request.user, count.organization_id, REVIEW_ROLES)
        values = validated(CountReview, request)
        if count.status != "pending" or count.created_by_id == request.user.pk:
            raise ValidationError("A different authorized staff member must review the pending count.")
        if values["action"] == "approve":
            Medicine.objects.select_for_update().get(pk=count.batch.medicine_id)
            batch = m.MedicineBatch.objects.select_for_update().get(pk=count.batch_id)
            if batch.updated_at != count.batch_updated_at:
                raise ValidationError("The batch changed after the count was recorded. Reject it and record a fresh count.")
            difference = count.counted - count.expected
            if difference:
                count.adjustment = services.move_stock(
                    batch, request.user, quantity=difference, kind="adjusted",
                    reason=f"Stocktake #{count.pk}. {values['reason']}", reference=uuid.uuid4(),
                    witness=values.get("witness"),
                )
        count.status = "approved" if values["action"] == "approve" else "rejected"
        count.reviewed_by = request.user
        count.review_reason = values["reason"]
        count.save(update_fields=["status", "reviewed_by", "review_reason", "adjustment", "updated_at"])
        services.event(count, request.user, f"stocktake.{count.status}", adjustment_id=count.adjustment_id)
        return Response(self.get_serializer(count).data)


class FormularySerializer(serializer_for(m.PharmacyFormularyEntry, ("active",))):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    register_code = serializers.CharField(source="register_entry.code", read_only=True, default=None)
    register_entry = serializers.PrimaryKeyRelatedField(
        queryset=TerminologyConcept.objects.filter(active=True, category="registered_medicine_reference"),
        required=False, allow_null=True,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["medicine"].pharmacy_id != attrs["organization"].owner_id:
            raise ValidationError("Medicine belongs to a different pharmacy.")
        return attrs


class FormularyUpdate(StrictSerializer):
    strength = serializers.CharField(max_length=120)
    dosage_form = serializers.CharField(max_length=120)
    register_entry = serializers.PrimaryKeyRelatedField(
        queryset=TerminologyConcept.objects.filter(active=True, category="registered_medicine_reference"),
        required=False, allow_null=True, default=None,
    )
    active = serializers.BooleanField()


class FormularyView(PharmacyView):
    pharmacy_page = "inventory"
    pharmacy_actions = {'create': 'catalogue_edit', 'configure': 'catalogue_edit'}
    model = m.PharmacyFormularyEntry
    serializer_class = FormularySerializer

    def get_queryset(self):
        return super().get_queryset().select_related("medicine", "register_entry")

    def create_record(self, serializer):
        require_organization(self.request.user, serializer.validated_data["organization"].pk, REVIEW_ROLES)
        return super().create_record(serializer)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def configure(self, request, pk=None):
        entry = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        require_organization(request.user, entry.organization_id, REVIEW_ROLES)
        values = validated(FormularyUpdate, request)
        for key, value in values.items():
            setattr(entry, key, value)
        entry.save()
        services.event(entry, request.user, "formulary.updated")
        return Response(self.get_serializer(entry).data)
