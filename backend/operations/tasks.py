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
    return {
        "subscriptions_expired": expired_subscriptions,
        "expired_batches_with_stock": expired_batches,
    }
