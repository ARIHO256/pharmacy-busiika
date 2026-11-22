from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import DoctorProfile, ProfileStatus, StaffProfile
from accounts.roles import portal_path_for_role
from communication.models import Notification
from communication.services import notify
from registry.models import PractitionerCredential


DEFAULT_WINDOWS = (90, 60, 30, 14, 7, 1, 0)


class Command(BaseCommand):
    help = "Notify professionals about expiring licences and expire overdue credentials."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            nargs="+",
            type=int,
            default=list(DEFAULT_WINDOWS),
            help="Reminder windows in days before expiry.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        windows = sorted({max(int(day), 0) for day in options["days"]}, reverse=True)
        sent = 0
        expired = 0

        overdue = PractitionerCredential.objects.select_related("practitioner").filter(
            status=PractitionerCredential.Status.VERIFIED,
            expires_on__lt=today,
        )
        for credential in overdue:
            self._mark_expired(credential)
            expired += 1
            sent += self._send_once(
                credential,
                today,
                "Your practising licence has expired",
                (
                    f"Credential {credential.identifier} expired on {credential.expires_on}. "
                    "Public availability and regulated actions are disabled until renewal is verified."
                ),
                "critical",
                "expired",
            )

        for days in windows:
            target = today + timedelta(days=days)
            credentials = PractitionerCredential.objects.select_related("practitioner").filter(
                status=PractitionerCredential.Status.VERIFIED,
                expires_on=target,
            )
            for credential in credentials:
                if days == 0:
                    self._mark_expired(credential)
                    expired += 1
                    title = "Your practising licence expires today"
                    priority = "critical"
                else:
                    title = f"Practising licence expires in {days} day{'s' if days != 1 else ''}"
                    priority = "high" if days <= 14 else "normal"
                body = (
                    f"Credential {credential.identifier} expires on {credential.expires_on}. "
                    "Upload the renewed licence early to avoid interruption to bookings and clinical work."
                )
                sent += self._send_once(
                    credential,
                    today,
                    title,
                    body,
                    priority,
                    f"{days}-days",
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Credential notification run complete: {sent} notification(s), "
                f"{expired} credential(s) expired."
            )
        )

    def _mark_expired(self, credential):
        if credential.status != PractitionerCredential.Status.EXPIRED:
            credential.status = PractitionerCredential.Status.EXPIRED
            credential.save(update_fields=["status"])
        user = credential.practitioner
        if user.is_verified:
            user.is_verified = False
            user.save(update_fields=["is_verified"])
        profile = None
        if user.role == "doctor":
            profile = DoctorProfile.objects.filter(user=user).first()
        else:
            profile = StaffProfile.objects.filter(user=user).first()
        if profile is not None and profile.status != ProfileStatus.EXPIRED:
            profile.status = ProfileStatus.EXPIRED
            profile.save(update_fields=["status"])

    def _send_once(self, credential, today, title, body, priority, window):
        marker = f"credential:{credential.pk}:{credential.expires_on}:{window}"
        exists = Notification.objects.filter(
            user=credential.practitioner,
            kind="credential_expiry",
            created_at__date=today,
            metadata__dedupe_key=marker,
        ).exists()
        if exists:
            return 0
        notify(
            credential.practitioner,
            title,
            body,
            kind="credential_expiry",
            priority=priority,
            action_url=portal_path_for_role(credential.practitioner.role),
            channels=["in_app", "email", "sms"],
            metadata={
                "credential_id": credential.pk,
                "expires_on": str(credential.expires_on),
                "reminder_window": window,
                "dedupe_key": marker,
            },
        )
        return 1
