import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

AUTH_USER = settings.AUTH_USER_MODEL


class Ward(models.Model):
    class Type(models.TextChoices):
        GENERAL = "general", "General ward"
        PRIVATE = "private", "Private ward"
        ICU = "icu", "Intensive care"
        HDU = "hdu", "High dependency"
        MATERNITY = "maternity", "Maternity"
        PAEDIATRIC = "paediatric", "Paediatric"
        EMERGENCY = "emergency", "Emergency observation"
        THEATRE = "theatre", "Theatre / recovery"
        ISOLATION = "isolation", "Isolation"

    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="wards")
    location = models.ForeignKey("registry.OrganizationLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="wards")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40)
    ward_type = models.CharField(max_length=24, choices=Type.choices, default=Type.GENERAL)
    floor = models.CharField(max_length=80, blank=True, default="")
    nurse_station = models.CharField(max_length=120, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["organization", "name"]
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="unique_ward_code")]

    def clean(self):
        if self.location_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "Location belongs to another organization."})

    def __str__(self):
        return f"{self.organization} — {self.name}"


class FacilityBed(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        RESERVED = "reserved", "Reserved"
        OCCUPIED = "occupied", "Occupied"
        CLEANING = "cleaning", "Cleaning"
        MAINTENANCE = "maintenance", "Maintenance"
        BLOCKED = "blocked", "Blocked"

    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name="beds")
    label = models.CharField(max_length=60)
    bed_type = models.CharField(max_length=80, blank=True, default="standard")
    daily_rate = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["ward", "label"]
        constraints = [models.UniqueConstraint(fields=["ward", "label"], name="unique_bed_per_ward")]

    def __str__(self):
        return f"{self.ward.name} / {self.label}"


class Admission(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ADMITTED = "admitted", "Admitted"
        TRANSFERRED = "transferred", "Transferred"
        DISCHARGE_PENDING = "discharge_pending", "Discharge pending"
        DISCHARGED = "discharged", "Discharged"
        CANCELLED = "cancelled", "Cancelled"
        DECEASED = "deceased", "Deceased"

    admission_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="admissions")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="admissions")
    visit = models.ForeignKey("workforce.PatientVisit", null=True, blank=True, on_delete=models.SET_NULL, related_name="admissions")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="admissions")
    admitting_clinician = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="admitted_patients")
    attending_clinician = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="attending_admissions")
    reason = models.TextField()
    provisional_diagnosis = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ADMITTED)
    admitted_at = models.DateTimeField(default=timezone.now)
    expected_discharge_at = models.DateTimeField(null=True, blank=True)
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharge_disposition = models.CharField(max_length=120, blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_admissions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-admitted_at"]
        indexes = [models.Index(fields=["organization", "status", "admitted_at"]), models.Index(fields=["patient", "status"])]

    def save(self, *args, **kwargs):
        if not self.admission_number:
            self.admission_number = f"ADM-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Admission subject must be a patient."})
        if self.ward_id and self.ward.organization_id != self.organization_id:
            raise ValidationError({"ward": "Ward belongs to another organization."})

    def __str__(self):
        return self.admission_number


class BedAllocation(models.Model):
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name="bed_allocations")
    bed = models.ForeignKey(FacilityBed, on_delete=models.PROTECT, related_name="allocations")
    assigned_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_beds")
    assigned_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.CharField(max_length=180, blank=True, default="")

    class Meta:
        ordering = ["-assigned_at"]
        indexes = [models.Index(fields=["bed", "released_at"]), models.Index(fields=["admission", "released_at"])]

    def clean(self):
        if self.admission_id and self.bed_id and self.admission.organization_id != self.bed.ward.organization_id:
            raise ValidationError({"bed": "Bed belongs to another organization."})
        conflict = BedAllocation.objects.filter(bed=self.bed, released_at__isnull=True)
        if self.pk:
            conflict = conflict.exclude(pk=self.pk)
        if conflict.exists():
            raise ValidationError({"bed": "Bed is already allocated."})


