import hashlib
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

AUTH_USER = settings.AUTH_USER_MODEL


def generate_client_id():
    return secrets.token_urlsafe(24)


class RoleContext(models.Model):
    """A user's role in a specific organization, branch and department.

    This is the canonical multi-role model. ``accounts.User.role`` remains only a
    backwards-compatible default role; authorization should use the active context.
    """

    user = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="role_contexts")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="role_contexts")
    location = models.ForeignKey("registry.OrganizationLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="role_contexts")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="role_contexts")
    role_code = models.CharField(max_length=64)
    title = models.CharField(max_length=160, blank=True, default="")
    permissions = models.JSONField(default=list, blank=True)
    is_primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_role_contexts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user_id", "-is_primary", "role_code"]
        constraints = [
            models.UniqueConstraint(fields=["user", "organization", "location", "department", "role_code"], name="unique_enterprise_role_context")
        ]
        indexes = [
            models.Index(fields=["user", "active"], name="ent_ctx_user_active"),
            models.Index(fields=["organization", "role_code", "active"], name="ent_ctx_org_role"),
        ]

    @property
    def is_current(self):
        today = timezone.localdate()
        return self.active and (not self.starts_on or self.starts_on <= today) and (not self.ends_on or self.ends_on >= today)

    def clean(self):
        if self.location_id and self.organization_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "The selected branch belongs to another organization."})
        if self.department_id and self.organization_id and self.department.organization_id != self.organization_id:
            raise ValidationError({"department": "The selected department belongs to another organization."})
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "Role end date cannot precede its start date."})

    def __str__(self):
        scope = self.organization.legal_name if self.organization_id else "Platform"
        return f"{self.user.email} · {self.role_code} · {scope}"


class ActiveRoleContext(models.Model):
    user = models.OneToOneField(AUTH_USER, on_delete=models.CASCADE, related_name="active_role_context")
    context = models.ForeignKey(RoleContext, on_delete=models.CASCADE, related_name="active_for_users")
    activated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.context_id and self.context.user_id != self.user_id:
            raise ValidationError({"context": "A user can activate only their own role context."})
        if self.context_id and not self.context.is_current:
            raise ValidationError({"context": "This role context is inactive or expired."})


class RoleDelegation(models.Model):
    delegator_context = models.ForeignKey(RoleContext, on_delete=models.CASCADE, related_name="delegations_given")
    delegatee_context = models.ForeignKey(RoleContext, on_delete=models.CASCADE, related_name="delegations_received")
    permissions = models.JSONField(default=list, blank=True)
    reason = models.TextField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    approved_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_role_delegations")
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["delegatee_context", "starts_at", "ends_at"], name="ent_delegate_window")]

    def clean(self):
        if self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": "Delegation must end after it starts."})
        if self.delegator_context_id == self.delegatee_context_id:
            raise ValidationError("A role context cannot delegate to itself.")


