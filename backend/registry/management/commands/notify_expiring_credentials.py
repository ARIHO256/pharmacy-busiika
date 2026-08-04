from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import DoctorProfile, ProfileStatus, ProviderProfile, StaffProfile
from accounts.roles import portal_path_for_role
from communication.models import Notification
from communication.services import notify
from registry.models import Organization, PractitionerCredential


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
        organizations_expired = 0

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

        # Facility and organization licence monitoring follows the same lifecycle as
        # practitioner credentials.  Expired facilities are removed from public use
        # immediately while preserving the record and renewal history.
        overdue_organizations = Organization.objects.select_related("owner").filter(
            status=Organization.Status.VERIFIED,
            license_expires_on__lt=today,
        )
        for organization in overdue_organizations:
            self._mark_organization_expired(organization)
            organizations_expired += 1
            sent += self._send_organization_once(
                organization, today,
                "Organization operating licence has expired",
                (
                    f"The operating licence for {organization.legal_name} expired on "
                    f"{organization.license_expires_on}. Public listing and new bookings "
                    "are suspended until a renewed licence is reviewed."
                ),
                "critical", "expired",
            )

        for days in windows:
            target = today + timedelta(days=days)
            organizations = Organization.objects.select_related("owner").filter(
                status=Organization.Status.VERIFIED,
                license_expires_on=target,
            )
            for organization in organizations:
                if days == 0:
                    self._mark_organization_expired(organization)
                    organizations_expired += 1
                    title = "Organization operating licence expires today"
                    priority = "critical"
                else:
                    title = f"Organization operating licence expires in {days} day{'s' if days != 1 else ''}"
                    priority = "high" if days <= 14 else "normal"
                sent += self._send_organization_once(
                    organization, today, title,
                    (
                        f"The operating licence for {organization.legal_name} expires on "
                        f"{organization.license_expires_on}. Submit the renewed licence early "
                        "to prevent an interruption to services."
                    ),
                    priority, f"{days}-days",
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Credential notification run complete: {sent} notification(s), "
                f"{expired} professional credential(s) expired, "
                f"{organizations_expired} organization licence(s) expired."
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
        if has_role_identity(user, "doctor"):
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
            action_url=portal_path_for_role(active_role(credential.practitioner)),
            channels=["in_app", "email", "sms"],
            metadata={
                "credential_id": credential.pk,
                "expires_on": str(credential.expires_on),
                "reminder_window": window,
                "dedupe_key": marker,
            },
        )
        return 1
    def _mark_organization_expired(self, organization):
        if organization.status != Organization.Status.SUSPENDED or organization.active:
            organization.status = Organization.Status.SUSPENDED
            organization.active = False
            organization.save(update_fields=["status", "active", "updated_at"])
        if organization.owner_id:
            owner = organization.owner
            if owner.is_verified:
                owner.is_verified = False
                owner.save(update_fields=["is_verified"])
            profile = ProviderProfile.objects.filter(user=owner).first()
            if profile is not None and profile.status != ProfileStatus.EXPIRED:
                profile.status = ProfileStatus.EXPIRED
                profile.verification_notes = (
                    f"Operating licence expired on {organization.license_expires_on}. "
                    "Renewal verification is required."
                )
                profile.save(update_fields=["status", "verification_notes"])
        try:
            from governance.services import audit
            audit(
                action="organization.licence.expired",
                resource=organization,
                purpose="credential_compliance",
                metadata={"expires_on": str(organization.license_expires_on)},
            )
        except Exception:
            pass

    def _send_organization_once(self, organization, today, title, body, priority, window):
        owner = organization.owner
        if owner is None:
            return 0
        marker = f"organization-credential:{organization.pk}:{organization.license_expires_on}:{window}"
        exists = Notification.objects.filter(
            user=owner,
            kind="credential_expiry",
            created_at__date=today,
            metadata__dedupe_key=marker,
        ).exists()
        if exists:
            return 0
        notify(
            owner, title, body,
            kind="credential_expiry",
            priority=priority,
            action_url=portal_path_for_role(owner.role),
            channels=["in_app", "email", "sms"],
            metadata={
                "organization_id": organization.pk,
                "expires_on": str(organization.license_expires_on),
                "reminder_window": window,
                "dedupe_key": marker,
            },
        )
        return 1