class AdmissionTransfer(models.Model):
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name="transfers")
    from_ward = models.ForeignKey(Ward, null=True, blank=True, on_delete=models.SET_NULL, related_name="outgoing_transfers")
    to_ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="incoming_transfers")
    reason = models.TextField()
    requested_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_admission_transfers")
    transferred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-transferred_at"]


class WardTask(models.Model):
    class Category(models.TextChoices):
        OBSERVATION = "observation", "Observation"
        MEDICATION = "medication", "Medication"
        PROCEDURE = "procedure", "Procedure"
        MOBILISATION = "mobilisation", "Mobilisation"
        NUTRITION = "nutrition", "Nutrition"
        REVIEW = "review", "Clinical review"
        DISCHARGE = "discharge", "Discharge task"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        OMITTED = "omitted", "Omitted"
        CANCELLED = "cancelled", "Cancelled"

    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name="tasks")
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.OTHER)
    title = models.CharField(max_length=220)
    instructions = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, choices=[("routine", "Routine"), ("urgent", "Urgent"), ("stat", "STAT")], default="routine")
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="ward_tasks")
    due_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    completed_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_ward_tasks")
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_ward_tasks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_at", "-created_at"]


class ClinicalRound(models.Model):
    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name="rounds")
    clinician = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="clinical_rounds")
    subjective = models.TextField(blank=True, default="")
    objective = models.TextField(blank=True, default="")
    assessment = models.TextField()
    plan = models.TextField()
    discharge_readiness = models.CharField(max_length=40, choices=[("not_ready", "Not ready"), ("planning", "Planning"), ("ready", "Ready")], default="not_ready")
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]


class DischargeSummary(models.Model):
    admission = models.OneToOneField(Admission, on_delete=models.CASCADE, related_name="discharge_summary")
    clinician = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="discharge_summaries")
    final_diagnosis = models.TextField()
    treatment_summary = models.TextField()
    procedures = models.TextField(blank=True, default="")
    discharge_medications = models.TextField(blank=True, default="")
    follow_up_plan = models.TextField(blank=True, default="")
    patient_instructions = models.TextField(blank=True, default="")
    fitness_notes = models.TextField(blank=True, default="")
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ImagingOrder(models.Model):
    class Modality(models.TextChoices):
        XRAY = "xray", "X-ray"
        ULTRASOUND = "ultrasound", "Ultrasound"
        CT = "ct", "CT"
        MRI = "mri", "MRI"
        MAMMOGRAPHY = "mammography", "Mammography"
        FLUOROSCOPY = "fluoroscopy", "Fluoroscopy"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ORDERED = "ordered", "Ordered"
        SCHEDULED = "scheduled", "Scheduled"
        CHECKED_IN = "checked_in", "Checked in"
        IN_PROGRESS = "in_progress", "In progress"
        PERFORMED = "performed", "Performed"
        REPORTING = "reporting", "Reporting"
        VERIFIED = "verified", "Verified"
        RELEASED = "released", "Released"
        CANCELLED = "cancelled", "Cancelled"

    order_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="imaging_orders")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="imaging_orders")
    admission = models.ForeignKey(Admission, null=True, blank=True, on_delete=models.SET_NULL, related_name="imaging_orders")
    ordering_clinician = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordered_imaging")
    modality = models.CharField(max_length=24, choices=Modality.choices)
    study_name = models.CharField(max_length=220)
    clinical_indication = models.TextField()
    provisional_diagnosis = models.CharField(max_length=240, blank=True, default="")
    priority = models.CharField(max_length=20, choices=[("routine", "Routine"), ("urgent", "Urgent"), ("stat", "STAT")], default="routine")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ORDERED)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    performed_at = models.DateTimeField(null=True, blank=True)
    radiographer = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="performed_imaging_orders")
    radiologist = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_imaging_reports")
    image_reference = models.CharField(max_length=240, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status", "created_at"]), models.Index(fields=["patient", "created_at"])]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"IMG-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class ImagingReport(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PRELIMINARY = "preliminary", "Preliminary"
        VERIFIED = "verified", "Verified"
        RELEASED = "released", "Released"
        AMENDED = "amended", "Amended"

    order = models.OneToOneField(ImagingOrder, on_delete=models.CASCADE, related_name="report")
    findings = models.TextField()
    impression = models.TextField()
    recommendations = models.TextField(blank=True, default="")
    critical = models.BooleanField(default=False)
    critical_message = models.TextField(blank=True, default="")
    report_file = models.FileField(upload_to="imaging/reports/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="authored_imaging_reports")
    verified_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_imaging_reports")
    verified_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class InventoryItem(models.Model):
    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="inventory_items")
    name = models.CharField(max_length=220)
    sku = models.CharField(max_length=80)
    category = models.CharField(max_length=100, blank=True, default="")
    unit = models.CharField(max_length=40, default="unit")
    reorder_level = models.PositiveIntegerField(default=0)
    controlled = models.BooleanField(default=False)
    requires_cold_chain = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["organization", "sku"], name="unique_inventory_sku")]

    @property
    def quantity_on_hand(self):
        return sum(batch.quantity_available for batch in self.batches.all())


