from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Invoice,
    JournalEntry,
    LedgerAccount,
    PaymentTransaction,
    Payout,
    Posting,
    Receipt,
)


def doctor_earnings(doctor):
    rate = getattr(settings, "COMMISSION_RATE", 0.10)
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
        Payout.objects.filter(doctor=doctor, status="pending").aggregate(total=Sum("amount"))["total"]
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
    if hasattr(invoice, "pharmacy_sale"):
        owner = invoice.organization.owner
        clearing = _account(f"asset:pharmacy:{owner.pk}:{invoice.gateway}", "Pharmacy receipts", LedgerAccount.Type.ASSET, owner)
        revenue = _account(f"revenue:pharmacy:{owner.pk}", "Pharmacy sales", LedgerAccount.Type.REVENUE, owner)
        entry = JournalEntry.objects.create(
            reference=reference, description=f"Pharmacy sale {invoice.number}",
            source_type="Invoice", source_id=str(invoice.pk), currency=invoice.currency,
        )
        for account, direction in ((clearing, Posting.Direction.DEBIT), (revenue, Posting.Direction.CREDIT)):
            Posting.objects.create(entry=entry, account=account, direction=direction, amount=invoice.amount, memo=invoice.number)
        return entry
    doctor = invoice.appointment.doctor if invoice.appointment_id else None
    commission_rate = getattr(settings, "COMMISSION_RATE", 0.10)
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
        PaymentTransaction.Method.WALLET: Invoice.Gateway.MOCK,
    }[method]
    invoice.gateway_ref = reference or payment.number
    if remaining == 0:
        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
    else:
        invoice.status = Invoice.Status.PARTIALLY_PAID
    invoice.save(update_fields=["gateway", "gateway_ref", "status", "paid_at", "updated_at"])
    if invoice.status == Invoice.Status.PAID:
        record_invoice_paid(invoice)
    return payment, receipt, invoice
