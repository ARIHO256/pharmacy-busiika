from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole
from accounts.roles import BILLING_ROLES, FACILITY_MANAGEMENT_ROLES
from workforce.access import organization_for_user

from .gateways import get_gateway
from .models import (
    CashierShift,
    Invoice,
    InvoiceItem,
    PaymentTransaction,
    Payout,
    Receipt,
)
from .serializers import (
    CashierInvoiceCreateSerializer,
    CashierShiftSerializer,
    InvoiceSerializer,
    PayoutSerializer,
    ReceiptSerializer,
)
from .services import confirm_invoice_payment, doctor_earnings, record_invoice_paid

PAYMENT_METHODS = {"mobile_money", "card", "wallet"}
CASHIER_ROLES = ["cashier", "admin"]
BILLING_OVERSIGHT_ROLES = list(
    BILLING_ROLES | FACILITY_MANAGEMENT_ROLES | {"hospital", "admin"}
)
INVOICE_VIEW_ROLES = ["patient", "doctor", "admin", "cashier", "facility_manager", "hospital"]


def _display_name(user):
    if user is None:
        return None
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


def _audit(request, action, invoice, metadata=None):
    try:
        from governance.services import audit

        audit(
            actor=getattr(request, "user", None)
            if getattr(request, "user", None) and request.user.is_authenticated
            else None,
            patient=invoice.patient,
            action=action,
            resource=invoice,
            purpose="payment",
            metadata=metadata or {},
            request=request,
        )
    except Exception:
        return None


def _notify_payment(invoice, title, body, action_url="/patient/invoices"):
    try:
        from communication.services import notify

        notify(
            invoice.patient,
            title,
            body,
            kind="payment",
            action_url=action_url,
            priority="high",
        )
    except Exception:
        pass


def _emit(name, invoice, payload, request=None):
    try:
        from interoperability.services import emit_event

        emit_event(
            name,
            invoice,
            payload,
            actor=getattr(request, "user", None),
            patient=invoice.patient,
            request=request,
        )
    except Exception:
        pass


class InitiatePaymentView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient"]

    @transaction.atomic
    def post(self, request):
        appointment_id = request.data.get("appointment_id")
        method = request.data.get("method")
        phone = request.data.get("phone")
        if not appointment_id:
            return Response({"detail": "appointment_id is required"}, status=400)
        if method not in PAYMENT_METHODS:
            return Response(
                {"detail": "method must be one of mobile_money, card, wallet"}, status=400
            )

        from appointments.models import Appointment

        appointment = Appointment.objects.filter(
            pk=appointment_id, patient=request.user
        ).select_related("doctor__doctor_profile").first()
        if appointment is None:
            return Response({"detail": "Appointment not found"}, status=404)
        if appointment.status in {
            Appointment.Status.CANCELLED,
            Appointment.Status.COMPLETED,
            Appointment.Status.MISSED,
        }:
            return Response(
                {"detail": "This appointment cannot be paid in its current state."},
                status=409,
            )

        amount = getattr(getattr(appointment.doctor, "doctor_profile", None), "fees", 0) or 0
        existing = (
            Invoice.objects.filter(
                patient=request.user,
                appointment=appointment,
                status__in=[
                    Invoice.Status.PENDING,
                    Invoice.Status.PARTIALLY_PAID,
                    Invoice.Status.PAID,
                ],
            )
            .order_by("-created_at")
            .first()
        )
        if existing and existing.status == Invoice.Status.PAID:
            return Response(
                {"detail": "Appointment is already paid.", "invoice_number": existing.number},
                status=409,
            )
        if (existing.balance if existing else amount) <= 0:
            return Response({"detail": "There is no outstanding amount to collect."}, status=400)
        invoice = existing or Invoice.objects.create(
            patient=request.user,
            appointment=appointment,
            amount=amount,
            gateway=Invoice.Gateway.MOCK
            if settings.MOCK_PAYMENTS
            else Invoice.Gateway.FLUTTERWAVE,
        )
        if not invoice.items.exists():
            InvoiceItem.objects.create(
                invoice=invoice,
                code="CONSULTATION",
                description=f"Consultation with {_display_name(appointment.doctor)}",
                quantity=1,
                unit_price=amount,
                service_type="consultation",
                source_id=str(appointment.id),
            )
            invoice.recalculate_amount()
        gateway = get_gateway(invoice.gateway)
        try:
            result = gateway.initiate(invoice, phone=phone)
        except NotImplementedError:
            return Response(
                {"detail": f"{invoice.gateway} gateway is not configured."}, status=503
            )
        invoice.gateway_ref = result["ref"]
        invoice.save(update_fields=["gateway_ref", "updated_at"])
        _audit(
            request,
            "payment.initiated",
            invoice,
            {"method": method, "appointment_id": appointment.id},
        )
        _emit(
            "payment.initiated",
            invoice,
            {
                "invoice_number": invoice.number,
                "appointment_id": appointment.id,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "gateway": invoice.gateway,
                "method": method,
            },
            request,
        )
        return Response(
            {
                "invoice_number": invoice.number,
                "amount": invoice.amount,
                "ref": result["ref"],
                "checkout_url": result["checkout_url"],
                "mock": invoice.gateway == Invoice.Gateway.MOCK,
            },
            status=status.HTTP_201_CREATED,
        )


