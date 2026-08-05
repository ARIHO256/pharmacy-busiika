import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("healthpilot")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Periodic jobs: dispatch queued notification deliveries (email/SMS/push) and
# appointment reminders whenever a beat scheduler is running.
app.conf.beat_schedule = {
    "dispatch-notifications-every-minute": {
        "task": "communication.tasks.dispatch_notification_deliveries",
        "schedule": 60.0,
    },
    "healthpilot-digest-weekly": {
        "task": "communication.tasks.send_weekly_health_digest",
        "schedule": 604800.0,  # 7 days
    },
}
