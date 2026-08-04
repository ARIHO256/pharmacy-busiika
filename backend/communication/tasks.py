from celery import shared_task
from django.core.management import call_command


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def dispatch_notification_deliveries(self, limit=200):
    call_command("dispatch_notifications", limit=limit, max_attempts=5)
    return {"processed_limit": limit}
