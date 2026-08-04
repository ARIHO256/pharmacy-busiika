from celery import shared_task
from django.core.management import call_command


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=8)
def publish_pending_outbox(self, limit=250):
    call_command("publish_outbox", limit=limit, mark_published=True)
    return {"processed_limit": limit}
