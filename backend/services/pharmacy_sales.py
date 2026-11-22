from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from governance.services import audit
from operations.services import allocate_order_stock, online_orderable_batches
from operations.access import organizations, require_role
from operations.serializers import StrictSerializer
from operations.views import validated
from payments.models import CashierShift, Invoice, InvoiceItem, PaymentTransaction, Receipt
from payments.serializers import CashierShiftSerializer, ReceiptSerializer
from payments.services import confirm_invoice_payment

from .models import Medicine, Order, OrderItem
from .views import provider_account_for

STAFF_ROLES = {"pharmacy", "pharmacist", "facility_manager", "cashier"}
METHODS = [
    PaymentTransaction.Method.CASH, PaymentTransaction.Method.MOBILE_MONEY,
    PaymentTransaction.Method.CARD, PaymentTransaction.Method.BANK,
]


class PaymentDetails(StrictSerializer):
    method = serializers.ChoiceField(choices=METHODS)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["method"] != PaymentTransaction.Method.CASH and not attrs["reference"]:
            raise serializers.ValidationError({"reference": "Enter the reference for the payment already received."})
        return attrs


class OfflinePaymentInput(PaymentDetails):
    amount = serializers.IntegerField(min_value=1)


def staff_pharmacy(user):
    require_role(user, STAFF_ROLES)
    account = provider_account_for(user, "pharmacy")
    pharmacy = organizations(user).filter(
        owner_id=getattr(account, "pk", None), organization_type="pharmacy", active=True, status="verified",
    ).filter(
        Q(parent_facility__isnull=True) | Q(parent_facility__active=True, parent_facility__status="verified"),
    ).order_by("pk").first()
    if pharmacy is None:
        raise PermissionDenied("An active verified pharmacy affiliation is required.")
    return pharmacy


class PharmacySaleReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        scope = {"patient": request.user} if request.user.role == "patient" else {"pharmacy_id": staff_pharmacy(request.user).owner_id}
        order = get_object_or_404(Order, pk=pk, invoice__isnull=False, **scope)
        receipt = get_object_or_404(Receipt, payment__invoice_id=order.invoice_id, payment__status="confirmed")
        audit(actor=request.user, action="pharmacy.receipt.viewed", resource=receipt, patient=order.patient,
              purpose="billing", request=request)
        return Response(ReceiptSerializer(receipt).data)

    @transaction.atomic
    def post(self, request, pk):
        pharmacy = staff_pharmacy(request.user)
        User.objects.select_for_update().get(pk=request.user.pk)
        order = get_object_or_404(Order.objects.select_for_update(), pk=pk, pharmacy_id=pharmacy.owner_id)
        data = validated(OfflinePaymentInput, request)
        if order.invoice_id:
            receipt = get_object_or_404(Receipt, payment__invoice_id=order.invoice_id, payment__status="confirmed")
            payment = receipt.payment
            if (payment.method, payment.amount, payment.reference) != (data["method"], data["amount"], data["reference"]):
                return Response({"detail": "This order already has a recorded payment."}, status=409)
            return Response(ReceiptSerializer(receipt).data)
        if order.status == Order.Status.CANCELLED:
            return Response({"detail": "Cancelled orders cannot receive payments."}, status=409)
        if data["amount"] != order.total:
            raise ValidationError({"amount": "Enter the full order total received."})
        items = list(order.items.all())
        if not items or any(item.qty <= 0 or item.price < 0 for item in items) or sum(item.qty * item.price for item in items) != order.total:
            return Response({"detail": "The order items do not match the sale total."}, status=409)

        receipt = issue_receipt(request, pharmacy, order, items, data)
        return Response(ReceiptSerializer(receipt).data, status=201)


def issue_receipt(request, pharmacy, order, items, data):
    invoice = Invoice.objects.create(
        patient=order.patient, organization=pharmacy, issued_by=request.user, amount=order.total,
        gateway=data["method"], currency="UGX",
    )
    for item in items:
        InvoiceItem.objects.create(
            invoice=invoice, description=item.name, quantity=item.qty, unit_price=item.price,
            service_type="pharmacy_sale", source_id=str(item.pk),
        )
    order.invoice = invoice
    order.save(update_fields=["invoice"])
    _, receipt, _ = confirm_invoice_payment(invoice=invoice, received_by=request.user, **data)
    audit(actor=request.user, action="pharmacy.payment.recorded", resource=receipt, patient=order.patient,
          purpose="billing", metadata={"order_id": order.pk, "amount": order.total}, request=request)
    return receipt


class CounterLine(StrictSerializer):
    medicine = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=1000000)


class CounterSaleInput(PaymentDetails):
    request_id = serializers.UUIDField()
    items = CounterLine(many=True, allow_empty=False, max_length=100)
    amount = serializers.IntegerField(min_value=1, max_value=2147483647)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        ids = [item["medicine"] for item in attrs["items"]]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError({"items": "List each medicine once."})
        return attrs


class PharmacyCounterSaleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacy = staff_pharmacy(request.user)
        products = Medicine.objects.filter(pharmacy_id=pharmacy.owner_id).order_by("name", "pk")
        search = request.query_params.get("search", "").strip()[:120]
        if search:
            products = products.filter(name__icontains=search)
        return Response([{
            "id": medicine.pk, "name": medicine.name, "price": medicine.price, "sale_type": medicine.sale_type,
            "stock": online_orderable_batches(medicine).filter(organization=pharmacy).aggregate(total=Sum("quantity"))["total"] or 0,
        } for medicine in products[:60]])

    @transaction.atomic
    def post(self, request):
        pharmacy = staff_pharmacy(request.user)
        User.objects.select_for_update().get(pk=request.user.pk)
        type(pharmacy).objects.select_for_update().get(pk=pharmacy.pk)
        values = validated(CounterSaleInput, request)
        lines = {row["medicine"]: row["quantity"] for row in values["items"]}
        existing = Order.objects.filter(counter_reference=values["request_id"]).first()
        if existing:
            if existing.pharmacy_id != pharmacy.owner_id:
                return Response({"detail": "The sale reference is already in use."}, status=409)
            receipt = get_object_or_404(Receipt, payment__invoice_id=existing.invoice_id, payment__status="confirmed")
            payment = receipt.payment
            if (dict(existing.items.values_list("medicine_id", "qty")) != lines or
                    (payment.amount, payment.method, payment.reference) != (values["amount"], values["method"], values["reference"])):
                return Response({"detail": "The sale reference is already in use for different items or payment details."}, status=409)
            return Response({"order_id": existing.pk, "receipt": ReceiptSerializer(receipt).data})

        products = list(Medicine.objects.select_for_update().filter(
            pharmacy_id=pharmacy.owner_id, pk__in=lines,
        ).order_by("pk"))
        if len(products) != len(lines):
            raise ValidationError({"items": "Select medicines from this pharmacy."})
        if any(product.sale_type != Medicine.SaleType.OTC for product in products):
            raise ValidationError({"items": "Only OTC medicines can be sold here. Use the prescription queue for prescription medicines."})
        total = sum(product.price * lines[product.pk] for product in products)
        if not 0 < total <= 2147483647 or values["amount"] != total:
            raise ValidationError({"amount": "The price changed or the amount is invalid. Check the current total before retrying."})
        order = Order.objects.create(
            pharmacy_id=pharmacy.owner_id, total=total, status=Order.Status.DELIVERED,
            counter_reference=values["request_id"], handed_over_at=timezone.now(),
            handed_over_by=request.user, handover_reference="Walk-in counter sale",
        )
        sale_items = []
        for product in products:
            quantity = lines[product.pk]
            allocate_order_stock(product, quantity, request.user, order.pk, organization=pharmacy)
            sale_items.append(OrderItem.objects.create(order=order, medicine=product, name=product.name, price=product.price, qty=quantity))
        payment = {key: values[key] for key in ("amount", "method", "reference")}
        receipt = issue_receipt(request, pharmacy, order, sale_items, payment)
        return Response({"order_id": order.pk, "receipt": ReceiptSerializer(receipt).data}, status=201)


class OpeningFloat(StrictSerializer):
    opening_float = serializers.IntegerField(min_value=0, max_value=2147483647)


class ClosingCash(StrictSerializer):
    closing_cash = serializers.IntegerField(min_value=0, max_value=2147483647)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


def shift_cash(shift):
    return PaymentTransaction.objects.filter(
        received_by=shift.cashier, invoice__organization=shift.organization,
        invoice__pharmacy_sale__isnull=False, status="confirmed", method="cash",
        confirmed_at__gte=shift.opened_at,
    ).aggregate(total=Sum("amount"))["total"] or 0


class PharmacyShiftView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pharmacy = staff_pharmacy(request.user)
        shifts = CashierShift.objects.filter(organization=pharmacy).select_related("cashier", "organization")
        if pharmacy.owner_id != request.user.pk:
            shifts = shifts.filter(cashier=request.user)
        rows = list(shifts[:25])
        for row in rows:
            if row.status == CashierShift.Status.OPEN:
                row.expected_cash = row.opening_float + shift_cash(row)
        return Response(CashierShiftSerializer(rows, many=True).data)

    @transaction.atomic
    def post(self, request):
        pharmacy = staff_pharmacy(request.user)
        User.objects.select_for_update().get(pk=request.user.pk)
        data = validated(OpeningFloat, request)
        if CashierShift.objects.filter(organization=pharmacy, cashier=request.user, status="open").exists():
            return Response({"detail": "You already have an open shift."}, status=409)
        shift = CashierShift.objects.create(organization=pharmacy, cashier=request.user, expected_cash=data["opening_float"], **data)
        return Response(CashierShiftSerializer(shift).data, status=201)


class PharmacyShiftCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        pharmacy = staff_pharmacy(request.user)
        User.objects.select_for_update().get(pk=request.user.pk)
        shift = get_object_or_404(CashierShift.objects.select_for_update(), pk=pk, organization=pharmacy, cashier=request.user)
        if shift.status != CashierShift.Status.OPEN:
            return Response({"detail": "This shift is already closed."}, status=409)
        data = validated(ClosingCash, request)
        shift.expected_cash = shift.opening_float + shift_cash(shift)
        shift.closing_cash = data["closing_cash"]
        shift.variance = shift.closing_cash - shift.expected_cash
        shift.notes = data["notes"]
        shift.status = CashierShift.Status.CLOSED
        shift.closed_at = timezone.now()
        shift.save()
        return Response(CashierShiftSerializer(shift).data)