class EnterpriseRecord(models.Model):
    """Schema-driven clinical, operational and administrative record.

    Each ``record_type`` has a strict payload schema in ``enterprise.schemas``.
    This provides a scalable extension layer for detailed hospital workflows while
    retaining proper patient, organization, assignment, status and audit columns.
    """

    class Domain(models.TextChoices):
        INPATIENT = "inpatient", "Inpatient care"
        MATERNITY = "maternity", "Maternity and child health"
        THEATRE = "theatre", "Theatre and anaesthesia"
        EMERGENCY = "emergency", "Emergency and ambulance"
        LABORATORY = "laboratory", "Advanced laboratory"
        RADIOLOGY = "radiology", "Radiology and imaging"
        PHARMACY = "pharmacy", "Pharmacy safety"
        FINANCE = "finance", "Finance and accounting"
        INSURANCE = "insurance", "Insurance operations"
        RECORDS = "records", "Medical records"
        SPECIALIST = "specialist", "Specialist clinical care"
        VERIFICATION = "verification", "Verification automation"
        SECURITY = "security", "Security and resilience"
        REPORTING = "reporting", "Analytics and reporting"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        ROUTINE = "routine", "Routine"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"
        CRITICAL = "critical", "Critical"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    reference = models.CharField(max_length=48, unique=True, blank=True)
    domain = models.CharField(max_length=24, choices=Domain.choices)
    record_type = models.CharField(max_length=80)
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="enterprise_records")
    location = models.ForeignKey("registry.OrganizationLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_records")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_records")
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.PROTECT, related_name="enterprise_patient_records")
    admission = models.ForeignKey("operations.Admission", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_records")
    appointment = models.ForeignKey("appointments.Appointment", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_records")
    owner = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_enterprise_records")
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_enterprise_records")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    status = models.CharField(max_length=40, default="draft")
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.ROUTINE)
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    sensitive = models.BooleanField(default=False)
    occurred_at = models.DateTimeField(default=timezone.now)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_enterprise_records")
    updated_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_enterprise_records")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["domain", "record_type", "status"], name="ent_record_type_status"),
            models.Index(fields=["organization", "domain", "created_at"], name="ent_record_org_domain"),
            models.Index(fields=["patient", "domain", "occurred_at"], name="ent_record_patient_time"),
            models.Index(fields=["assigned_to", "status", "due_at"], name="ent_record_assignee"),
            models.Index(fields=["reference"], name="ent_record_reference"),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = (self.record_type or self.domain or "REC").replace("_", "-")[:12].upper()
            self.reference = f"{prefix}-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        from .schemas import validate_record
        validate_record(self.domain, self.record_type, self.payload)
        if self.patient_id and getattr(self.patient, "role", None) != "patient":
            raise ValidationError({"patient": "The linked patient must have a patient account."})
        if self.location_id and self.organization_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "The branch belongs to another organization."})

    def __str__(self):
        return f"{self.reference} · {self.title}"


class WorkflowTransition(models.Model):
    record = models.ForeignKey(EnterpriseRecord, on_delete=models.CASCADE, related_name="transitions")
    action = models.CharField(max_length=80)
    from_status = models.CharField(max_length=40, blank=True, default="")
    to_status = models.CharField(max_length=40)
    reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_transitions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ResourceAttachment(models.Model):
    class MalwareStatus(models.TextChoices):
        PENDING = "pending", "Pending scan"
        CLEAN = "clean", "Clean"
        INFECTED = "infected", "Infected"
        ERROR = "error", "Scan error"

    record = models.ForeignKey(EnterpriseRecord, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="enterprise/records/%Y/%m/")
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=80, blank=True, default="")
    visibility = models.CharField(max_length=24, default="care_team")
    checksum_sha256 = models.CharField(max_length=64, blank=True, default="")
    malware_status = models.CharField(max_length=16, choices=MalwareStatus.choices, default=MalwareStatus.PENDING)
    uploaded_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_attachments")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.file and not self.checksum_sha256:
            digest = hashlib.sha256()
            for chunk in self.file.chunks():
                digest.update(chunk)
            self.checksum_sha256 = digest.hexdigest()
            try:
                self.file.seek(0)
            except Exception:
                pass
        super().save(*args, **kwargs)


class ClinicalCode(models.Model):
    system = models.CharField(max_length=40)
    version = models.CharField(max_length=40, blank=True, default="")
    code = models.CharField(max_length=80)
    display = models.CharField(max_length=260)
    description = models.TextField(blank=True, default="")
    category = models.CharField(max_length=80, blank=True, default="")
    active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["system", "code"]
        constraints = [models.UniqueConstraint(fields=["system", "version", "code"], name="unique_enterprise_clinical_code")]
        indexes = [models.Index(fields=["system", "code", "active"], name="ent_code_system_active")]


