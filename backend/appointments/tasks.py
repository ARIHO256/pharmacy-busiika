import os
from datetime import datetime, timedelta

from celery import shared_task
from django.core.management import call_command
from django.utils import timezone


@shared_task
def send_scheduled_appointment_reminders(hours=24):
    call_command("send_appointment_reminders", hours=hours)
    return {"hours": hours}


@shared_task
def mark_no_show_appointments():
    """Mark stale pending appointments as missed.

    An appointment whose end datetime passed more than ``NO_SHOW_GRACE_HOURS``
    (default 24) ago while still ``pending`` is treated as a no-show.  Only
    ``pending`` appointments are touched — confirmed/completed/cancelled ones
    are never auto-missed.
    """
    from .models import Appointment, AppointmentStatusHistory

    grace_hours = int(os.getenv("NO_SHOW_GRACE_HOURS", "24"))
    cutoff = timezone.now() - timedelta(hours=grace_hours)
    current_tz = timezone.get_current_timezone()

    marked = []
    candidates = Appointment.objects.filter(
        status=Appointment.Status.PENDING
    ).select_related("patient")
    for appointment in candidates:
        end_at = timezone.make_aware(
            datetime.combine(appointment.date, appointment.end_time), current_tz
        )
        if end_at >= cutoff:
            continue
        # Appointment.transition_to() intentionally does not allow
        # pending -> missed (the status machine is owned elsewhere), so the
        # transition is applied directly here with the same history record.
        appointment.status = Appointment.Status.MISSED
        appointment.save(update_fields=["status", "updated_at"])
        AppointmentStatusHistory.objects.create(
            appointment=appointment,
            actor=None,
            from_status=Appointment.Status.PENDING,
            to_status=Appointment.Status.MISSED,
            reason=f"Automatically marked as no-show after {grace_hours}h grace period.",
            metadata={"task": "appointments.tasks.mark_no_show_appointments"},
        )
        try:
            from communication.services import notify

            notify(
                appointment.patient,
                "Appointment missed",
                f"Your appointment on {appointment.date} at "
                f"{appointment.start_time.strftime('%H:%M')} was marked as missed.",
                kind="appointment",
            )
        except Exception:
            pass
        marked.append(appointment.id)
    return {"marked": len(marked), "appointment_ids": marked}
