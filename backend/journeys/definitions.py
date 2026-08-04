"""Server-side workflow definitions for every deep application page.

The frontend catalogue describes navigation.  This registry is authoritative for
who may use a page, which data is accepted and which state transitions are legal.
Every page therefore has a dedicated, role-checked transactional API even when it
shares rendering infrastructure with another role.
"""

import json
from copy import deepcopy
from pathlib import Path

MANIFEST = json.loads((Path(__file__).with_name("page_manifest.json")).read_text(encoding="utf-8"))

COMMON_FIELDS = [
    {"name": "title", "label": "Title", "type": "text", "required": True, "max_length": 220},
    {"name": "summary", "label": "Details", "type": "textarea", "required": False, "max_length": 4000},
    {"name": "patient", "label": "Patient", "type": "entity", "entity": "patient", "required": False},
    {"name": "priority", "label": "Priority", "type": "choice", "choices": ["low", "routine", "high", "urgent", "critical"], "required": False},
    {"name": "due_at", "label": "Due date and time", "type": "datetime", "required": False},
]

COMMON_ACTIONS = {
    "submit": {"label": "Submit", "from": ["draft", "awaiting_information"], "to": "submitted"},
    "assign": {"label": "Assign", "from": ["submitted", "pending", "triaged"], "to": "assigned", "fields": [{"name": "assigned_to", "label": "Assign to", "type": "entity", "entity": "staff", "required": True}]},
    "start": {"label": "Start work", "from": ["submitted", "pending", "assigned", "scheduled"], "to": "in_progress"},
    "request_information": {"label": "Request information", "from": ["submitted", "assigned", "in_progress", "under_review"], "to": "awaiting_information", "note_required": True},
    "provide_information": {"label": "Provide information", "from": ["awaiting_information"], "to": "submitted", "note_required": True},
    "approve": {"label": "Approve", "from": ["submitted", "assigned", "in_progress", "under_review", "pending_approval"], "to": "approved", "note_required": True},
    "reject": {"label": "Reject", "from": ["submitted", "assigned", "in_progress", "under_review", "pending_approval"], "to": "rejected", "note_required": True},
    "complete": {"label": "Complete", "from": ["assigned", "in_progress", "approved", "processing"], "to": "completed", "note_required": False},
    "cancel": {"label": "Cancel", "from": ["draft", "submitted", "pending", "assigned", "scheduled", "awaiting_information"], "to": "cancelled", "note_required": True},
    "reopen": {"label": "Reopen", "from": ["completed", "rejected", "cancelled", "closed"], "to": "in_progress", "note_required": True},
}


def field(name, label, type="text", *, required=False, choices=None, entity=None, help_text="", max_length=None):
    value = {"name": name, "label": label, "type": type, "required": required}
    if choices is not None:
        value["choices"] = choices
    if entity:
        value["entity"] = entity
    if help_text:
        value["help_text"] = help_text
    if max_length:
        value["max_length"] = max_length
    return value


def action(label, to, from_statuses, *, note_required=False, roles=None, fields=None, tone="primary"):
    value = {"label": label, "to": to, "from": from_statuses, "note_required": note_required, "tone": tone}
    if roles:
        value["roles"] = roles
    if fields:
        value["fields"] = fields
    return value


OVERRIDES = {}


def configure(slugs, *, fields=None, actions=None, initial_status="draft", category=None, patient_required=False, supports_comments=True, supports_attachments=True, adapter=None, create_allowed=True):
    for slug in slugs:
        OVERRIDES[slug] = {
            "fields": fields,
            "actions": actions,
            "initial_status": initial_status,
            "category": category,
            "patient_required": patient_required,
            "supports_comments": supports_comments,
            "supports_attachments": supports_attachments,
            "adapter": adapter,
            "create_allowed": create_allowed,
        }


# Patient transactions.
configure(
    ["reschedule-appointment"],
    category="appointment",
    patient_required=True,
    adapter="appointment_reschedule",
    fields=[
        field("appointment", "Appointment", "entity", required=True, entity="appointment"),
        field("new_date", "New date", "date", required=True),
        field("new_start_time", "New start time", "time", required=True),
        field("reason", "Reason for rescheduling", "textarea", required=True, max_length=1200),
    ],
    initial_status="submitted",
    actions={
        "approve": action("Approve new slot", "approved", ["submitted", "under_review"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "receptionist", "operations_admin", "admin"]),
        "reject": action("Decline request", "rejected", ["submitted", "under_review"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "receptionist", "operations_admin", "admin"], tone="danger"),
        "cancel": COMMON_ACTIONS["cancel"],
    },
)
configure(
    ["cancel-refund"],
    category="appointment",
    patient_required=True,
    adapter="appointment_cancel_refund",
    fields=[field("appointment", "Appointment", "entity", required=True, entity="appointment"), field("reason", "Cancellation reason", "textarea", required=True), field("refund_reason", "Refund explanation", "textarea")],
    initial_status="submitted",
    actions={
        "approve": action("Approve cancellation", "approved", ["submitted", "under_review"], note_required=True, roles=["receptionist", "cashier", "finance_manager", "operations_admin", "admin"]),
        "process_refund": action("Process eligible refund", "completed", ["approved"], note_required=True, roles=["cashier", "accountant", "finance_manager", "operations_admin", "admin"]),
        "reject": action("Reject request", "rejected", ["submitted", "under_review"], note_required=True, roles=["receptionist", "finance_manager", "operations_admin", "admin"], tone="danger"),
    },
)
configure(
    ["virtual-waiting-room"],
    category="appointment",
    patient_required=True,
    adapter="waiting_room",
    fields=[field("appointment", "Appointment", "entity", required=True, entity="appointment"), field("device_ready", "Camera and microphone checked", "boolean"), field("consent_confirmed", "Telemedicine consent confirmed", "boolean")],
    initial_status="waiting",
    actions={
        "check_in": action("Check in", "checked_in", ["waiting", "scheduled"], roles=["patient", "receptionist"]),
        "mark_ready": action("Mark ready", "ready", ["checked_in"], roles=["patient"]),
        "call_next": action("Call patient", "called", ["ready", "checked_in"], roles=["doctor", "clinical_officer", "dentist", "receptionist"]),
        "join": action("Join consultation", "in_progress", ["called", "ready"], roles=["patient", "doctor", "clinical_officer", "dentist"]),
        "complete": action("End consultation", "completed", ["in_progress"], roles=["doctor", "clinical_officer", "dentist"]),
    },
)
configure(
    ["refill-request", "medication-adherence", "privacy-request", "caregiver-invitation", "patient-feedback", "complaint-detail"],
    category="patient_service",
    patient_required=True,
    fields=[field("request_type", "Request type", "text"), field("details", "Request details", "textarea", required=True), field("related_reference", "Related reference", "text")],
    initial_status="submitted",
    actions=COMMON_ACTIONS,
)
configure(
    ["consent-centre"],
    category="governance",
    patient_required=True,
    adapter="consent",
    fields=[field("consent_type", "Consent type", "choice", required=True, choices=["treatment", "telemedicine", "data_sharing", "pharmacy", "laboratory", "insurance", "research", "marketing"]), field("purpose", "Purpose", "text", required=True), field("data_categories", "Data categories", "list"), field("valid_until", "Valid until", "datetime")],
    initial_status="active",
    actions={"revoke": action("Revoke consent", "revoked", ["active"], note_required=True, roles=["patient"], tone="danger")},
)

