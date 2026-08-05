from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    CommissionRule,
    Invoice,
    JournalEntry,
    LedgerAccount,
    PaymentTransaction,
    Payout,
    Posting,
    Receipt,
    WalletAccount,
    WalletTransaction,
)


def resolve_commission_rate(doctor=None, organization=None):
    """Most specific active CommissionRule wins; fall back to COMMISSION_RATE."""
    if doctor is not None:
        rule = CommissionRule.objects.filter(doctor=doctor, active=True).first()
        if rule:
            return rule.rate
    if organization is not None:
        rule = CommissionRule.objects.filter(organization=organization, active=True).first()
        if rule:
            return rule.rate
    return getattr(settings, "COMMISSION_RATE", 0.10)


def doctor_earnings(doctor):
    rate = resolve_commission_rate(doctor=doctor)
    gross = (
        Invoice.objects.filter(appointment__doctor=doctor, status="paid").aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )
    total = int(round(gross * (1 - rate)))
    paid_out = (
        Payout.objects.filter(doctor=doctor, status="paid").aggregate(total=Sum("amount"))["total"]
        or 0
    )
    reserved = (
        Payout.objects.filter(doctor=doctor, status__in=["pending", "approved"]).aggregate(total=Sum("amount"))["total"]
        or 0
    )
    return {"total": total, "pending": max(total - paid_out - reserved, 0), "paid_out": paid_out}


def _account(code, name, account_type, owner=None):
    account, _ = LedgerAccount.objects.get_or_create(
        code=code,
        defaults={"name": name, "account_type": account_type, "owner": owner},
    )
    return account


@transaction.atomic
def record_invoice_paid(invoice):
    """Create one balanced, immutable journal entry for a fully paid invoice."""
    reference = f"INVPAID-{invoice.number}"
    existing = JournalEntry.objects.filter(reference=reference).first()
    if existing:
        return existing
    if invoice.amount <= 0:
        return None
    doctor = invoice.appointment.doctor if invoice.appointment_id else None
    commission_rate = resolve_commission_rate(doctor=doctor, organization=invoice.organization)
    commission = int(round(invoice.amount * commission_rate)) if doctor else invoice.amount
    provider_amount = invoice.amount - commission if doctor else 0

    clearing = _account(
        f"asset:gateway:{invoice.gateway}",
        f"{invoice.gateway.replace('_', ' ').title()} clearing",
        LedgerAccount.Type.ASSET,
    )
    platform_revenue = _account(
        "revenue:platform-commission",
        "Platform commission revenue",
        LedgerAccount.Type.REVENUE,
    )
    provider_payable = None
    if doctor:
        provider_payable = _account(
            f"liability:provider:{doctor.id}",
            f"Payable to {doctor.email}",
            LedgerAccount.Type.LIABILITY,
            owner=doctor,
        )

    entry = JournalEntry.objects.create(
        reference=reference,
        description=f"Payment received for invoice {invoice.number}",
        source_type="Invoice",
        source_id=str(invoice.id),
        currency=invoice.currency,
    )
    Posting.objects.create(
        entry=entry,
        account=clearing,
        direction=Posting.Direction.DEBIT,
        amount=invoice.amount,
        memo=invoice.number,
    )
    if provider_payable and provider_amount:
        Posting.objects.create(
            entry=entry,
            account=provider_payable,
            direction=Posting.Direction.CREDIT,
            amount=provider_amount,
            memo="Provider share",
        )
    Posting.objects.create(
        entry=entry,
        account=platform_revenue,
        direction=Posting.Direction.CREDIT,
        amount=commission,
        memo="Platform commission",
    )
    if not entry.is_balanced:
        raise RuntimeError(f"Unbalanced journal entry {entry.reference}")
    return entry


