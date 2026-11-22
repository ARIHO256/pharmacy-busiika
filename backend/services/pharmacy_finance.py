from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from governance.services import audit
from operations.services import restore_order_stock
from payments.models import Invoice, JournalEntry, PaymentTransaction, Posting
from payments.serializers import ReceiptSerializer
from payments.services import confirm_invoice_payment

from .models import Order, PharmacyCreditCollection, PharmacyRefund
from .pharmacy_permissions import require_verified_owner
from .pharmacy_sales import OfflinePaymentInput, staff_pharmacy


def finance_context(request):
    require_verified_owner(request.user)
    return staff_pharmacy(request.user)


class RefundInput(serializers.Serializer):
    order = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=1000)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    action = serializers.ChoiceField(choices=["refund", "void"], default="refund")

    def validate(self, attrs):
        if attrs["action"] == "refund" and not attrs["reference"]:
            raise ValidationError({"reference": "Record a payment reference for the refund."})
        return attrs


class PharmacyRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        finance_context(request)
        refunds = PharmacyRefund.objects.filter(order__pharmacy=request.user).order_by("-created_at")
        eligible = Order.objects.filter(pharmacy=request.user, invoice__status=Invoice.Status.PAID, refund__isnull=True)
        voidable = Order.objects.filter(pharmacy=request.user, handed_over_at__isnull=True,
                                        status__in=["pending", "confirmed", "ready"]).filter(
            Q(invoice__isnull=True)
            | Q(invoice__status=Invoice.Status.PENDING),
        )
        return Response({"voidable": list(voidable.order_by("-pk").values("id", "total", "status")[:100]), "records": list(refunds.values("id", "order_id", "amount", "reason", "reference", "created_at")[:100]),
                         "eligible": list(eligible.exclude(status=Order.Status.CANCELLED).order_by("-pk").values("id", "total", "status")[:100])})

    @transaction.atomic
    def post(self, request):
        finance_context(request)
        payload = RefundInput(data=request.data)
        payload.is_valid(raise_exception=True)
        fields = dict(payload.validated_data)
        order = get_object_or_404(Order.objects.select_for_update(), pk=fields.pop("order"), pharmacy=request.user)
        if fields.pop("action") == "void":
            if order.handed_over_at or order.status not in {"pending", "confirmed", "ready"}:
                raise ValidationError("Only orders awaiting handover may be voided.")
            if order.invoice_id:
                invoice = Invoice.objects.select_for_update().get(pk=order.invoice_id, organization__owner=request.user)
                if invoice.status != Invoice.Status.PENDING or invoice.paid_amount:
                    raise ValidationError("A paid or partially paid order cannot be voided here.")
                invoice.status = Invoice.Status.VOID
                invoice.save(update_fields=["status", "updated_at"])
            restore_order_stock(order, request.user)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
            audit(actor=request.user, action="pharmacy.sale.voided", resource=order, patient=order.patient,
                  metadata={"pharmacy_id": request.user.pk, "reason": fields["reason"]}, purpose="billing", request=request)
            return Response({"id": order.pk, "status": order.status})
        if not order.invoice_id or order.status == Order.Status.CANCELLED or hasattr(order, "refund"):
            raise ValidationError("Select a paid sale that has not already been refunded.")
        invoice = Invoice.objects.select_for_update().get(pk=order.invoice_id, organization__owner=request.user)
        if order.status == Order.Status.DISPATCHED and not order.handed_over_at:
            raise ValidationError("Record the delivery or arrange return of the dispatched goods before refunding.")
        if invoice.status != Invoice.Status.PAID:
            raise ValidationError("Only fully paid sales can be refunded here.")
        source = JournalEntry.objects.filter(reference=f"INVPAID-{invoice.number}").first()
        if not source:
            raise ValidationError("The original payment must have a posted ledger entry.")
        if not order.handed_over_at and order.status != Order.Status.DISPATCHED:
            restore_order_stock(order, request.user)
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status"])
        refund = PharmacyRefund.objects.create(order=order, amount=invoice.amount, approved_by=request.user, **fields)
        reversal = JournalEntry.objects.create(
            reference=f"PHREF-{refund.pk}", description=f"Refund for {invoice.number}",
            source_type="PharmacyRefund", source_id=str(refund.pk), currency=invoice.currency,
        )
        Posting.objects.bulk_create([
            Posting(entry=reversal, account=posting.account, amount=posting.amount, memo=invoice.number,
                    direction=Posting.Direction.CREDIT if posting.direction == Posting.Direction.DEBIT else Posting.Direction.DEBIT)
            for posting in source.postings.all()
        ])
        invoice.payments.filter(status=PaymentTransaction.Status.CONFIRMED).update(status=PaymentTransaction.Status.REFUNDED)
        invoice.status = Invoice.Status.REFUNDED
        invoice.save(update_fields=["status", "updated_at"])
        audit(actor=request.user, action="pharmacy.sale.refunded", resource=refund, patient=order.patient,
              metadata={"pharmacy_id": request.user.pk, "order": order.pk}, purpose="billing", request=request)
        return Response({"id": refund.pk, "amount": refund.amount, "reference": refund.reference}, status=201)


