from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from communication.models import Notification
from communication.services import notify

from appointments.models import Appointment


class Command(BaseCommand):
    help = "Queue patient and doctor reminders for confirmed appointments in the next 24 hours."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Look-ahead window in hours (default: 24).",
        )

    def handle(self, *args, **options):
        now = timezone.localtime()
        until = now + timedelta(hours=max(options["hours"], 1))
        appointments = Appointment.objects.select_related("patient", "doctor").filter(
            status=Appointment.Status.CONFIRMED,
            date__range=(now.date(), until.date()),
        )
        sent = 0
        for appointment in appointments:
            starts_at = timezone.make_aware(
                datetime.combine(appointment.date, appointment.start_time),
                timezone.get_current_timezone(),
            )
            if not (now <= starts_at <= until):
                continue
            minutes = max(int((starts_at - now).total_seconds() // 60), 0)
            for user, action_url, counterpart in (
                (
                    appointment.patient,
                    "/patient/appointments",
                    appointment.doctor.display_name,
                ),
                (
                    appointment.doctor,
                    "/doctor/appointments",
                    appointment.patient.display_name,
                ),
            ):
                marker = f"appointment:{appointment.pk}:24h:{user.pk}"
                if Notification.objects.filter(
                    user=user,
                    kind="appointment_reminder",
                    metadata__dedupe_key=marker,
                ).exists():
                    continue
                notify(
                    user,
                    "Upcoming appointment reminder",
                    (
                        f"Your appointment with {counterpart} starts on "
                        f"{appointment.date:%d %b %Y} at {appointment.start_time:%H:%M} "
                        f"(about {minutes} minutes from now)."
                    ),
                    kind="appointment_reminder",
                    priority="high" if minutes <= 120 else "normal",
                    action_url=action_url,
                    channels=["in_app", "email", "sms", "push"],
                    metadata={
                        "appointment_id": appointment.pk,
                        "starts_at": starts_at.isoformat(),
                        "dedupe_key": marker,
                    },
                )
                sent += 1
        self.stdout.write(self.style.SUCCESS(f"Queued {sent} appointment reminder(s)."))