@transaction.atomic
def confirm_invoice_payment(
    *, invoice, amount, method, received_by=None, reference="", notes=""
):
    """Record an immutable payment and issue a receipt.

    The invoice is row-locked so two cashiers cannot overpay it concurrently.
    """
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")
    if invoice.status in {Invoice.Status.VOID, Invoice.Status.REFUNDED}:
        raise ValueError("This invoice cannot receive payments.")
    balance = invoice.balance
    if amount > balance:
        raise ValueError(f"Payment exceeds the outstanding balance of {invoice.currency} {balance}.")
    payment = PaymentTransaction.objects.create(
        invoice=invoice,
        amount=amount,
        method=method,
        reference=reference,
        status=PaymentTransaction.Status.CONFIRMED,
        received_by=received_by,
        notes=notes,
        confirmed_at=timezone.now(),
    )
    receipt = Receipt.objects.create(payment=payment, issued_by=received_by)
    remaining = invoice.balance
    invoice.gateway = {
        PaymentTransaction.Method.CASH: Invoice.Gateway.CASH,
        PaymentTransaction.Method.MOBILE_MONEY: Invoice.Gateway.MOBILE_MONEY,
        PaymentTransaction.Method.CARD: Invoice.Gateway.CARD,
        PaymentTransaction.Method.BANK: Invoice.Gateway.BANK,
        PaymentTransaction.Method.INSURANCE: Invoice.Gateway.INSURANCE,
        PaymentTransaction.Method.WALLET: Invoice.Gateway.WALLET,
    }[method]
    invoice.gateway_ref = reference or payment.number
    if remaining == 0:
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
    else:
        invoice.status = Invoice.Status.PARTIALLY_PAID
    invoice.save(update_fields=["gateway", "gateway_ref", "status", "paid_at", "updated_at"])
    if invoice.status == Invoice.Status.PAID:
        try:
            from workforce.services import advance_active_visit

            advance_active_visit(
                invoice.patient,
                "completed",
                actor=received_by,
                reason=f"Invoice {invoice.number} paid in full",
            )
        except Exception:
            pass
        record_invoice_paid(invoice)
        _apply_paid_source(invoice)
    return payment, receipt, invoice


def _notify(user, title, body, action_url=""):
    if not user:
        return
    try:
        from communication.services import notify

        notify(user, title, body, kind="payment", action_url=action_url, priority="high")
    except Exception:
        pass


def _emit_event(name, obj, payload, patient=None):
    try:
        from interoperability.services import emit_event

        emit_event(name, obj, payload, patient=patient)
    except Exception:
        pass