# Clinical result, order, task and document transactions.
configure(
    ["results-inbox", "critical-results", "lab-result-detail", "imaging-report", "critical-result-notification", "referring-doctor-acknowledgement"],
    category="clinical_results",
    patient_required=True,
    adapter="result_review",
    fields=[field("result_type", "Result type", "choice", required=True, choices=["laboratory", "imaging"]), field("result_id", "Result", "number", required=True), field("clinical_interpretation", "Clinical interpretation", "textarea")],
    initial_status="pending_review",
    actions={
        "acknowledge": action("Acknowledge result", "acknowledged", ["pending_review", "escalated"], note_required=True),
        "escalate": action("Escalate critical result", "escalated", ["pending_review", "acknowledged"], note_required=True, fields=[field("assigned_to", "Escalate to", "entity", required=True, entity="staff")], tone="danger"),
        "close": action("Close follow-up", "completed", ["acknowledged", "escalated"], note_required=True),
    },
)
configure(
    ["order-entry", "admission-orders", "clinical-tasks", "procedure-documentation", "medication-renewals", "referral-reception"],
    category="clinical_care",
    patient_required=True,
    fields=[field("order_type", "Order or task type", "choice", required=True, choices=["laboratory", "imaging", "medication", "admission", "procedure", "referral", "follow_up", "other"]), field("instructions", "Instructions", "textarea", required=True), field("assigned_to", "Assigned professional", "entity", entity="staff"), field("urgency", "Urgency", "choice", choices=["routine", "urgent", "critical"])],
    initial_status="submitted",
    actions=COMMON_ACTIONS,
)
configure(
    ["medical-certificates", "sick-note", "referral-letter", "discharge-summary", "birth-record", "operation-note-editor"],
    category="clinical_document",
    patient_required=True,
    adapter="clinical_document",
    fields=[field("document_type", "Document type", "text", required=True), field("clinical_summary", "Clinical summary", "textarea", required=True), field("recommendations", "Recommendations", "textarea"), field("valid_from", "Valid from", "date"), field("valid_until", "Valid until", "date")],
    initial_status="draft",
    actions={
        "submit": COMMON_ACTIONS["submit"],
        "sign": action("Electronically sign", "signed", ["draft", "submitted"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "medical_director", "admin"]),
        "revoke": action("Revoke document", "revoked", ["signed"], note_required=True, roles=["medical_director", "clinical_safety_admin", "admin"], tone="danger"),
    },
)
configure(
    ["on-call-schedule", "multidisciplinary-team", "patient-handover", "nursing-handover", "shift-summary"],
    category="coordination",
    patient_required=False,
    fields=[field("participants", "Participants", "list", required=True), field("agenda", "Agenda or handover summary", "textarea", required=True), field("scheduled_at", "Scheduled time", "datetime"), field("acknowledgements_required", "Acknowledgements required", "boolean")],
    initial_status="scheduled",
    actions={
        "acknowledge": action("Acknowledge", "acknowledged", ["scheduled", "in_progress"], note_required=True),
        "start": COMMON_ACTIONS["start"],
        "complete": COMMON_ACTIONS["complete"],
        "cancel": COMMON_ACTIONS["cancel"],
    },
)

# Nursing and maternity bedside transactions.
configure(
    ["emar", "due-medications", "overdue-medications", "medication-omissions"],
    category="nursing_medication",
    patient_required=True,
    adapter="medication_administration",
    fields=[field("medication", "Medication", "text", required=True), field("dose", "Dose", "text", required=True), field("route", "Route", "choice", choices=["oral", "IV", "IM", "SC", "topical", "inhaled", "other"]), field("scheduled_at", "Scheduled time", "datetime", required=True), field("five_rights_confirmed", "Five rights confirmed", "boolean"), field("omission_reason", "Omission reason", "textarea")],
    initial_status="scheduled",
    actions={
        "administer": action("Record administration", "administered", ["scheduled", "due", "overdue"], note_required=True, roles=["nurse", "midwife", "theatre_nurse"]),
        "omit": action("Record omission", "omitted", ["scheduled", "due", "overdue"], note_required=True, roles=["nurse", "midwife", "theatre_nurse"], tone="danger"),
        "escalate": action("Escalate overdue dose", "escalated", ["overdue", "omitted"], note_required=True, roles=["nurse", "midwife", "theatre_nurse"]),
    },
)
configure(
    ["fluid-balance", "intake-output", "wound-assessment", "pain-assessment", "fall-risk", "pressure-injury-risk", "infection-control-checklist", "transfusion-observation", "early-warning", "nursing-discharge", "patient-education", "supply-requests", "equipment-checklist", "isolation-board"],
    category="nursing_care",
    patient_required=True,
    fields=[field("assessment", "Assessment", "textarea", required=True), field("measurements", "Measurements", "json"), field("interventions", "Interventions", "textarea"), field("review_due_at", "Review due", "datetime")],
    initial_status="in_progress",
    actions={"complete": COMMON_ACTIONS["complete"], "escalate": action("Escalate", "escalated", ["in_progress", "completed"], note_required=True, tone="danger"), "reopen": COMMON_ACTIONS["reopen"]},
)
configure(
    ["visual-partograph", "newborn-assessment", "apgar-chart", "mother-baby-linking", "immunization-calendar", "vaccination-administration", "growth-chart", "child-health-visit", "family-planning"],
    category="maternity_child_health",
    patient_required=True,
    adapter="maternity_operation",
    fields=[field("observed_at", "Observation time", "datetime", required=True), field("measurements", "Clinical measurements", "json", required=True), field("assessment", "Assessment", "textarea"), field("intervention", "Intervention", "textarea")],
    initial_status="in_progress",
    actions={"record": action("Record observation", "in_progress", ["in_progress", "draft"]), "escalate": action("Escalate danger sign", "escalated", ["in_progress"], note_required=True, tone="danger"), "complete": COMMON_ACTIONS["complete"]},
)

# Front desk and records.
configure(
    ["create-appointment", "appointment-calendar", "provider-schedules", "patient-arrival-board", "walk-in-conversion", "service-routing", "admission-registration", "discharge-coordination", "call-centre", "sms-confirmation"],
    category="front_desk",
    patient_required=True,
    fields=[field("appointment", "Appointment", "entity", entity="appointment"), field("service", "Service or department", "text"), field("scheduled_at", "Scheduled time", "datetime"), field("callback_number", "Callback number", "text"), field("notes", "Front desk notes", "textarea")],
    initial_status="submitted",
    actions={"confirm": action("Confirm", "confirmed", ["submitted", "pending"]), "check_in": action("Check in", "checked_in", ["confirmed", "submitted"]), "route": action("Route patient", "routed", ["checked_in"], note_required=True), "complete": COMMON_ACTIONS["complete"], "cancel": COMMON_ACTIONS["cancel"]},
)
configure(
    ["master-patient-index", "duplicate-candidates", "identity-comparison", "merge-wizard", "unmerge-review", "identity-conflicts", "demographic-correction", "scan-classify", "record-release", "disclosure-authorization", "legal-holds", "record-restriction", "confidential-segmentation", "retention-schedules", "archival-queue", "destruction-approval", "data-export", "patient-access-request", "record-movement", "unmatched-documents"],
    category="records_management",
    patient_required=True,
    adapter="records_management",
    fields=[field("request_type", "Records action", "text", required=True), field("reason", "Reason and legal basis", "textarea", required=True), field("canonical_patient", "Canonical patient", "entity", entity="patient"), field("candidate_patient", "Candidate patient", "entity", entity="patient"), field("retention_until", "Retention or hold until", "date")],
    initial_status="submitted",
    actions={"verify": action("Verify identity", "verified", ["submitted", "under_review"], note_required=True), "approve": COMMON_ACTIONS["approve"], "reject": COMMON_ACTIONS["reject"], "execute": action("Execute approved action", "completed", ["approved", "verified"], note_required=True, roles=["records_officer", "compliance_admin", "admin"]), "reopen": COMMON_ACTIONS["reopen"]},
)

# Finance.
configure(
    ["deposit-collection", "split-payment", "multiple-payment-methods", "patient-insurer-split", "credit-balance", "refund-request", "void-payment", "credit-notes", "debit-notes", "bank-reconciliation", "mobile-money-reconciliation", "gateway-reconciliation", "supplier-invoices", "supplier-payments", "expense-register", "journal-entries", "general-ledger", "trial-balance", "income-statement", "balance-sheet", "cash-flow", "tax-report", "period-closing", "budget-management", "department-budgets", "approval-limits", "financial-exceptions", "revenue-leakage", "forecasting"],
    category="finance",
    adapter="finance_operation",
    fields=[field("transaction_date", "Transaction date", "date", required=True), field("amount", "Amount", "money", required=True), field("currency", "Currency", "choice", choices=["UGX", "USD", "KES", "TZS", "RWF"]), field("account_code", "Account or budget code", "text"), field("reference", "External reference", "text"), field("details", "Details", "textarea", required=True), field("invoice", "Invoice", "entity", entity="invoice")],
    initial_status="submitted",
    actions={"approve": COMMON_ACTIONS["approve"], "reject": COMMON_ACTIONS["reject"], "post": action("Post to ledger", "posted", ["approved"], note_required=True, roles=["accountant", "finance_manager", "admin"]), "reconcile": action("Reconcile", "completed", ["posted", "processing", "submitted"], note_required=True, roles=["accountant", "finance_manager", "admin"]), "reverse": action("Create reversal", "reversed", ["posted", "completed"], note_required=True, roles=["finance_manager", "admin"], tone="danger")},
)

