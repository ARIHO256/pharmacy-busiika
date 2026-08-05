"""Send an occasional informational HealthPilot digest to users.

Rotates through a set of platform and wellness messages so users periodically
hear from HealthPilot. Users who disable email in their notification
preferences are skipped automatically (in-app delivery still applies).

Usage:
    python manage.py send_health_digest                 # patients, weekly rotation
    python manage.py send_health_digest --role doctor   # any role
    python manage.py send_health_digest --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User
from communication.services import notify

MESSAGES = [
    (
        "Your health record travels with you",
        "HealthPilot keeps your visits, results, prescriptions and invoices in one place. "
        "Open your Health Record any time to review or share them with your care team.",
        "/patient/health-record",
    ),
    (
        "Book your next review in a minute",
        "Appointments with verified clinicians are a few taps away — online or in person. "
        "Your care team is notified instantly when you book.",
        "/patient/appointments",
    ),
    (
        "Medicine delivered to your door",
        "Order from verified pharmacies in the Pharmacy store and track your order from "
        "confirmation to delivery.",
        "/patient/store",
    ),
    (
        "Your laboratory results, explained",
        "When a result is released, HealthPilot lets you and your referring clinician know "
        "right away — no more queuing for printouts.",
        "/patient/health-record",
    ),
    (
        "Keep your cover ready",
        "Check your insurance membership and coverage before your next visit so billing "
        "stays smooth at the facility.",
        "/patient/insurance",
    ),
]


class Command(BaseCommand):
    help = "Send the rotating HealthPilot digest to active users."

    def add_arguments(self, parser):
        parser.add_argument("--role", default="patient")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        week = timezone.localdate().isocalendar().week
        title, body, action_url = MESSAGES[week % len(MESSAGES)]
        recipients = User.objects.filter(role=options["role"], is_active=True, email__contains="@")
        if options["dry_run"]:
            self.stdout.write(f"Would send to {recipients.count()} {options['role']} users: {title}")
            return
        sent = 0
        for user in recipients.iterator():
            notify(
                user,
                f"HealthPilot — {title}",
                body,
                kind="general",
                action_url=action_url,
                channels=["in_app", "email"],
            )
            sent += 1
        self.stdout.write(f"HealthPilot digest sent to {sent} {options['role']} users: {title}")