def _apply_paid_source(invoice):
    """Advance the object an invoice was issued for once it is fully paid.

    Every transition is guarded on the current status so replays (duplicate
    webhooks, repeated cashier confirmations) never apply twice.
    """
    if invoice.appointment_id:
        appointment = invoice.appointment
        if appointment.status == appointment.Status.PENDING:
            try:
                appointment.transition_to(
                    appointment.Status.CONFIRMED,
                    actor=None,
                    reason="Payment verified",
                    metadata={"invoice": invoice.number},
                )
            except DjangoValidationError:
                pass
        _notify(
            appointment.doctor,
            "Payment received",
            f"Invoice {invoice.number} for appointment #{appointment.id} has been paid.",
            action_url="/doctor/appointments",
        )
        return

    source_type = invoice.source_type
    source_id = invoice.source_id
    if not source_type or not source_id:
        return

    if source_type == Invoice.SourceType.ORDER:
        from services.models import Order

        order = Order.objects.filter(pk=source_id).select_related("patient", "pharmacy").first()
        if order is None:
            return
        if order.status == Order.Status.PENDING:
            order.status = Order.Status.CONFIRMED
            order.save(update_fields=["status"])
        _notify(
            order.patient,
            "Order confirmed",
            f"Your pharmacy order #{order.id} has been paid and confirmed.",
            action_url="/patient/orders",
        )
        _notify(
            order.pharmacy,
            "Order paid",
            f"Order #{order.id} has been paid by the patient and is ready to fulfil.",
            action_url="/pharmacy/orders",
        )
        _emit_event(
            "order.confirmed",
            order,
            {"order_id": order.id, "invoice_number": invoice.number, "amount": invoice.amount},
            patient=order.patient,
        )
    elif source_type == Invoice.SourceType.LAB_ORDER:
        from services.models import LabOrder

        order = LabOrder.objects.filter(pk=source_id).select_related("patient", "lab", "test").first()
        if order is None:
            return
        if order.status == LabOrder.Status.AWAITING_PAYMENT:
            order.status = LabOrder.Status.READY_FOR_COLLECTION
            order.save(update_fields=["status", "updated_at"])
        _notify(
            order.patient,
            "Lab test payment received",
            f"{order.test.name} is paid. Please visit the laboratory for sample collection.",
            action_url="/patient/health-record",
        )
        _notify(
            order.lab,
            "Lab order paid",
            f"Lab order #{order.id} ({order.test.name}) has been paid and is ready for collection.",
            action_url="/lab",
        )
        _emit_event(
            "lab_order.ready_for_collection",
            order,
            {"lab_order_id": order.id, "invoice_number": invoice.number, "amount": invoice.amount},
            patient=order.patient,
        )
    elif source_type == Invoice.SourceType.HOSPITAL_BOOKING:
        from services.models import HospitalBooking

        booking = HospitalBooking.objects.filter(pk=source_id).select_related("patient", "hospital", "service").first()
        if booking is None:
            return
        if booking.status == HospitalBooking.Status.PENDING:
            booking.status = HospitalBooking.Status.CONFIRMED
            booking.save(update_fields=["status"])
        _notify(
            booking.patient,
            "Booking confirmed",
            f"Your hospital booking #{booking.id} for {booking.date} has been paid and confirmed.",
            action_url="/patient/appointments",
        )
        _notify(
            booking.hospital,
            "Booking paid",
            f"Booking #{booking.id} for {booking.date} has been paid by the patient.",
            action_url="/hospital",
        )
        _emit_event(
            "hospital_booking.confirmed",
            booking,
            {"booking_id": booking.id, "invoice_number": invoice.number, "amount": invoice.amount},
            patient=booking.patient,
        )
    elif source_type == Invoice.SourceType.SUBSCRIPTION:
        from operations.models import AccountSubscription

        subscription = (
            AccountSubscription.objects.filter(pk=source_id).select_related("plan", "user").first()
        )
        if subscription is None:
            return
        if subscription.status != AccountSubscription.Status.ACTIVE:
            cycle_days = {"monthly": 30, "quarterly": 90, "annual": 365}[subscription.plan.billing_cycle]
            subscription.status = AccountSubscription.Status.ACTIVE
            subscription.starts_at = timezone.now()
            subscription.ends_at = timezone.now() + timedelta(days=cycle_days)
            subscription.save(update_fields=["status", "starts_at", "ends_at"])
        _notify(
            subscription.user,
            "Subscription active",
            f"Your {subscription.plan.name} subscription is now active until {subscription.ends_at:%d %b %Y}.",
            action_url="/patient/billing",
        )
        _emit_event(
            "subscription.activated",
            subscription,
            {"subscription_id": subscription.id, "invoice_number": invoice.number, "amount": invoice.amount},
            patient=subscription.user,
        )
    elif source_type == Invoice.SourceType.WALLET_TOPUP:
        if WalletTransaction.objects.filter(
            invoice=invoice, kind=WalletTransaction.Kind.TOPUP
        ).exists():
            return
        credit_wallet(
            user=invoice.patient,
            amount=invoice.amount,
            kind=WalletTransaction.Kind.TOPUP,
            invoice=invoice,
            reference=invoice.number,
        )
        _notify(
            invoice.patient,
            "Wallet topped up",
            f"Your wallet has been credited with {invoice.currency} {invoice.amount:,}.",
            action_url="/patient/wallet",
        )
        _emit_event(
            "wallet.topped_up",
            invoice,
            {"invoice_number": invoice.number, "amount": invoice.amount, "currency": invoice.currency},
            patient=invoice.patient,
        )