class InventoryBatch(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=100)
    expiry_date = models.DateField(null=True, blank=True)
    quantity_received = models.PositiveIntegerField(default=0)
    quantity_available = models.PositiveIntegerField(default=0)
    unit_cost = models.PositiveBigIntegerField(default=0)
    selling_price = models.PositiveBigIntegerField(default=0)
    storage_location = models.CharField(max_length=120, blank=True, default="")
    supplier_name = models.CharField(max_length=180, blank=True, default="")
    received_at = models.DateTimeField(default=timezone.now)
    recalled = models.BooleanField(default=False)
    recall_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["expiry_date", "received_at"]
        constraints = [models.UniqueConstraint(fields=["item", "batch_number"], name="unique_inventory_batch")]


class StockMovement(models.Model):
    class Type(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        DISPENSE = "dispense", "Dispense"
        ISSUE = "issue", "Department issue"
        TRANSFER = "transfer", "Transfer"
        ADJUSTMENT = "adjustment", "Adjustment"
        RETURN = "return", "Return"
        EXPIRED = "expired", "Expired"
        DAMAGE = "damage", "Damaged"
        RECALL = "recall", "Recall"

    batch = models.ForeignKey(InventoryBatch, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=24, choices=Type.choices)
    quantity = models.IntegerField()
    balance_after = models.IntegerField()
    reason = models.TextField(blank=True, default="")
    reference = models.CharField(max_length=120, blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="stock_movements")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        ORDERED = "ordered", "Ordered"
        PART_RECEIVED = "part_received", "Part received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="purchase_orders")
    supplier_name = models.CharField(max_length=220)
    supplier_contact = models.CharField(max_length=160, blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    expected_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_purchase_orders")
    approved_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_purchase_orders")
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"PO-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        return sum(item.quantity * item.unit_cost for item in self.items.all())


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    inventory_item = models.ForeignKey(InventoryItem, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchase_order_items")
    description = models.CharField(max_length=220)
    quantity = models.PositiveIntegerField()
    unit_cost = models.PositiveBigIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)


class SubscriptionPlan(models.Model):
    class Audience(models.TextChoices):
        PATIENT = "patient", "Patient"
        PROFESSIONAL = "professional", "Professional"
        ORGANIZATION = "organization", "Organization"

    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=140)
    audience = models.CharField(max_length=20, choices=Audience.choices)
    price = models.PositiveBigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="UGX")
    billing_cycle = models.CharField(max_length=20, choices=[("monthly", "Monthly"), ("quarterly", "Quarterly"), ("annual", "Annual")], default="monthly")
    description = models.TextField(blank=True, default="")
    features = models.JSONField(default=list, blank=True)
    limits = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["audience", "price"]


class AccountSubscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.CASCADE, related_name="account_subscriptions")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    provider_reference = models.CharField(max_length=160, blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.CheckConstraint(check=models.Q(user__isnull=False) | models.Q(organization__isnull=False), name="subscription_has_owner")]