# Pharmacy and laboratory.
configure(
    ["prescription-workspace", "dispensing-labels", "label-printing", "prescription-clarification", "substitution-authorization", "pharmacist-intervention", "controlled-drug-register", "narcotics-balance", "witness-confirmation", "product-recall", "drug-return", "stock-transfer", "stock-adjustment", "stock-count", "variance-investigation", "goods-received", "supplier-invoice-matching", "reorder-recommendations", "cold-chain-chart", "temperature-excursion", "damaged-stock", "quarantine-stock"],
    category="pharmacy_inventory",
    adapter="inventory_operation",
    fields=[field("item_reference", "Medicine or stock item", "text", required=True), field("batch_number", "Batch number", "text"), field("quantity", "Quantity", "number"), field("location", "Storage location", "text"), field("temperature", "Temperature °C", "number"), field("reason", "Reason or clinical note", "textarea", required=True)],
    initial_status="submitted",
    actions={"review": action("Review", "under_review", ["submitted"]), "approve": COMMON_ACTIONS["approve"], "reject": COMMON_ACTIONS["reject"], "execute": action("Execute transaction", "completed", ["approved", "under_review"], note_required=True), "quarantine": action("Quarantine stock", "quarantined", ["submitted", "under_review", "approved"], note_required=True, tone="danger"), "recall": action("Initiate recall", "recalled", ["submitted", "under_review", "approved"], note_required=True, tone="danger")},
)
configure(
    ["collection-worklist", "phlebotomy-queue", "accessioning", "barcode-labels", "barcode-scanner", "rejected-specimens", "transport-manifest", "aliquot-creation", "storage-locations", "result-entry", "result-comparison", "validation-queue", "release-queue", "critical-escalation", "microbiology", "sensitivity-grid", "histopathology", "blood-bank", "crossmatch", "transfusion-compatibility", "reagent-inventory", "equipment-register", "calibration-calendar", "quality-control", "turnaround-time", "lab-report-printing"],
    category="laboratory",
    adapter="laboratory_operation",
    patient_required=True,
    fields=[field("specimen_reference", "Specimen or order reference", "text", required=True), field("test_name", "Test", "text"), field("result", "Result or observation", "textarea"), field("quality_data", "Quality-control data", "json"), field("critical", "Critical result", "boolean")],
    initial_status="submitted",
    actions={"receive": action("Receive specimen", "received", ["submitted", "collected"]), "process": action("Start processing", "processing", ["received"]), "validate": action("Validate", "validated", ["processing", "pending_validation"], note_required=True), "release": action("Release result", "released", ["validated"], note_required=True), "reject": action("Reject specimen", "rejected", ["submitted", "received"], note_required=True, tone="danger"), "escalate": action("Escalate critical result", "escalated", ["validated", "released"], note_required=True, tone="danger")},
)

# Emergency, theatre and facility safety.
configure(
    ["call-intake", "dispatch-map", "incident-detail", "ambulance-detail", "crew-roster", "live-telemetry", "route-eta", "emergency-triage", "trauma-chart", "resuscitation-timeline", "medication-timeline", "procedure-timeline", "gcs-chart", "observation-chart", "transfer-form", "receiving-handover", "mass-casualty", "ambulance-equipment", "ambulance-cleaning", "paramedic-workspace"],
    category="emergency",
    adapter="emergency_operation",
    patient_required=False,
    fields=[field("incident_location", "Incident or pickup location", "text", required=True), field("destination", "Destination", "text"), field("latitude", "Pickup latitude", "number"), field("longitude", "Pickup longitude", "number"), field("destination_latitude", "Destination latitude", "number"), field("destination_longitude", "Destination longitude", "number"), field("severity", "Severity", "choice", choices=["low", "moderate", "high", "critical"]), field("clinical_observations", "Clinical observations", "json"), field("notes", "Notes", "textarea")],
    initial_status="new",
    actions={"triage": action("Triage", "triaged", ["new", "submitted"], note_required=True), "dispatch": action("Dispatch ambulance", "dispatched", ["new", "triaged"], note_required=True, roles=["ambulance_dispatcher", "operations_admin", "admin"]), "en_route": action("Mark en route", "en_route", ["dispatched"], roles=["paramedic", "ambulance_dispatcher"]), "arrive": action("Record arrival", "on_scene", ["en_route"], roles=["paramedic"]), "transport": action("Begin transport", "transporting", ["on_scene"], roles=["paramedic"]), "handover": action("Complete receiving handover", "completed", ["transporting", "on_scene"], note_required=True), "cancel": COMMON_ACTIONS["cancel"]},
)
configure(
    ["theatre-calendar", "operating-room-schedule", "surgical-waiting-list", "surgical-case-detail", "team-assignment", "patient-preparation", "consent-checklist", "pre-anaesthetic", "anaesthesia-chart", "intraoperative-timeline", "vital-sign-graph", "medication-fluid-chart", "blood-product-chart", "instrument-count", "implant-register", "consumable-usage", "recovery-score", "recovery-observation", "post-operative-orders", "specimen-tracking", "sterilization", "theatre-turnaround", "theatre-utilization"],
    category="theatre",
    adapter="theatre_operation",
    patient_required=True,
    fields=[field("scheduled_at", "Scheduled date and time", "datetime"), field("scheduled_end", "Expected end date and time", "datetime"), field("theatre_room", "Operating room", "text"), field("procedure", "Procedure", "text", required=True), field("team", "Theatre team", "list"), field("observations", "Observations and counts", "json"), field("notes", "Notes", "textarea")],
    initial_status="scheduled",
    actions={"check_in": action("Pre-op check-in", "pre_op", ["scheduled"]), "anaesthesia_start": action("Start anaesthesia", "anaesthesia", ["pre_op"], roles=["anaesthetist"]), "procedure_start": action("Start procedure", "in_theatre", ["anaesthesia", "pre_op"]), "count_signoff": action("Sign instrument count", "count_verified", ["in_theatre"], note_required=True), "recovery": action("Transfer to recovery", "recovery", ["in_theatre", "count_verified"]), "complete": action("Complete case", "completed", ["recovery"], note_required=True), "cancel": COMMON_ACTIONS["cancel"]},
)

# Administration and platform operations.
configure(
    ["user-detail", "account-activity", "session-management", "role-matrix", "permission-comparison", "organization-detail", "branch-detail", "professional-detail", "verification-case", "licence-viewer", "ocr-comparison", "verification-timeline", "credential-renewals", "subscription-detail", "payment-reconciliation", "refund-detail", "notification-monitor", "template-editor", "cms-editor", "integration-detail", "event-delivery", "dead-letter", "event-replay", "worker-health", "system-metrics", "audit-explorer", "security-incident", "backup-restore", "data-export-centre", "retention-controls", "feature-flags", "localization", "maintenance-mode", "regulatory-reporting"],
    category="administration",
    fields=[field("subject_reference", "Subject or resource reference", "text"), field("action_reason", "Reason", "textarea", required=True), field("configuration", "Configuration or decision data", "json")],
    initial_status="submitted",
    actions={"review": action("Start review", "under_review", ["submitted", "pending"]), "approve": COMMON_ACTIONS["approve"], "reject": COMMON_ACTIONS["reject"], "execute": action("Execute approved action", "completed", ["approved"], note_required=True, roles=["admin", "platform_super_admin", "operations_admin", "compliance_admin", "clinical_safety_admin"]), "retry": action("Retry", "processing", ["failed", "dead_letter", "rejected"], note_required=True), "revoke": action("Revoke", "revoked", ["approved", "active", "completed"], note_required=True, tone="danger")},
)