class TariffSchedule(models.Model):
    payer = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="tariff_schedules")
    provider = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="provider_tariff_schedules")
    name = models.CharField(max_length=180)
    currency = models.CharField(max_length=3, default="UGX")
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    items = models.JSONField(default=list, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PayerContract(models.Model):
    payer = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="payer_contracts")
    provider = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="provider_contracts")
    contract_number = models.CharField(max_length=100)
    status = models.CharField(max_length=24, default="active")
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    tariff = models.ForeignKey(TariffSchedule, null=True, blank=True, on_delete=models.SET_NULL, related_name="contracts")
    terms = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["payer", "provider", "contract_number"], name="unique_enterprise_payer_contract")]


class MedicationKnowledge(models.Model):
    generic_name = models.CharField(max_length=180)
    brand_names = models.JSONField(default=list, blank=True)
    atc_code = models.CharField(max_length=30, blank=True, default="")
    strengths = models.JSONField(default=list, blank=True)
    dosage_forms = models.JSONField(default=list, blank=True)
    contraindications = models.JSONField(default=list, blank=True)
    pregnancy_category = models.CharField(max_length=40, blank=True, default="")
    renal_guidance = models.TextField(blank=True, default="")
    hepatic_guidance = models.TextField(blank=True, default="")
    max_dose_guidance = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["generic_name"]


class MedicationInteraction(models.Model):
    medicine_a = models.ForeignKey(MedicationKnowledge, on_delete=models.CASCADE, related_name="interactions_as_a")
    medicine_b = models.ForeignKey(MedicationKnowledge, on_delete=models.CASCADE, related_name="interactions_as_b")
    severity = models.CharField(max_length=20, choices=[("minor", "Minor"), ("moderate", "Moderate"), ("major", "Major"), ("contraindicated", "Contraindicated")])
    mechanism = models.TextField(blank=True, default="")
    clinical_effect = models.TextField()
    management = models.TextField()
    evidence = models.CharField(max_length=80, blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["medicine_a", "medicine_b"], name="unique_enterprise_medication_interaction")]


class PACSNode(models.Model):
    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="pacs_nodes")
    name = models.CharField(max_length=140)
    ae_title = models.CharField(max_length=32)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=104)
    dicomweb_base_url = models.URLField(blank=True, default="")
    tls_enabled = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    last_echo_at = models.DateTimeField(null=True, blank=True)
    last_echo_ok = models.BooleanField(default=False)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "ae_title"], name="unique_enterprise_pacs_ae_title")]


class ImagingStudy(models.Model):
    study_instance_uid = models.CharField(max_length=128, unique=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="enterprise_imaging_studies")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="enterprise_imaging_studies")
    imaging_order = models.ForeignKey("operations.ImagingOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_studies")
    pacs_node = models.ForeignKey(PACSNode, null=True, blank=True, on_delete=models.SET_NULL, related_name="studies")
    accession_number = models.CharField(max_length=80, blank=True, default="")
    modality = models.CharField(max_length=24)
    description = models.CharField(max_length=240)
    study_date = models.DateTimeField(null=True, blank=True)
    series_count = models.PositiveIntegerField(default=0)
    instance_count = models.PositiveIntegerField(default=0)
    viewer_url = models.URLField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AmbulanceVehicle(models.Model):
    organization = models.ForeignKey("registry.Organization", on_delete=models.CASCADE, related_name="ambulance_vehicles")
    call_sign = models.CharField(max_length=60)
    registration_number = models.CharField(max_length=60)
    vehicle_type = models.CharField(max_length=40, default="basic_life_support")
    status = models.CharField(max_length=24, default="available")
    crew = models.ManyToManyField(AUTH_USER, blank=True, related_name="ambulance_assignments")
    equipment = models.JSONField(default=list, blank=True)
    last_service_on = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "registration_number"], name="unique_enterprise_ambulance_registration")]


