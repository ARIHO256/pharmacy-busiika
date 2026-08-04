from celery import shared_task
from django.core.management import call_command


@shared_task
def notify_credential_expiry():
    call_command("notify_expiring_credentials")
    return {"status": "complete"}


@shared_task
def synchronize_provider_registry():
    call_command("sync_provider_registry")
    return {"status": "complete"}