# ---------------------------------------------------------------------------
# Workflow-completion overrides for critical actor journeys.
# These definitions intentionally replace generic title/details forms with
# domain-specific fields, role-separated actions and adapters.
# ---------------------------------------------------------------------------
configure(
    ["refill-request"],
    category="patient_medication",
    patient_required=True,
    adapter="medication_renewal",
    fields=[
        field("prescription", "Prescription", "entity", required=True, entity="prescription"),
        field("reason", "Why a refill is needed", "textarea", required=True, max_length=2000),
        field("remaining_doses", "Estimated doses remaining", "number"),
        field("preferred_pharmacy", "Preferred pharmacy", "text"),
        field("urgent", "Urgent request", "boolean"),
    ],
    initial_status="submitted",
    actions={
        "start_review": action("Start medication review", "under_review", ["submitted"], roles=["doctor", "clinical_officer", "medical_director"]),
        "approve": action("Approve renewal", "approved", ["submitted", "under_review"], note_required=True, roles=["doctor", "clinical_officer", "medical_director"]),
        "reject": action("Decline renewal", "rejected", ["submitted", "under_review"], note_required=True, roles=["doctor", "clinical_officer", "medical_director"], tone="danger"),
        "complete": action("Issue renewed prescription", "completed", ["approved"], note_required=True, roles=["doctor", "clinical_officer", "medical_director"]),
        "cancel": action("Withdraw request", "cancelled", ["submitted", "under_review"], note_required=True, roles=["patient"], tone="danger"),
    },
)
configure(
    ["medication-adherence"],
    category="patient_medication",
    patient_required=True,
    adapter="medication_adherence",
    fields=[
        field("prescription", "Prescription", "entity", required=True, entity="prescription"),
        field("prescription_item", "Medicine item identifier", "number"),
        field("scheduled_for", "Dose scheduled for", "datetime", required=True),
        field("dose_status", "Dose status", "choice", required=True, choices=["taken", "missed", "late", "skipped", "unavailable"]),
        field("taken_at", "Time taken", "datetime"),
        field("note", "Note", "textarea", max_length=1200),
    ],
    initial_status="recorded",
    actions={"correct": action("Submit correction", "correction_requested", ["recorded"], note_required=True, roles=["patient"])},
)
configure(
    ["privacy-requests"],
    category="privacy",
    patient_required=True,
    adapter="privacy_request",
    fields=[
        field("request_type", "Request type", "choice", required=True, choices=["access", "correction", "export", "restriction", "deletion", "complaint"]),
        field("details", "Request details", "textarea", required=True, max_length=6000),
        field("identity_confirmation", "I confirm this request concerns my information", "boolean", required=True),
    ],
    initial_status="received",
    actions={
        "verify_identity": action("Verify identity", "verifying", ["received"], note_required=True, roles=["compliance_officer", "compliance_admin"]),
        "start": action("Start processing", "in_progress", ["verifying", "received"], roles=["compliance_officer", "compliance_admin"]),
        "request_information": action("Request information", "waiting", ["received", "verifying", "in_progress"], note_required=True, roles=["compliance_officer", "compliance_admin"]),
        "provide_information": action("Provide information", "in_progress", ["waiting"], note_required=True, roles=["patient"]),
        "complete": action("Complete privacy request", "completed", ["in_progress", "verifying"], note_required=True, roles=["compliance_officer", "compliance_admin"]),
        "decline": action("Decline with legal reason", "declined", ["received", "verifying", "in_progress"], note_required=True, roles=["compliance_admin"], tone="danger"),
    },
)
configure(
    ["caregiver-invitation"],
    category="patient_authority",
    patient_required=True,
    adapter="caregiver_invitation",
    fields=[
        field("caregiver", "Caregiver account", "entity", required=True, entity="user"),
        field("relationship", "Relationship", "choice", required=True, choices=["parent", "guardian", "spouse", "child", "sibling", "caregiver", "legal_representative", "other"]),
        field("can_book", "May book appointments", "boolean"),
        field("can_view_records", "May view approved records", "boolean"),
        field("can_manage_billing", "May manage billing", "boolean"),
        field("can_receive_notifications", "May receive notifications", "boolean"),
        field("expires_at", "Authority expiry", "datetime"),
        field("notes", "Authority notes", "textarea"),
    ],
    initial_status="pending",
    actions={
        "accept": action("Accept invitation", "accepted", ["pending"], note_required=True, roles=["patient"]),
        "verify": action("Verify authority", "active", ["pending", "accepted"], note_required=True, roles=["records_officer", "compliance_officer", "compliance_admin"]),
        "reject": action("Reject authority", "rejected", ["pending", "accepted"], note_required=True, roles=["records_officer", "compliance_officer", "compliance_admin"], tone="danger"),
        "revoke": action("Revoke authority", "revoked", ["active"], note_required=True, roles=["patient", "records_officer", "compliance_admin"], tone="danger"),
    },
)
configure(
    ["feedback-complaint"],
    category="patient_feedback",
    patient_required=True,
    adapter="patient_feedback",
    fields=[
        field("category", "Category", "choice", required=True, choices=["clinical", "medication", "billing", "privacy", "staff", "facility", "technology", "other"]),
        field("severity", "Severity", "choice", required=True, choices=["low", "moderate", "high", "critical"]),
        field("subject", "Subject", "text", required=True),
        field("details", "What happened", "textarea", required=True, max_length=6000),
        field("anonymous_to_facility", "Hide my identity from routine facility staff", "boolean"),
    ],
    initial_status="open",
    actions={
        "acknowledge": action("Acknowledge complaint", "acknowledged", ["open"], note_required=True, roles=["quality_officer", "compliance_officer", "facility_manager"]),
        "investigate": action("Start investigation", "investigating", ["open", "acknowledged"], roles=["quality_officer", "compliance_officer"]),
        "request_information": action("Request more information", "waiting_user", ["open", "acknowledged", "investigating"], note_required=True, roles=["quality_officer", "compliance_officer"]),
        "provide_information": action("Provide information", "investigating", ["waiting_user"], note_required=True, roles=["patient"]),
        "resolve": action("Record resolution", "resolved", ["investigating", "acknowledged"], note_required=True, roles=["quality_officer", "compliance_officer", "facility_manager"]),
        "close": action("Close case", "closed", ["resolved"], note_required=True, roles=["quality_officer", "compliance_officer"]),
    },
)

configure(
    ["results-inbox", "critical-results"],
    category="clinical_results",
    patient_required=True,
    adapter="result_review",
    fields=[
        field("result_type", "Result type", "choice", required=True, choices=["laboratory", "imaging"]),
        field("lab_result", "Laboratory result", "entity", entity="lab_result"),
        field("imaging_result", "Imaging report", "entity", entity="imaging_result"),
        field("clinical_interpretation", "Clinical interpretation", "textarea", max_length=4000),
        field("follow_up_required", "Follow-up required", "boolean"),
    ],
    initial_status="pending_review",
    actions={
        "acknowledge": action("Acknowledge and document action", "acknowledged", ["pending_review", "escalated"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "medical_director"]),
        "escalate": action("Escalate critical finding", "escalated", ["pending_review", "acknowledged"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "medical_director"], fields=[field("assigned_to", "Escalate to", "entity", required=True, entity="staff")], tone="danger"),
        "close": action("Close follow-up", "completed", ["acknowledged", "escalated"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "medical_director"]),
    },
)
configure(
    ["clinical-task-inbox", "order-entry", "admission-orders", "procedure-documentation"],
    category="clinical_care",
    patient_required=True,
    adapter="clinical_task",
    fields=[
        field("task_type", "Task or order type", "choice", required=True, choices=["laboratory", "imaging", "medication", "admission", "procedure", "referral", "follow_up", "documentation", "other"]),
        field("instructions", "Clinical instructions", "textarea", required=True),
        field("assigned_to", "Assigned professional", "entity", entity="staff"),
        field("urgency", "Urgency", "choice", choices=["routine", "urgent", "critical"]),
        field("due_at", "Due date and time", "datetime"),
    ],
    initial_status="open",
    actions={
        "assign": action("Assign task", "assigned", ["open", "submitted"], roles=["doctor", "clinical_officer", "medical_director"], fields=[field("assigned_to", "Assign to", "entity", required=True, entity="staff")]),
        "start": action("Start task", "in_progress", ["open", "assigned"], roles=["doctor", "clinical_officer", "nurse", "lab_technician", "radiographer", "pharmacist"]),
        "block": action("Mark blocked", "blocked", ["open", "assigned", "in_progress"], note_required=True),
        "complete": action("Complete task", "completed", ["in_progress", "assigned"], note_required=True),
        "cancel": action("Cancel task", "cancelled", ["open", "assigned", "blocked"], note_required=True, roles=["doctor", "clinical_officer", "medical_director"], tone="danger"),
    },
)
configure(
    ["multidisciplinary-team"],
    category="clinical_collaboration",
    patient_required=True,
    adapter="care_conference",
    fields=[
        field("scheduled_at", "Meeting date and time", "datetime", required=True),
        field("chair", "Meeting chair", "entity", entity="staff"),
        field("participants", "Participant user IDs", "list"),
        field("agenda", "Clinical agenda", "textarea", required=True),
    ],
    initial_status="planned",
    actions={
        "start": action("Start meeting", "in_progress", ["planned"], roles=["doctor", "clinical_officer", "medical_director"]),
        "complete": action("Sign meeting outcome", "completed", ["in_progress"], note_required=True, roles=["doctor", "clinical_officer", "medical_director"]),
        "cancel": action("Cancel meeting", "cancelled", ["planned"], note_required=True, roles=["doctor", "medical_director"], tone="danger"),
    },
)
configure(
    ["on-call-schedule"],
    category="workforce_schedule",
    adapter="on_call_shift",
    fields=[
        field("assigned_to", "On-call professional", "entity", required=True, entity="staff"),
        field("starts_at", "Starts at", "datetime", required=True),
        field("ends_at", "Ends at", "datetime", required=True),
        field("location", "Coverage area", "text"),
        field("notes", "Handover notes", "textarea"),
    ],
    initial_status="scheduled",
    actions={
        "confirm": action("Confirm shift", "confirmed", ["scheduled"], roles=["doctor", "clinical_officer", "medical_director"]),
        "start": action("Start on-call shift", "in_progress", ["confirmed", "scheduled"]),
        "complete": action("End shift", "completed", ["in_progress"], note_required=True),
        "cancel": action("Cancel shift", "cancelled", ["scheduled", "confirmed"], note_required=True, roles=["medical_director", "facility_manager"], tone="danger"),
    },
)

