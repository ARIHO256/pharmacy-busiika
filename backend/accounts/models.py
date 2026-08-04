from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

import uuid


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_verified", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        PATIENT = "patient", "Patient"
        DOCTOR = "doctor", "Doctor"
        NURSE = "nurse", "Nurse / Midwife"
        RECEPTIONIST = "receptionist", "Receptionist"
        CASHIER = "cashier", "Cashier / Billing officer"
        PHARMACIST = "pharmacist", "Pharmacist"
        LAB_TECHNICIAN = "lab_technician", "Laboratory professional"
        FACILITY_MANAGER = "facility_manager", "Facility manager"
        RECORDS_OFFICER = "records_officer", "Medical records officer"
        INSURANCE_OFFICER = "insurance_officer", "Insurance officer"
        STOREKEEPER = "storekeeper", "Storekeeper / Procurement"
        MIDWIFE = "midwife", "Midwife"
        CLINICAL_OFFICER = "clinical_officer", "Clinical Officer"
        DENTIST = "dentist", "Dentist"
        RADIOLOGIST = "radiologist", "Radiologist"
        RADIOGRAPHER = "radiographer", "Radiographer / Sonographer"
        PHYSIOTHERAPIST = "physiotherapist", "Physiotherapist"
        NUTRITIONIST = "nutritionist", "Nutritionist / Dietitian"
        PSYCHOLOGIST = "psychologist", "Psychologist / Counsellor"
        ANAESTHETIST = "anaesthetist", "Anaesthetist"
        THEATRE_NURSE = "theatre_nurse", "Theatre Nurse"
        MEDICAL_DIRECTOR = "medical_director", "Medical Director"
        ACCOUNTANT = "accountant", "Accountant"
        FINANCE_MANAGER = "finance_manager", "Finance Manager"
        PROCUREMENT_OFFICER = "procurement_officer", "Procurement Officer"
        QUALITY_OFFICER = "quality_officer", "Quality Assurance Officer"
        COMPLIANCE_OFFICER = "compliance_officer", "Data Protection / Compliance Officer"
        HR_OFFICER = "hr_officer", "Human Resources Officer"
        IT_SUPPORT = "it_support", "IT Support Officer"
        CLAIMS_REVIEWER = "claims_reviewer", "Insurance Claims Reviewer"
        AMBULANCE_DISPATCHER = "ambulance_dispatcher", "Ambulance Dispatcher"
        PARAMEDIC = "paramedic", "Paramedic"
        PHARMACY = "pharmacy", "Pharmacy organization"
        LAB = "lab", "Laboratory organization"
        HOSPITAL = "hospital", "Hospital / Clinic organization"
        INSURANCE = "insurance", "Insurance organization"
        ADMIN = "admin", "Platform administrator"

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.PATIENT)
    phone = models.CharField(max_length=30, blank=True, default="")
    is_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    mfa_enabled = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_password_change_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def __str__(self):
        return f"{self.email} ({self.role})"


class ProfileStatus(models.TextChoices):
    PENDING = "pending", "Pending verification"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"
    EXPIRED = "expired", "Expired"
    REVOKED = "revoked", "Revoked"


class PatientProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"
        PREFER_NOT_TO_SAY = "prefer_not_to_say", "Prefer not to say"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="patient_profile"
    )
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=Gender.choices, blank=True, default=""
    )
    blood_group = models.CharField(max_length=5, blank=True, default="")
    allergies = models.TextField(blank=True, default="")
    medical_history = models.TextField(blank=True, default="")
    emergency_contact = models.CharField(max_length=50, blank=True, default="")
    location = models.CharField(max_length=180, blank=True, default="")
    address = models.TextField(blank=True, default="")

    def __str__(self):
        return f"PatientProfile: {self.user.email}"