class AmbulanceTelemetry(models.Model):
    vehicle = models.ForeignKey(AmbulanceVehicle, on_delete=models.CASCADE, related_name="telemetry")
    dispatch = models.ForeignKey("operations.AmbulanceDispatch", null=True, blank=True, on_delete=models.SET_NULL, related_name="telemetry")
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kph = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    heading = models.PositiveSmallIntegerField(default=0)
    accuracy_m = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["vehicle", "recorded_at"], name="ent_vehicle_recorded")]


class PresenceState(models.Model):
    user = models.OneToOneField(AUTH_USER, on_delete=models.CASCADE, related_name="presence_state")
    status = models.CharField(max_length=24, default="offline")
    current_context = models.ForeignKey(RoleContext, null=True, blank=True, on_delete=models.SET_NULL, related_name="presence_states")
    connection_count = models.PositiveIntegerField(default=0)
    last_seen_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)


class MessageReceipt(models.Model):
    message = models.ForeignKey("communication.Message", on_delete=models.CASCADE, related_name="receipts")
    user = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="message_receipts")
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    device_id = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["message", "user"], name="unique_enterprise_message_receipt")]


class TelemedicineSession(models.Model):
    class Mode(models.TextChoices):
        VIDEO = "video", "Video"
        AUDIO = "audio", "Audio"

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    appointment = models.OneToOneField("appointments.Appointment", null=True, blank=True, on_delete=models.SET_NULL, related_name="enterprise_telemedicine_session")
    provider = models.CharField(max_length=24, default="jitsi")
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.VIDEO)
    external_id = models.CharField(max_length=180, blank=True, default="")
    join_url = models.URLField(blank=True, default="")
    host_url = models.URLField(blank=True, default="")
    status = models.CharField(max_length=24, default="scheduled")
    scheduled_start = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    waiting_room_enabled = models.BooleanField(default=True)
    recording_enabled = models.BooleanField(default=False)
    recording_consent_required = models.BooleanField(default=True)
    encryption_mode = models.CharField(max_length=40, default="transport")
    quality_metrics = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TelemedicineParticipant(models.Model):
    session = models.ForeignKey(TelemedicineSession, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="telemedicine_participations")
    role = models.CharField(max_length=32)
    waiting_status = models.CharField(max_length=24, default="invited")
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    recording_consent = models.BooleanField(default=False)
    consented_at = models.DateTimeField(null=True, blank=True)
    network_metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "user"], name="unique_enterprise_telemedicine_participant")]


class NotificationProvider(models.Model):
    channel = models.CharField(max_length=24, choices=[("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp"), ("push", "Push"), ("voice", "Voice")])
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=80)
    priority = models.PositiveSmallIntegerField(default=100)
    active = models.BooleanField(default=True)
    credentials_reference = models.CharField(max_length=240, blank=True, default="")
    configuration = models.JSONField(default=dict, blank=True)
    cost_per_message = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    currency = models.CharField(max_length=3, default="UGX")
    health_status = models.CharField(max_length=24, default="unknown")
    last_health_check_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["channel", "priority"]
        constraints = [models.UniqueConstraint(fields=["channel", "name"], name="unique_enterprise_notification_provider")]


class CommunicationConsent(models.Model):
    user = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="enterprise_communication_consents")
    channel = models.CharField(max_length=24)
    purpose = models.CharField(max_length=80)
    granted = models.BooleanField(default=True)
    source = models.CharField(max_length=80, blank=True, default="")
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "channel", "purpose"], name="unique_enterprise_communication_consent")]


