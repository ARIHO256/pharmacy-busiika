"""Scheduled follow-up recall reminders for clinical encounters."""

import datetime

from celery import shared_task
from django.utils import timezone

from communication.models import Notification
from communication.services import notify

from .models import ClinicalEncounter

# Patients are reminded this many days ahead of their follow-up date.
FOLLOW_UP_RECALL_DAYS = 3


@shared_task
def send_follow_up_recalls(days=FOLLOW_UP_RECALL_DAYS):
    """Notify patients whose encounter follow-up date is coming up.

    Encounters with a follow_up_date in [today, today + days] trigger one
    reminder suggesting the patient rebooks. Reruns are safe: each reminder
    carries a dedupe_key in its metadata and is skipped when a notification
    with the same key already exists (same pattern as the appointment
    reminder command).
    """
    today = timezone.localdate()
    until = today + datetime.timedelta(days=max(days, 0))
    encounters = ClinicalEncounter.objects.select_related("patient", "doctor").filter(
        follow_up_date__range=(today, until),
    )
    sent = 0
    for encounter in encounters:
        marker = f"follow_up:{encounter.pk}:{encounter.follow_up_date.isoformat()}"
        if Notification.objects.filter(
            user=encounter.patient,
            kind="follow_up_recall",
            metadata__dedupe_key=marker,
        ).exists():
            continue
        notify(
            encounter.patient,
            "Follow-up appointment reminder",
            (
                f"Your follow-up with {encounter.doctor.display_name} is due on "
                f"{encounter.follow_up_date:%d %b %Y}. Please book a new appointment."
            ),
            kind="follow_up_recall",
            action_url="/patient/appointments",
            channels=["in_app", "email"],
            metadata={
                "encounter_id": encounter.pk,
                "follow_up_date": encounter.follow_up_date.isoformat(),
                "dedupe_key": marker,
            },
        )
        sent += 1
    return {"sent": sent, "window_days": days}
