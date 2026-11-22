import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

AUTH_USER = settings.AUTH_USER_MODEL


class Organization(models.Model):
    """Canonical facility/provider organization record.

    User accounts authenticate people or provider operators.  This record is the
    durable identity of the healthcare organization and can survive account,
    portal, or vendor changes.
    """

    class Type(models.TextChoices):
        HOSPITAL = "hospital", "Hospital"
        CLINIC = "clinic", "Clinic"
        PHARMACY = "pharmacy", "Pharmacy"
        LABORATORY = "laboratory", "Laboratory"
        INSURER = "insurer", "Insurance provider"
        IMAGING = "imaging", "Imaging centre"
        HOME_CARE = "home_care", "Home care"
        PUBLIC_HEALTH = "public_health", "Public health"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending verification"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        INACTIVE = "inactive", "Inactive"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_health_organizations",
    )
    parent_facility = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="embedded_pharmacies")
    legal_name = models.CharField(max_length=220)
    trading_name = models.CharField(max_length=220, blank=True, default="")
    organization_type = models.CharField(max_length=30, choices=Type.choices)
    license_number = models.CharField(max_length=120, blank=True, default="")
    license_document = models.FileField(upload_to="registry/organizations/", null=True, blank=True)
    services_description = models.TextField(blank=True, default="")
    issuing_authority = models.CharField(max_length=180, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    contact_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    address = models.TextField(blank=True, default="")
    district = models.CharField(max_length=120, blank=True, default="")
    country_code = models.CharField(max_length=2, default="UG")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["legal_name"]
        indexes = [
            models.Index(fields=["organization_type", "status", "active"]),
            models.Index(fields=["license_number"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["organization_type", "license_number"],
                condition=~models.Q(license_number=""),
                name="unique_registry_license_by_type",
            )
        ]

    def __str__(self):
        return self.trading_name or self.legal_name


class OrganizationLocation(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="locations"
    )
    name = models.CharField(max_length=180)
    address = models.TextField()
    district = models.CharField(max_length=120, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    timezone = models.CharField(max_length=60, default="Africa/Kampala")
    phone = models.CharField(max_length=40, blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"], name="unique_org_location_name"
            )
        ]

    def __str__(self):
        return f"{self.organization} — {self.name}"


class PractitionerCredential(models.Model):
    class Type(models.TextChoices):
        LICENSE = "license", "Professional license"
        DEGREE = "degree", "Degree"
        CERTIFICATE = "certificate", "Certificate"
        SPECIALTY = "specialty", "Specialty credential"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    practitioner = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="professional_credentials"
    )
    credential_type = models.CharField(max_length=20, choices=Type.choices)
    identifier = models.CharField(max_length=140)
    issuer = models.CharField(max_length=180)
    title = models.CharField(max_length=180, blank=True, default="")
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    document = models.FileField(upload_to="registry/credentials/", null=True, blank=True)
    verified_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_professional_credentials",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["practitioner", "issuer", "identifier"],
                name="unique_practitioner_credential",
            )
        ]
        indexes = [models.Index(fields=["identifier", "status"])]

    def clean(self):
        if self.practitioner_id:
            from accounts.roles import PROFESSIONAL_ROLES
            if self.practitioner.role not in PROFESSIONAL_ROLES:
                raise ValidationError({"practitioner": "Credential owner must be a regulated health professional."})
        if self.issued_on and self.expires_on and self.expires_on <= self.issued_on:
            raise ValidationError({"expires_on": "Expiry must be after issue date."})

    def __str__(self):
        return f"{self.identifier} — {self.practitioner}"


class PractitionerRole(models.Model):
    practitioner = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="registry_roles"
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="practitioner_roles"
    )
    location = models.ForeignKey(
        OrganizationLocation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="practitioner_roles",
    )
    role_name = models.CharField(max_length=120, default="Clinician")
    specialty = models.CharField(max_length=160, blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    telemedicine_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["organization", "practitioner"]
        constraints = [
            models.UniqueConstraint(
                fields=["practitioner", "organization", "role_name", "specialty"],
                name="unique_practitioner_role",
            )
        ]

    def clean(self):
        if self.practitioner_id:
            from accounts.roles import PROFESSIONAL_ROLES
            if self.practitioner.role not in PROFESSIONAL_ROLES:
                raise ValidationError({"practitioner": "Role holder must be a health professional."})
        if self.location_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "Location belongs to another organization."})
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})

    def __str__(self):
        return f"{self.practitioner} at {self.organization}"


class CareRelationship(models.Model):
    """Relationship-based access evidence, separate from account roles."""

    class Type(models.TextChoices):
        TREATMENT = "treatment", "Treatment"
        PRIMARY_CARE = "primary_care", "Primary care"
        REFERRAL = "referral", "Referral"
        CARE_TEAM = "care_team", "Care team"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENDED = "ended", "Ended"
        REVOKED = "revoked", "Revoked"

    patient = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="care_relationships"
    )
    practitioner = models.ForeignKey(
        AUTH_USER, on_delete=models.CASCADE, related_name="patient_relationships"
    )
    organization = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="care_relationships",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="care_relationships",
    )
    relationship_type = models.CharField(
        max_length=30, choices=Type.choices, default=Type.TREATMENT
    )
    purpose = models.CharField(max_length=80, default="treatment")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    starts_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_care_relationships",
    )

    class Meta:
        ordering = ["-starts_at"]
        indexes = [
            models.Index(fields=["patient", "practitioner", "status"]),
            models.Index(fields=["organization", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "practitioner", "appointment"],
                condition=models.Q(appointment__isnull=False),
                name="unique_care_relationship_per_appointment",
            )
        ]

    def clean(self):
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Care subject must be a patient."})
        if self.practitioner_id:
            from accounts.roles import CLINICAL_ROLES
            if self.practitioner.role not in CLINICAL_ROLES:
                raise ValidationError({"practitioner": "Care provider must be a clinician."})

    def __str__(self):
        return f"{self.practitioner_id} → {self.patient_id} ({self.status})"