class EscalationPolicy(models.Model):
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="notification_escalation_policies")
    name = models.CharField(max_length=160)
    event_type = models.CharField(max_length=100)
    conditions = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EscalationStep(models.Model):
    policy = models.ForeignKey(EscalationPolicy, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField()
    delay_minutes = models.PositiveIntegerField(default=0)
    channel = models.CharField(max_length=24)
    target_type = models.CharField(max_length=32, default="assigned_user")
    target = models.CharField(max_length=180, blank=True, default="")
    template_code = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        ordering = ["policy", "order"]
        constraints = [models.UniqueConstraint(fields=["policy", "order"], name="unique_enterprise_escalation_step")]


class EventSchema(models.Model):
    name = models.CharField(max_length=140)
    version = models.PositiveIntegerField(default=1)
    subject = models.CharField(max_length=180)
    json_schema = models.JSONField(default=dict)
    compatibility = models.CharField(max_length=24, default="backward")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["name", "version"], name="unique_enterprise_event_schema")]


class IntegrationEndpoint(models.Model):
    name = models.CharField(max_length=140)
    endpoint_type = models.CharField(max_length=32, choices=[("webhook", "Webhook"), ("kafka", "Kafka"), ("rabbitmq", "RabbitMQ"), ("fhir", "FHIR"), ("sftp", "SFTP"), ("warehouse", "Warehouse")])
    base_url = models.CharField(max_length=500, blank=True, default="")
    topic = models.CharField(max_length=180, blank=True, default="")
    credentials_reference = models.CharField(max_length=240, blank=True, default="")
    configuration = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    health_status = models.CharField(max_length=24, default="unknown")
    last_health_check_at = models.DateTimeField(null=True, blank=True)


class EventDelivery(models.Model):
    event = models.ForeignKey("interoperability.OutboxEvent", on_delete=models.CASCADE, related_name="enterprise_deliveries")
    endpoint = models.ForeignKey(IntegrationEndpoint, on_delete=models.CASCADE, related_name="deliveries")
    schema = models.ForeignKey(EventSchema, null=True, blank=True, on_delete=models.SET_NULL, related_name="deliveries")
    status = models.CharField(max_length=24, default="pending")
    attempt_count = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True, default="")
    idempotency_key = models.CharField(max_length=180, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DeadLetterEvent(models.Model):
    delivery = models.OneToOneField(EventDelivery, on_delete=models.CASCADE, related_name="dead_letter")
    reason = models.TextField()
    payload_snapshot = models.JSONField(default=dict)
    quarantined_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(blank=True, default="")
    resolved_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="resolved_dead_letters")


class ReplayRequest(models.Model):
    endpoint = models.ForeignKey(IntegrationEndpoint, on_delete=models.CASCADE, related_name="replay_requests")
    filters = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="pending")
    requested_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="event_replay_requests")
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    replayed_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)


class ContentEntry(models.Model):
    class Type(models.TextChoices):
        PAGE = "page", "Page"
        BANNER = "banner", "Banner"
        PROMOTION = "promotion", "Promotion"
        FAQ = "faq", "FAQ"
        TEMPLATE = "template", "Communication template"
        CATEGORY = "category", "Service category"
        LEGAL = "legal", "Legal content"

    content_type = models.CharField(max_length=24, choices=Type.choices)
    slug = models.SlugField(max_length=180)
    locale = models.CharField(max_length=12, default="en-UG")
    title = models.CharField(max_length=240)
    summary = models.TextField(blank=True, default="")
    body = models.TextField(blank=True, default="")
    media = models.FileField(upload_to="cms/%Y/%m/", null=True, blank=True)
    target_url = models.CharField(max_length=500, blank=True, default="")
    audience = models.JSONField(default=list, blank=True)
    placement = models.CharField(max_length=100, blank=True, default="")
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=24, default="draft")
    metadata = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_content_entries")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["content_type", "slug", "locale", "version"], name="unique_enterprise_content_version")]
        indexes = [models.Index(fields=["content_type", "status", "placement"], name="ent_content_placement")]


class FeatureConfiguration(models.Model):
    key = models.CharField(max_length=180, unique=True)
    scope_type = models.CharField(max_length=24, default="platform")
    scope_id = models.CharField(max_length=80, blank=True, default="")
    value = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    requires_restart = models.BooleanField(default=False)
    updated_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_feature_configurations")
    updated_at = models.DateTimeField(auto_now=True)