configure(
    ["emar", "due-medications", "overdue-medications", "medication-omissions"],
    category="nursing_medication",
    patient_required=True,
    adapter="medication_administration",
    fields=[
        field("admission", "Admission", "entity", entity="admission"),
        field("medication", "Medication", "text", required=True),
        field("dose", "Dose", "text", required=True),
        field("route", "Route", "text", required=True),
        field("scheduled_at", "Scheduled time", "datetime", required=True),
        field("right_patient", "Right patient verified", "boolean", required=True),
        field("right_medication", "Right medication verified", "boolean", required=True),
        field("right_dose", "Right dose verified", "boolean", required=True),
        field("right_route", "Right route verified", "boolean", required=True),
        field("right_time", "Right time verified", "boolean", required=True),
        field("observations", "Pre/post-dose observations", "textarea"),
    ],
    initial_status="due",
    actions={
        "administer": action("Administer and sign", "given", ["due", "overdue"], note_required=True, roles=["nurse", "midwife"]),
        "omit": action("Record omission", "omitted", ["due", "overdue"], note_required=True, roles=["nurse", "midwife"], fields=[field("omission_reason", "Omission reason", "choice", required=True, choices=["patient_refused", "contraindicated", "unavailable", "nil_by_mouth", "clinical_hold", "other"])], tone="danger"),
        "escalate": action("Escalate overdue dose", "escalated", ["overdue", "omitted"], note_required=True, roles=["nurse", "midwife"], fields=[field("assigned_to", "Notify clinician", "entity", required=True, entity="staff")], tone="danger"),
    },
)

configure(
    ["create-appointment"],
    category="front_desk",
    patient_required=True,
    adapter="appointment_create",
    fields=[
        field("provider", "Provider", "entity", required=True, entity="staff"),
        field("appointment_date", "Appointment date", "date", required=True),
        field("start_time", "Start time", "time", required=True),
        field("end_time", "End time", "time", required=True),
        field("appointment_type", "Appointment type", "choice", required=True, choices=["in_person", "video", "phone", "home_visit"]),
        field("reason", "Reason for visit", "textarea", required=True),
    ],
    initial_status="submitted",
    actions={"confirm": action("Confirm booking", "confirmed", ["submitted"], note_required=True, roles=["receptionist"]), "cancel": COMMON_ACTIONS["cancel"]},
)
configure(
    ["queue-ticket", "patient-arrival-board", "walk-in-conversion"],
    category="front_desk_queue",
    patient_required=True,
    adapter="queue_ticket",
    fields=[
        field("appointment", "Appointment", "entity", entity="appointment"),
        field("service", "Service or department", "text", required=True),
        field("counter", "Counter or desk", "text"),
        field("priority", "Queue priority", "choice", choices=["routine", "urgent", "critical"]),
    ],
    initial_status="waiting",
    actions={
        "call": action("Call patient", "called", ["waiting"], roles=["receptionist"]),
        "serve": action("Start service", "serving", ["called", "waiting"], roles=["receptionist"]),
        "complete": action("Complete front-desk service", "completed", ["serving", "called"], roles=["receptionist"]),
        "cancel": action("Remove from queue", "cancelled", ["waiting", "called"], note_required=True, roles=["receptionist"], tone="danger"),
    },
)
configure(
    ["call-centre"],
    category="front_desk_communication",
    patient_required=False,
    adapter="call_centre_callback",
    fields=[
        field("patient", "Patient", "entity", entity="patient"),
        field("phone", "Callback phone", "text", required=True),
        field("scheduled_for", "Callback time", "datetime", required=True),
        field("assigned_to", "Assigned agent", "entity", entity="staff"),
        field("reason", "Reason for callback", "textarea", required=True),
    ],
    initial_status="scheduled",
    actions={
        "attempt": action("Record attempt", "attempted", ["scheduled", "no_answer"], note_required=True, roles=["receptionist"]),
        "reached": action("Patient reached", "reached", ["scheduled", "attempted", "no_answer"], note_required=True, roles=["receptionist"]),
        "no_answer": action("No answer", "no_answer", ["scheduled", "attempted"], note_required=True, roles=["receptionist"]),
        "complete": action("Complete callback", "completed", ["reached"], note_required=True, roles=["receptionist"]),
    },
)
configure(
    ["sms-confirmation"],
    category="front_desk_communication",
    patient_required=True,
    adapter="sms_confirmation",
    fields=[
        field("appointment", "Appointment", "entity", required=True, entity="appointment"),
        field("message", "Confirmation message", "textarea", required=True),
        field("phone", "Recipient phone", "text", required=True),
    ],
    initial_status="queued",
    actions={"send": action("Send confirmation", "sent", ["queued", "failed"], roles=["receptionist"]), "retry": action("Retry delivery", "queued", ["failed"], note_required=True, roles=["receptionist"])},
)

configure(
    ["master-patient-index", "duplicate-inbox", "patient-comparison", "merge-wizard", "unmerge-review", "identity-conflicts", "demographic-correction", "scan-upload", "document-classification", "record-release", "disclosure-authorization", "legal-holds", "record-restriction", "confidential-segmentation", "retention-schedules", "archival-queue", "destruction-approval", "data-export", "patient-access-request", "record-movement", "unmatched-documents"],
    category="records_management",
    patient_required=False,
    adapter="records_management",
    fields=[
        field("patient", "Patient", "entity", entity="patient"),
        field("request_type", "Records operation", "choice", required=True, choices=["correction", "release", "merge", "unmerge", "legal_hold", "restriction", "classification", "archive", "destruction", "export", "movement"]),
        field("secondary_patient", "Possible duplicate patient", "entity", entity="patient"),
        field("reason", "Reason and legal basis", "textarea", required=True),
        field("details", "Operational details", "json"),
    ],
    initial_status="submitted",
    actions={
        "review": action("Start identity/records review", "under_review", ["submitted"], roles=["records_officer", "compliance_officer"]),
        "approve": action("Approve records operation", "approved", ["under_review", "submitted"], note_required=True, roles=["records_officer", "compliance_admin"]),
        "reject": action("Reject operation", "rejected", ["under_review", "submitted"], note_required=True, roles=["records_officer", "compliance_admin"], tone="danger"),
        "execute": action("Execute approved operation", "completed", ["approved"], note_required=True, roles=["records_officer", "compliance_admin"]),
        "reverse": action("Request controlled reversal", "reversal_requested", ["completed"], note_required=True, roles=["records_officer", "compliance_admin"], tone="danger"),
    },
)

configure(
    ["deposit-collection", "split-payment", "payer-split", "refund-request", "void-payment", "bank-reconciliation", "mobile-money-reconciliation", "gateway-reconciliation", "expense-register", "supplier-invoices", "supplier-payments", "credit-notes", "debit-notes", "journal-entries", "period-close", "budget-management", "department-budgets", "approval-limits", "financial-exceptions"],
    category="finance",
    adapter="finance_operation",
    fields=[
        field("invoice", "Invoice", "entity", entity="invoice"),
        field("operation_type", "Financial operation", "choice", required=True, choices=["deposit", "split_payment", "payer_allocation", "refund", "void", "reconciliation", "expense", "supplier_invoice", "supplier_payment", "credit_note", "debit_note", "journal", "period_close", "budget", "approval_limit", "exception"]),
        field("amount", "Amount", "money", required=True),
        field("currency", "Currency", "choice", choices=["UGX", "USD", "KES", "TZS", "RWF"]),
        field("account_code", "Debit account code", "text"),
        field("offset_account_code", "Credit account code", "text"),
        field("reference", "Bank, mobile-money or supplier reference", "text"),
        field("details", "Narration and evidence", "textarea", required=True),
    ],
    initial_status="submitted",
    actions={
        "review": action("Review transaction", "under_review", ["submitted"], roles=["accountant", "finance_manager"]),
        "approve": action("Approve transaction", "approved", ["submitted", "under_review"], note_required=True, roles=["finance_manager"]),
        "reject": action("Reject transaction", "rejected", ["submitted", "under_review"], note_required=True, roles=["finance_manager"], tone="danger"),
        "post": action("Post to ledger", "posted", ["approved"], note_required=True, roles=["accountant", "finance_manager"]),
        "reconcile": action("Mark reconciled", "completed", ["posted", "processing"], note_required=True, roles=["accountant", "finance_manager"]),
        "reverse": action("Create controlled reversal", "reversed", ["posted", "completed"], note_required=True, roles=["finance_manager"], tone="danger"),
    },
)