class MockWebhookView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request, invoice_number):
        if not settings.MOCK_PAYMENTS:
            return Response({"detail": "Mock payments are disabled."}, status=404)
        invoice = get_object_or_404(
            Invoice.objects.select_for_update(), number=invoice_number
        )
        if invoice.status != Invoice.Status.PAID:
            reference = invoice.gateway_ref or f"MOCK-{invoice.number}"
            try:
                payment, receipt, invoice = confirm_invoice_payment(
                    invoice=invoice,
                    amount=invoice.balance,
                    method=PaymentTransaction.Method.WALLET,
                    reference=reference,
                )
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=409)

            appointment = invoice.appointment
            if appointment is not None and appointment.status == appointment.Status.PENDING:
                try:
                    appointment.transition_to(
                        appointment.Status.CONFIRMED,
                        actor=None,
                        reason="Payment verified",
                        metadata={"invoice": invoice.number},
                    )
                except DjangoValidationError:
                    pass

            _notify_payment(
                invoice,
                "Payment received",
                f"Invoice {invoice.number} for {invoice.currency} {invoice.amount:,} has been paid. Receipt {receipt.number} is ready.",
            )
            if appointment is not None:
                try:
                    from communication.services import notify

                    notify(
                        appointment.doctor,
                        "Payment received",
                        f"Invoice {invoice.number} for appointment #{appointment.id} has been paid.",
                        kind="payment",
                        action_url="/doctor/appointments",
                    )
                except Exception:
                    pass
            _audit(request, "payment.confirmed", invoice, {"gateway": "mock"})
            _emit(
                "payment.confirmed",
                invoice,
                {
                    "invoice_number": invoice.number,
                    "payment_number": payment.number,
                    "receipt_number": receipt.number,
                    "appointment_id": invoice.appointment_id,
                    "amount": invoice.amount,
                    "currency": invoice.currency,
                    "gateway": invoice.gateway,
                },
                request,
            )
        return Response({"status": "paid"})


class InvoiceListView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INVOICE_VIEW_ROLES

    def get(self, request):
        user = request.user
        invoices = Invoice.objects.select_related(
            "patient", "organization", "appointment__doctor", "issued_by"
        ).prefetch_related("items", "payments", "payments__receipt")
        if user.role == "patient":
            invoices = invoices.filter(patient=user)
        elif user.role == "doctor":
            invoices = invoices.filter(appointment__doctor=user)
        elif user.role != "admin":
            organization = organization_for_user(user, request.query_params.get("organization"))
            if organization is None:
                return Response([])
            invoices = invoices.filter(organization=organization)
        status_value = request.query_params.get("status")
        if status_value:
            invoices = invoices.filter(status=status_value)
        return Response(InvoiceSerializer(invoices, many=True, context={"request": request}).data)


