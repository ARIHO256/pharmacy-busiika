import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Department(models.Model):
    organization = models.ForeignKey(
        "registry.Organization", on_delete=models.CASCADE, related_name="departments"
    )
    location = models.ForeignKey(
        "registry.OrganizationLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="departments",
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, blank=True, default="")
    description = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_department_per_organization"
            )
        ]

    def clean(self):
        if self.location_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "Location belongs to another organization."})

    def __str__(self):
        return f"{self.organization} — {self.name}"


class StaffMembership(models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        ENDED = "ended", "Ended"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_memberships",
    )
    organization = models.ForeignKey(
        "registry.Organization", on_delete=models.CASCADE, related_name="staff_memberships"
    )
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_memberships",
    )
    role = models.CharField(max_length=24)
    job_title = models.CharField(max_length=160, blank=True, default="")
    employee_number = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    is_primary = models.BooleanField(default=False)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_staff_memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["organization", "user__first_name", "user__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization", "role"],
                name="unique_staff_role_per_organization",
            )
        ]
        indexes = [
            models.Index(fields=["organization", "role", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def clean(self):
        from accounts.roles import FACILITY_OPERATIONS_ROLES

        if self.role not in FACILITY_OPERATIONS_ROLES:
            raise ValidationError({"role": "Unsupported facility role."})
        if self.department_id and self.department.organization_id != self.organization_id:
            raise ValidationError({"department": "Department belongs to another organization."})
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "End date cannot be before start date."})

    def __str__(self):
        return f"{self.user} — {self.role} at {self.organization}"


class StaffInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    organization = models.ForeignKey(
        "registry.Organization", on_delete=models.CASCADE, related_name="staff_invitations"
    )
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_invitations",
    )
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, default="")
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    role = models.CharField(max_length=24)
    job_title = models.CharField(max_length=160, blank=True, default="")
    employee_number = models.CharField(max_length=80, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_staff_invitations",
    )
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_staff_invitations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["email", "status"])]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def clean(self):
        from accounts.roles import FACILITY_OPERATIONS_ROLES

        if self.role not in FACILITY_OPERATIONS_ROLES:
            raise ValidationError({"role": "Unsupported facility role."})
        if self.department_id and self.department.organization_id != self.organization_id:
            raise ValidationError({"department": "Department belongs to another organization."})

    def __str__(self):
        return f"{self.email} invited as {self.role}"


class PatientVisit(models.Model):
    class Type(models.TextChoices):
        APPOINTMENT = "appointment", "Appointment"
        WALK_IN = "walk_in", "Walk-in"
        EMERGENCY = "emergency", "Emergency"
        FOLLOW_UP = "follow_up", "Follow-up"

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        WAITING_TRIAGE = "waiting_triage", "Waiting for triage"
        TRIAGED = "triaged", "Triaged"
        WAITING_CLINICIAN = "waiting_clinician", "Waiting for clinician"
        IN_CONSULTATION = "in_consultation", "In consultation"
        LABORATORY = "laboratory", "At laboratory"
        PHARMACY = "pharmacy", "At pharmacy"
        BILLING = "billing", "At billing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        EMERGENCY = "emergency", "Emergency"

    organization = models.ForeignKey(
        "registry.Organization", on_delete=models.PROTECT, related_name="patient_visits"
    )
    location = models.ForeignKey(
        "registry.OrganizationLocation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_visits",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="facility_visits",
    )
    appointment = models.OneToOneField(
        "appointments.Appointment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="facility_visit",
    )
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="registered_patient_visits",
    )
    assigned_doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_doctor_visits",
    )
    assigned_nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_nurse_visits",
    )
    visit_number = models.CharField(max_length=40, unique=True, blank=True)
    queue_number = models.PositiveIntegerField(default=0)
    visit_type = models.CharField(max_length=20, choices=Type.choices, default=Type.WALK_IN)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.REGISTERED)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.ROUTINE)
    reason = models.TextField(blank=True, default="")
    checked_in_at = models.DateTimeField(auto_now_add=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-checked_in_at"]
        indexes = [
            models.Index(fields=["organization", "status", "checked_in_at"]),
            models.Index(fields=["patient", "checked_in_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.visit_number:
            self.visit_number = f"VIS-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Visit subject must be a patient."})
        if self.location_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "Location belongs to another organization."})

    def __str__(self):
        return self.visit_number


class TriageRecord(models.Model):
    class Level(models.TextChoices):
        RED = "red", "Immediate"
        ORANGE = "orange", "Very urgent"
        YELLOW = "yellow", "Urgent"
        GREEN = "green", "Standard"
        BLUE = "blue", "Non-urgent"

    visit = models.OneToOneField(PatientVisit, on_delete=models.CASCADE, related_name="triage")
    nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triage_records",
    )
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.GREEN)
    chief_complaint = models.TextField()
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulse_bpm = models.PositiveIntegerField(null=True, blank=True)
    respiratory_rate = models.PositiveIntegerField(null=True, blank=True)
    systolic_bp = models.PositiveIntegerField(null=True, blank=True)
    diastolic_bp = models.PositiveIntegerField(null=True, blank=True)
    oxygen_saturation = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    pain_score = models.PositiveSmallIntegerField(null=True, blank=True)
    allergies = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Triage {self.visit.visit_number}"


class NursingNote(models.Model):
    class Type(models.TextChoices):
        ASSESSMENT = "assessment", "Assessment"
        PROGRESS = "progress", "Progress note"
        HANDOVER = "handover", "Handover"
        DISCHARGE = "discharge", "Discharge note"
        PROCEDURE = "procedure", "Procedure note"

    visit = models.ForeignKey(PatientVisit, on_delete=models.CASCADE, related_name="nursing_notes")
    nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nursing_notes",
    )
    note_type = models.CharField(max_length=20, choices=Type.choices, default=Type.PROGRESS)
    note = models.TextField()
    handover = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.note_type} — {self.visit.visit_number}"


class MedicationAdministration(models.Model):
    class Status(models.TextChoices):
        GIVEN = "given", "Given"
        HELD = "held", "Held"
        REFUSED = "refused", "Refused"
        MISSED = "missed", "Missed"

    visit = models.ForeignKey(
        PatientVisit, on_delete=models.CASCADE, related_name="medication_administrations"
    )
    nurse = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="medication_administrations",
    )
    medication = models.CharField(max_length=220)
    dose = models.CharField(max_length=120)
    route = models.CharField(max_length=80, blank=True, default="")
    scheduled_for = models.DateTimeField(null=True, blank=True)
    administered_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GIVEN)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-administered_at"]

    def __str__(self):
        return f"{self.medication} — {self.visit.visit_number}"