# Completion adapters for pages that previously opened generic workflow cases.
# Each transactional page now creates a canonical OperationalAction or a concrete
# domain record. Dashboards, directories, analytics and detail views are marked
# read-only below and use their page-data endpoint instead.
configure(
    ["sick-notes", "referral-letters"],
    category="clinical_document",
    patient_required=True,
    adapter="clinical_document",
    fields=[
        field("document_type", "Document type", "choice", required=True, choices=["sick_note", "referral_letter"]),
        field("clinical_summary", "Clinical summary", "textarea", required=True),
        field("recommendations", "Recommendations", "textarea"),
        field("valid_from", "Valid from", "date"),
        field("valid_until", "Valid until", "date"),
    ],
    initial_status="draft",
    actions={
        "submit": COMMON_ACTIONS["submit"],
        "sign": action("Electronically sign", "signed", ["draft", "submitted"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "medical_director"]),
        "revoke": action("Revoke document", "revoked", ["signed"], note_required=True, roles=["medical_director", "clinical_safety_admin"], tone="danger"),
    },
)

configure(
    ["clinical-templates", "favourite-order-sets", "diagnosis-favourites"],
    category="clinical_personalisation",
    adapter="operational_action",
    fields=[
        field("name", "Name", "text", required=True),
        field("content", "Template or favourite definition", "json", required=True),
        field("shared", "Share with department", "boolean"),
        field("active", "Active", "boolean"),
    ],
    initial_status="submitted",
    actions={
        "activate": action("Activate", "executed", ["submitted", "approved"], roles=["doctor", "clinical_officer", "dentist", "physiotherapist", "nutritionist", "psychologist"]),
        "archive": action("Archive", "cancelled", ["submitted", "executed"], note_required=True),
    },
)

configure(
    ["shift-summary", "patient-education", "supply-requests", "equipment-checklist"],
    category="nursing_operations",
    patient_required=False,
    adapter="operational_action",
    fields=[
        field("patient", "Patient", "entity", entity="patient"),
        field("admission", "Admission", "entity", entity="admission"),
        field("operation_type", "Nursing operation", "choice", required=True, choices=["shift_summary", "patient_education", "supply_request", "equipment_check"]),
        field("details", "Clinical or operational details", "textarea", required=True),
        field("items", "Items or checklist", "json"),
        field("due_at", "Due at", "datetime"),
    ],
    initial_status="submitted",
    actions={
        "acknowledge": action("Acknowledge", "approved", ["submitted"], note_required=True),
        "execute": action("Complete operation", "executed", ["submitted", "approved"], note_required=True),
        "escalate": action("Escalate", "under_review", ["submitted", "approved"], note_required=True, tone="danger"),
        "cancel": COMMON_ACTIONS["cancel"],
    },
)

configure(
    ["delivery-team", "caesarean-escalation", "mother-baby-link", "postnatal-monitoring"],
    category="maternity_child_health",
    patient_required=True,
    adapter="maternity_operation",
    fields=[
        field("operation_type", "Maternity operation", "choice", required=True, choices=["delivery_team", "caesarean_escalation", "mother_baby_link", "postnatal_monitoring"]),
        field("episode_reference", "Maternity episode number", "text", required=True),
        field("observed_at", "Observed at", "datetime", required=True),
        field("measurements", "Measurements", "json"),
        field("assessment", "Assessment", "textarea", required=True),
        field("intervention", "Intervention", "textarea"),
    ],
    initial_status="in_progress",
    actions={
        "record": action("Record update", "in_progress", ["in_progress", "draft"]),
        "escalate": action("Escalate", "escalated", ["in_progress"], note_required=True, tone="danger"),
        "complete": COMMON_ACTIONS["complete"],
    },
)

configure(
    ["operation-note"],
    category="clinical_document",
    patient_required=True,
    adapter="clinical_document",
    fields=[
        field("document_type", "Document type", "text", required=True),
        field("clinical_summary", "Procedure and findings", "textarea", required=True),
        field("recommendations", "Post-operative plan", "textarea", required=True),
    ],
    initial_status="draft",
    actions={"submit": COMMON_ACTIONS["submit"], "sign": action("Sign operation note", "signed", ["draft", "submitted"], note_required=True, roles=["doctor", "clinical_officer", "dentist", "medical_director"])},
)
configure(
    ["post-op-orders"],
    category="theatre",
    patient_required=True,
    adapter="theatre_operation",
    fields=[field("surgical_case_reference", "Surgical case number", "text", required=True), field("orders", "Post-operative orders", "json", required=True), field("priority", "Priority", "choice", choices=["routine", "urgent", "critical"])],
    initial_status="submitted",
    actions={"approve": action("Approve orders", "approved", ["submitted"], note_required=True, roles=["doctor", "anaesthetist", "medical_director"]), "execute": action("Activate orders", "executed", ["approved"], note_required=True, roles=["nurse", "theatre_nurse", "doctor", "anaesthetist"])},
)

configure(
    ["cancel-appointment", "service-routing", "referral-reception", "admission-registration", "discharge-checkout", "missing-information", "duplicate-warning", "insurance-check", "preauthorization-check", "deposit-request", "appointment-slip", "visitor-management"],
    category="front_desk",
    patient_required=True,
    adapter="front_desk_operation",
    fields=[
        field("operation_type", "Front-desk operation", "text", required=True),
        field("appointment", "Appointment", "entity", entity="appointment"),
        field("admission", "Admission", "entity", entity="admission"),
        field("invoice", "Invoice", "entity", entity="invoice"),
        field("service", "Service or department", "text"),
        field("scheduled_at", "Scheduled time", "datetime"),
        field("details", "Details", "textarea", required=True),
    ],
    initial_status="submitted",
    actions={
        "verify": action("Verify", "under_review", ["submitted"], note_required=True),
        "approve": action("Approve", "approved", ["submitted", "under_review"], note_required=True),
        "execute": action("Complete operation", "executed", ["approved", "submitted"], note_required=True),
        "reject": action("Reject", "rejected", ["submitted", "under_review"], note_required=True, tone="danger"),
        "cancel": COMMON_ACTIONS["cancel"],
    },
)

configure(
    ["mobile-money-collections"],
    category="finance",
    adapter="finance_operation",
    fields=[field("invoice", "Invoice", "entity", entity="invoice", required=True), field("operation_type", "Operation", "text", required=True), field("amount", "Amount", "money", required=True), field("currency", "Currency", "choice", choices=["UGX", "USD", "KES", "TZS", "RWF"]), field("reference", "Mobile-money reference", "text"), field("details", "Collection instructions", "textarea", required=True)],
    initial_status="submitted",
    actions={"initiate": action("Initiate collection", "processing", ["submitted"]), "confirm": action("Confirm callback", "posted", ["processing"], note_required=True), "reconcile": action("Reconcile", "completed", ["posted"], note_required=True), "fail": action("Mark failed", "rejected", ["processing"], note_required=True, tone="danger")},
)

configure(
    ["clarification-chat"],
    category="pharmacy",
    patient_required=True,
    adapter="operational_action",
    fields=[field("prescription", "Prescription", "entity", entity="prescription", required=True), field("question", "Clarification question", "textarea", required=True), field("assigned_to", "Prescriber", "entity", entity="staff")],
    initial_status="submitted",
    actions={"respond": action("Respond", "approved", ["submitted", "under_review"], note_required=True), "accept": action("Accept clarification", "executed", ["approved"], note_required=True), "cancel": COMMON_ACTIONS["cancel"]},
)
configure(
    ["drug-returns", "stock-transfers", "stock-adjustments", "purchase-order-detail", "supplier-invoice-match"],
    category="pharmacy_inventory",
    adapter="inventory_operation",
    fields=[field("operation_type", "Inventory operation", "text", required=True), field("batch_number", "Batch number", "text"), field("quantity", "Quantity", "number"), field("source_location", "Source location", "text"), field("destination_location", "Destination location", "text"), field("reference", "Purchase order or invoice reference", "text"), field("reason", "Reason", "textarea", required=True)],
    initial_status="submitted",
    actions={"review": action("Review", "under_review", ["submitted"]), "approve": action("Approve", "approved", ["submitted", "under_review"], note_required=True), "execute": action("Post inventory movement", "executed", ["approved"], note_required=True), "reject": action("Reject", "rejected", ["submitted", "under_review"], note_required=True, tone="danger")},
)
configure(
    ["report-printing"],
    category="laboratory",
    adapter="operational_action",
    fields=[field("result_reference", "Released result reference", "text", required=True), field("format", "Output format", "choice", choices=["pdf", "label", "secure_link"]), field("copies", "Copies", "number"), field("reason", "Purpose", "textarea")],
    initial_status="submitted",
    actions={"generate": action("Generate report", "executed", ["submitted"], note_required=True)},
)