class MasterPatientIndex(models.Model):
    enterprise_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    patient = models.OneToOneField(AUTH_USER, on_delete=models.PROTECT, related_name="master_patient_index")
    national_identifier = models.CharField(max_length=120, blank=True, default="")
    identifiers = models.JSONField(default=list, blank=True)
    normalized_name = models.CharField(max_length=240)
    normalized_phone = models.CharField(max_length=60, blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=20, blank=True, default="")
    status = models.CharField(max_length=24, default="active")
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["normalized_name", "date_of_birth"], name="ent_mpi_name_dob"), models.Index(fields=["national_identifier"], name="ent_mpi_national_id")]


class DuplicatePatientCandidate(models.Model):
    patient_a = models.ForeignKey(MasterPatientIndex, on_delete=models.CASCADE, related_name="duplicate_candidates_as_a")
    patient_b = models.ForeignKey(MasterPatientIndex, on_delete=models.CASCADE, related_name="duplicate_candidates_as_b")
    score = models.DecimalField(max_digits=5, decimal_places=2)
    matching_fields = models.JSONField(default=list)
    status = models.CharField(max_length=24, default="pending")
    reviewed_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_duplicate_patients")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["patient_a", "patient_b"], name="unique_enterprise_duplicate_pair")]


class PatientMerge(models.Model):
    survivor = models.ForeignKey(MasterPatientIndex, on_delete=models.PROTECT, related_name="surviving_merges")
    duplicate = models.ForeignKey(MasterPatientIndex, on_delete=models.PROTECT, related_name="duplicate_merges")
    field_decisions = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="proposed")
    reason = models.TextField()
    requested_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="requested_patient_merges")
    approved_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_patient_merges")
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    reversed_at = models.DateTimeField(null=True, blank=True)


class RecordsRequest(models.Model):
    class Type(models.TextChoices):
        CORRECTION = "correction", "Record correction"
        RELEASE = "release", "Release of information"
        LEGAL_HOLD = "legal_hold", "Legal hold"
        RETENTION = "retention", "Retention action"
        EXPORT = "export", "Patient export"
        DELETION = "deletion", "Deletion assessment"
        SCAN = "scan", "Scanned document indexing"

    request_number = models.CharField(max_length=48, unique=True, blank=True)
    request_type = models.CharField(max_length=24, choices=Type.choices)
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="records_requests")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="records_requests")
    status = models.CharField(max_length=24, default="submitted")
    reason = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    requested_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_records_requests")
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_records_requests")
    decision_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_records_requests")
    decision = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = f"REC-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class FHIRResource(models.Model):
    resource_type = models.CharField(max_length=80)
    logical_id = models.UUIDField(default=uuid.uuid4, editable=False)
    version_id = models.PositiveIntegerField(default=1)
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="fhir_resources")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="fhir_resources")
    source_model = models.CharField(max_length=120, blank=True, default="")
    source_id = models.CharField(max_length=80, blank=True, default="")
    data = models.JSONField(default=dict)
    status = models.CharField(max_length=24, default="active")
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["resource_type", "logical_id", "version_id"], name="unique_enterprise_fhir_version")]
        indexes = [models.Index(fields=["resource_type", "logical_id", "version_id"], name="ent_fhir_identity"), models.Index(fields=["patient", "resource_type"], name="ent_fhir_patient_type")]