class PatientRelationship(models.Model):
    """Verified caregiver/guardian authority over a patient account.

    Dependents are represented by normal patient users with unusable passwords, so
    every clinical, billing and scheduling record continues to reference the same
    canonical patient entity. Access is always mediated by this relationship.
    """

    class Relationship(models.TextChoices):
        PARENT = "parent", "Parent"
        GUARDIAN = "guardian", "Legal guardian"
        SPOUSE = "spouse", "Spouse"
        CHILD = "child", "Adult child"
        SIBLING = "sibling", "Sibling"
        CAREGIVER = "caregiver", "Caregiver"
        LEGAL_REPRESENTATIVE = "legal_representative", "Legal representative"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending verification"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"
        EXPIRED = "expired", "Expired"

    caregiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="managed_patient_relationships"
    )
    patient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="caregiver_relationships"
    )
    relationship = models.CharField(max_length=32, choices=Relationship.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    can_book = models.BooleanField(default=True)
    can_view_records = models.BooleanField(default=True)
    can_manage_billing = models.BooleanField(default=True)
    can_receive_notifications = models.BooleanField(default=True)
    authority_document = models.FileField(
        upload_to="patients/caregiver-authority/", null=True, blank=True
    )
    verified_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_patient_relationships"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["patient__first_name", "patient__last_name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["caregiver", "patient"], name="unique_patient_caregiver_relationship"
            ),
            models.CheckConstraint(
                condition=~models.Q(caregiver=models.F("patient")),
                name="patient_caregiver_cannot_be_same_user",
            ),
        ]
        indexes = [
            models.Index(fields=["caregiver", "status"]),
            models.Index(fields=["patient", "status"]),
        ]

    @property
    def is_current(self):
        return self.status == self.Status.ACTIVE and (
            self.expires_at is None or self.expires_at > timezone.now()
        )

    def __str__(self):
        return f"{self.caregiver.email} -> {self.patient.email} ({self.relationship})"


class DoctorProfile(models.Model):
    class Cadre(models.TextChoices):
        MEDICAL_OFFICER = "medical_officer", "Medical Officer"
        SPECIALIST = "specialist", "Specialist Doctor"
        CONSULTANT = "consultant", "Consultant"
        CLINICAL_OFFICER = "clinical_officer", "Clinical Officer"
        DENTIST = "dentist", "Dentist"
        OTHER = "other", "Other"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="doctor_profile"
    )
    year_of_completion = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1950), MaxValueValidator(2100)],
    )
    university = models.CharField(max_length=220, blank=True, default="")
    cadre = models.CharField(max_length=40, choices=Cadre.choices, blank=True, default="")
    specialization = models.CharField(max_length=120, blank=True, default="")
    hospital = models.CharField(max_length=200, blank=True, default="")
    experience_years = models.PositiveIntegerField(default=0)
    fees = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True, default="")
    license_number = models.CharField(max_length=140, blank=True, default="")
    license_issuer = models.CharField(max_length=180, blank=True, default="")
    license_issued_on = models.DateField(null=True, blank=True)
    license_expires_on = models.DateField(null=True, blank=True)
    license_document = models.FileField(
        upload_to="doctors/licenses/", null=True, blank=True
    )
    certificates = models.FileField(
        upload_to="doctors/certificates/", null=True, blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=ProfileStatus.choices,
        default=ProfileStatus.PENDING,
    )
    verification_notes = models.TextField(blank=True, default="")
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["license_number", "status"])]

    def __str__(self):
        return f"DoctorProfile: {self.user.email} ({self.status})"