class ReceiptView(APIView):
    """Legacy invoice receipt endpoint; returns the latest issued receipt."""

    permission_classes = [IsRole]
    allowed_roles = INVOICE_VIEW_ROLES

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("patient", "organization", "appointment__doctor"),
            pk=pk,
        )
        involved = request.user == invoice.patient
        if invoice.appointment is not None and request.user == invoice.appointment.doctor:
            involved = True
        if request.user.role == "admin":
            involved = True
        if request.user.role in {"cashier", "facility_manager", "hospital"}:
            organization = organization_for_user(request.user, invoice.organization_id)
            involved = organization is not None
        if not involved:
            return Response({"detail": "Not allowed"}, status=403)
        receipt = Receipt.objects.filter(payment__invoice=invoice).select_related(
            "payment__invoice__patient", "payment__invoice__organization", "issued_by"
        ).order_by("-created_at").first()
        _audit(request, "payment.receipt.viewed", invoice)
        if receipt:
            return Response({**ReceiptSerializer(receipt).data, "patient": _display_name(invoice.patient)})
        return Response(
            {
                "number": invoice.number,
                "invoice_number": invoice.number,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "status": invoice.status,
                "patient_name": _display_name(invoice.patient),
                "patient": _display_name(invoice.patient),
                "doctor": _display_name(invoice.appointment.doctor)
                if invoice.appointment
                else None,
                "date": invoice.appointment.date if invoice.appointment else None,
                "gateway": invoice.gateway,
                "gateway_ref": invoice.gateway_ref,
                "paid_at": invoice.paid_at,
                "items": [],
                "balance": invoice.balance,
            }
        )


class ReceiptDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INVOICE_VIEW_ROLES

    def get(self, request, pk):
        receipt = get_object_or_404(
            Receipt.objects.select_related(
                "payment__invoice__patient", "payment__invoice__organization", "issued_by"
            ).prefetch_related("payment__invoice__items"),
            pk=pk,
        )
        invoice = receipt.payment.invoice
        if request.user.role == "patient" and invoice.patient_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=403)
        if request.user.role == "doctor" and (
            invoice.appointment_id is None or invoice.appointment.doctor_id != request.user.id
        ):
            return Response({"detail": "Not allowed."}, status=403)
        if request.user.role in {"cashier", "facility_manager", "hospital"} and organization_for_user(
            request.user, invoice.organization_id
        ) is None:
            return Response({"detail": "Not allowed."}, status=403)
        return Response(ReceiptSerializer(receipt).data)


class CashierInvoiceListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = BILLING_OVERSIGHT_ROLES

    def get(self, request):
        organization = organization_for_user(
            request.user, request.query_params.get("organization")
        )
        if request.user.role == "admin" and request.query_params.get("organization"):
            from registry.models import Organization

            organization = Organization.objects.filter(
                pk=request.query_params["organization"]
            ).first()
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        invoices = (
            Invoice.objects.filter(organization=organization)
            .select_related("patient", "appointment__doctor", "organization", "issued_by")
            .prefetch_related("items", "payments", "payments__receipt")
        )
        return Response(InvoiceSerializer(invoices, many=True).data)

    @transaction.atomic
    def post(self, request):
        if request.user.role not in CASHIER_ROLES:
            return Response(
                {"detail": "Only a cashier or platform administrator can issue an invoice."},
                status=403,
            )
        organization = organization_for_user(request.user, request.data.get("organization"))
        if request.user.role == "admin" and request.data.get("organization"):
            from registry.models import Organization

            organization = Organization.objects.filter(pk=request.data["organization"]).first()
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        serializer = CashierInvoiceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        items = data.pop("items")
        invoice = Invoice.objects.create(
            patient=data["patient"],
            organization=organization,
            appointment=data.get("appointment"),
            issued_by=request.user,
            discount_amount=data.get("discount_amount", 0),
            tax_amount=data.get("tax_amount", 0),
            currency=data.get("currency", "UGX").upper(),
            notes=data.get("notes", ""),
            due_at=data.get("due_at"),
            status=Invoice.Status.PENDING,
            gateway=Invoice.Gateway.CASH,
        )
        for item in items:
            InvoiceItem.objects.create(invoice=invoice, **item)
        invoice.recalculate_amount()
        _audit(request, "invoice.issued", invoice, {"organization_id": organization.id})
        _notify_payment(
            invoice,
            "New invoice",
            f"Invoice {invoice.number} for {invoice.currency} {invoice.amount:,} was issued by {organization.legal_name}.",
        )
        _emit(
            "invoice.issued",
            invoice,
            {
                "invoice_number": invoice.number,
                "patient_id": invoice.patient_id,
                "organization_id": organization.id,
                "amount": invoice.amount,
                "currency": invoice.currency,
            },
            request,
        )
        return Response(InvoiceSerializer(invoice).data, status=201)