configure(
    ["room-assignment", "acquisition-status", "imaging-export", "secure-study-link"],
    category="radiology",
    patient_required=True,
    adapter="radiology_operation",
    fields=[field("imaging_order", "Imaging order ID", "number", required=True), field("operation_type", "Radiology operation", "text", required=True), field("room", "Room or modality", "text"), field("status", "Acquisition status", "text"), field("expires_at", "Secure link expiry", "datetime"), field("details", "Details", "textarea")],
    initial_status="submitted",
    actions={"approve": action("Approve", "approved", ["submitted"], note_required=True), "execute": action("Execute", "executed", ["submitted", "approved"], note_required=True), "reject": action("Reject", "rejected", ["submitted"], note_required=True, tone="danger")},
)
configure(
    ["report-templates", "voice-dictation"],
    category="radiology",
    adapter="operational_action",
    fields=[field("name", "Name", "text", required=True), field("content", "Template or dictation content", "textarea", required=True), field("metadata", "Metadata", "json")],
    initial_status="submitted",
    actions={"approve": action("Approve", "approved", ["submitted"], note_required=True), "publish": action("Publish", "executed", ["approved"], note_required=True), "archive": action("Archive", "cancelled", ["approved", "executed"], note_required=True)},
)

configure(
    ["equipment-check", "cleaning-check", "offline-paramedic"],
    category="emergency",
    adapter="emergency_operation",
    fields=[field("dispatch_reference", "Dispatch or emergency number", "text"), field("operation_type", "Emergency operation", "text", required=True), field("checklist", "Checklist or offline payload", "json", required=True), field("recorded_at", "Recorded at", "datetime", required=True), field("notes", "Notes", "textarea")],
    initial_status="submitted",
    actions={"synchronize": action("Synchronize", "executed", ["submitted", "approved"], note_required=True), "approve": action("Approve", "approved", ["submitted"], note_required=True), "reject": action("Reject", "rejected", ["submitted"], note_required=True, tone="danger")},
)

configure(
    ["room-management", "service-catalogue", "price-lists", "queue-configuration", "discharge-clearance", "staff-onboarding", "shift-calendar", "leave-calendar", "payroll-integration", "maintenance-requests", "biomedical-equipment", "supplier-management", "corrective-action", "complaint-detail"],
    category="facility_operations",
    adapter="facility_operation",
    fields=[field("operation_type", "Facility operation", "text", required=True), field("subject_user", "Staff or responsible user", "entity", entity="staff"), field("department", "Department ID", "number"), field("effective_at", "Effective at", "datetime"), field("details", "Details", "textarea", required=True), field("configuration", "Structured configuration", "json")],
    initial_status="submitted",
    actions={"review": action("Review", "under_review", ["submitted"]), "approve": action("Approve", "approved", ["submitted", "under_review"], note_required=True), "execute": action("Apply change", "executed", ["approved"], note_required=True), "reject": action("Reject", "rejected", ["submitted", "under_review"], note_required=True, tone="danger"), "reverse": action("Reverse", "reversed", ["executed"], note_required=True, tone="danger")},
)

configure(
    ["plan-designer", "provider-contract", "tariff-editor", "preauthorization-workbench", "claim-line-adjudication", "diagnosis-procedure-coding", "document-review", "medical-review", "settlement-reconciliation", "provider-payment"],
    category="insurance",
    patient_required=False,
    adapter="insurance_operation",
    fields=[field("operation_type", "Insurance operation", "text", required=True), field("claim_id", "Claim ID", "number"), field("preauthorization_id", "Preauthorization ID", "number"), field("policy_id", "Policy ID", "number"), field("amount", "Amount", "money"), field("decision", "Decision", "choice", choices=["approve", "partially_approve", "reject", "query", "hold", "pay"]), field("details", "Decision details", "textarea", required=True), field("configuration", "Benefits, contract or tariff configuration", "json")],
    initial_status="submitted",
    actions={"review": action("Review", "under_review", ["submitted"]), "approve": action("Approve", "approved", ["submitted", "under_review"], note_required=True), "execute": action("Apply decision", "executed", ["approved"], note_required=True), "query": action("Request information", "under_review", ["submitted", "under_review"], note_required=True), "reject": action("Reject", "rejected", ["submitted", "under_review"], note_required=True, tone="danger")},
)

# Detail and analytical pages use their own data endpoint and do not create fake
# workflow records. Transactional controls are exposed only on request/action pages.
READ_ONLY_PAGES = [
    "appointment-detail", "consultation-detail", "secure-conversation", "prescription-detail",
    "allergy-medication-card", "laboratory-order-detail", "laboratory-result-trends",
    "imaging-order-detail", "diagnostic-viewer", "admission-detail", "ward-care-team",
    "discharge-summary", "referral-detail", "insurance-policy-detail", "preauthorization-detail",
    "claim-detail", "payment-methods", "mobile-money-status", "receipt-detail",
    "medical-documents", "emergency-medical-card", "notification-inbox", "family-access",
    "dependent-dashboard", "my-patients", "patient-detail", "daily-inpatients",
    "consultation-history", "secure-message-inbox", "follow-up-recall-list", "personal-audit",
    "professional-credentials", "professional-subscription", "assigned-patients",
    "ward-patient-list", "patient-nursing-chart", "provider-schedules", "appointment-calendar",
    "master-patient-index", "patient-account", "pending-payments", "cash-drawer",
    "shift-transactions", "end-of-day", "receipt-history", "daily-cashbook",
    "accounts-receivable", "accounts-payable", "general-ledger", "trial-balance",
    "income-statement", "balance-sheet", "cash-flow", "tax-report", "revenue-analytics",
    "ageing-analysis", "revenue-leakage", "department-profitability", "forecasting",
    "consolidated-reporting", "stock-valuation", "expiry-calendar", "pharmacy-sales",
    "turnaround-time", "imaging-calendar", "modality-worklist", "pacs-viewer",
    "system-metrics", "worker-health", "audit-explorer", "notification-monitor",
    "antenatal-dashboard", "pregnancy-detail", "high-risk-pregnancy", "labour-ward-board",
    "turnaround", "utilization", "medication-history", "study-comparison", "repeat-analysis",
    "command-dashboard", "multi-branch-dashboard", "department-detail", "visual-bed-map",
    "ward-detail", "staff-profile", "staff-credential", "inventory-valuation", "financial-reports",
    "member-directory", "member-profile", "benefit-comparison", "provider-network",
    "eligibility-detail", "claims-ageing", "loss-ratio", "utilization-analytics", "dead-letter",
]
for _slug in READ_ONLY_PAGES:
    if _slug in MANIFEST and _slug not in OVERRIDES:
        configure([_slug], fields=[], actions={}, create_allowed=False)
    elif _slug in MANIFEST:
        OVERRIDES[_slug]["create_allowed"] = False

ADMIN_READ_ONLY_PAGES = [
    "user-detail", "account-activity", "session-management", "role-matrix",
    "permission-comparison", "organization-detail", "branch-detail",
    "professional-detail", "verification-case", "licence-viewer",
    "ocr-comparison", "verification-timeline", "credential-renewals",
    "subscription-detail", "payment-reconciliation", "refund-detail",
    "notification-monitor", "template-editor", "cms-editor",
    "integration-detail", "event-delivery", "worker-health", "system-metrics",
    "audit-explorer", "security-incident", "backup-restore",
    "data-export-centre", "retention-controls", "regulatory-reporting",
]
for _slug in ADMIN_READ_ONLY_PAGES:
    if _slug in MANIFEST:
        configure([_slug], fields=[], actions={}, create_allowed=False)

configure(
    ["event-replay"],
    category="administration",
    adapter="admin_operation",
    fields=[field("dead_letter_id", "Dead-letter event ID", "number", required=True), field("action_reason", "Replay reason", "textarea", required=True)],
    initial_status="submitted",
    actions={"execute": action("Queue replay", "completed", ["submitted", "approved"], note_required=True, roles=["it_support", "platform_super_admin"])},
)
configure(
    ["feature-flags", "localization", "maintenance-mode"],
    category="administration",
    adapter="admin_operation",
    fields=[field("configuration_key", "Configuration key", "text", required=True), field("configuration", "Configuration", "json", required=True), field("action_reason", "Change reason", "textarea", required=True)],
    initial_status="submitted",
    actions={"approve": action("Approve change", "approved", ["submitted"], note_required=True, roles=["platform_super_admin"]), "execute": action("Apply configuration", "completed", ["approved"], note_required=True, roles=["platform_super_admin"])},
)


SCHEMA_DRIVEN_DOMAINS = {
    "inpatient", "maternity", "theatre", "emergency", "laboratory",
    "radiology", "pharmacy", "finance", "insurance", "records",
    "specialist", "verification", "security", "reporting",
}


