from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import BigIntegerField, F, Sum
from django.db.models.functions import Cast
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import MedicineBatch, PharmacyPurchaseReceipt, StockMovement
from payments.models import PaymentTransaction

from .models import Medicine, Order
from .pharmacy_permissions import require_verified_owner


def amount(value):
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class ReportDates(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        today = timezone.localdate()
        end = attrs.get("end", today)
        start = attrs.get("start", end - timedelta(days=29))
        if start > end or end > today or (end - start).days > 365:
            raise ValidationError("Choose a date range of up to 366 days ending today or earlier.")
        return {"start": start, "end": end}


def batch_costs(scope, batches):
    purchased = PharmacyPurchaseReceipt.objects.filter(
        movement__batch__in=scope, line__purchase__organization__in=scope.values("organization_id"),
    ).values("movement__batch_id").annotate(
        units=Sum("movement__quantity"), spend=Sum(Cast("movement__quantity", BigIntegerField()) * F("line__unit_cost")),
    )
    additions = dict(StockMovement.objects.filter(batch__in=scope, quantity__gt=0)
                     .exclude(kind="returned").values_list("batch_id").annotate(units=Sum("quantity")))
    changes = dict(StockMovement.objects.filter(batch__in=scope).values_list("batch_id").annotate(units=Sum("quantity")))
    opening = {row.pk: row.quantity - changes.get(row.pk, 0) for row in batches}
    return {
        row["movement__batch_id"]: Decimal(row["spend"]) / row["units"]
        for row in purchased
        if row["units"] > 0
        and row["units"] == additions.get(row["movement__batch_id"])
        and opening.get(row["movement__batch_id"]) == 0
    }


class PharmacyReportsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        require_verified_owner(request.user)
        dates = ReportDates(data=request.query_params)
        dates.is_valid(raise_exception=True)
        start, end = dates.validated_data["start"], dates.validated_data["end"]
        today = timezone.localdate()
        batch_scope = MedicineBatch.objects.filter(
            organization__owner=request.user, organization__organization_type="pharmacy",
            organization__active=True, organization__status="verified", medicine__pharmacy=request.user,
        )
        batches = list(batch_scope.only("quantity", "status", "expires_on"))
        unit_costs = batch_costs(batch_scope, batches)
        payments = PaymentTransaction.objects.filter(
            invoice__pharmacy_sale__pharmacy=request.user,
            invoice__organization__owner=request.user, invoice__organization__organization_type="pharmacy",
            invoice__currency="UGX", status=PaymentTransaction.Status.CONFIRMED,
            confirmed_at__date__range=(start, end),
        ).exclude(invoice__pharmacy_sale__status=Order.Status.CANCELLED)
        by_method = list(payments.order_by("method").values("method").annotate(total=Sum("amount")))
        revenue_by_order = dict(payments.order_by().values_list("invoice__pharmacy_sale__pk").annotate(total=Sum("amount")))
        orders = Order.objects.filter(pk__in=revenue_by_order).prefetch_related("items")
        movement_cost = defaultdict(Decimal)
        traced_units = defaultdict(int)
        uncosted = set()
        for order_id, batch_id, quantity in StockMovement.objects.filter(
            order_id__in=revenue_by_order, kind="dispensed", quantity__lt=0, reversal__isnull=True,
        ).values_list("order_id", "batch_id", "quantity"):
            traced_units[order_id] -= quantity
            if batch_id in unit_costs:
                movement_cost[order_id] -= quantity * unit_costs[batch_id]
            else:
                uncosted.add(order_id)

        costed_revenue = 0
        cost_of_goods = Decimal(0)
        for order in orders:
            units = sum(item.qty for item in order.items.all())
            if units > 0 and traced_units[order.pk] == units and order.pk not in uncosted:
                costed_revenue += revenue_by_order[order.pk]
                cost_of_goods += movement_cost[order.pk]

        valuation = Decimal(0)
        counted_units = 0
        unknown_units = 0
        excluded_units = 0
        for batch in batches:
            if batch.status != "available" or batch.expires_on <= today:
                excluded_units += batch.quantity
            elif batch.pk in unit_costs:
                counted_units += batch.quantity
                valuation += batch.quantity * unit_costs[batch.pk]
            else:
                unknown_units += batch.quantity
        unbatched_units = Medicine.objects.filter(
            pharmacy=request.user, batches__isnull=True, stock__gt=0,
        ).aggregate(total=Sum("stock"))["total"] or 0
        revenue = sum(revenue_by_order.values())
        return Response({
            "start": start, "end": end, "stock_as_of": today, "currency": "UGX",
            "sales": {"revenue": revenue, "paid_orders": len(revenue_by_order), "payment_methods": by_method},
            "margin": {"costed_revenue": costed_revenue, "uncosted_revenue": revenue - costed_revenue,
                       "estimated_cost": amount(cost_of_goods), "estimated_gross_margin": amount(costed_revenue - cost_of_goods)},
            "stock": {"estimated_value": amount(valuation), "counted_units": counted_units,
                      "unknown_cost_units": unknown_units, "unbatched_units": unbatched_units, "excluded_units": excluded_units},
        })