class CashierRecordPaymentView(APIView):
    permission_classes = [IsRole]
    allowed_roles = CASHIER_ROLES

    @transaction.atomic
    def post(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("organization", "patient"), pk=pk
        )
        if request.user.role != "admin" and organization_for_user(
            request.user, invoice.organization_id
        ) is None:
            return Response({"detail": "This invoice is outside your organization."}, status=403)
        method = request.data.get("method")
        if method not in PaymentTransaction.Method.values:
            return Response({"detail": "Invalid payment method."}, status=400)
        try:
            amount = int(request.data.get("amount"))
        except (TypeError, ValueError):
            return Response({"detail": "amount must be an integer."}, status=400)
        try:
            payment, receipt, invoice = confirm_invoice_payment(
                invoice=invoice,
                amount=amount,
                method=method,
                received_by=request.user,
                reference=str(request.data.get("reference", "")).strip(),
                notes=str(request.data.get("notes", "")).strip(),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=409)
        _audit(
            request,
            "payment.recorded",
            invoice,
            {"payment_number": payment.number, "receipt_number": receipt.number},
        )
        _notify_payment(
            invoice,
            "Payment received",
            f"We received {invoice.currency} {payment.amount:,} for invoice {invoice.number}. Receipt {receipt.number} is ready.",
        )
        _emit(
            "payment.recorded",
            invoice,
            {
                "invoice_number": invoice.number,
                "payment_number": payment.number,
                "receipt_number": receipt.number,
                "amount": payment.amount,
                "balance": invoice.balance,
                "method": payment.method,
            },
            request,
        )
        return Response(
            {"invoice": InvoiceSerializer(invoice).data, "receipt": ReceiptSerializer(receipt).data},
            status=201,
        )


class CashierShiftListCreateView(APIView):
    permission_classes = [IsRole]

    @property
    def allowed_roles(self):
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            return set(CASHIER_ROLES) | FACILITY_MANAGEMENT_ROLES
        return CASHIER_ROLES

    def get(self, request):
        organization = organization_for_user(
            request.user, request.query_params.get("organization")
        )
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        shifts = CashierShift.objects.filter(organization=organization).select_related(
            "cashier", "organization"
        )
        if request.user.role == "cashier":
            shifts = shifts.filter(cashier=request.user)
        return Response(CashierShiftSerializer(shifts, many=True).data)

    def post(self, request):
        organization = organization_for_user(request.user, request.data.get("organization"))
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        if CashierShift.objects.filter(
            cashier=request.user, organization=organization, status=CashierShift.Status.OPEN
        ).exists():
            return Response({"detail": "You already have an open cashier shift."}, status=409)
        try:
            opening_float = int(request.data.get("opening_float", 0))
        except (TypeError, ValueError):
            return Response({"detail": "opening_float must be an integer."}, status=400)
        shift = CashierShift.objects.create(
            cashier=request.user,
            organization=organization,
            opening_float=max(opening_float, 0),
            expected_cash=max(opening_float, 0),
            notes=str(request.data.get("notes", "")),
        )
        return Response(CashierShiftSerializer(shift).data, status=201)


