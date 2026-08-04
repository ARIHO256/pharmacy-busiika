from datetime import timedelta
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Consent(models.Model):
    """Executable patient consent used by access-control decisions.

    The model intentionally stores purpose and data categories separately so a
    patient can permit treatment access without implicitly permitting research,
    marketing, or insurance use.
    """

    class Type(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        TELEMEDICINE = "telemedicine", "Telemedicine"
        DATA_SHARING = "data_sharing", "Clinical data sharing"
        PHARMACY = "pharmacy", "Pharmacy fulfilment"
        LABORATORY = "laboratory", "Laboratory services"
        INSURANCE = "insurance", "Insurance processing"
        RESEARCH = "research", "Research"
        MARKETING = "marketing", "Marketing"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="health_consents",
    )
    granted_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_health_consents",
        help_text="Optional named recipient. Null means the stated recipient class.",
    )
    consent_type = models.CharField(max_length=30, choices=Type.choices)
    purpose = models.CharField(max_length=80, blank=True, default="treatment")
    data_categories = models.JSONField(default=list, blank=True)
    recipient_class = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    source = models.CharField(
        max_length=50,
        blank=True,
        default="patient_portal",
        help_text="patient_portal, appointment_booking, signed_form, imported",
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True, default="")
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-granted_at"]
        indexes = [
            models.Index(fields=["patient", "status", "consent_type"]),
            models.Index(fields=["granted_to", "status"]),
        ]

    def clean(self):
        if self.valid_until and self.valid_until <= self.valid_from:
            raise ValidationError({"valid_until": "Must be after valid_from."})
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Consent subject must be a patient."})

    @property
    def is_current(self):
        now = timezone.now()
        if self.status != self.Status.ACTIVE:
            return False
        if self.valid_from > now:
            return False
        if self.valid_until and self.valid_until <= now:
            return False
        return True

    def revoke(self, reason=""):
        if self.status == self.Status.REVOKED:
            return
        self.status = self.Status.REVOKED
        self.revoked_at = timezone.now()
        self.revocation_reason = reason or "Revoked by patient"
        self.save(update_fields=["status", "revoked_at", "revocation_reason"])

    def __str__(self):
        return f"{self.patient_id}: {self.consent_type} ({self.status})"


def default_break_glass_expiry():
    return timezone.now() + timedelta(minutes=30)


class BreakGlassAccess(models.Model):
    """Time-bound emergency access with mandatory reason and later review."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        REVIEWED = "reviewed", "Reviewed"
        REJECTED = "rejected", "Rejected"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="break_glass_requests",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="break_glass_accesses",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="break_glass_accesses",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_break_glass_expiry)
    ended_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_break_glass_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["requester", "patient", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    @property
    def is_current(self):
        return self.status == self.Status.ACTIVE and self.expires_at > timezone.now()

    def end(self):
        if self.status == self.Status.ACTIVE:
            self.status = self.Status.ENDED
            self.ended_at = timezone.now()
            self.save(update_fields=["status", "ended_at"])

    def __str__(self):
        return f"Emergency access {self.requester_id}->{self.patient_id}"


class AuditEvent(models.Model):
    """Append-only security and clinical access audit trail."""

    class Decision(models.TextChoices):
        ALLOW = "allow", "Allowed"
        DENY = "deny", "Denied"
        NOT_APPLICABLE = "n/a", "Not applicable"

    event_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="governance_audit_events",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_audit_events",
    )
    action = models.CharField(max_length=160)
    resource_type = models.CharField(max_length=100, blank=True, default="")
    resource_id = models.CharField(max_length=100, blank=True, default="")
    purpose = models.CharField(max_length=80, blank=True, default="")
    decision = models.CharField(
        max_length=10,
        choices=Decision.choices,
        default=Decision.NOT_APPLICABLE,
    )
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    correlation_id = models.CharField(max_length=100, blank=True, default="")
    emergency_access = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["action", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Audit events are append-only and cannot be edited.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit events are append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.action} ({self.created_at})"


def default_privileged_access_expiry():
    return timezone.now() + timedelta(minutes=20)


class PrivilegedAccessGrant(models.Model):
    """Controlled, audited administrator access to a named patient's records.

    Platform administration does not imply standing access to clinical data. A grant
    is patient-specific, purpose-bound, read-only by default, short-lived and must
    be approved by a separate clinical-safety/compliance principal unless the
    requester is a Django superuser operating under emergency recovery procedures.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"
        REVIEWED = "reviewed", "Reviewed"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privileged_access_requests",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="privileged_admin_accesses",
    )
    purpose = models.CharField(max_length=120)
    reason = models.TextField()
    scopes = models.JSONField(default=list, blank=True)
    read_only = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    mfa_verified_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_privileged_access_grants",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(default=default_privileged_access_expiry)
    revoked_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_privileged_access_grants",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["requester", "patient", "status"], name="gov_priv_actor_patient"),
            models.Index(fields=["expires_at", "status"], name="gov_priv_expiry_status"),
        ]

    def clean(self):
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Privileged access target must be a patient."})
        if self.requester_id and self.patient_id and self.requester_id == self.patient_id:
            raise ValidationError("A patient does not require an administrator elevation to access their own record.")
        if self.approved_by_id and self.approved_by_id == self.requester_id:
            raise ValidationError({"approved_by": "The requester cannot approve their own elevated access."})
        if self.expires_at <= timezone.now() and self.status in {self.Status.PENDING, self.Status.ACTIVE}:
            raise ValidationError({"expires_at": "Expiry must be in the future."})

    @property
    def is_current(self):
        return self.status == self.Status.ACTIVE and self.expires_at > timezone.now()

    def revoke(self, actor=None, notes=""):
        if self.status == self.Status.ACTIVE:
            self.status = self.Status.REVOKED
            self.revoked_at = timezone.now()
            self.reviewed_by = actor or self.reviewed_by
            self.review_notes = notes or self.review_notes
            self.save(update_fields=["status", "revoked_at", "reviewed_by", "review_notes"])

    def __str__(self):
        return f"Privileged access {self.requester_id}->{self.patient_id} ({self.status})"
