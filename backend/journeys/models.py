import secrets
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

AUTH_USER = settings.AUTH_USER_MODEL


class WorkflowCase(models.Model):
    """A page-specific, stateful healthcare or operational workflow.

    Deep pages use a dedicated ``page_slug`` endpoint backed by this model.  The
    payload is validated against the server-side page definition, while patient,
    organization, assignment, status, due dates and audit history remain queryable
    first-class columns.
    """

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        ROUTINE = "routine", "Routine"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"
        CRITICAL = "critical", "Critical"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    reference = models.CharField(max_length=48, unique=True, blank=True)
    page_slug = models.SlugField(max_length=100, db_index=True)
    category = models.CharField(max_length=80, blank=True, default="")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="workflow_cases")
    location = models.ForeignKey("registry.OrganizationLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_cases")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_cases")
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.PROTECT, related_name="patient_workflow_cases")
    subject_user = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.PROTECT, related_name="subject_workflow_cases")
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_workflow_cases")
    appointment = models.ForeignKey("appointments.Appointment", null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_cases")
    admission = models.ForeignKey("operations.Admission", null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_cases")
    invoice = models.ForeignKey("payments.Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_cases")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    title = models.CharField(max_length=220)
    summary = models.TextField(blank=True, default="")
    status = models.CharField(max_length=40, default="draft", db_index=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.ROUTINE)
    data = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_workflow_cases")
    updated_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_workflow_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["page_slug", "status", "priority"], name="journey_page_status"),
            models.Index(fields=["organization", "page_slug", "status"], name="journey_org_page"),
            models.Index(fields=["patient", "page_slug", "status"], name="journey_patient_page"),
            models.Index(fields=["assigned_to", "status", "due_at"], name="journey_assignee_due"),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = "".join(part[:3] for part in self.page_slug.split("-")[:2]).upper()[:6] or "CASE"
            self.reference = f"{prefix}-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        if self.patient_id and self.patient.role != "patient":
            raise ValidationError({"patient": "Workflow patient must be a patient account."})
        if self.location_id and self.organization_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "Branch belongs to another organization."})
        if self.department_id and self.organization_id and self.department.organization_id != self.organization_id:
            raise ValidationError({"department": "Department belongs to another organization."})

    def __str__(self):
        return f"{self.reference} · {self.page_slug} · {self.status}"


class OperationalAction(models.Model):
    """Canonical transaction record for page actions that do not map to a single clinical model.

    A WorkflowCase coordinates people, comments and approvals.  This model records
    the authoritative operational request/effect so a page never reports success
    merely because a generic case changed state.
    """

    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        EXECUTED = "executed", "Executed"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        REVERSED = "reversed", "Reversed"
        FAILED = "failed", "Failed"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    workflow_case = models.OneToOneField(
        WorkflowCase, on_delete=models.CASCADE, related_name="operational_action"
    )
    page_slug = models.SlugField(max_length=100, db_index=True)
    domain = models.CharField(max_length=80, db_index=True)
    operation_code = models.CharField(max_length=100, db_index=True)
    organization = models.ForeignKey(
        "registry.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="operational_actions"
    )
    location = models.ForeignKey(
        "registry.OrganizationLocation", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_actions"
    )
    department = models.ForeignKey(
        "workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_actions"
    )
    patient = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.PROTECT, related_name="patient_operational_actions"
    )
    subject_user = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.PROTECT, related_name="subject_operational_actions"
    )
    appointment = models.ForeignKey(
        "appointments.Appointment", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_actions"
    )
    admission = models.ForeignKey(
        "operations.Admission", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_actions"
    )
    invoice = models.ForeignKey(
        "payments.Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="operational_actions"
    )
    state = models.CharField(max_length=24, choices=State.choices, default=State.SUBMITTED, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    effect_log = models.JSONField(default=list, blank=True)
    effect_reference_type = models.CharField(max_length=100, blank=True, default="")
    effect_reference_id = models.CharField(max_length=100, blank=True, default="")
    requires_approval = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_operational_actions"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    executed_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="executed_operational_actions"
    )
    executed_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_operational_actions"
    )
    updated_by = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_operational_actions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-created_at"]
        indexes = [
            models.Index(fields=["page_slug", "state"], name="journey_op_page_state"),
            models.Index(fields=["organization", "domain", "state"], name="journey_op_org_domain"),
            models.Index(fields=["patient", "page_slug"], name="journey_op_patient"),
        ]

    def clean(self):
        if self.location_id and self.organization_id and self.location.organization_id != self.organization_id:
            raise ValidationError({"location": "Branch belongs to another organization."})
        if self.department_id and self.organization_id and self.department.organization_id != self.organization_id:
            raise ValidationError({"department": "Department belongs to another organization."})

    def __str__(self):
        return f"{self.page_slug} · {self.operation_code} · {self.state}"