class CashierShiftCloseView(APIView):
    permission_classes = [IsRole]
    allowed_roles = CASHIER_ROLES

    @transaction.atomic
    def post(self, request, pk):
        shift = get_object_or_404(
            CashierShift.objects.select_for_update().select_related("organization"), pk=pk
        )
        if request.user.role != "admin" and shift.cashier_id != request.user.id:
            return Response({"detail": "Only the cashier who opened the shift may close it."}, status=403)
        if shift.status != CashierShift.Status.OPEN:
            return Response({"detail": "Shift is already closed."}, status=409)
        cash_received = (
            PaymentTransaction.objects.filter(
                received_by=shift.cashier,
                invoice__organization=shift.organization,
                method=PaymentTransaction.Method.CASH,
                status=PaymentTransaction.Status.CONFIRMED,
                confirmed_at__gte=shift.opened_at,
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        try:
            closing_cash = int(request.data.get("closing_cash"))
        except (TypeError, ValueError):
            return Response({"detail": "closing_cash must be an integer."}, status=400)
        shift.expected_cash = shift.opening_float + cash_received
        shift.closing_cash = closing_cash
        shift.variance = closing_cash - shift.expected_cash
        shift.status = CashierShift.Status.CLOSED
        shift.closed_at = timezone.now()
        shift.notes = str(request.data.get("notes", shift.notes))
        shift.save()
        return Response(CashierShiftSerializer(shift).data)


class BillingSummaryView(APIView):
    permission_classes = [IsRole]
    allowed_roles = BILLING_OVERSIGHT_ROLES

    def get(self, request):
        organization = organization_for_user(
            request.user, request.query_params.get("organization")
        )
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        invoices = Invoice.objects.filter(organization=organization)
        payments = PaymentTransaction.objects.filter(
            invoice__organization=organization,
            status=PaymentTransaction.Status.CONFIRMED,
        )
        today = timezone.localdate()
        today_payments = payments.filter(confirmed_at__date=today)
        return Response(
            {
                "pending_invoices": invoices.filter(
                    status__in=[Invoice.Status.PENDING, Invoice.Status.PARTIALLY_PAID]
                ).count(),
                "outstanding_amount": sum(
                    invoice.balance
                    for invoice in invoices.filter(
                        status__in=[Invoice.Status.PENDING, Invoice.Status.PARTIALLY_PAID]
                    ).prefetch_related("payments")
                ),
                "collected_today": today_payments.aggregate(total=Sum("amount"))["total"] or 0,
                "cash_today": today_payments.filter(
                    method=PaymentTransaction.Method.CASH
                ).aggregate(total=Sum("amount"))["total"]
                or 0,
                "receipts_today": Receipt.objects.filter(
                    payment__invoice__organization=organization, created_at__date=today
                ).count(),
            }
        )


class EarningsView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["doctor"]

    def get(self, request):
        earnings = doctor_earnings(request.user)
        payouts = Payout.objects.filter(doctor=request.user)
        return Response({**earnings, "payouts": PayoutSerializer(payouts, many=True).data})


class WithdrawView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["doctor"]

    def post(self, request):
        try:
            amount = int(request.data.get("amount"))
        except (TypeError, ValueError):
            return Response({"detail": "amount must be an integer"}, status=400)
        if amount <= 0:
            return Response({"detail": "amount must be positive"}, status=400)
        earnings = doctor_earnings(request.user)
        if amount > earnings["pending"]:
            return Response({"detail": "Amount exceeds pending earnings"}, status=400)
        payout = Payout.objects.create(doctor=request.user, amount=amount, status="pending")
        try:
            from governance.services import audit

            audit(
                actor=request.user,
                action="payout.requested",
                resource=payout,
                purpose="payment",
                metadata={"amount": amount},
                request=request,
            )
        except Exception:
            pass
        return Response(PayoutSerializer(payout).data, status=status.HTTP_201_CREATED)