def wallet_for(user):
    wallet, _ = WalletAccount.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def pay_invoice_from_wallet(*, invoice, user):
    """Pay an invoice's outstanding balance from the user's wallet balance."""
    amount = invoice.balance
    if amount <= 0:
        raise ValueError("This invoice has no outstanding balance.")
    payment, receipt, invoice = confirm_invoice_payment(
        invoice=invoice,
        amount=amount,
        method=PaymentTransaction.Method.WALLET,
        received_by=user,
    )
    debit_wallet(
        user=user,
        amount=amount,
        kind=WalletTransaction.Kind.PAYMENT,
        invoice=invoice,
        reference=payment.number,
    )
    return payment, receipt, invoice


@transaction.atomic
def credit_wallet(*, user, amount, kind, invoice=None, reference=""):
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Wallet credit amount must be greater than zero.")
    wallet = WalletAccount.objects.select_for_update().filter(user=user).first()
    if wallet is None:
        wallet = WalletAccount.objects.create(user=user)
        wallet = WalletAccount.objects.select_for_update().get(pk=wallet.pk)
    wallet.balance = int(wallet.balance) + amount
    wallet.save(update_fields=["balance", "updated_at"])
    return WalletTransaction.objects.create(
        wallet=wallet,
        direction=WalletTransaction.Direction.CREDIT,
        kind=kind,
        amount=amount,
        invoice=invoice,
        reference=reference,
    )


@transaction.atomic
def debit_wallet(*, user, amount, kind, invoice=None, reference=""):
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Wallet debit amount must be greater than zero.")
    wallet = WalletAccount.objects.select_for_update().filter(user=user).first()
    if wallet is None or int(wallet.balance) < amount:
        raise ValueError("Insufficient wallet balance.")
    wallet.balance = int(wallet.balance) - amount
    wallet.save(update_fields=["balance", "updated_at"])
    return WalletTransaction.objects.create(
        wallet=wallet,
        direction=WalletTransaction.Direction.DEBIT,
        kind=kind,
        amount=amount,
        invoice=invoice,
        reference=reference,
    )


@transaction.atomic
def process_payout(*, payout, action, admin, reference="", notes=""):
    """Move a payout through the admin approval workflow.

    ``approve`` reserves the funds (derived in doctor_earnings), ``pay`` posts a
    balanced journal entry settling the provider liability, and ``reject``
    releases the reservation.
    """
    payout = Payout.objects.select_for_update().get(pk=payout.pk)
    if action == "approve":
        if payout.status != Payout.Status.PENDING:
            raise ValueError("Only a pending payout can be approved.")
        payout.status = Payout.Status.APPROVED
    elif action == "pay":
        if payout.status != Payout.Status.APPROVED:
            raise ValueError("Only an approved payout can be marked as paid.")
        payout.status = Payout.Status.PAID
        if reference:
            payout.reference = reference
        provider_payable = _account(
            f"liability:provider:{payout.doctor_id}",
            f"Payable to {payout.doctor.email}",
            LedgerAccount.Type.LIABILITY,
            owner=payout.doctor,
        )
        settlement = _account(
            f"asset:gateway:{payout.method}",
            f"{payout.get_method_display()} clearing",
            LedgerAccount.Type.ASSET,
        )
        entry = JournalEntry.objects.create(
            reference=f"PAYOUT-{payout.pk}",
            description=f"Payout {payout.pk} disbursed to {payout.doctor.email}",
            source_type="Payout",
            source_id=str(payout.pk),
        )
        Posting.objects.create(
            entry=entry,
            account=provider_payable,
            direction=Posting.Direction.DEBIT,
            amount=payout.amount,
            memo="Provider payout",
        )
        Posting.objects.create(
            entry=entry,
            account=settlement,
            direction=Posting.Direction.CREDIT,
            amount=payout.amount,
            memo=payout.reference or f"Payout {payout.pk}",
        )
        if not entry.is_balanced:
            raise RuntimeError(f"Unbalanced journal entry {entry.reference}")
    elif action == "reject":
        if payout.status not in {Payout.Status.PENDING, Payout.Status.APPROVED}:
            raise ValueError("Only a pending or approved payout can be rejected.")
        payout.status = Payout.Status.REJECTED
    else:
        raise ValueError("action must be approve, pay or reject.")
    if notes:
        payout.notes = notes
    payout.processed_by = admin
    payout.processed_at = timezone.now()
    payout.save()
    return payout