class SupportTicket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING_USER = "waiting_user", "Waiting for user"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    number = models.CharField(max_length=40, unique=True, blank=True)
    requester = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="support_tickets")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="support_tickets")
    category = models.CharField(max_length=60, default="general")
    priority = models.CharField(max_length=20, choices=[("low", "Low"), ("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")], default="normal")
    subject = models.CharField(max_length=220)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_support_tickets")
    resolution = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"SUP-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class Announcement(models.Model):
    class Audience(models.TextChoices):
        ALL = "all", "Everyone"
        PATIENTS = "patients", "Patients"
        PROFESSIONALS = "professionals", "Health professionals"
        ORGANIZATIONS = "organizations", "Organizations"
        STAFF = "staff", "Facility staff"

    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="announcements")
    audience = models.CharField(max_length=24, choices=Audience.choices, default=Audience.ALL)
    title = models.CharField(max_length=220)
    body = models.TextField()
    severity = models.CharField(max_length=20, choices=[("info", "Information"), ("success", "Success"), ("warning", "Warning"), ("critical", "Critical")], default="info")
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_announcements")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-starts_at"]


class EmergencyCase(models.Model):
    class Acuity(models.TextChoices):
        RESUSCITATION = "resuscitation", "Resuscitation"
        EMERGENT = "emergent", "Emergent"
        URGENT = "urgent", "Urgent"
        LESS_URGENT = "less_urgent", "Less urgent"
        NON_URGENT = "non_urgent", "Non-urgent"

    class Status(models.TextChoices):
        ARRIVED = "arrived", "Arrived"
        TRIAGED = "triaged", "Triaged"
        IN_TREATMENT = "in_treatment", "In treatment"
        OBSERVATION = "observation", "Observation"
        REFERRED = "referred", "Referred"
        ADMITTED = "admitted", "Admitted"
        DISCHARGED = "discharged", "Discharged"
        LEFT = "left", "Left before completion"
        DECEASED = "deceased", "Deceased"

    case_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="emergency_cases")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="emergency_cases")
    visit = models.ForeignKey("workforce.PatientVisit", null=True, blank=True, on_delete=models.SET_NULL, related_name="emergency_cases")
    arrival_mode = models.CharField(max_length=30, choices=[("walk_in", "Walk in"), ("ambulance", "Ambulance"), ("referral", "Referral"), ("police", "Police"), ("other", "Other")], default="walk_in")
    acuity = models.CharField(max_length=24, choices=Acuity.choices, default=Acuity.URGENT)
    chief_complaint = models.TextField()
    triage_notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ARRIVED)
    assigned_clinician = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_emergency_cases")
    disposition = models.CharField(max_length=180, blank=True, default="")
    arrival_at = models.DateTimeField(default=timezone.now)
    treatment_started_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_emergency_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-arrival_at"]
        indexes = [models.Index(fields=["organization", "status", "arrival_at"], name="operations_ed_org_status_idx"), models.Index(fields=["patient", "arrival_at"], name="operations_ed_patient_idx")]

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = f"ED-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class AmbulanceDispatch(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ASSIGNED = "assigned", "Assigned"
        EN_ROUTE = "en_route", "En route"
        ON_SCENE = "on_scene", "On scene"
        TRANSPORTING = "transporting", "Transporting"
        ARRIVED = "arrived", "Arrived at destination"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    dispatch_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="ambulance_dispatches")
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="ambulance_dispatches")
    caller_name = models.CharField(max_length=180)
    caller_phone = models.CharField(max_length=40)
    pickup_location = models.TextField()
    destination = models.TextField(blank=True, default="")
    priority = models.CharField(max_length=20, choices=[("routine", "Routine"), ("urgent", "Urgent"), ("critical", "Critical")], default="urgent")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REQUESTED)
    dispatcher = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="dispatched_ambulances")
    paramedic = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="paramedic_dispatches")
    ambulance_identifier = models.CharField(max_length=80, blank=True, default="")
    pickup_coordinates = models.JSONField(blank=True, default=dict)
    destination_coordinates = models.JSONField(blank=True, default=dict)
    clinical_notes = models.TextField(blank=True, default="")
    requested_at = models.DateTimeField(default=timezone.now)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    arrived_scene_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [models.Index(fields=["organization", "status", "requested_at"], name="operations_amb_org_status_idx")]

    def save(self, *args, **kwargs):
        if not self.dispatch_number:
            self.dispatch_number = f"AMB-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class SurgicalCase(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        SCHEDULED = "scheduled", "Scheduled"
        PRE_OP = "pre_op", "Pre-operative"
        IN_THEATRE = "in_theatre", "In theatre"
        RECOVERY = "recovery", "Recovery"
        COMPLETED = "completed", "Completed"
        POSTPONED = "postponed", "Postponed"
        CANCELLED = "cancelled", "Cancelled"

    case_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="surgical_cases")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="surgical_cases")
    admission = models.ForeignKey(Admission, null=True, blank=True, on_delete=models.SET_NULL, related_name="surgical_cases")
    procedure_name = models.CharField(max_length=240)
    preoperative_diagnosis = models.TextField()
    postoperative_diagnosis = models.TextField(blank=True, default="")
    surgeon = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="surgeon_cases")
    anaesthetist = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="anaesthesia_cases")
    theatre_nurse = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="theatre_nurse_cases")
    theatre_name = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REQUESTED)
    urgency = models.CharField(max_length=20, choices=[("elective", "Elective"), ("urgent", "Urgent"), ("emergency", "Emergency")], default="elective")
    consent_obtained = models.BooleanField(default=False)
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    operation_notes = models.TextField(blank=True, default="")
    anaesthesia_notes = models.TextField(blank=True, default="")
    complications = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_surgical_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_start", "-created_at"]
        indexes = [models.Index(fields=["organization", "status", "scheduled_start"], name="operations_surg_org_idx")]

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = f"SURG-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class SurgicalChecklist(models.Model):
    surgical_case = models.OneToOneField(SurgicalCase, on_delete=models.CASCADE, related_name="checklist")
    patient_identity_confirmed = models.BooleanField(default=False)
    procedure_confirmed = models.BooleanField(default=False)
    site_marked = models.BooleanField(default=False)
    consent_confirmed = models.BooleanField(default=False)
    allergies_reviewed = models.BooleanField(default=False)
    anaesthesia_safety_check = models.BooleanField(default=False)
    antibiotic_prophylaxis = models.BooleanField(default=False)
    team_introduction_complete = models.BooleanField(default=False)
    instrument_count_complete = models.BooleanField(default=False)
    specimen_labelled = models.BooleanField(default=False)
    recovery_plan_confirmed = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    completed_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="completed_surgical_checklists")
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def completion_percent(self):
        names = [
            "patient_identity_confirmed", "procedure_confirmed", "site_marked", "consent_confirmed",
            "allergies_reviewed", "anaesthesia_safety_check", "antibiotic_prophylaxis",
            "team_introduction_complete", "instrument_count_complete", "specimen_labelled",
            "recovery_plan_confirmed",
        ]
        return round(sum(bool(getattr(self, name)) for name in names) * 100 / len(names))


