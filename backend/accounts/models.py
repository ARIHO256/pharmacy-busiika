from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    registration_number = models.CharField(max_length=140, blank=True, default="")
    license_issuer = models.CharField(max_length=180, blank=True, default="")
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
        indexes = [models.Index(fields=["registration_number", "status"])]

    def __str__(self):
        return f"StaffProfile: {self.user.email} ({self.user.role})"