class PartnerApplication(models.Model):
    client_id = models.CharField(max_length=120, unique=True, default=generate_client_id)
    name = models.CharField(max_length=180)
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="partner_applications")
    redirect_uris = models.JSONField(default=list)
    scopes = models.JSONField(default=list)
    jwks_uri = models.URLField(blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PartnerAccessToken(models.Model):
    application = models.ForeignKey(PartnerApplication, on_delete=models.CASCADE, related_name="tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list)
    subject = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.CASCADE, related_name="partner_access_tokens")
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def issue(cls, application, scopes, subject=None, ttl_minutes=60):
        raw = secrets.token_urlsafe(48)
        obj = cls.objects.create(
            application=application,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            scopes=scopes,
            subject=subject,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
        )
        return obj, raw


class FHIRSubscription(models.Model):
    application = models.ForeignKey(PartnerApplication, on_delete=models.CASCADE, related_name="fhir_subscriptions")
    criteria = models.CharField(max_length=500)
    endpoint = models.URLField()
    payload_type = models.CharField(max_length=80, default="application/fhir+json")
    secret_reference = models.CharField(max_length=240, blank=True, default="")
    status = models.CharField(max_length=24, default="active")
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    error_count = models.PositiveIntegerField(default=0)


class RegulatorConnector(models.Model):
    profession = models.CharField(max_length=80)
    authority = models.CharField(max_length=180)
    country_code = models.CharField(max_length=2, default="UG")
    base_url = models.URLField(blank=True, default="")
    credentials_reference = models.CharField(max_length=240, blank=True, default="")
    lookup_template = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)


class VerificationAutomation(models.Model):
    credential = models.ForeignKey("registry.PractitionerCredential", null=True, blank=True, on_delete=models.CASCADE, related_name="automated_scans")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="automated_verification_scans")
    model_name = models.CharField(max_length=120, default="document-screening-v1")
    model_version = models.CharField(max_length=80, default="1.0")
    status = models.CharField(max_length=24, default="queued")
    extracted_fields = models.JSONField(default=dict, blank=True)
    document_quality_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    match_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fraud_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    flags = models.JSONField(default=list, blank=True)
    regulator_response = models.JSONField(default=dict, blank=True)
    recommendation = models.CharField(max_length=24, blank=True, default="")
    human_decision = models.CharField(max_length=24, blank=True, default="")
    reviewed_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_automated_verifications")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class SecurityOperation(models.Model):
    class Type(models.TextChoices):
        UPLOAD_SCAN = "upload_scan", "Upload malware scan"
        ALERT = "alert", "Security alert"
        VULNERABILITY_SCAN = "vulnerability_scan", "Vulnerability scan"
        BACKUP = "backup", "Backup"
        RESTORE_TEST = "restore_test", "Restore test"
        DISASTER_RECOVERY = "disaster_recovery", "Disaster recovery"
        DPIA = "dpia", "Data protection impact assessment"
        CLINICAL_SAFETY = "clinical_safety", "Clinical safety case"
        PEN_TEST = "pen_test", "Penetration test"

    operation_type = models.CharField(max_length=32, choices=Type.choices)
    reference = models.CharField(max_length=60, unique=True, blank=True)
    status = models.CharField(max_length=24, default="planned")
    severity = models.CharField(max_length=16, default="medium")
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True, default="")
    scope = models.JSONField(default=dict, blank=True)
    findings = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    next_due_at = models.DateTimeField(null=True, blank=True)
    owner = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_security_operations")
    approved_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_security_operations")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"SEC-{timezone.now():%y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class SavedReport(models.Model):
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.CASCADE, related_name="saved_reports")
    name = models.CharField(max_length=180)
    domain = models.CharField(max_length=60)
    definition = models.JSONField(default=dict)
    visibility = models.CharField(max_length=24, default="organization")
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="saved_reports")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReportRun(models.Model):
    report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=24, default="queued")
    parameters = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    output_file = models.FileField(upload_to="reports/%Y/%m/", null=True, blank=True)
    requested_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="report_runs")
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True, default="")


class ReportSchedule(models.Model):
    report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name="schedules")
    cron_expression = models.CharField(max_length=80)
    recipients = models.JSONField(default=list)
    formats = models.JSONField(default=list)
    active = models.BooleanField(default=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="report_schedules")