def _field_from_enterprise_schema(name, spec, *, required=None):
    kind_map = {
        "select": "choice", "string": "text", "text": "text",
        "textarea": "textarea", "datetime": "datetime", "date": "date",
        "number": "number", "boolean": "boolean", "list": "list",
        "json": "json",
    }
    kind = kind_map.get(spec.get("kind"), spec.get("kind") or "text")
    entity = None
    entity_names = {
        "receiver_id": "staff", "notified_user_id": "staff", "staff_id": "staff",
        "clinician_id": "staff", "doctor_id": "staff", "reviewer_id": "staff",
        "patient_id": "patient", "admission_id": "admission", "appointment_id": "appointment",
        "invoice_id": "invoice", "prescription_id": "prescription",
        "lab_result_id": "lab_result", "imaging_result_id": "imaging_result",
        "claim_id": "claim", "transaction_id": "payment", "payment_id": "payment",
        "dispensing_record_id": "dispensing_record", "inventory_batch_id": "inventory_batch",
        "batch_id": "inventory_batch", "organization_id": "organization",
        "branch_id": "branch", "location_id": "branch", "department_id": "department",
    }
    if name in entity_names:
        kind = "entity"
        entity = entity_names[name]
    value = field(
        name,
        spec.get("label") or name.replace("_", " ").title(),
        kind,
        required=bool(spec.get("required")) if required is None else bool(required),
        choices=spec.get("options") if kind == "choice" else None,
        entity=entity,
    )
    value["schema_field"] = True
    return value


def _schema_driven_override(definition):
    """Turn schema-backed catalogue pages into real transactional workflows.

    The previous deep UI exposed many record-type pages through shared shells.  A
    page that declares enterprise ``recordTypes`` now receives fields and a state
    machine directly from the validated enterprise schema.  The resulting POST
    creates a canonical ``EnterpriseRecord`` and every action updates that record.
    """
    record_types = list(definition.get("recordTypes") or [])
    if not record_types or not definition.get("create_allowed", True):
        return definition
    try:
        from enterprise.schemas import WORKFLOWS, schema_for
    except Exception:
        return definition
    schemas = [(record_type, schema_for(record_type)) for record_type in record_types]
    schemas = [(record_type, schema) for record_type, schema in schemas if schema]
    if not schemas:
        return definition

    # Canonical adapters already perform additional domain side effects, while
    # pages without one use the generic schema-backed enterprise-record adapter.
    if not definition.get("adapter"):
        definition["adapter"] = "enterprise_record"

    relation_fields = []
    domains = {schema["domain"] for _, schema in schemas}
    patient_domains = {"inpatient", "maternity", "theatre", "emergency", "laboratory", "radiology", "pharmacy", "specialist", "insurance", "records"}
    if domains & patient_domains:
        relation_fields.append(field("patient", "Patient", "entity", entity="patient", required=bool(definition.get("patient_required"))))
    if domains & {"inpatient", "maternity", "theatre"}:
        relation_fields.append(field("admission", "Admission", "entity", entity="admission"))
    if "maternity" in domains:
        relation_fields.append(field("episode_reference", "Maternity episode number", "text"))
    if "theatre" in domains:
        relation_fields.append(field("surgical_case_reference", "Surgical case number", "text"))
    if "emergency" in domains:
        relation_fields.append(field("emergency_reference", "Emergency or dispatch number", "text"))
    if "laboratory" in domains:
        relation_fields.append(field("specimen_reference", "Laboratory order or specimen reference", "text"))
    if "pharmacy" in domains:
        relation_fields.append(field("batch_number", "Inventory batch number", "text"))
    if domains & {"specialist", "radiology", "laboratory"}:
        relation_fields.append(field("appointment", "Appointment", "entity", entity="appointment"))
    relation_fields.append(field("assigned_to", "Assigned professional", "entity", entity="staff"))

    definition["record_type_fields"] = {
        record_type: [_field_from_enterprise_schema(name, spec) for name, spec in (schema.get("fields") or {}).items()]
        for record_type, schema in schemas
    }
    if len(schemas) > 1:
        relation_fields.append(field("record_type", "Record type", "choice", required=True, choices=[item[0] for item in schemas]))
        # The form initially exposes the union for discoverability, but only a
        # field required by every supported type is marked required.  The client
        # uses ``record_type_fields`` to switch to the selected type, and the
        # EnterpriseRecord model repeats authoritative per-type validation.
        merged = {}
        presence = {}
        required_count = {}
        for _, schema in schemas:
            for name, spec in (schema.get("fields") or {}).items():
                merged.setdefault(name, spec)
                presence[name] = presence.get(name, 0) + 1
                required_count[name] = required_count.get(name, 0) + int(bool(spec.get("required")))
        schema_fields = [
            _field_from_enterprise_schema(
                name, spec,
                required=presence.get(name) == len(schemas) and required_count.get(name) == len(schemas),
            )
            for name, spec in merged.items()
        ]
    else:
        schema_fields = definition["record_type_fields"][schemas[0][0]]

    definition["fields"] = relation_fields + schema_fields
    definition["patient_required"] = bool(definition.get("patient_required") or domains & {"maternity", "theatre", "specialist"})

    workflow = WORKFLOWS.get(schemas[0][0], WORKFLOWS["generic"])
    if workflow:
        initial = next(iter(workflow))
        definition["initial_status"] = initial
        transitions = {}
        for from_status, choices in workflow.items():
            for code, to_status in choices.items():
                config = transitions.setdefault(code, {
                    "label": code.replace("_", " ").title(),
                    "from": [],
                    "to": to_status,
                    "note_required": code in {"reject", "cancel", "hold", "amend", "reopen", "escalate", "withhold", "omit"},
                    "tone": "danger" if code in {"reject", "cancel", "withhold", "omit", "escalate"} else "primary",
                })
                config["from"].append(from_status)
        definition["actions"] = transitions
    return definition


def definition_for(slug):
    page = MANIFEST.get(slug)
    if not page:
        return None
    definition = deepcopy(page)
    definition["initial_status"] = "draft"
    definition["category"] = page.get("group", "workflow")
    definition["fields"] = deepcopy(COMMON_FIELDS)
    definition["actions"] = deepcopy(COMMON_ACTIONS)
    definition["patient_required"] = False
    definition["supports_comments"] = True
    definition["supports_attachments"] = True
    definition["adapter"] = None
    definition["create_allowed"] = True
    definition["data_endpoint"] = f"/api/v1/journeys/pages/{slug}/data/"
    override = OVERRIDES.get(slug, {})
    for key, value in override.items():
        if value is not None:
            definition[key] = deepcopy(value)
    definition = _schema_driven_override(definition)
    slug_lower = slug.lower()
    if definition.get("create_allowed", True):
        definition["page_mode"] = "record_workspace" if definition.get("recordTypes") else "transaction"
    elif any(token in slug_lower for token in ("dashboard", "analytics", "statement", "balance", "cash-flow", "trial-balance", "income-statement", "reporting", "metrics", "health")):
        definition["page_mode"] = "dashboard"
    elif any(token in slug_lower for token in ("detail", "viewer", "profile", "card", "summary")):
        definition["page_mode"] = "detail"
    elif any(token in slug_lower for token in ("queue", "inbox", "worklist", "calendar", "board", "directory", "list", "monitor", "explorer", "renewals")):
        definition["page_mode"] = "work_queue"
    else:
        definition["page_mode"] = "reference"
    definition["canonical_source"] = (
        "enterprise_record" if definition.get("recordTypes")
        else definition.get("adapter")
        or ("workflow_queue" if definition["page_mode"] == "work_queue" else "page_data")
    )
    # Patient pages always bind to the logged-in patient unless explicitly linked
    # to a dependent. Clinical pages require a selected patient when configured.
    return definition


def allowed_roles(slug):
    definition = definition_for(slug)
    return set(definition.get("roles", [])) if definition else set()


def validate_payload(definition, payload, *, partial=False):
    errors = {}
    fields = {item["name"]: item for item in definition.get("fields", [])}
    for name, spec in fields.items():
        value = payload.get(name)
        if spec.get("required") and not partial and value in (None, "", [], {}):
            errors[name] = "This field is required."
            continue
        if value in (None, ""):
            continue
        max_length = spec.get("max_length")
        if max_length and len(str(value)) > max_length:
            errors[name] = f"Maximum length is {max_length}."
        if spec.get("type") == "choice" and spec.get("choices") and value not in spec["choices"]:
            errors[name] = "Select a valid choice."
        if spec.get("type") in {"number", "money"}:
            try:
                float(value)
            except (TypeError, ValueError):
                errors[name] = "Enter a valid number."
    return errors
