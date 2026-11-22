from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.db.models import CharField, Exists, F, OuterRef, Q, Sum
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from governance.services import audit
from operations.models import MedicineBatch, PharmacyPurchaseLine, WorkflowEvent
from operations.serializers import BatchSerializer
from operations.services import move_stock, pack_units, refresh_stock

from .models import Medicine
from .pharmacy_permissions import require_pharmacy_permission
from .pharmacy_sales import staff_pharmacy


class OpeningLot(serializers.Serializer):
    batch_number = serializers.CharField(max_length=120)
    expires_on = serializers.DateField()
    units = serializers.IntegerField(min_value=0, max_value=2147483647, default=0)
    packs = serializers.IntegerField(min_value=0, max_value=2147483647, default=0)
    witness = serializers.IntegerField(min_value=1, required=False)


class OpeningStock(serializers.Serializer):
    medicine = serializers.IntegerField(min_value=1)
    expected_stock = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=1200)
    lots = OpeningLot(many=True, allow_empty=True, max_length=100)

    def validate_lots(self, lots):
        if len({lot["batch_number"].casefold() for lot in lots}) != len(lots):
            raise ValidationError("Enter each lot once.")
        return lots


class PharmacyStockSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacy = staff_pharmacy(request.user, roles={"pharmacy", "pharmacist", "storekeeper"})
        require_pharmacy_permission(request.user, pharmacy.owner_id, "stock-control")
        products = Medicine.objects.filter(pharmacy_id=pharmacy.owner_id).annotate(
            has_batches=Exists(MedicineBatch.objects.filter(medicine_id=OuterRef("pk"))),
        ).filter(Q(sale_type="unclassified") | Q(has_batches=False, stock__gt=0))
        search = request.query_params.get("search", "").strip()[:120]
        products = products.filter(name__icontains=search).order_by("name", "pk")
        return Response(list(products.values("id", "name", "sale_type", "stock", "has_batches", "unit_label", "units_per_pack")[:100]))

    @transaction.atomic
    def post(self, request):
        pharmacy = staff_pharmacy(request.user, roles={"pharmacy", "pharmacist", "storekeeper"})
        require_pharmacy_permission(request.user, pharmacy.owner_id, "stock-control", "stock_receive")
        payload = OpeningStock(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        medicine = get_object_or_404(Medicine.objects.select_for_update(), pk=data["medicine"], pharmacy_id=pharmacy.owner_id)
        if medicine.batches.exists() or medicine.stock != data["expected_stock"]:
            raise ValidationError("Stock changed. Refresh this worklist before reconciling.")
        if medicine.sale_type == Medicine.SaleType.UNCLASSIFIED and data["lots"]:
            raise ValidationError("Classify this product in Medicine Inventory before entering lots.")
        total = 0
        controlled = medicine.sale_type == Medicine.SaleType.CONTROLLED
        for lot in data["lots"]:
            quantity = lot["units"] + pack_units(medicine, lot["packs"])
            total += quantity
            if not quantity or total > 2147483647:
                raise ValidationError("Each lot needs a positive quantity within the stock limit.")
            fields = {
                "organization": pharmacy.pk, "medicine": medicine.pk, "batch_number": lot["batch_number"],
                "expires_on": lot["expires_on"], "controlled": controlled, "opening_quantity": quantity,
            }
            if lot.get("witness"):
                fields["opening_witness"] = lot["witness"]
            details = BatchSerializer(data=fields)
            details.is_valid(raise_exception=True)
            values = dict(details.validated_data)
            values.pop("opening_quantity")
            witness = values.pop("opening_witness", None)
            batch = MedicineBatch.objects.create(created_by=request.user, **values)
            move_stock(batch, request.user, quantity=quantity, kind="received", witness=witness,
                       reason=f"Opening stock reconciliation: {data['reason']}", reference=uuid4())
        refresh_stock(medicine)
        audit(
            actor=request.user, action="pharmacy.stock_reconciled", resource=medicine, purpose="operations", request=request,
            metadata={"pharmacy_id": pharmacy.owner_id, "before": data["expected_stock"], "counted": total, "reason": data["reason"]},
        )
        return Response({"stock": total})


class PharmacyStockAlertsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacy = staff_pharmacy(request.user, roles={"pharmacy", "pharmacist", "storekeeper"})
        require_pharmacy_permission(request.user, pharmacy.owner_id, "stock-control")
        today = timezone.localdate()
        batches = MedicineBatch.objects.filter(organization=pharmacy).filter(
            Q(expires_on__lte=today + timedelta(days=90)) | ~Q(status="available"),
        ).filter(quantity__gt=0).order_by("expires_on", "pk")
        products = Medicine.objects.filter(pharmacy=pharmacy.owner, reorder_level__gt=0).annotate(
            available=Sum("batches__quantity", filter=Q(batches__organization=pharmacy, batches__status="available",
                                                       batches__expires_on__gt=today), default=0),
        ).filter(available__lte=F("reorder_level"))
        outstanding = PharmacyPurchaseLine.objects.filter(
            purchase__organization=pharmacy, purchase__status="approved", received__lt=F("ordered"),
        ).order_by("purchase_id", "pk")
        return Response({
            "batches": list(batches.values("id", "medicine__name", "batch_number", "expires_on", "quantity", "status")[:100]),
            "reorders": list(products.order_by("available", "name").values("id", "name", "available", "reorder_level")[:100]),
            "deliveries": list(outstanding.values("id", "purchase_id", "medicine__name", "ordered", "received")[:100]),
        })


class PharmacyAuditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from governance.models import AuditEvent
        from .pharmacy_permissions import require_verified_owner

        require_verified_owner(request.user)
        from payments.models import Receipt

        contains = request.query_params.get("search", "").strip()[:100]
        actor_filter = Q(action__icontains=contains) | Q(actor__email__icontains=contains) | Q(
            actor__first_name__icontains=contains,
        ) | Q(actor__last_name__icontains=contains) | Q(actor__role__icontains=contains)
        scoped = WorkflowEvent.objects.filter(
            actor_filter, organization__owner=request.user, organization__organization_type="pharmacy",
        ).select_related("actor").order_by("-occurred_at", "-pk")[:100]
        receipts = Receipt.objects.filter(payment__invoice__pharmacy_sale__pharmacy=request.user).annotate(
            audit_id=Cast("pk", CharField()),
        ).values("audit_id")
        account = list(AuditEvent.objects.filter(
            Q(metadata__pharmacy_id=request.user.pk)
            | Q(actor=request.user, action__in=["pharmacy.custom_role.created", "pharmacy.custom_role.updated",
                 "pharmacy.staff_role.assigned", "pharmacy.role_permissions.updated"])
            | Q(resource_type="Receipt", resource_id__in=receipts, action__in=[
                "pharmacy.payment.recorded", "pharmacy.receipt.viewed",
            ]),
        ).filter(
            actor_filter | Q(metadata__worker__name__icontains=contains) | Q(metadata__worker__email__icontains=contains)
            | Q(metadata__worker__role__icontains=contains) | Q(metadata__worker__custom_role__icontains=contains),
        ).select_related("actor").order_by("-created_at", "-pk")[:100])
        linked = {row.metadata.get("workflow_event_id") for row in account}
        rows = []
        for row in [*account, *(row for row in scoped if row.pk not in linked)]:
            historical = isinstance(row, WorkflowEvent)
            actor = row.actor
            snapshot = {} if historical else row.metadata.get("worker", {})
            rows.append({
                "id": f"{'event' if historical else 'audit'}-{row.pk}", "action": row.action,
                "actor": snapshot.get("name") or (actor.get_full_name().strip() or actor.display_name if actor else ""),
                "actor_email": snapshot.get("email") or (actor.email if actor else ""),
                "actor_role": snapshot.get("role") or (actor.role if actor else ""),
                "custom_role": snapshot.get("custom_role"),
                "created_at": row.occurred_at if historical else row.created_at,
                "record": f"{row.resource_type} #{row.resource_id}",
            })
        return Response(sorted(rows, key=lambda row: row["created_at"], reverse=True)[:100])
