from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid

AUTH_USER = settings.AUTH_USER_MODEL


# ---------------------------------------------------------------------------
# PHARMACY
# ---------------------------------------------------------------------------
class Medicine(models.Model):
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="medicines")
    inventory_item = models.ForeignKey(
        "operations.InventoryItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="store_listings",
        help_text="Linked operations inventory record kept in sync with store stock.",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.IntegerField()
    stock = models.IntegerField(default=0)
    image = models.ImageField(upload_to="medicines/", null=True, blank=True)

    def __str__(self):
        return self.name


class CartItem(models.Model):
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="cart_items")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="cart_items")
    qty = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.patient_id} x{self.qty} {self.medicine_id}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="orders")
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="pharmacy_orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total = models.IntegerField(default=0)
    delivery = models.BooleanField(default=False)
    delivery_fee = models.IntegerField(default=0)
    address = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.pk} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=200)
    price = models.IntegerField()
    qty = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.name} x{self.qty}"


class PharmacyOrder(models.Model):
    """A prescription sent to a pharmacy for fulfilment."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        PREPARED = "prepared", "Prepared"
        DELIVERED = "delivered", "Delivered"
        REJECTED = "rejected", "Rejected"

    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="rx_orders")
    # Lazy link to prescriptions.Prescription (parallel app). Stored as a plain
    # integer id so this app's migrations stay self-contained; resolved at
    # runtime via get_prescription().
    prescription_id = models.IntegerField(null=True, blank=True)
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="patient_rx_orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PharmacyOrder #{self.pk} ({self.status})"

    def get_prescription(self):
        if not self.prescription_id:
            return None
        try:
            from prescriptions.models import Prescription
        except Exception:
            return None
        try:
            return Prescription.objects.filter(pk=self.prescription_id).first()
        except Exception:
            return None


class Supplier(models.Model):
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="suppliers")
    suppliername = models.CharField(max_length=200)
    contact = models.CharField(max_length=100, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    supply_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.suppliername


class SupplierProduct(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    qty = models.IntegerField(default=0)
    price = models.IntegerField(default=0)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# LAB
# ---------------------------------------------------------------------------
class LabTest(models.Model):
    lab = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="lab_tests")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.IntegerField()
    sample_type = models.CharField(max_length=100, blank=True, default="")

    def __str__(self):
        return self.name


class LabOrder(models.Model):
    class Status(models.TextChoices):
        BOOKED = "booked", "Ordered"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        READY_FOR_COLLECTION = "ready_for_collection", "Ready for collection"
        SAMPLE_COLLECTED = "sample_collected", "Sample collected"
        SAMPLE_RECEIVED = "sample_received", "Sample received"
        PROCESSING = "processing", "In progress"
        PRELIMINARY = "preliminary", "Preliminary"
        AWAITING_VALIDATION = "awaiting_validation", "Awaiting validation"
        VALIDATED = "validated", "Validated"
        COMPLETED = "completed", "Released"
        AMENDED = "amended", "Amended"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected specimen"

    class Priority(models.TextChoices):
        ROUTINE = "routine", "Routine"
        URGENT = "urgent", "Urgent"
        STAT = "stat", "STAT / emergency"

    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="lab_orders")
    lab = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="lab_work")
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name="orders")
    referring_doctor = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referred_lab_orders",
    )
    referring_facility = models.CharField(max_length=220, blank=True, default="")
    clinical_indication = models.TextField(blank=True, default="")
    provisional_diagnosis = models.CharField(max_length=250, blank=True, default="")
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.ROUTINE)
    specimen_id = models.CharField(max_length=80, blank=True, default="")
    specimen_type = models.CharField(max_length=120, blank=True, default="")
    collection_notes = models.TextField(blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")
    collected_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collected_lab_specimens",
    )
    collected_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    result_released = models.BooleanField(default=False)
    # Lazy link to prescriptions.Prescription (parallel app), optional.
    prescription_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.BOOKED)
    result_file = models.FileField(upload_to="lab-results/", null=True, blank=True)
    result_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["lab", "status", "created_at"]),
            models.Index(fields=["patient", "created_at"]),
            models.Index(fields=["specimen_id"]),
        ]

    def __str__(self):
        return f"LabOrder #{self.pk} ({self.status})"


# ---------------------------------------------------------------------------
# HOSPITAL
# ---------------------------------------------------------------------------
class HospitalService(models.Model):
    hospital = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="hospital_services")
    name = models.CharField(max_length=200)
    price = models.IntegerField()

    def __str__(self):
        return self.name


class HospitalBooking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="hospital_bookings")
    hospital = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="bookings")
    service = models.ForeignKey(HospitalService, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking #{self.pk} ({self.status})"


class Bed(models.Model):
    hospital = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="beds")
    ward = models.CharField(max_length=100)
    label = models.CharField(max_length=100)
    is_occupied = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.ward} / {self.label}"


# ---------------------------------------------------------------------------
# INSURANCE
# ---------------------------------------------------------------------------
class InsurancePolicy(models.Model):
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="policies")
    name = models.CharField(max_length=200)
    coverage_percent = models.IntegerField(default=0)
    premium = models.IntegerField(default=0)
    annual_limit = models.PositiveBigIntegerField(default=0, help_text="0 means no configured annual limit")
    deductible = models.PositiveBigIntegerField(default=0)
    copay_percent = models.PositiveSmallIntegerField(default=0)
    copay_fixed = models.PositiveBigIntegerField(default=0)
    waiting_period_days = models.PositiveIntegerField(default=0)
    requires_preauthorization = models.BooleanField(default=False)
    network_only = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    description = models.TextField(blank=True, default="")
    exclusions = models.TextField(blank=True, default="")
    terms_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class PatientCoverage(models.Model):
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="coverages")
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="covered_members")
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name="coverages")
    member_id = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate)
    expires_on = models.DateField(null=True, blank=True)
    dependant_code = models.CharField(max_length=80, blank=True, default="")
    employer_or_group = models.CharField(max_length=180, blank=True, default="")
    verified_at = models.DateTimeField(null=True, blank=True)
    last_eligibility_check_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["provider", "member_id", "active"], name="services_pa_provide_f3fe31_idx"),
            models.Index(fields=["patient", "active", "expires_on"], name="services_pa_patient_15fa55_idx"),
        ]

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.active and self.effective_from <= today and (
            self.expires_on is None or self.expires_on >= today
        )

    def __str__(self):
        return f"{self.member_id} ({self.policy_id})"


class InsuranceClaim(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in_review", "In review"
        QUERY = "query", "Information requested"
        PARTIALLY_APPROVED = "partially_approved", "Partially approved"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    claim_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="claims")
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="provider_claims")
    # Lazy link to payments.Invoice (parallel app). Stored as plain integer id.
    invoice_id = models.IntegerField(null=True, blank=True)
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name="claims")
    coverage = models.ForeignKey(
        PatientCoverage, null=True, blank=True, on_delete=models.SET_NULL, related_name="claims"
    )
    preauthorization = models.ForeignKey(
        "InsurancePreauthorization", null=True, blank=True, on_delete=models.SET_NULL, related_name="claims"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    amount = models.IntegerField(default=0)
    approved_amount = models.PositiveBigIntegerField(default=0)
    patient_responsibility = models.PositiveBigIntegerField(default=0)
    diagnosis_code = models.CharField(max_length=80, blank=True, default="")
    clinical_summary = models.TextField(blank=True, default="")
    decision_reason = models.TextField(blank=True, default="")
    requested_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_insurance_claims"
    )
    reviewed_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_insurance_claims"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "status", "created_at"], name="services_in_provide_b9f0c8_idx"),
            models.Index(fields=["patient", "status", "created_at"], name="services_in_patient_4c5802_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = f"CLM-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"
        if self.status == self.Status.SUBMITTED and self.submitted_at is None:
            self.submitted_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.claim_number or f'Claim #{self.pk}'} ({self.status})"

    def get_invoice(self):
        if not self.invoice_id:
            return None
        try:
            from payments.models import Invoice
        except Exception:
            return None
        try:
            return Invoice.objects.filter(pk=self.invoice_id).first()
        except Exception:
            return None


class InsuranceBenefitRule(models.Model):
    """A policy-level benefit, exclusion and authorization rule."""

    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name="benefit_rules")
    service_code = models.CharField(max_length=80, blank=True, default="")
    service_category = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default="")
    coverage_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    annual_limit = models.PositiveBigIntegerField(default=0)
    per_visit_limit = models.PositiveBigIntegerField(default=0)
    copay_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    copay_fixed = models.PositiveBigIntegerField(default=0)
    waiting_period_days = models.PositiveIntegerField(default=0)
    requires_preauthorization = models.BooleanField(default=False)
    excluded = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["service_category", "service_code", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "service_code", "service_category"],
                name="unique_policy_benefit_rule",
            )
        ]


class InsuranceEligibilityCheck(models.Model):
    class Result(models.TextChoices):
        ELIGIBLE = "eligible", "Eligible"
        INACTIVE = "inactive", "Inactive"
        EXPIRED = "expired", "Expired"
        WAITING_PERIOD = "waiting_period", "Waiting period"
        NOT_FOUND = "not_found", "Not found"

    coverage = models.ForeignKey(
        PatientCoverage, null=True, blank=True, on_delete=models.SET_NULL, related_name="eligibility_checks"
    )
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="eligibility_checks")
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="processed_eligibility_checks")
    member_id = models.CharField(max_length=100)
    service_code = models.CharField(max_length=80, blank=True, default="")
    service_category = models.CharField(max_length=120, blank=True, default="")
    estimated_amount = models.PositiveBigIntegerField(default=0)
    result = models.CharField(max_length=24, choices=Result.choices)
    coverage_percent = models.PositiveSmallIntegerField(default=0)
    covered_amount = models.PositiveBigIntegerField(default=0)
    patient_responsibility = models.PositiveBigIntegerField(default=0)
    requires_preauthorization = models.BooleanField(default=False)
    reason = models.CharField(max_length=255, blank=True, default="")
    response_snapshot = models.JSONField(default=dict, blank=True)
    requested_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_eligibility_checks"
    )
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]
        indexes = [models.Index(fields=["provider", "member_id", "checked_at"], name="services_in_provide_e16c40_idx")]


class InsurancePreauthorization(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        IN_REVIEW = "in_review", "In review"
        QUERY = "query", "Information requested"
        APPROVED = "approved", "Approved"
        PARTIALLY_APPROVED = "partially_approved", "Partially approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    authorization_number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="insurance_preauthorizations")
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="provider_preauthorizations")
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.PROTECT, related_name="preauthorizations")
    coverage = models.ForeignKey(PatientCoverage, on_delete=models.PROTECT, related_name="preauthorizations")
    requesting_facility = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_preauthorizations"
    )
    service_code = models.CharField(max_length=80, blank=True, default="")
    service_name = models.CharField(max_length=180)
    clinical_indication = models.TextField(blank=True, default="")
    diagnosis_code = models.CharField(max_length=80, blank=True, default="")
    requested_amount = models.PositiveBigIntegerField(default=0)
    approved_amount = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SUBMITTED)
    decision_reason = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_preauthorizations"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "status", "created_at"], name="services_in_provide_0c359a_idx")]

    def save(self, *args, **kwargs):
        if not self.authorization_number:
            self.authorization_number = f"PA-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)


class InsuranceClaimItem(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        PARTIALLY_APPROVED = "partially_approved", "Partially approved"
        REJECTED = "rejected", "Rejected"

    claim = models.ForeignKey(InsuranceClaim, on_delete=models.CASCADE, related_name="items")
    invoice_item_id = models.IntegerField(null=True, blank=True)
    service_code = models.CharField(max_length=80, blank=True, default="")
    description = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.PositiveBigIntegerField(default=0)
    requested_amount = models.PositiveBigIntegerField(default=0)
    approved_amount = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SUBMITTED)
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]


class InsuranceRemittance(models.Model):
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="insurance_remittances")
    claim = models.ForeignKey(InsuranceClaim, on_delete=models.PROTECT, related_name="remittances")
    remittance_number = models.CharField(max_length=60, unique=True)
    paid_amount = models.PositiveBigIntegerField()
    payment_reference = models.CharField(max_length=120)
    paid_on = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_insurance_remittances"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on", "-id"]


class LabResult(models.Model):
    """Structured laboratory result; a PDF may remain attached to LabOrder."""

    class Status(models.TextChoices):
        PRELIMINARY = "preliminary", "Preliminary"
        FINAL = "final", "Final"
        AMENDED = "amended", "Amended"
        CORRECTED = "corrected", "Corrected"
        CANCELLED = "cancelled", "Cancelled"

    class Interpretation(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        LOW = "low", "Low"
        ABNORMAL = "abnormal", "Abnormal"
        CRITICAL = "critical", "Critical"
        UNKNOWN = "unknown", "Unknown"

    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name="results")
    code_system = models.CharField(max_length=100, blank=True, default="local")
    code = models.CharField(max_length=80, blank=True, default="")
    name = models.CharField(max_length=250)
    value_numeric = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    value_text = models.CharField(max_length=500, blank=True, default="")
    unit = models.CharField(max_length=50, blank=True, default="")
    reference_low = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    reference_high = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    interpretation = models.CharField(
        max_length=20,
        choices=Interpretation.choices,
        default=Interpretation.UNKNOWN,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRELIMINARY)
    entered_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entered_lab_results",
    )
    verified_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_lab_results",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="released_lab_results",
    )
    released_at = models.DateTimeField(null=True, blank=True)
    amendment_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "code", "name"], name="unique_result_per_order_code")
        ]

    def __str__(self):
        return f"{self.name}: {self.value_numeric if self.value_numeric is not None else self.value_text}"


class CriticalResultAcknowledgement(models.Model):
    result = models.OneToOneField(
        LabResult, on_delete=models.CASCADE, related_name="acknowledgement"
    )
    acknowledged_by = models.ForeignKey(
        AUTH_USER, on_delete=models.PROTECT, related_name="acknowledged_critical_results"
    )
    notes = models.TextField(blank=True, default="")
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Acknowledged result {self.result_id}"


class LabTestPanel(models.Model):
    """A reusable group of laboratory tests sold and ordered as one panel."""

    lab = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="lab_test_panels")
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=80)
    description = models.TextField(blank=True, default="")
    price = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["lab", "code"], name="unique_lab_panel_code")
        ]
        indexes = [models.Index(fields=["lab", "active", "name"], name="services_panel_lab_idx")]

    def __str__(self):
        return f"{self.name} ({self.code})"


class LabTestPanelItem(models.Model):
    panel = models.ForeignKey(LabTestPanel, on_delete=models.CASCADE, related_name="items")
    test = models.ForeignKey(LabTest, on_delete=models.PROTECT, related_name="panel_items")
    sequence = models.PositiveSmallIntegerField(default=1)
    required = models.BooleanField(default=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["panel", "test"], name="unique_test_in_lab_panel")
        ]

    def __str__(self):
        return f"{self.panel.code}: {self.test.name}"


class SpecimenEvent(models.Model):
    class Type(models.TextChoices):
        LABELLED = "labelled", "Label generated"
        COLLECTED = "collected", "Collected"
        RECEIVED = "received", "Received"
        ALIQUOTED = "aliquoted", "Aliquoted"
        TRANSFERRED = "transferred", "Transferred"
        PROCESSING = "processing", "Processing"
        STORED = "stored", "Stored"
        REJECTED = "rejected", "Rejected"
        DISPOSED = "disposed", "Disposed"

    order = models.ForeignKey(LabOrder, on_delete=models.CASCADE, related_name="specimen_events")
    event_type = models.CharField(max_length=24, choices=Type.choices)
    barcode = models.CharField(max_length=100, blank=True, default="")
    location = models.CharField(max_length=180, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    performed_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="laboratory_specimen_events",
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [
            models.Index(fields=["order", "occurred_at"], name="services_spec_order_idx"),
            models.Index(fields=["barcode"], name="services_spec_barcode_idx"),
        ]

    def __str__(self):
        return f"{self.order_id}: {self.event_type}"


class DispensingRecord(models.Model):
    class Status(models.TextChoices):
        REVIEWED = "reviewed", "Prescription reviewed"
        CLARIFICATION = "clarification", "Clarification required"
        PARTIAL = "partial", "Partially dispensed"
        DISPENSED = "dispensed", "Dispensed"
        HELD = "held", "Held"
        CANCELLED = "cancelled", "Cancelled"

    pharmacy_order = models.ForeignKey(
        PharmacyOrder, on_delete=models.CASCADE, related_name="dispensing_records"
    )
    pharmacist = models.ForeignKey(
        AUTH_USER, on_delete=models.PROTECT, related_name="dispensing_records"
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REVIEWED)
    clarification_note = models.TextField(blank=True, default="")
    substitution_authorised_by = models.CharField(max_length=200, blank=True, default="")
    counselling_notes = models.TextField(blank=True, default="")
    dispensed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pharmacy_order", "status"], name="services_disp_order_idx"),
            models.Index(fields=["pharmacist", "created_at"], name="services_disp_staff_idx"),
        ]

    def __str__(self):
        return f"Dispensing #{self.pk} for order {self.pharmacy_order_id}"


class DispensingItem(models.Model):
    record = models.ForeignKey(DispensingRecord, on_delete=models.CASCADE, related_name="items")
    prescription_item_id = models.PositiveIntegerField(null=True, blank=True)
    medicine_name = models.CharField(max_length=220)
    prescribed_quantity = models.PositiveIntegerField(default=0)
    dispensed_quantity = models.PositiveIntegerField(default=0)
    batch_number = models.CharField(max_length=100, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    substituted_product = models.CharField(max_length=220, blank=True, default="")
    label_instructions = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["record", "prescription_item_id", "medicine_name"],
                name="unique_dispensing_record_item",
            )
        ]

    def __str__(self):
        return f"{self.medicine_name} x {self.dispensed_quantity}"