class ReleaseAcceptance(models.Model):
    """Human and operational sign-off required before a deployment is promoted."""

    class Type(models.TextChoices):
        DOCTOR_WORKFLOW = "doctor_workflow", "Doctor workflow acceptance"
        NURSING_WORKFLOW = "nursing_workflow", "Nursing and midwifery acceptance"
        LABORATORY_WORKFLOW = "laboratory_workflow", "Laboratory acceptance"
        PHARMACY_WORKFLOW = "pharmacy_workflow", "Pharmacy acceptance"
        FINANCE_WORKFLOW = "finance_workflow", "Finance acceptance"
        RECORDS_WORKFLOW = "records_workflow", "Medical records acceptance"
        ADMIN_WORKFLOW = "admin_workflow", "Administrator acceptance"
        PRIVACY_LEGAL = "privacy_legal", "Privacy and legal approval"
        CLINICAL_SAFETY = "clinical_safety", "Clinical safety approval"
        SECURITY = "security", "Security approval"
        BACKUP_RESTORE = "backup_restore", "Backup and restore evidence"
        DISASTER_RECOVERY = "disaster_recovery", "Disaster recovery approval"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    release_version = models.CharField(max_length=80, db_index=True)
    environment = models.CharField(max_length=40, default="production", db_index=True)
    acceptance_type = models.CharField(max_length=40, choices=Type.choices, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewer = models.ForeignKey(
        AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="release_acceptances"
    )
    reviewer_name = models.CharField(max_length=220)
    reviewer_title = models.CharField(max_length=180, blank=True, default="")
    reviewer_email = models.EmailField(blank=True, default="")
    statement = models.TextField()
    evidence = models.FileField(upload_to="release-acceptance/%Y/%m/", null=True, blank=True)
    evidence_hash = models.CharField(max_length=128, blank=True, default="")
    signed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["acceptance_type", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["release_version", "environment", "acceptance_type"],
                name="journey_unique_release_acceptance",
            )
        ]

    @property
    def is_currently_accepted(self):
        return (
            self.status == self.Status.ACCEPTED
            and self.signed_at is not None
            and (self.expires_at is None or self.expires_at > timezone.now())
        )

    def __str__(self):
        return f"{self.release_version} · {self.acceptance_type} · {self.status}"


class WorkflowActionEvent(models.Model):
    case = models.ForeignKey(WorkflowCase, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=80)
    actor = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_action_events")
    actor_role = models.CharField(max_length=64, blank=True, default="")
    from_status = models.CharField(max_length=40, blank=True, default="")
    to_status = models.CharField(max_length=40, blank=True, default="")
    note = models.TextField(blank=True, default="")
    data = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=100, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["case", "created_at"], name="journey_event_case")]


class WorkflowComment(models.Model):
    class Visibility(models.TextChoices):
        CARE_TEAM = "care_team", "Care team"
        PATIENT = "patient", "Patient visible"
        INTERNAL = "internal", "Internal administration"

    case = models.ForeignKey(WorkflowCase, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="workflow_comments")
    body = models.TextField()
    visibility = models.CharField(max_length=20, choices=Visibility.choices, default=Visibility.CARE_TEAM)
    attachment = models.FileField(upload_to="workflow-comments/%Y/%m/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class GeneratedClinicalDocument(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SIGNED = "signed", "Signed"
        REVOKED = "revoked", "Revoked"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    verification_code = models.CharField(max_length=48, unique=True, blank=True)
    document_type = models.CharField(max_length=60)
    title = models.CharField(max_length=220)
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="generated_clinical_documents")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_clinical_documents")
    workflow_case = models.ForeignKey(WorkflowCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="generated_documents")
    content = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    file = models.FileField(upload_to="clinical-documents/%Y/%m/", null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_clinical_documents")
    signed_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="signed_clinical_documents")
    signed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.verification_code:
            self.verification_code = f"DOC-{secrets.token_urlsafe(18)}"
        super().save(*args, **kwargs)


class ResultReview(models.Model):
    class Action(models.TextChoices):
        ACKNOWLEDGE = "acknowledge", "Acknowledge"
        ESCALATE = "escalate", "Escalate"
        COMMENT = "comment", "Comment"
        CLOSE = "close", "Close"

    result_type = models.CharField(max_length=24, choices=[("laboratory", "Laboratory"), ("imaging", "Imaging")])
    result_id = models.PositiveBigIntegerField()
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="result_reviews")
    reviewer = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="performed_result_reviews")
    action = models.CharField(max_length=20, choices=Action.choices)
    note = models.TextField(blank=True, default="")
    escalated_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="escalated_result_reviews")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["result_type", "result_id", "created_at"], name="journey_result_review")]