class CreditInput(serializers.Serializer):
    order = serializers.IntegerField(min_value=1)
    due_date = serializers.DateField()

    def validate_due_date(self, value):
        if value < timezone.localdate():
            raise ValidationError("Choose today or a future due date.")
        return value


def eligible_credit_orders(user):
    return Order.objects.filter(pharmacy=user, patient__isnull=False, invoice__isnull=True).exclude(
        status=Order.Status.CANCELLED,
    ).filter(total__gt=0)


class PharmacyCreditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        finance_context(request)
        credit = Invoice.objects.filter(
            organization__owner=request.user, pharmacy_sale__pharmacy=request.user, due_at__isnull=False,
        ).select_related("patient", "pharmacy_sale").prefetch_related("payments__receipt")
        patient = request.query_params.get("patient")
        if patient:
            credit = credit.filter(patient_id=serializers.IntegerField(min_value=1).run_validation(patient))
        return Response({
            "accounts": [{"id": row.pk, "order": row.pharmacy_sale.pk, "patient": row.patient.display_name,
                          "patient_id": row.patient_id, "due_at": row.due_at, "amount": row.amount,
                          "balance": 0 if row.status in {Invoice.Status.REFUNDED, Invoice.Status.VOID} else row.balance, "status": row.status, "payments": [
                              {"id": payment.pk, "amount": payment.amount, "status": payment.status,
                               "date": payment.confirmed_at, "number": payment.number}
                              for payment in row.payments.all()
                          ]} for row in credit.order_by("-pk")[:100]],
            "eligible": [{"id": row.pk, "patient": row.patient.display_name, "amount": row.total}
                         for row in eligible_credit_orders(request.user).select_related("patient").order_by("-pk")[:100]],
        })

    @transaction.atomic
    def post(self, request):
        from datetime import datetime, time
        from payments.models import InvoiceItem

        pharmacy = finance_context(request)
        data = CreditInput(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        order = get_object_or_404(eligible_credit_orders(request.user).select_for_update(), pk=fields["order"])
        invoice = Invoice.objects.create(
            organization=pharmacy, patient=order.patient, amount=order.total, currency="UGX",
            issued_by=request.user, status=Invoice.Status.PENDING,
            due_at=timezone.make_aware(datetime.combine(fields["due_date"], time.max)),
        )
        for item in order.items.all():
            InvoiceItem.objects.create(invoice=invoice, description=item.name, quantity=item.qty, unit_price=item.price,
                                       service_type="pharmacy_sale", source_id=str(item.pk))
        order.invoice = invoice
        order.save(update_fields=["invoice"])
        audit(actor=request.user, action="pharmacy.credit.issued", resource=invoice, patient=order.patient,
              metadata={"pharmacy_id": request.user.pk}, purpose="billing", request=request)
        return Response({"id": invoice.pk}, status=201)


class CreditPaymentInput(OfflinePaymentInput):
    request_id = serializers.UUIDField()


class PharmacyCreditPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        finance_context(request)
        invoice = get_object_or_404(Invoice.objects.select_for_update(of=("self",)), pk=pk, organization__owner=request.user,
                                    pharmacy_sale__pharmacy=request.user, due_at__isnull=False)
        data = CreditPaymentInput(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        request_id = values.pop("request_id")
        previous = PharmacyCreditCollection.objects.filter(request_id=request_id).select_related("payment__receipt").first()
        if previous:
            transaction_record = previous.payment
            if transaction_record.invoice_id != invoice.pk or any(getattr(transaction_record, key) != value for key, value in values.items()):
                raise ValidationError("This payment reference was already used for different payment details.")
            return Response(ReceiptSerializer(transaction_record.receipt).data)
        try:
            payment, receipt, _ = confirm_invoice_payment(invoice=invoice, received_by=request.user, **values)
        except ValueError as error:
            raise ValidationError(str(error))
        PharmacyCreditCollection.objects.create(request_id=request_id, payment=payment)
        audit(actor=request.user, action="pharmacy.credit.payment_recorded", resource=receipt, patient=invoice.patient,
              metadata={"pharmacy_id": request.user.pk}, purpose="billing", request=request)
        return Response(ReceiptSerializer(receipt).data, status=201)