class ProviderProfile(models.Model):
    """Organization operator profile for pharmacy/lab/hospital/insurance accounts."""

    class OrganizationType(models.TextChoices):
        HOSPITAL = "hospital", "Hospital"
        CLINIC = "clinic", "Clinic"
        PHARMACY = "pharmacy", "Pharmacy"
        LABORATORY = "laboratory", "Laboratory"
        INSURER = "insurer", "Insurance provider"

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="provider_profile"
    )
    organization_type = models.CharField(
        max_length=30,
        choices=OrganizationType.choices,
        default=OrganizationType.HOSPITAL,
    )
    org_name = models.CharField(max_length=200, blank=True, default="")
    license_number = models.CharField(max_length=120, blank=True, default="")
    license_issuer = models.CharField(max_length=180, blank=True, default="")
    license_issued_on = models.DateField(null=True, blank=True)
    license_expires_on = models.DateField(null=True, blank=True)
    license_document = models.FileField(
        upload_to="organizations/licenses/", null=True, blank=True
    )
    district = models.CharField(max_length=120, blank=True, default="")
    address = models.TextField(blank=True, default="")
    services_description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=ProfileStatus.choices,
        default=ProfileStatus.PENDING,
    )
    verification_notes = models.TextField(blank=True, default="")

    def __str__(self):
        return f"ProviderProfile: {self.user.email} ({self.status})"


class StaffProfile(models.Model):
    """Personal professional/employment details for organization-invited staff."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="staff_profile"
    )
    employee_number = models.CharField(max_length=80, blank=True, default="")
    cadre = models.CharField(max_length=120, blank=True, default="")
    university = models.CharField(max_length=220, blank=True, default="")
    year_of_completion = models.PositiveSmallIntegerField(null=True, blank=True)
    qualification = models.CharField(max_length=220, blank=True, default="")
    specialty = models.CharField(max_length=120, blank=True, default="")
    workplace = models.CharField(max_length=200, blank=True, default="")
    experience_years = models.PositiveIntegerField(default=0)
    consultation_fee = models.PositiveIntegerField(default=0)
    offers_appointments = models.BooleanField(default=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    registration_number = models.CharField(max_length=140, blank=True, default="")
    license_issuer = models.CharField(max_length=180, blank=True, default="")
    license_issued_on = models.DateField(null=True, blank=True)
    license_expires_on = models.DateField(null=True, blank=True)
    license_document = models.FileField(
        upload_to="staff/licenses/", null=True, blank=True
    )
    bio = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=ProfileStatus.choices,
        default=ProfileStatus.PENDING,
    )

    class Meta:
        indexes = [
            models.Index(fields=["registration_number", "status"]),
            models.Index(fields=["offers_appointments", "status"], name="accounts_st_offers__84a3d0_idx"),
        ]

    def __str__(self):
        return f"StaffProfile: {self.user.email} ({self.user.role})"


class OneTimeToken(models.Model):
    """Hashed, expiring tokens for email verification, password reset and MFA."""

    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", "Email verification"
        PASSWORD_RESET = "password_reset", "Password reset"
        MFA_LOGIN = "mfa_login", "MFA login"
        PHONE_VERIFICATION = "phone_verification", "Phone verification"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="one_time_tokens")
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    token_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["public_id", "purpose"]),
            models.Index(fields=["user", "purpose", "expires_at"]),
        ]

    @property
    def active(self):
        return self.consumed_at is None and self.expires_at > timezone.now()


class SecurityEvent(models.Model):
    class Type(models.TextChoices):
        LOGIN_SUCCESS = "login_success", "Login success"
        LOGIN_FAILED = "login_failed", "Login failed"
        ACCOUNT_LOCKED = "account_locked", "Account locked"
        PASSWORD_CHANGED = "password_changed", "Password changed"
        PASSWORD_RESET = "password_reset", "Password reset"
        EMAIL_VERIFIED = "email_verified", "Email verified"
        PHONE_VERIFIED = "phone_verified", "Phone verified"
        SESSION_REVOKED = "session_revoked", "Session revoked"
        LOGOUT = "logout", "Logout"
        MFA_ENABLED = "mfa_enabled", "MFA enabled"
        MFA_DISABLED = "mfa_disabled", "MFA disabled"
        MFA_CHALLENGE = "mfa_challenge", "MFA challenge"

    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="security_events")
    event_type = models.CharField(max_length=32, choices=Type.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=100, blank=True, default="")
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "event_type", "created_at"])]
