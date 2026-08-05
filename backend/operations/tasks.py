from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import AccountSubscription, InventoryBatch


@shared_task
def expire_subscriptions_and_scan_stock():
    now = timezone.now()
    expired_subscriptions = AccountSubscription.objects.filter(
        status__in=[AccountSubscription.Status.TRIAL, AccountSubscription.Status.ACTIVE],
        ends_at__lte=now,
    ).update(status=AccountSubscription.Status.EXPIRED, auto_renew=False)
    expired_batches = InventoryBatch.objects.filter(
        expiry_date__lt=timezone.localdate(), quantity_available__gt=0
    ).count()
    renewal_invoices = _create_renewal_invoices(now)
    return {
        "subscriptions_expired": expired_subscriptions,
        "expired_batches_with_stock": expired_batches,
        "renewal_invoices_created": renewal_invoices,
    }


def _create_renewal_invoices(now):
    """Invoice auto-renewing subscriptions that expire within the next 3 days."""
    from payments.models import Invoice, InvoiceItem

    due = AccountSubscription.objects.filter(
        status=AccountSubscription.Status.ACTIVE,
        auto_renew=True,
        user__isnull=False,
        ends_at__gt=now,
        ends_at__lte=now + timedelta(days=3),
    ).select_related("plan", "user")
    created = 0
    for subscription in due:
        if subscription.plan.price <= 0:
            continue
        already_invoiced = Invoice.objects.filter(
            source_type=Invoice.SourceType.SUBSCRIPTION,
            source_id=str(subscription.id),
            status__in=[Invoice.Status.PENDING, Invoice.Status.PARTIALLY_PAID],
        ).exists()
        if already_invoiced:
            continue
        invoice = Invoice.objects.create(
            patient=subscription.user,
            source_type=Invoice.SourceType.SUBSCRIPTION,
            source_id=str(subscription.id),
            notes=f"Renewal for {subscription.plan.name}",
        )
        InvoiceItem.objects.create(
            invoice=invoice,
            code=subscription.plan.code,
            description=f"{subscription.plan.name} subscription renewal ({subscription.plan.get_billing_cycle_display()})",
            quantity=1,
            unit_price=subscription.plan.price,
            service_type="subscription",
            source_id=str(subscription.id),
        )
        invoice.recalculate_amount()
        try:
            from communication.services import notify

            notify(
                subscription.user,
                "Subscription renewal due",
                f"Your {subscription.plan.name} subscription renews on {subscription.ends_at:%d %b %Y}. "
                f"Invoice {invoice.number} for {invoice.currency} {invoice.amount:,} is ready to pay.",
                kind="payment",
                action_url="/patient/invoices",
            )
        except Exception:
            pass
        created += 1
    return created
