"""Operational extensions. Existing clinical and financial records remain authoritative."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .storage import private_storage

USER = settings.AUTH_USER_MODEL


class Record(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OrganizationRecord(Record):
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT)
    created_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")

    class Meta:
        abstract = True


class WorkflowEvent(models.Model):
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, null=True, blank=True)
    resource_type = models.CharField(max_length=80)
    resource_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=80)
    actor = models.ForeignKey(USER, on_delete=models.PROTECT)
    data = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class Admission(OrganizationRecord):
    visit = models.ForeignKey("workforce.PatientVisit", on_delete=models.PROTECT, null=True, blank=True, related_name="admissions")
    patient = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="admissions")
    attending_doctor = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="inpatients")
    bed = models.ForeignKey("services.Bed", on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[("admitted", "Admitted"), ("discharged", "Discharged")], default="admitted")
    reason = models.TextField()
    admitted_at = models.DateTimeField(default=timezone.now)
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharge_summary = models.TextField(blank=True)
    follow_up = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["bed"], condition=models.Q(status="admitted", bed__isnull=False), name="one_active_admission_per_bed"),
            models.UniqueConstraint(fields=["patient"], condition=models.Q(status="admitted"), name="one_active_admission_per_patient"),
        ]


class MedicationSchedule(OrganizationRecord):
    admission = models.ForeignKey(Admission, on_delete=models.PROTECT, related_name="medication_schedules")
    prescription = models.ForeignKey("prescriptions.Prescription", on_delete=models.PROTECT)
    medication_name = models.CharField(max_length=250)
    dose = models.CharField(max_length=120)
    route = models.CharField(max_length=80)
    due_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("scheduled", "given", "withheld", "refused", "cancelled")], default="scheduled")
    administered_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="inpatient_doses")
    administered_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["admission", "prescription", "medication_name", "due_at"], name="unique_inpatient_scheduled_dose")]


class ProcedureBooking(OrganizationRecord):
    patient = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="procedures")
    admission = models.ForeignKey(Admission, on_delete=models.PROTECT, null=True, blank=True)
    surgeon = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="procedure_bookings")
    theatre = models.CharField(max_length=120)
    procedure = models.CharField(max_length=250)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("scheduled", "in_progress", "completed", "cancelled")], default="scheduled")
    notes = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F("starts_at")), name="procedure_positive_duration")]


class MedicineBatch(OrganizationRecord):
    medicine = models.ForeignKey("services.Medicine", on_delete=models.PROTECT, related_name="batches")
    supplier = models.ForeignKey("services.Supplier", on_delete=models.PROTECT, null=True, blank=True)
    batch_number = models.CharField(max_length=120)
    expires_on = models.DateField()
    quantity = models.PositiveIntegerField(default=0)
    controlled = models.BooleanField(default=False)
    min_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_temperature = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("available", "quarantined", "recalled")], default="available")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["medicine", "batch_number"], name="unique_medicine_batch")]
        indexes = [models.Index(fields=["medicine", "status", "expires_on"])]


class StockMovement(models.Model):
    order = models.ForeignKey("services.Order", on_delete=models.PROTECT, null=True, blank=True, related_name="stock_movements")
    pharmacy_order = models.ForeignKey("services.PharmacyOrder", on_delete=models.PROTECT, null=True, blank=True, related_name="dispensing_movements")
    reversal_of = models.OneToOneField("self", on_delete=models.RESTRICT, null=True, blank=True, related_name="reversal")
    prescription_item = models.ForeignKey("prescriptions.PrescriptionItem", on_delete=models.PROTECT, null=True, blank=True, related_name="batch_movements")
    batch = models.ForeignKey(MedicineBatch, on_delete=models.PROTECT, related_name="movements")
    quantity = models.IntegerField()
    balance = models.PositiveIntegerField()
    kind = models.CharField(max_length=24, choices=[(x, x) for x in ("received", "dispensed", "adjusted", "returned", "destroyed")])
    reason = models.TextField()
    reference = models.UUIDField(default=uuid.uuid4, unique=True)
    patient = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="dispensed_stock")
    actor = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="stock_movements")
    witness = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="witnessed_stock_movements")
    occurred_at = models.DateTimeField(auto_now_add=True)


class TemperatureReading(models.Model):
    batch = models.ForeignKey(MedicineBatch, on_delete=models.PROTECT, related_name="temperatures")
    temperature = models.DecimalField(max_digits=6, decimal_places=2)
    observed_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(USER, on_delete=models.PROTECT)
    excursion = models.BooleanField(default=False)


class ReferralRoute(OrganizationRecord):
    referral = models.OneToOneField("clinical.Referral", on_delete=models.PROTECT, related_name="routing")
    assigned_to = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="received_referrals")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    outcome = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)


class BenefitRule(OrganizationRecord):
    policy = models.ForeignKey("services.InsurancePolicy", on_delete=models.PROTECT, related_name="benefit_rules")
    service_code = models.CharField(max_length=100)
    coverage_percent = models.PositiveSmallIntegerField()
    annual_limit = models.PositiveIntegerField()
    requires_authorization = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["policy", "service_code"], name="unique_policy_service_benefit"),
            models.CheckConstraint(condition=models.Q(coverage_percent__lte=100), name="benefit_percent_lte_100"),
        ]


class Preauthorization(OrganizationRecord):
    coverage = models.ForeignKey("services.PatientCoverage", on_delete=models.PROTECT)
    service_code = models.CharField(max_length=100)
    requested_amount = models.PositiveIntegerField()
    approved_amount = models.PositiveIntegerField(default=0)
    expires_on = models.DateField()
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("requested", "approved", "rejected")], default="requested")
    reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="authorizations_decided")


class ClaimAssessment(OrganizationRecord):
    claim = models.OneToOneField("services.InsuranceClaim", on_delete=models.PROTECT, related_name="assessment")
    service_code = models.CharField(max_length=100)
    authorization = models.ForeignKey(Preauthorization, on_delete=models.PROTECT, null=True, blank=True)
    covered_amount = models.PositiveIntegerField(default=0)
    patient_amount = models.PositiveIntegerField(default=0)
    decision = models.CharField(max_length=24, default="pending")
    rule_snapshot = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)


class Person(Record):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    given_name = models.CharField(max_length=150)
    family_name = models.CharField(max_length=150)
    birth_date = models.DateField(null=True, blank=True)
    merged_into = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True)
    version = models.PositiveIntegerField(default=1)


class PatientIdentity(Record):
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="patient_accounts")
    patient = models.OneToOneField(USER, on_delete=models.PROTECT, related_name="master_identity")


class PatientIdentifier(Record):
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="identifiers")
    system = models.CharField(max_length=200)
    value = models.CharField(max_length=150)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["system", "value"], name="unique_patient_identifier_namespace")]


class IdentityMerge(models.Model):
    source = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="merge_sources")
    target = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="merge_targets")
    reason = models.TextField()
    actor = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="identity_merges")
    created_at = models.DateTimeField(auto_now_add=True)
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="reversed_merges")
    reversal_reason = models.TextField(blank=True)


class ImagingOrder(OrganizationRecord):
    patient = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="imaging_orders")
    referring_doctor = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="requested_imaging")
    modality = models.CharField(max_length=20, choices=[(x, x) for x in ("CT", "MR", "US", "CR", "DX", "NM", "MG", "OT")])
    body_site = models.CharField(max_length=120)
    indication = models.TextField()
    accession_number = models.UUIDField(default=uuid.uuid4, unique=True)
    study_uid = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("ordered", "scheduled", "acquired", "reported", "cancelled")], default="ordered")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    report = models.TextField(blank=True)
    reported_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="reported_imaging")
    reported_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)


class ClinicalRule(Record):
    submitted_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="submitted_clinical_rules")
    code = models.CharField(max_length=100)
    version = models.PositiveIntegerField()
    kind = models.CharField(max_length=24, choices=[("interaction", "Interaction"), ("duplication", "Duplication")])
    medicine_a = models.CharField(max_length=250)
    medicine_b = models.CharField(max_length=250)
    severity = models.CharField(max_length=20, choices=[(x, x) for x in ("info", "warning", "critical")])
    message = models.TextField()
    evidence_url = models.URLField()
    approved_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_clinical_rules")
    active = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["code", "version"], name="unique_clinical_rule_version")]


class OfflineNode(OrganizationRecord):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True)
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)


class OfflineChange(Record):
    node = models.ForeignKey(OfflineNode, on_delete=models.PROTECT)
    change_id = models.UUIDField()
    patient = models.ForeignKey(USER, on_delete=models.PROTECT)
    kind = models.CharField(max_length=30, choices=[("observation", "Observation"), ("nursing_note", "Nursing note")])
    encrypted_payload = models.BinaryField()
    payload_digest = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("pending", "applied", "rejected")], default="pending")
    result_id = models.PositiveBigIntegerField(null=True, blank=True)
    reviewed_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="offline_reviews")
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["node", "change_id"], name="unique_offline_change_id")]


class PrivateDocument(OrganizationRecord):
    patient = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True)
    file = models.FileField(storage=private_storage, upload_to="private-documents/%Y/%m/", max_length=300)
    filename = models.CharField(max_length=180)
    sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=[(x, x) for x in ("pending", "clean", "infected", "failed")], default="pending")
    scanned_at = models.DateTimeField(null=True, blank=True)
    scan_detail = models.CharField(max_length=250, blank=True)


class VideoSession(Record):
    appointment = models.OneToOneField("appointments.Appointment", on_delete=models.PROTECT, related_name="video_session")
    room_id = models.UUIDField(default=uuid.uuid4, unique=True)
    recording_requested = models.BooleanField(default=False)
    patient_recording_consent = models.BooleanField(default=False)
    doctor_recording_consent = models.BooleanField(default=False)
    ended_at = models.DateTimeField(null=True, blank=True)


class VideoQualityEvent(models.Model):
    session = models.ForeignKey(VideoSession, on_delete=models.PROTECT, related_name="quality_events")
    actor = models.ForeignKey(USER, on_delete=models.PROTECT)
    packet_loss = models.FloatField()
    round_trip_ms = models.PositiveIntegerField()
    occurred_at = models.DateTimeField(auto_now_add=True)


class ResearchExport(Record):
    requested_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="research_exports")
    purpose = models.TextField()
    status = models.CharField(max_length=20, default="requested")
    approved_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="approved_research_exports")
    approved_at = models.DateTimeField(null=True, blank=True)
    data = models.JSONField(default=list, blank=True)


class CopilotModel(Record):
    submitted_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="submitted_copilot_models")
    name = models.CharField(max_length=100)
    version = models.CharField(max_length=100)
    adapter = models.CharField(max_length=200)
    intended_use = models.CharField(max_length=80, default="administrative_draft")
    evaluation_reference = models.CharField(max_length=300)
    approved_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True)
    active = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "version"], name="unique_copilot_model_version")]


class CopilotDraft(Record):
    model = models.ForeignKey(CopilotModel, on_delete=models.PROTECT)
    author = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="copilot_drafts")
    source_text = models.TextField()
    output = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="draft")
    reviewed_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="copilot_reviews")
    review_note = models.TextField(blank=True)


class PharmacyPurchase(OrganizationRecord):
    supplier = models.ForeignKey("services.Supplier", on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default="draft")
    status_reason = models.CharField(max_length=2000, blank=True)


class PharmacyPurchaseLine(models.Model):
    purchase = models.ForeignKey(PharmacyPurchase, on_delete=models.PROTECT, related_name="lines")
    medicine = models.ForeignKey("services.Medicine", on_delete=models.PROTECT)
    ordered = models.PositiveIntegerField()
    received = models.PositiveIntegerField(default=0)
    unit_cost = models.PositiveIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["purchase", "medicine"], name="unique_pharmacy_purchase_medicine")]


class PharmacyPurchaseReceipt(models.Model):
    line = models.ForeignKey(PharmacyPurchaseLine, on_delete=models.PROTECT, related_name="receipts")
    movement = models.OneToOneField(StockMovement, on_delete=models.PROTECT)

    class Meta:
        ordering = ["pk"]


class PharmacyStockCount(OrganizationRecord):
    batch = models.ForeignKey(MedicineBatch, on_delete=models.PROTECT)
    expected = models.PositiveIntegerField()
    counted = models.PositiveIntegerField()
    batch_updated_at = models.DateTimeField()
    reason = models.CharField(max_length=2000)
    status = models.CharField(max_length=20, default="pending")
    reviewed_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, related_name="+")
    review_reason = models.CharField(max_length=2000, blank=True)
    adjustment = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True)


class PharmacyFormularyEntry(OrganizationRecord):
    medicine = models.ForeignKey("services.Medicine", on_delete=models.PROTECT)
    strength = models.CharField(max_length=120)
    dosage_form = models.CharField(max_length=120)
    register_entry = models.ForeignKey("interoperability.TerminologyConcept", on_delete=models.PROTECT, null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "medicine"], name="unique_pharmacy_formulary_medicine")]


class PharmacyPrescriptionReview(Record):
    order = models.OneToOneField("services.PharmacyOrder", on_delete=models.PROTECT, related_name="safety_review")
    reviewer = models.ForeignKey(USER, on_delete=models.PROTECT)
    notes = models.TextField()
    counselling = models.TextField()
    medication_check = models.JSONField(default=dict)
    product_ids = models.JSONField(default=dict)
    prescription_version = models.PositiveIntegerField()


class PharmacySubstitution(Record):
    order = models.ForeignKey("services.PharmacyOrder", on_delete=models.PROTECT, related_name="substitutions")
    item = models.ForeignKey("prescriptions.PrescriptionItem", on_delete=models.PROTECT)
    replacement = models.ForeignKey("services.Medicine", on_delete=models.PROTECT)
    requested_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    reason = models.TextField()
    status = models.CharField(max_length=20, default="pending")
    decided_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, related_name="+")
    decision_note = models.TextField(blank=True)
    prescription_version = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "item"], condition=models.Q(status__in=["pending", "approved"]),
                                    name="unique_current_pharmacy_substitution"),
        ]


class PharmacyReturn(OrganizationRecord):
    movement = models.ForeignKey(StockMovement, on_delete=models.PROTECT, related_name="patient_returns")
    quantity = models.PositiveIntegerField()
    reason = models.TextField()
    disposition = models.CharField(max_length=30, default="segregated")
    disposition_note = models.TextField(blank=True)
    intake_witness = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    disposition_witness = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    resolved_by = models.ForeignKey(USER, on_delete=models.PROTECT, null=True, blank=True, related_name="+")


class PharmacyRecallContact(OrganizationRecord):
    batch = models.ForeignKey(MedicineBatch, on_delete=models.PROTECT)
    patient = models.ForeignKey(USER, on_delete=models.PROTECT)
    status = models.CharField(max_length=24, default="pending")
    notes = models.TextField(blank=True)
    notified_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["batch", "patient"], name="unique_recall_batch_patient")]


class PharmacySafetyReport(OrganizationRecord):
    kind = models.CharField(max_length=24, choices=[("medication_error", "Medication error"), ("adverse_reaction", "Adverse reaction"), ("quality_defect", "Quality defect")])
    movement = models.ForeignKey(StockMovement, on_delete=models.PROTECT, null=True, blank=True)
    description = models.TextField()
    state = models.CharField(max_length=16, default="open")
    external_reference = models.CharField(max_length=200, blank=True)
    resolution = models.TextField(blank=True)


class PharmacyTransfer(OrganizationRecord):
    source = models.ForeignKey(MedicineBatch, on_delete=models.PROTECT, related_name="+")
    destination = models.ForeignKey(MedicineBatch, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=20, default="requested")
    dispatch = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    receipt = models.OneToOneField(StockMovement, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
