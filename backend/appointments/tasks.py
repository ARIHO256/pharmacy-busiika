from celery import shared_task
from django.core.management import call_command


@shared_task
def send_scheduled_appointment_reminders(hours=24):
    call_command("send_appointment_reminders", hours=hours)
    return {"hours": hours}
