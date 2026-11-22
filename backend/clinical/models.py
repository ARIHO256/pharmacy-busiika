from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

AUTH_USER = settings.AUTH_USER_MODEL


class ClinicalEncounter(models.Model):
    """Versioned clinical note attached to a booked appointment."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINAL = "final", "Final"
        AMENDED = "amended", "Amended"
        ENTERED_IN_ERROR = "entered_in_error", "Entered in error"

    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="clinical_encounter",
    )
    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.PROTECT, related_name="clinical_encounters"
    )
    doctor = models.ForeignKey(
        AUTH_USER, on_delete=models.PROTECT, related_name="authored_encounters"
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT
    )
    chief_complaint = models.TextField(blank=True, default="")
    history_of_present_illness = models.TextField(blank=True, default="")
    examination = models.TextField(blank=True, default="")
    assessment = models.TextField(blank=True, default="")
    treatment_plan = models.TextField(blank=True, default="")
    safety_net_advice = models.TextField(blank=True, default="")
    telemedicine_limitations = models.TextField(blank=True, default="")
    follow_up_date = models.DateField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    signed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["doctor", "created_at"]),
        ]

    def clean(self):
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Encounter patient must have patient role."})
        if self.doctor_id and self.doctor.role != "doctor":
            raise ValidationError({"doctor": "Encounter author must have doctor role."})
        if self.appointment_id:
            if self.patient_id and self.appointment.patient_id != self.patient_id:
                raise ValidationError("Patient does not match appointment.")
            if self.doctor_id and self.appointment.doctor_id != self.doctor_id:
                raise ValidationError("Doctor does not match appointment.")

    def snapshot(self):
        return {
            "status": self.status,
            "chief_complaint": self.chief_complaint,
            "history_of_present_illness": self.history_of_present_illness,
            "examination": self.examination,
            "assessment": self.assessment,
            "treatment_plan": self.treatment_plan,
            "safety_net_advice": self.safety_net_advice,
            "telemedicine_limitations": self.telemedicine_limitations,
            "follow_up_date": self.follow_up_date.isoformat()
            if self.follow_up_date
            else None,
            "version": self.version,
            "signed_at": self.signed_at.isoformat() if self.signed_at else None,
        }

    def finalize(self, author):
        author_id = getattr(author, "id", None)
        if author_id and author_id != self.doctor_id:
            raise ValidationError("Only the authoring doctor can finalize this note.")
        if self.status != self.Status.DRAFT:
            raise ValidationError("Only a draft encounter can be finalized.")
        if not self.assessment.strip() or not self.treatment_plan.strip():
            raise ValidationError(
                "Assessment and treatment plan are required before finalization."
            )
        self.status = self.Status.FINAL
        self.signed_at = timezone.now()
        self.save(update_fields=["status", "signed_at", "updated_at"])
        EncounterRevision.objects.create(
            encounter=self,
            version=self.version,
            snapshot=self.snapshot(),
            reason="Finalized",
            author=author,
        )

    def amend(self, author, reason, changes):
        author_id = getattr(author, "id", None)
        if not author_id or author_id != self.doctor_id:
            raise ValidationError("Only the authoring doctor can amend this note.")
        if self.status not in {self.Status.FINAL, self.Status.AMENDED}:
            raise ValidationError("Only a signed encounter can be amended.")
        reason = str(reason or "").strip()
        if len(reason) < 10:
            raise ValidationError("A specific amendment reason of at least 10 characters is required.")
        editable = {
            "chief_complaint",
            "history_of_present_illness",
            "examination",
            "assessment",
            "treatment_plan",
            "safety_net_advice",
            "telemedicine_limitations",
            "follow_up_date",
        }
        for field, value in changes.items():
            if field in editable:
                setattr(self, field, value)
        if not self.assessment.strip() or not self.treatment_plan.strip():
            raise ValidationError("Assessment and treatment plan cannot be empty.")
        self.version += 1
        self.status = self.Status.AMENDED
        self.signed_at = timezone.now()
        self.save(
            update_fields=[
                *sorted(editable),
                "version",
                "status",
                "signed_at",
                "updated_at",
            ]
        )
        EncounterRevision.objects.create(
            encounter=self,
            version=self.version,
            snapshot=self.snapshot(),
            reason=reason,
            author=author,
        )

    def __str__(self):
        return f"Encounter #{self.pk} ({self.status})"


class EncounterRevision(models.Model):
    encounter = models.ForeignKey(
        ClinicalEncounter, on_delete=models.CASCADE, related_name="revisions"
    )
    version = models.PositiveIntegerField()
    snapshot = models.JSONField(default=dict)
    reason = models.CharField(max_length=500)
    author = models.ForeignKey(
        AUTH_USER, null=True, on_delete=models.SET_NULL, related_name="encounter_revisions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["encounter", "version"], name="unique_encounter_revision"
            )
        ]


class Allergy(models.Model):
    class Severity(models.TextChoices):
        UNKNOWN = "unknown", "Unknown"
        MILD = "mild", "Mild"
        MODERATE = "moderate", "Moderate"
        SEVERE = "severe", "Severe"
        LIFE_THREATENING = "life_threatening", "Life threatening"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ENTERED_IN_ERROR = "entered_in_error", "Entered in error"

    class Verification(models.TextChoices):
        PATIENT_REPORTED = "patient_reported", "Patient reported"
        CLINICIAN_VERIFIED = "clinician_verified", "Clinician verified"
        REFUTED = "refuted", "Refuted"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="structured_allergies"
    )
    substance = models.CharField(max_length=200)
    reaction = models.CharField(max_length=300, blank=True, default="")
    severity = models.CharField(
        max_length=30, choices=Severity.choices, default=Severity.UNKNOWN
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.ACTIVE
    )
    verification = models.CharField(
        max_length=30,
        choices=Verification.choices,
        default=Verification.PATIENT_REPORTED,
    )
    recorded_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_allergies",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["substance"]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "substance"], name="unique_patient_allergy_substance"
            )
        ]


class Condition(models.Model):
    class ClinicalStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        RESOLVED = "resolved", "Resolved"
        REMISSION = "remission", "Remission"
        UNKNOWN = "unknown", "Unknown"

    class Verification(models.TextChoices):
        PATIENT_REPORTED = "patient_reported", "Patient reported"
        PROVISIONAL = "provisional", "Provisional"
        CONFIRMED = "confirmed", "Confirmed"
        REFUTED = "refuted", "Refuted"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="conditions"
    )
    code_system = models.CharField(max_length=100, blank=True, default="local")
    code = models.CharField(max_length=80, blank=True, default="")
    display = models.CharField(max_length=250)
    clinical_status = models.CharField(
        max_length=30, choices=ClinicalStatus.choices, default=ClinicalStatus.ACTIVE
    )
    verification = models.CharField(
        max_length=30,
        choices=Verification.choices,
        default=Verification.PATIENT_REPORTED,
    )
    onset_date = models.DateField(null=True, blank=True)
    resolved_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_conditions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class MedicationStatement(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        STOPPED = "stopped", "Stopped"
        UNKNOWN = "unknown", "Unknown"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="medication_statements"
    )
    medication_name = models.CharField(max_length=250)
    dose = models.CharField(max_length=120, blank=True, default="")
    frequency = models.CharField(max_length=120, blank=True, default="")
    route = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    source = models.CharField(max_length=50, default="patient_reported")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_medications",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Observation(models.Model):
    class Category(models.TextChoices):
        VITAL_SIGNS = "vital_signs", "Vital signs"
        LABORATORY = "laboratory", "Laboratory"
        CLINICAL = "clinical", "Clinical"
        DEVICE = "device", "Device"

    class Interpretation(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        LOW = "low", "Low"
        ABNORMAL = "abnormal", "Abnormal"
        CRITICAL = "critical", "Critical"
        UNKNOWN = "unknown", "Unknown"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="observations"
    )
    encounter = models.ForeignKey(
        ClinicalEncounter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="observations",
    )
    category = models.CharField(max_length=30, choices=Category.choices)
    code_system = models.CharField(max_length=100, blank=True, default="local")
    code = models.CharField(max_length=80, blank=True, default="")
    display = models.CharField(max_length=250)
    value_numeric = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    value_text = models.CharField(max_length=500, blank=True, default="")
    unit = models.CharField(max_length=50, blank=True, default="")
    reference_low = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    reference_high = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    interpretation = models.CharField(
        max_length=20,
        choices=Interpretation.choices,
        default=Interpretation.UNKNOWN,
    )
    observed_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_observations",
    )
    source = models.CharField(max_length=80, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at"]
        indexes = [models.Index(fields=["patient", "category", "observed_at"])]

    def clean(self):
        if self.value_numeric is None and not self.value_text:
            raise ValidationError("An observation requires a numeric or text value.")


class Referral(models.Model):
    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        EMERGENCY = "emergency", "Emergency"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        ACCEPTED = "accepted", "Accepted"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="referrals"
    )
    encounter = models.ForeignKey(
        ClinicalEncounter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referrals",
    )
    referring_provider = models.ForeignKey(
        AUTH_USER, on_delete=models.PROTECT, related_name="created_referrals"
    )
    target_specialty = models.CharField(max_length=200)
    target_facility = models.CharField(max_length=250, blank=True, default="")
    reason = models.TextField()
    clinical_summary = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.ROUTINE
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SENT
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class CarePlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On hold"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="care_plans"
    )
    encounter = models.ForeignKey(
        ClinicalEncounter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="care_plans",
    )
    author = models.ForeignKey(
        AUTH_USER, on_delete=models.PROTECT, related_name="authored_care_plans"
    )
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True, default="")
    goals = models.JSONField(default=list, blank=True)
    activities = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
