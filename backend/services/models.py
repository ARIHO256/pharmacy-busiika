from django.conf import settings
from django.db import models

AUTH_USER = settings.AUTH_USER_MODEL


# ---------------------------------------------------------------------------
# PHARMACY
# ---------------------------------------------------------------------------
class MedicineTaxonomyNode(models.Model):
    class Level(models.IntegerChoices):
        FAMILY = 2, "Product family"
        CATEGORY = 3, "Category"
        SUBCATEGORY = 4, "Subcategory"

    node_id = models.SlugField(max_length=220, primary_key=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    level = models.PositiveSmallIntegerField(choices=Level.choices)
    name = models.CharField(max_length=200)
    image_url = models.URLField(max_length=500, blank=True)
    sort_order = models.PositiveIntegerField()
    pharmacy = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.PROTECT, related_name="custom_medicine_taxonomy")
    attribute_fields = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["sort_order", "node_id"]


class MedicineTaxonomyOverride(models.Model):
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE)
    node = models.ForeignKey(MedicineTaxonomyNode, on_delete=models.PROTECT)
    name = models.CharField(max_length=200, blank=True)
    archived = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["pharmacy", "node"], name="unique_pharmacy_taxonomy_override")]


class Medicine(models.Model):
    class SaleType(models.TextChoices):
        UNCLASSIFIED = "unclassified", "Unclassified"
        OTC = "otc", "Over the counter"
        PRESCRIPTION = "prescription", "Prescription only"
        CONTROLLED = "controlled", "Controlled"

    sale_type = models.CharField(max_length=20, choices=SaleType.choices, default=SaleType.UNCLASSIFIED)

    product_attributes = models.JSONField(default=dict, blank=True)
    taxonomy_node = models.ForeignKey(MedicineTaxonomyNode, on_delete=models.PROTECT, null=True, blank=True, related_name="medicines")
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="medicines")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.IntegerField()
    units_per_pack = models.PositiveIntegerField(default=1)
    unit_label = models.CharField(max_length=32, default="unit")
    reorder_level = models.PositiveIntegerField(default=0)
    wholesale_minimum = models.PositiveIntegerField(null=True, blank=True)
    wholesale_unit_price = models.PositiveIntegerField(null=True, blank=True)
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
        READY = "ready", "Ready for pickup"
        DISPATCHED = "dispatched", "Dispatched"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="orders", null=True, blank=True)
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="pharmacy_orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total = models.IntegerField(default=0)
    counter_reference = models.UUIDField(unique=True, null=True, blank=True, editable=False)
    invoice = models.OneToOneField("payments.Invoice", on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="pharmacy_sale")
    pickup_instructions = models.CharField(max_length=500, blank=True)
    delivery = models.BooleanField(default=False)
    address = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    handed_over_at = models.DateTimeField(null=True, blank=True)
    handover_reference = models.CharField(max_length=200, blank=True)
    handed_over_by = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, null=True, related_name="+")

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

    handed_over_at = models.DateTimeField(null=True, blank=True)
    handover_reference = models.CharField(max_length=200, blank=True)
    handed_over_by = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, null=True, related_name="+")

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
    qualification_reference = models.CharField(max_length=200, blank=True)
    qualified_until = models.DateField(null=True, blank=True)
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

    visit = models.ForeignKey("workforce.PatientVisit", null=True, blank=True, on_delete=models.PROTECT, related_name="lab_orders")
    arrived_at = models.DateTimeField(null=True, blank=True)
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
    description = models.TextField(blank=True, default="")

    def __str__(self):
        return self.name


class PatientCoverage(models.Model):
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="coverages")
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="covered_members")
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name="coverages")
    member_id = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.member_id} ({self.policy_id})"


class InsuranceClaim(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="claims")
    provider = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="provider_claims")
    # Lazy link to payments.Invoice (parallel app). Stored as plain integer id.
    invoice_id = models.IntegerField(null=True, blank=True)
    policy = models.ForeignKey(InsurancePolicy, on_delete=models.CASCADE, related_name="claims")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    amount = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Claim #{self.pk} ({self.status})"

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
    escalated_at = models.DateTimeField(null=True, blank=True)
    amendment_reason = models.TextField(blank=True, default="")
    supersedes = models.OneToOneField("self", on_delete=models.RESTRICT, null=True, blank=True, related_name="replacement")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "code", "name"], condition=models.Q(supersedes__isnull=True), name="unique_initial_result_per_order_code")
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


class PharmacyRolePolicy(models.Model):
    pharmacy = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="pharmacy_role_policies")
    role = models.CharField(max_length=24)
    permissions = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("pharmacy", "role"), name="unique_pharmacy_role_policy")]


class PharmacyRefund(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="refund")
    amount = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=1000)
    reference = models.CharField(max_length=120)
    approved_by = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PharmacyOrderIssue(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="issues", null=True, blank=True)
    prescription_order = models.ForeignKey(PharmacyOrder, on_delete=models.PROTECT, related_name="issues", null=True, blank=True)
    category = models.CharField(max_length=32)
    note = models.CharField(max_length=1000)
    outcome = models.CharField(max_length=1000, blank=True)
    opened_by = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="+")
    resolved_by = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="+", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(order__isnull=False, prescription_order__isnull=True)
                           | models.Q(order__isnull=True, prescription_order__isnull=False)),
                name="pharmacy_issue_single_order",
            ),
        ]


class PharmacyCreditCollection(models.Model):
    request_id = models.UUIDField(unique=True)
    payment = models.OneToOneField("payments.PaymentTransaction", on_delete=models.PROTECT)