class WaitingRoomEntry(models.Model):
    """Live, auditable queue state for an appointment or walk-in consultation."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CHECKED_IN = "checked_in", "Checked in"
        READY = "ready", "Ready"
        CALLED = "called", "Called"
        IN_PROGRESS = "in_progress", "In consultation"
        COMPLETED = "completed", "Completed"
        LEFT = "left", "Left queue"

    appointment = models.OneToOneField(
        "appointments.Appointment", on_delete=models.CASCADE, related_name="waiting_room_entry"
    )
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="waiting_room_entries")
    organization = models.ForeignKey(
        "registry.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="waiting_room_entries"
    )
    workflow_case = models.OneToOneField(
        WorkflowCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="waiting_room_entry"
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.WAITING)
    queue_number = models.PositiveIntegerField(default=0)
    device_status = models.JSONField(default=dict, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    called_at = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["organization", "status", "created_at"], name="journey_wait_org_status"),
            models.Index(fields=["patient", "status"], name="journey_wait_patient"),
        ]

    @property
    def queue_position(self):
        active = [self.Status.WAITING, self.Status.CHECKED_IN, self.Status.READY]
        if self.status not in active:
            return 0
        return WaitingRoomEntry.objects.filter(
            appointment__doctor_id=self.appointment.doctor_id,
            appointment__date=self.appointment.date,
            status__in=active,
            created_at__lt=self.created_at,
        ).count() + 1


class MedicationRenewalRequest(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    workflow_case = models.OneToOneField(WorkflowCase, on_delete=models.CASCADE, related_name="medication_renewal")
    prescription = models.ForeignKey("prescriptions.Prescription", on_delete=models.PROTECT, related_name="renewal_requests")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="medication_renewal_requests")
    prescriber = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="assigned_medication_renewals")
    reason = models.TextField()
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SUBMITTED)
    decision_note = models.TextField(blank=True, default="")
    decided_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_medication_renewals")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class MedicationAdherenceEntry(models.Model):
    class Status(models.TextChoices):
        TAKEN = "taken", "Taken"
        MISSED = "missed", "Missed"
        LATE = "late", "Taken late"
        SKIPPED = "skipped", "Skipped on advice"
        UNAVAILABLE = "unavailable", "Medicine unavailable"

    workflow_case = models.ForeignKey(WorkflowCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="adherence_entries")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.CASCADE, related_name="medication_adherence_entries")
    prescription = models.ForeignKey("prescriptions.Prescription", on_delete=models.CASCADE, related_name="adherence_entries")
    prescription_item = models.ForeignKey("prescriptions.PrescriptionItem", null=True, blank=True, on_delete=models.SET_NULL, related_name="adherence_entries")
    scheduled_for = models.DateTimeField()
    taken_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    note = models.TextField(blank=True, default="")
    source = models.CharField(max_length=30, default="patient_portal")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_for", "-id"]
        indexes = [models.Index(fields=["patient", "scheduled_for", "status"], name="journey_adherence_due")]


class ClinicalTask(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        BLOCKED = "blocked", "Blocked"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    workflow_case = models.OneToOneField(WorkflowCase, on_delete=models.CASCADE, related_name="clinical_task")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="clinical_tasks")
    task_type = models.CharField(max_length=80)
    instructions = models.TextField()
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_clinical_tasks")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.OPEN)
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_clinical_tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_at", "-created_at"]
        indexes = [models.Index(fields=["assigned_to", "status", "due_at"], name="journey_task_assignee")]


class CareConference(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    workflow_case = models.OneToOneField(WorkflowCase, on_delete=models.CASCADE, related_name="care_conference")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="care_conferences")
    organization = models.ForeignKey("registry.Organization", null=True, blank=True, on_delete=models.PROTECT, related_name="care_conferences")
    title = models.CharField(max_length=220)
    scheduled_at = models.DateTimeField()
    agenda = models.TextField()
    minutes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PLANNED)
    participants = models.ManyToManyField(AUTH_USER, blank=True, related_name="care_conference_participation")
    chair = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="chaired_care_conferences")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class QueueTicket(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        CALLED = "called", "Called"
        SERVING = "serving", "Serving"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    number = models.CharField(max_length=40, unique=True, blank=True)
    organization = models.ForeignKey("registry.Organization", on_delete=models.PROTECT, related_name="queue_tickets")
    department = models.ForeignKey("workforce.Department", null=True, blank=True, on_delete=models.SET_NULL, related_name="queue_tickets")
    patient = models.ForeignKey(AUTH_USER, on_delete=models.PROTECT, related_name="queue_tickets")
    appointment = models.ForeignKey("appointments.Appointment", null=True, blank=True, on_delete=models.SET_NULL, related_name="queue_tickets")
    workflow_case = models.OneToOneField(WorkflowCase, null=True, blank=True, on_delete=models.SET_NULL, related_name="queue_ticket")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    counter = models.CharField(max_length=40, blank=True, default="")
    issued_by = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="issued_queue_tickets")
    issued_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["issued_at", "id"]
        indexes = [models.Index(fields=["organization", "status", "issued_at"], name="journey_queue_org_status")]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"Q-{timezone.localdate():%y%m%d}-{secrets.token_hex(2).upper()}"
        super().save(*args, **kwargs)


class CallCentreCallback(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ATTEMPTED = "attempted", "Attempted"
        REACHED = "reached", "Reached"
        NO_ANSWER = "no_answer", "No answer"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    workflow_case = models.OneToOneField(WorkflowCase, on_delete=models.CASCADE, related_name="callback")
    patient = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="call_centre_callbacks")
    phone = models.CharField(max_length=40)
    reason = models.TextField()
    scheduled_for = models.DateTimeField()
    assigned_to = models.ForeignKey(AUTH_USER, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_callbacks")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SCHEDULED)
    outcome = models.TextField(blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
