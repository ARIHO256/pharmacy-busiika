from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpResponse
import logging
import os
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole, request_role
from accounts.professionals import professional_profile
from accounts.roles import BILLING_ROLES, BOOKABLE_PROVIDER_ROLES, FACILITY_MANAGEMENT_ROLES
from workforce.access import organization_for_user
from enterprise.access import active_role, is_platform_super_admin

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
INVOICE_VIEW_ROLES = ["patient", *sorted(BOOKABLE_PROVIDER_ROLES), "admin", "cashier", "facility_manager", "hospital"]
logger = logging.getLogger(__name__)


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
        requested_gateway = str(request.data.get("gateway") or "").strip().lower()
        if not appointment_id:
            return Response({"detail": "appointment_id is required"}, status=400)
        if method not in PAYMENT_METHODS:
            return Response(
                {"detail": "method must be one of mobile_money, card, wallet"}, status=400
            )

        from appointments.models import Appointment

        appointment = Appointment.objects.filter(pk=appointment_id).select_related(
            "patient", "doctor__doctor_profile", "doctor__staff_profile"
        ).first()
        if appointment is not None and appointment.patient_id != request.user.id:
            from accounts.models import PatientRelationship
            from django.db.models import Q
            relation = PatientRelationship.objects.filter(
                caregiver=request.user,
                patient=appointment.patient,
                status=PatientRelationship.Status.ACTIVE,
                can_manage_billing=True,
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()
            if relation is None:
                appointment = None
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

        provider_profile = professional_profile(appointment.doctor)
        amount = (getattr(provider_profile, "fees", None) or getattr(provider_profile, "consultation_fee", 0) or 0)
        existing = (
            Invoice.objects.filter(
                patient=appointment.patient,
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
        gateway_by_method = {
            "mobile_money": {"mtn_momo", "airtel_money", "flutterwave", "mock"},
            "card": {"flutterwave", "paystack", "mock"},
            "wallet": {"mock"},
        }
        default_gateway = Invoice.Gateway.MOCK if settings.MOCK_PAYMENTS else os.getenv("PAYMENT_GATEWAY", Invoice.Gateway.FLUTTERWAVE)
        selected_gateway = requested_gateway or default_gateway
        if selected_gateway not in gateway_by_method[method]:
            return Response({"detail": f"Gateway {selected_gateway} is not available for {method}."}, status=400)
        invoice = existing or Invoice.objects.create(
            patient=appointment.patient,
            appointment=appointment,
            amount=amount,
            gateway=selected_gateway,
        )
        if existing and existing.status != Invoice.Status.PAID and existing.gateway != selected_gateway:
            existing.gateway = selected_gateway
            existing.gateway_ref = ""
            existing.save(update_fields=["gateway", "gateway_ref", "updated_at"])
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
        except Exception as exc:
            return Response(
                {"detail": f"{invoice.gateway} gateway could not be initialized: {exc}"}, status=503
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
                "checkout_url": result.get("checkout_url", ""),
                "instructions": result.get("instructions", ""),
                "gateway": invoice.gateway,
                "status": result.get("status", "initiated"),
                "mock": invoice.gateway == Invoice.Gateway.MOCK,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentStatusView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "cashier", "finance_manager", "facility_manager", "admin"]

    def get(self, request, invoice_number):
        invoice = Invoice.objects.filter(number=invoice_number).select_related("patient").first()
        if not invoice:
            return Response({"detail": "Invoice not found."}, status=404)
        if request_role(request) == "patient" and invoice.patient_id != request.user.id:
            return Response({"detail": "Not permitted."}, status=403)
        verification = None
        if invoice.status not in {Invoice.Status.PAID, Invoice.Status.VOID, Invoice.Status.REFUNDED} and invoice.gateway_ref and invoice.gateway not in {Invoice.Gateway.MOCK, Invoice.Gateway.CASH, Invoice.Gateway.BANK, Invoice.Gateway.INSURANCE}:
            try:
                gateway = get_gateway(invoice.gateway)
                verification = gateway.verify(reference=invoice.gateway_ref, transaction_id=invoice.gateway_ref)
                if verification.get("successful"):
                    confirm_invoice_payment(
                        invoice=invoice, amount=invoice.balance, method=PaymentTransaction.Method.MOBILE_MONEY if invoice.gateway in {Invoice.Gateway.MTN_MOMO, Invoice.Gateway.AIRTEL_MONEY} else PaymentTransaction.Method.CARD,
                        reference=str(verification.get("provider_id") or invoice.gateway_ref), notes=f"Verified by payment status check through {invoice.gateway}",
                    )
                    invoice.refresh_from_db()
            except Exception as exc:
                verification = {"successful": False, "pending": True, "detail": str(exc)}
        return Response({"invoice_number": invoice.number, "status": invoice.status, "gateway": invoice.gateway, "balance": invoice.balance, "verification": verification})


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
        role = active_role(user)
        if role == "patient":
            from accounts.models import PatientRelationship
            from django.db.models import Q
            dependent_ids = PatientRelationship.objects.filter(
                caregiver=user, status=PatientRelationship.Status.ACTIVE, can_manage_billing=True
            ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).values_list("patient_id", flat=True)
            invoices = invoices.filter(Q(patient=user) | Q(patient_id__in=dependent_ids))
        elif role in BOOKABLE_PROVIDER_ROLES:
            invoices = invoices.filter(appointment__doctor=user)
        elif not is_platform_super_admin(user):
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
        involved = _invoice_access_allowed(request.user, invoice)
        if not involved:
            return Response({"detail": "Not allowed"}, status=403)
        receipt = Receipt.objects.filter(payment__invoice=invoice).select_related(
            "payment__invoice__patient", "payment__invoice__organization", "issued_by"
        ).order_by("-created_at").first()
        _audit(request, "payment.receipt.viewed", invoice)
        if receipt:
            return Response(ReceiptSerializer(receipt).data)
        return Response(
            {
                "number": invoice.number,
                "invoice_number": invoice.number,
                "amount": invoice.amount,
                "currency": invoice.currency,
                "status": invoice.status,
                "patient_name": _display_name(invoice.patient),
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
        if not _invoice_access_allowed(request.user, invoice):
            return Response({"detail": "Not allowed."}, status=403)
        return Response(ReceiptSerializer(receipt).data)


class CashierInvoiceListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = BILLING_OVERSIGHT_ROLES

    def get(self, request):
        organization = organization_for_user(
            request.user, request.query_params.get("organization")
        )
        if request_role(request) == "admin" and request.query_params.get("organization"):
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
        if request_role(request) not in CASHIER_ROLES:
            return Response(
                {"detail": "Only a cashier or platform administrator can issue an invoice."},
                status=403,
            )
        organization = organization_for_user(request.user, request.data.get("organization"))
        if request_role(request) == "admin" and request.data.get("organization"):
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
        if request_role(request) != "admin" and organization_for_user(
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
    allowed_roles = CASHIER_ROLES

    def get(self, request):
        organization = organization_for_user(
            request.user, request.query_params.get("organization")
        )
        if not organization:
            return Response({"detail": "No organization is in scope."}, status=400)
        shifts = CashierShift.objects.filter(organization=organization).select_related(
            "cashier", "organization"
        )
        if request_role(request) == "cashier":
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
        if request_role(request) != "admin" and shift.cashier_id != request.user.id:
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
    allowed_roles = sorted(BOOKABLE_PROVIDER_ROLES)

    def get(self, request):
        earnings = doctor_earnings(request.user)
        payouts = Payout.objects.filter(doctor=request.user)
        return Response({**earnings, "payouts": PayoutSerializer(payouts, many=True).data})


class WithdrawView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(BOOKABLE_PROVIDER_ROLES)

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


class GatewayWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, gateway):
        from .webhooks import InvalidWebhook, process_webhook
        try:
            event, invoice, duplicate = process_webhook(
                gateway,
                request.body,
                {key.lower(): value for key, value in request.headers.items()},
            )
        except InvalidWebhook as exc:
            return Response({"detail": str(exc)}, status=401)
        if invoice:
            _notify_payment(invoice, "Payment received", f"Invoice {invoice.number} has been paid successfully.")
            _audit(request, "payment.webhook.confirmed", invoice, {"gateway": gateway, "event_id": event.event_id})
        return Response({"received": True, "duplicate": duplicate})


class InvoiceAdjustmentView(APIView):
    permission_classes = [IsRole]
    allowed_roles = list(BILLING_ROLES | FACILITY_MANAGEMENT_ROLES | {"admin", "hospital"})

    def get(self, request):
        from .models import InvoiceAdjustment
        from .serializers import InvoiceAdjustmentSerializer
        qs = InvoiceAdjustment.objects.select_related("invoice__organization", "requested_by", "approved_by")
        organization = organization_for_user(request.user, request.query_params.get("organization"))
        if request_role(request) != "admin":
            qs = qs.filter(invoice__organization=organization)
        return Response(InvoiceAdjustmentSerializer(qs, many=True).data)

    def post(self, request):
        from .models import InvoiceAdjustment
        from .serializers import InvoiceAdjustmentSerializer
        invoice = Invoice.objects.filter(pk=request.data.get("invoice")).select_related("organization").first()
        if not invoice:
            return Response({"invoice": ["Invoice not found."]}, status=400)
        if request_role(request) != "admin" and organization_for_user(request.user, invoice.organization_id) is None:
            return Response({"detail": "Invoice is outside your organization."}, status=403)
        serializer = InvoiceAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = serializer.save(requested_by=request.user)
        _audit(request, "invoice.adjustment.requested", invoice, {"adjustment": row.number, "amount": row.amount})
        return Response(InvoiceAdjustmentSerializer(row).data, status=201)


class InvoiceAdjustmentActionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["finance_manager", "facility_manager", "admin", "hospital"]

    @transaction.atomic
    def post(self, request, pk):
        from .models import InvoiceAdjustment
        from .serializers import InvoiceAdjustmentSerializer
        row = InvoiceAdjustment.objects.select_for_update().select_related("invoice", "invoice__organization").filter(pk=pk).first()
        if not row:
            return Response({"detail": "Adjustment not found."}, status=404)
        action = request.data.get("action")
        if action == "reject":
            row.status = InvoiceAdjustment.Status.REJECTED
        elif action in {"approve", "apply"}:
            row.status = InvoiceAdjustment.Status.APPROVED
            row.approved_by = request.user
            row.approved_at = timezone.now()
            if action == "apply":
                invoice = row.invoice
                if row.adjustment_type in {InvoiceAdjustment.Type.CREDIT, InvoiceAdjustment.Type.DISCOUNT, InvoiceAdjustment.Type.WRITE_OFF}:
                    invoice.discount_amount += row.amount
                else:
                    invoice.tax_amount += row.amount
                invoice.recalculate_amount()
                row.status = InvoiceAdjustment.Status.APPLIED
        else:
            return Response({"detail": "action must be approve, apply or reject."}, status=400)
        row.save()
        _audit(request, f"invoice.adjustment.{action}", row.invoice, {"adjustment": row.number})
        return Response(InvoiceAdjustmentSerializer(row).data)


class RefundRequestView(APIView):
    def get(self, request):
        from .models import RefundRequest
        from .serializers import RefundRequestSerializer
        qs = RefundRequest.objects.select_related("payment__invoice__organization", "requested_by", "approved_by")
        if request_role(request) == "patient":
            qs = qs.filter(payment__invoice__patient=request.user)
        elif request_role(request) != "admin":
            qs = qs.filter(payment__invoice__organization=organization_for_user(request.user))
        return Response(RefundRequestSerializer(qs, many=True).data)

    def post(self, request):
        from .models import RefundRequest
        from .serializers import RefundRequestSerializer
        payment = PaymentTransaction.objects.filter(pk=request.data.get("payment"), status=PaymentTransaction.Status.CONFIRMED).select_related("invoice__patient", "invoice__organization").first()
        if not payment:
            return Response({"payment": ["Confirmed payment not found."]}, status=400)
        allowed = payment.invoice.patient_id == request.user.id or request_role(request) == "admin" or organization_for_user(request.user, payment.invoice.organization_id)
        if not allowed:
            return Response({"detail": "Not permitted."}, status=403)
        amount = int(request.data.get("amount") or payment.amount)
        already = payment.refund_requests.filter(status__in=[RefundRequest.Status.REQUESTED, RefundRequest.Status.APPROVED, RefundRequest.Status.PROCESSING, RefundRequest.Status.COMPLETED]).aggregate(total=Sum("amount"))["total"] or 0
        if amount <= 0 or amount + already > payment.amount:
            return Response({"amount": ["Refund amount exceeds the refundable payment balance."]}, status=400)
        row = RefundRequest.objects.create(payment=payment, amount=amount, reason=request.data.get("reason", ""), requested_by=request.user)
        _audit(request, "refund.requested", payment.invoice, {"refund": row.number, "amount": amount})
        return Response(RefundRequestSerializer(row).data, status=201)


class RefundRequestActionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["finance_manager", "facility_manager", "admin", "hospital"]

    @transaction.atomic
    def post(self, request, pk):
        from .gateways import GatewayError, get_gateway
        from .models import RefundRequest
        from .serializers import RefundRequestSerializer
        row = RefundRequest.objects.select_for_update().select_related("payment__invoice").filter(pk=pk).first()
        if not row:
            return Response({"detail": "Refund request not found."}, status=404)
        action = request.data.get("action")
        if action == "reject":
            row.status = RefundRequest.Status.REJECTED
            row.approved_by = request.user
            row.approved_at = timezone.now()
        elif action == "approve":
            row.status = RefundRequest.Status.APPROVED
            row.approved_by = request.user
            row.approved_at = timezone.now()
        elif action == "process":
            row.status = RefundRequest.Status.PROCESSING
            row.approved_by = row.approved_by or request.user
            row.approved_at = row.approved_at or timezone.now()
            try:
                result = get_gateway(row.payment.invoice.gateway).refund(row.payment, row.amount, row.reason)
                row.gateway_reference = result.get("reference", "")
                if result.get("status") in {"processed", "completed", "success", "successful", "refunded"}:
                    row.status = RefundRequest.Status.COMPLETED
                    row.completed_at = timezone.now()
                    row.payment.status = PaymentTransaction.Status.REFUNDED
                    row.payment.save(update_fields=["status"])
                    invoice = row.payment.invoice
                    invoice.status = Invoice.Status.REFUNDED
                    invoice.save(update_fields=["status", "updated_at"])
            except (GatewayError, ValueError) as exc:
                row.status = RefundRequest.Status.FAILED
                row.error = str(exc)
        else:
            return Response({"detail": "action must be approve, process or reject."}, status=400)
        row.save()
        _audit(request, f"refund.{action}", row.payment.invoice, {"refund": row.number, "status": row.status})
        return Response(RefundRequestSerializer(row).data)


def _invoice_access_allowed(user, invoice):
    if not user or not user.is_authenticated:
        return False
    role = active_role(user)
    if is_platform_super_admin(user):
        return True
    if role == "patient":
        if invoice.patient_id == user.id:
            return True
        from accounts.models import PatientRelationship
        from django.db.models import Q
        return PatientRelationship.objects.filter(
            caregiver=user, patient_id=invoice.patient_id,
            status=PatientRelationship.Status.ACTIVE, can_manage_billing=True,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).exists()
    if role in BOOKABLE_PROVIDER_ROLES:
        return bool(invoice.appointment_id and invoice.appointment.doctor_id == user.id)
    if role in BILLING_OVERSIGHT_ROLES:
        return organization_for_user(user, invoice.organization_id) is not None
    return False


def _invoice_pdf(invoice, receipt=None):
    """Generate a server-side PDF suitable for email, archive and printing."""
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    def safe(value):
        return escape(str(value or ""))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=(receipt.number if receipt else invoice.number),
        author="MyDoctor Platform",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="RightSmall", parent=styles["BodyText"], alignment=TA_RIGHT, fontSize=8, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], fontSize=22, leading=26, textColor=colors.HexColor("#123b72"), spaceAfter=4))
    story = []
    org_name = invoice.organization.legal_name if invoice.organization else "MyDoctor Platform"
    doc_kind = "RECEIPT" if receipt else "INVOICE"
    doc_number = receipt.number if receipt else invoice.number
    story.append(Table([
        [Paragraph(f'<b>{safe(org_name)}</b><br/><font size="9">Connected healthcare services</font>', styles["BodyText"]), Paragraph(f"<b>{safe(doc_kind)}</b><br/>{safe(doc_number)}", styles["RightSmall"])],
    ], colWidths=[120 * mm, 42 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#dbeafe")), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.append(Spacer(1, 8 * mm))
    patient_name = _display_name(invoice.patient)
    issued = invoice.created_at.astimezone().strftime("%d %b %Y %H:%M") if invoice.created_at else ""
    due = invoice.due_at.astimezone().strftime("%d %b %Y") if invoice.due_at else "On receipt"
    details = [
        [Paragraph("<b>Bill to</b>", styles["BodyText"]), Paragraph("<b>Document details</b>", styles["BodyText"])],
        [Paragraph(f"{safe(patient_name)}<br/>{safe(invoice.patient.email)}<br/>{safe(invoice.patient.phone)}", styles["BodyText"]), Paragraph(f"Issued: {safe(issued)}<br/>Due: {safe(due)}<br/>Status: {safe(invoice.get_status_display())}", styles["BodyText"])],
    ]
    story.append(Table(details, colWidths=[88 * mm, 74 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#cbd5e1")), ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#e2e8f0")), ("PADDING", (0, 0), (-1, -1), 7)]))
    story.append(Spacer(1, 6 * mm))
    item_rows = [["Description", "Qty", "Unit price", "Discount", "Line total"]]
    for item in invoice.items.all():
        item_rows.append([
            Paragraph(safe(item.description), styles["BodyText"]),
            f"{item.quantity:g}",
            f"{invoice.currency} {item.unit_price:,}",
            f"{invoice.currency} {item.discount_amount:,}",
            f"{invoice.currency} {item.line_total:,}",
        ])
    if len(item_rows) == 1:
        item_rows.append(["General healthcare services", "1", f"{invoice.currency} {invoice.amount:,}", "-", f"{invoice.currency} {invoice.amount:,}"])
    items_table = Table(item_rows, colWidths=[70 * mm, 15 * mm, 28 * mm, 25 * mm, 29 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b72")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 5 * mm))
    subtotal = sum(item.line_total for item in invoice.items.all()) or invoice.amount + invoice.discount_amount - invoice.tax_amount
    totals = [
        ["Subtotal", f"{invoice.currency} {subtotal:,}"],
        ["Discount", f"{invoice.currency} {invoice.discount_amount:,}"],
        ["Tax", f"{invoice.currency} {invoice.tax_amount:,}"],
        ["Total", f"{invoice.currency} {invoice.amount:,}"],
        ["Paid", f"{invoice.currency} {invoice.paid_amount:,}"],
        ["Balance", f"{invoice.currency} {invoice.balance:,}"],
    ]
    totals_table = Table(totals, colWidths=[35 * mm, 42 * mm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
        ("FONTNAME", (0, 5), (-1, 5), "Helvetica-Bold"),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#eff6ff")),
        ("LINEABOVE", (0, 3), (-1, 3), .7, colors.HexColor("#93c5fd")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(totals_table)
    if receipt:
        payment = receipt.payment
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"<b>Payment confirmation</b><br/>Payment number: {safe(payment.number)}<br/>Method: {safe(payment.get_method_display())}<br/>Reference: {safe(payment.reference or '-')}<br/>Received: {safe(payment.confirmed_at or payment.created_at)}", styles["BodyText"]))
    if invoice.notes:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(f"<b>Notes</b><br/>{safe(invoice.notes)}", styles["BodyText"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Generated securely by MyDoctor. Keep this document for your records. Verification and audit references are retained by the issuing organization.", styles["RightSmall"]))
    doc.build(story)
    return buffer.getvalue()


class InvoicePDFView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INVOICE_VIEW_ROLES

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice.objects.select_related("patient", "organization", "appointment__doctor").prefetch_related("items", "payments"), pk=pk)
        if not _invoice_access_allowed(request.user, invoice):
            return Response({"detail": "Not allowed."}, status=403)
        try:
            payload = _invoice_pdf(invoice)
        except ImportError:
            return Response({"detail": "PDF generation dependency is unavailable."}, status=503)
        _audit(request, "invoice.pdf.generated", invoice)
        response = HttpResponse(payload, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{invoice.number}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class ReceiptPDFView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INVOICE_VIEW_ROLES

    def get(self, request, pk):
        receipt = get_object_or_404(Receipt.objects.select_related("payment__invoice__patient", "payment__invoice__organization", "payment__invoice__appointment__doctor").prefetch_related("payment__invoice__items", "payment__invoice__payments"), pk=pk)
        invoice = receipt.payment.invoice
        if not _invoice_access_allowed(request.user, invoice):
            return Response({"detail": "Not allowed."}, status=403)
        try:
            payload = _invoice_pdf(invoice, receipt=receipt)
        except ImportError:
            return Response({"detail": "PDF generation dependency is unavailable."}, status=503)
        _audit(request, "receipt.pdf.generated", invoice, {"receipt": receipt.number})
        response = HttpResponse(payload, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{receipt.number}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class SendInvoiceView(APIView):
    permission_classes = [IsRole]
    allowed_roles = INVOICE_VIEW_ROLES

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice.objects.select_related("patient", "organization", "appointment__doctor").prefetch_related("items", "payments"), pk=pk)
        if not _invoice_access_allowed(request.user, invoice):
            return Response({"detail": "Not allowed."}, status=403)
        recipient = invoice.patient.email
        if not recipient:
            return Response({"detail": "Patient does not have an email address."}, status=409)
        try:
            pdf = _invoice_pdf(invoice)
            message = EmailMessage(
                subject=f"Invoice {invoice.number} from {invoice.organization.legal_name if invoice.organization else 'MyDoctor'}",
                body=(
                    f"Hello {_display_name(invoice.patient)},\n\n"
                    f"Your invoice {invoice.number} for {invoice.currency} {invoice.amount:,} is attached. "
                    f"Current balance: {invoice.currency} {invoice.balance:,}.\n\n"
                    "Sign in to MyDoctor to view payments, receipts and care information."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient],
            )
            message.attach(f"{invoice.number}.pdf", pdf, "application/pdf")
            message.send(fail_silently=False)
        except Exception:
            logger.exception("Invoice %s could not be emailed", invoice.number)
            return Response({"detail": "Invoice email could not be sent. Please verify the mail provider configuration and try again."}, status=503)
        _notify_payment(invoice, "Invoice sent", f"Invoice {invoice.number} has been sent to {recipient}.")
        _audit(request, "invoice.emailed", invoice, {"recipient": recipient})
        _emit("invoice.emailed", invoice, {"invoice_number": invoice.number, "recipient": recipient}, request)
        return Response({"detail": "Invoice sent.", "recipient": recipient})