class MaternityEpisode(models.Model):
    class Status(models.TextChoices):
        ANTENATAL = "antenatal", "Antenatal"
        ADMITTED = "admitted", "Admitted"
        IN_LABOUR = "in_labour", "In labour"
        DELIVERED = "delivered", "Delivered"
        POSTNATAL = "postnatal", "Postnatal"
        DISCHARGED = "discharged", "Discharged"
        REFERRED = "referred", "Referred"

    episode_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="maternity_episodes")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="maternity_episodes")
    admission = models.ForeignKey(Admission, null=True, blank=True, on_delete=models.SET_NULL, related_name="maternity_episodes")
    gravida = models.PositiveSmallIntegerField(default=1)
    para = models.PositiveSmallIntegerField(default=0)
    expected_delivery_date = models.DateField(null=True, blank=True)
    gestational_age_weeks = models.PositiveSmallIntegerField(null=True, blank=True)
    risk_level = models.CharField(max_length=20, choices=[("low", "Low"), ("moderate", "Moderate"), ("high", "High")], default="low")
    risk_notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.ANTENATAL)
    assigned_midwife = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="midwife_episodes")
    assigned_clinician = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="maternity_clinician_episodes")
    labour_started_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    delivery_method = models.CharField(max_length=60, blank=True, default="")
    birth_outcome = models.CharField(max_length=80, blank=True, default="")
    newborn_weight_grams = models.PositiveIntegerField(null=True, blank=True)
    apgar_one_minute = models.PositiveSmallIntegerField(null=True, blank=True)
    apgar_five_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    newborn_notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_maternity_episodes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status", "created_at"], name="operations_mat_org_status_idx")]

    def save(self, *args, **kwargs):
        if not self.episode_number:
            self.episode_number = f"MAT-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class StaffShift(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        ABSENT = "absent", "Absent"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="staff_shifts")
    staff = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="work_shifts")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="staff_shifts")
    shift_type = models.CharField(max_length=40, choices=[("day", "Day"), ("evening", "Evening"), ("night", "Night"), ("on_call", "On call"), ("custom", "Custom")], default="day")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    location = models.CharField(max_length=160, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_staff_shifts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["organization", "starts_at", "status"], name="operations_shift_org_idx"), models.Index(fields=["staff", "starts_at"], name="operations_shift_staff_idx")]

    def clean(self):
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Shift must end after it starts."})


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="leave_requests")
    staff = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=60, default="annual")
    starts_on = models.DateField()
    ends_on = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_leave_requests")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class QualityIncident(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        INVESTIGATING = "investigating", "Investigating"
        ACTION_REQUIRED = "action_required", "Action required"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    incident_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="quality_incidents")
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="quality_incidents")
    category = models.CharField(max_length=80, choices=[("medication", "Medication"), ("clinical", "Clinical care"), ("infection", "Infection prevention"), ("fall", "Patient fall"), ("privacy", "Privacy"), ("equipment", "Equipment"), ("service", "Service quality"), ("other", "Other")], default="clinical")
    severity = models.CharField(max_length=20, choices=[("low", "Low"), ("moderate", "Moderate"), ("high", "High"), ("critical", "Critical")], default="moderate")
    title = models.CharField(max_length=220)
    description = models.TextField()
    immediate_actions = models.TextField(blank=True, default="")
    root_cause = models.TextField(blank=True, default="")
    corrective_actions = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    occurred_at = models.DateTimeField(default=timezone.now)
    reported_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="reported_quality_incidents")
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_quality_incidents")
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["organization", "status", "severity"], name="operations_qi_org_status_idx")]

    def save(self, *args, **kwargs):
        if not self.incident_number:
            self.incident_number = f"QI-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        super().save(*args, **kwargs)


class PrivacyRequest(models.Model):
    class Type(models.TextChoices):
        ACCESS = "access", "Data access"
        CORRECTION = "correction", "Data correction"
        EXPORT = "export", "Data export"
        RESTRICTION = "restriction", "Restrict processing"
        DELETION = "deletion", "Deletion request"
        COMPLAINT = "complaint", "Privacy complaint"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        VERIFYING = "verifying", "Verifying identity"
        IN_PROGRESS = "in_progress", "In progress"
        WAITING = "waiting", "Waiting for requester"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"

    request_number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="privacy_requests")
    requester = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="privacy_requests")
    requester_email = models.EmailField(blank=True, default="")
    request_type = models.CharField(max_length=24, choices=Type.choices)
    details = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.RECEIVED)
    identity_verified = models.BooleanField(default=False)
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_privacy_requests")
    due_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True, default="")
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["organization", "status", "created_at"], name="operations_priv_org_status_idx")]

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = f"PRIV-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:7].upper()}"
        if not self.requester_email and self.requester_id:
            self.requester_email = self.requester.email
        super().save(*args, **kwargs)
