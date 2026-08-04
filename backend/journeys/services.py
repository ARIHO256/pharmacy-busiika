import datetime
import math
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from rest_framework.exceptions import PermissionDenied, ValidationError

from enterprise.access import (
    active_context_for,
    active_department,
    active_location,
    active_organization,
    active_role,
    is_platform_super_admin,
)
from governance.models import AuditEvent
from governance.services import audit

from .definitions import definition_for, validate_payload
from .models import (
    GeneratedClinicalDocument, OperationalAction, ResultReview,
    WorkflowActionEvent, WorkflowCase,
)



ADMIN_SYSTEM_PAGES = {
    "worker-health", "system-metrics", "backup-restore", "integration-detail",
    "event-delivery", "dead-letter", "event-replay", "notification-monitor",
}
ADMIN_COMPLIANCE_PAGES = {
    "audit-explorer", "security-incident", "data-export-centre", "retention-controls",
    "regulatory-reporting", "privacy-request", "legal-holds", "record-restriction",
}
ADMIN_CLINICAL_SAFETY_PAGES = {
    "verification-case", "licence-viewer", "ocr-comparison", "verification-timeline",
    "credential-renewals", "critical-results", "clinical-audit", "mortality-review",
}
ADMIN_OPERATIONS_PAGES = {
    "subscription-detail", "payment-reconciliation", "refund-detail", "cms-editor",
    "template-editor", "maintenance-mode", "organization-detail", "branch-detail",
}
ADMIN_IDENTITY_PAGES = {
    "user-detail", "account-activity", "session-management", "role-matrix",
    "permission-comparison", "professional-detail", "feature-flags", "localization",
}


def admin_page_allowed(user, slug):
    role = active_role(user)
    if is_platform_super_admin(user):
        return True
    if slug in ADMIN_SYSTEM_PAGES:
        return role in {"it_support", "operations_admin"}
    if slug in ADMIN_COMPLIANCE_PAGES:
        return role in {"compliance_officer", "compliance_admin"}
    if slug in ADMIN_CLINICAL_SAFETY_PAGES:
        return role in {"medical_director", "clinical_safety_admin"}
    if slug in ADMIN_OPERATIONS_PAGES:
        return role in {"facility_manager", "operations_admin"}
    if slug in ADMIN_IDENTITY_PAGES:
        return False
    return False

TERMINAL_STATUSES = {"completed", "closed", "cancelled", "rejected", "revoked", "released", "signed", "reversed"}

OPERATIONAL_ADAPTERS = {
    "operational_action", "front_desk_operation", "facility_operation",
    "insurance_operation", "radiology_operation",
}

_OPERATIONAL_STATE_MAP = {
    "draft": OperationalAction.State.DRAFT,
    "submitted": OperationalAction.State.SUBMITTED,
    "pending": OperationalAction.State.SUBMITTED,
    "under_review": OperationalAction.State.UNDER_REVIEW,
    "processing": OperationalAction.State.UNDER_REVIEW,
    "approved": OperationalAction.State.APPROVED,
    "executed": OperationalAction.State.EXECUTED,
    "completed": OperationalAction.State.EXECUTED,
    "posted": OperationalAction.State.EXECUTED,
    "released": OperationalAction.State.EXECUTED,
    "signed": OperationalAction.State.EXECUTED,
    "rejected": OperationalAction.State.REJECTED,
    "cancelled": OperationalAction.State.CANCELLED,
    "revoked": OperationalAction.State.CANCELLED,
    "reversed": OperationalAction.State.REVERSED,
    "failed": OperationalAction.State.FAILED,
}


def _operational_state(status):
    return _OPERATIONAL_STATE_MAP.get(str(status or "").lower(), OperationalAction.State.SUBMITTED)


def _operational_domain(definition, case):
    return str(definition.get("category") or case.category or "operations")[:80]


def _create_operational_action(case, definition, user):
    """Persist the authoritative transaction behind a workflow case.

    WorkflowCase remains the collaboration/approval envelope. OperationalAction
    is the canonical effect record for cross-domain pages that do not own a
    narrower model. This prevents a page from reporting success only because a
    generic case exists.
    """
    adapter = definition.get("adapter")
    if adapter not in OPERATIONAL_ADAPTERS:
        return None
    actions = definition.get("actions") or {}
    requires_approval = any(code in actions for code in {"approve", "authorize", "verify"})
    operation_code = str(case.data.get("operation_type") or case.page_slug).strip()[:100]
    action, created = OperationalAction.objects.get_or_create(
        workflow_case=case,
        defaults={
            "page_slug": case.page_slug,
            "domain": _operational_domain(definition, case),
            "operation_code": operation_code,
            "organization": case.organization,
            "location": case.location,
            "department": case.department,
            "patient": case.patient,
            "subject_user": case.subject_user,
            "appointment": case.appointment,
            "admission": case.admission,
            "invoice": case.invoice,
            "state": _operational_state(case.status),
            "payload": case.data or {},
            "result": case.result or {},
            "requires_approval": requires_approval,
            "created_by": user,
            "updated_by": user,
        },
    )
    if not created:
        action.payload = case.data or {}
        action.result = case.result or {}
        action.state = _operational_state(case.status)
        action.updated_by = user
        action.save(update_fields=["payload", "result", "state", "updated_by", "updated_at"])
    return action


def _append_effect(action, *, event, actor, details=None):
    log = list(action.effect_log or [])
    log.append({
        "event": event,
        "actor_id": getattr(actor, "id", None),
        "actor_role": active_role(actor) if actor else "system",
        "at": timezone.now().isoformat(),
        "details": details or {},
    })
    action.effect_log = log[-250:]


def _execute_operational_effect(case, definition, action, action_code, payload, user):
    """Apply bounded, idempotent domain effects for cross-domain actions.

    Effects deliberately use existing domain services/models and never fabricate
    successful external-provider outcomes. External operations remain pending
    until their signed callback or provider adapter confirms them.
    """
    slug = case.page_slug
    details = {}
    effect_type = ""
    effect_id = ""

    if definition.get("adapter") == "front_desk_operation":
        if slug == "cancel-appointment" and case.appointment_id and action_code in {"approve", "execute"}:
            appointment = case.appointment
            if appointment.status != appointment.Status.CANCELLED:
                appointment.transition_to(appointment.Status.CANCELLED, actor=user, reason=payload.get("note") or case.data.get("details", ""), metadata={"workflow_case": str(case.public_id)})
            details = {"appointment_status": appointment.status}
            effect_type, effect_id = "appointments.Appointment", str(appointment.id)
        elif slug == "discharge-checkout" and case.admission_id and action_code == "execute":
            admission = case.admission
            if admission.status not in {admission.Status.DISCHARGED, admission.Status.DECEASED, admission.Status.CANCELLED}:
                admission.status = admission.Status.DISCHARGE_PENDING
                admission.save(update_fields=["status", "updated_at"])
            details = {"admission_status": admission.status}
            effect_type, effect_id = "operations.Admission", str(admission.id)
        elif slug == "deposit-request" and case.invoice_id and action_code in {"approve", "execute"}:
            details = {"invoice_id": case.invoice_id, "deposit_requested": True, "provider_confirmation_required": True}
            effect_type, effect_id = "payments.Invoice", str(case.invoice_id)
        else:
            details = {"front_desk_operation": slug, "completed": action_code == "execute"}

    elif definition.get("adapter") == "radiology_operation":
        from operations.models import ImagingOrder
        order_id = case.data.get("imaging_order")
        order = ImagingOrder.objects.filter(pk=order_id).first() if order_id else None
        if not order:
            raise ValidationError({"imaging_order": "Select an imaging order available in this context."})
        if case.organization_id and order.organization_id != case.organization_id:
            raise PermissionDenied("The imaging order belongs to another organization.")
        if slug == "room-assignment" and action_code == "execute":
            room_note = f"Room/modality assigned: {case.data.get('room', '')}"
            order.clinical_indication = "\n".join(filter(None, [order.clinical_indication, room_note]))
            order.save(update_fields=["clinical_indication", "updated_at"])
        elif slug == "acquisition-status" and action_code == "execute":
            status_value = str(case.data.get("status") or "performed").lower()
            allowed = {choice[0] for choice in ImagingOrder.Status.choices}
            if status_value not in allowed:
                raise ValidationError({"status": "Select a valid imaging-order status."})
            order.status = status_value
            order.performed_at = order.performed_at or timezone.now()
            order.radiographer = order.radiographer or user
            order.save(update_fields=["status", "performed_at", "radiographer", "updated_at"])
        elif slug in {"imaging-export", "secure-study-link"} and action_code == "execute":
            details["external_provider_confirmation_required"] = True
            details["expires_at"] = case.data.get("expires_at")
        details.update({"imaging_order_id": order.id, "imaging_status": order.status})
        effect_type, effect_id = "operations.ImagingOrder", str(order.id)

    elif definition.get("adapter") == "insurance_operation":
        from services.models import InsuranceClaim, InsurancePreauthorization
        claim = InsuranceClaim.objects.filter(pk=case.data.get("claim_id")).first() if case.data.get("claim_id") else None
        preauth = InsurancePreauthorization.objects.filter(pk=case.data.get("preauthorization_id")).first() if case.data.get("preauthorization_id") else None
        decision = str(case.data.get("decision") or "").lower()
        if action_code == "execute" and preauth:
            mapping = {
                "approve": preauth.Status.APPROVED,
                "partially_approve": preauth.Status.PARTIALLY_APPROVED,
                "reject": preauth.Status.REJECTED,
                "query": preauth.Status.QUERY,
                "hold": preauth.Status.IN_REVIEW,
            }
            if decision in mapping:
                preauth.status = mapping[decision]
                preauth.decision_reason = payload.get("note") or case.data.get("details", "")
                preauth.reviewed_by = user
                preauth.reviewed_at = timezone.now()
                if decision in {"approve", "partially_approve"} and case.data.get("amount") not in (None, ""):
                    preauth.approved_amount = int(Decimal(str(case.data.get("amount"))))
                preauth.save()
            details = {"preauthorization_id": preauth.id, "status": preauth.status}
            effect_type, effect_id = "services.InsurancePreauthorization", str(preauth.id)
        elif action_code == "execute" and claim:
            mapping = {
                "approve": claim.Status.APPROVED,
                "partially_approve": claim.Status.PARTIALLY_APPROVED,
                "reject": claim.Status.REJECTED,
                "query": claim.Status.QUERY,
                "hold": claim.Status.IN_REVIEW,
            }
            if decision == "pay":
                mapping[decision] = claim.Status.PAID
            if decision in mapping:
                claim.status = mapping[decision]
                claim.decision_reason = payload.get("note") or case.data.get("details", "")
                claim.reviewed_by = user
                claim.reviewed_at = timezone.now()
                if decision in {"approve", "partially_approve", "pay"} and case.data.get("amount") not in (None, ""):
                    claim.approved_amount = int(Decimal(str(case.data.get("amount"))))
                claim.save()
            details = {"claim_id": claim.id, "status": claim.status}
            effect_type, effect_id = "services.InsuranceClaim", str(claim.id)
        else:
            details = {"insurance_operation": slug, "decision": decision or None}

    elif definition.get("adapter") == "facility_operation":
        # Facility changes are deliberately applied only through approved, scoped
        # actions. The canonical OperationalAction is the source of truth for
        # configuration changes that span several facility tables.
        details = {
            "facility_operation": slug,
            "configuration": case.data.get("configuration") or {},
            "effective_at": case.data.get("effective_at"),
            "applied": action_code == "execute",
        }

    else:
        details = {"operation": action.operation_code, "completed": action_code in {"activate", "execute", "generate", "publish", "accept"}}

    if effect_type:
        action.effect_reference_type = effect_type
        action.effect_reference_id = effect_id
    action.result = {**(action.result or {}), **details}
    _append_effect(action, event=action_code, actor=user, details=details)
    return details


def _sync_operational_action(case, definition, action_code, payload, user):
    if definition.get("adapter") not in OPERATIONAL_ADAPTERS:
        return None
    action = OperationalAction.objects.select_for_update().filter(workflow_case=case).first()
    if not action:
        action = _create_operational_action(case, definition, user)
    action.state = _operational_state(case.status)
    action.updated_by = user
    if action_code in {"approve", "authorize", "verify"}:
        action.approved_by = user
        action.approved_at = timezone.now()
    if action_code in {"execute", "activate", "generate", "publish", "accept", "complete"}:
        if action.requires_approval and not action.approved_at and action_code == "execute":
            raise ValidationError({"action": "This transaction must be approved before execution."})
        _execute_operational_effect(case, definition, action, action_code, payload, user)
        action.executed_by = user
        action.executed_at = timezone.now()
    elif action_code in {"reject", "cancel", "archive", "reverse", "revoke"}:
        _append_effect(action, event=action_code, actor=user, details={"note": payload.get("note", "")})
    action.result = {**(action.result or {}), **(case.result or {})}
    action.save()
    case.result = {
        **(case.result or {}),
        "operational_action_id": action.id,
        "operational_action_public_id": str(action.public_id),
        "operational_state": action.state,
        "effect_reference_type": action.effect_reference_type,
        "effect_reference_id": action.effect_reference_id,
    }
    case.save(update_fields=["result", "updated_at"])
    return action


def request_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")) or None


def assert_page_access(user, slug):
    definition = definition_for(slug)
    if not definition:
        raise ValidationError({"page_slug": "Unknown workflow page."})
    role = active_role(user)
    if definition.get("category") == "administration":
        if not admin_page_allowed(user, slug):
            raise PermissionDenied("The active administrator role is not permitted to use this administration page.")
    elif not is_platform_super_admin(user) and role not in set(definition.get("roles", [])):
        raise PermissionDenied("The active role is not allowed to use this workflow page.")
    return definition


def workflow_queryset(user, slug=None):
    qs = WorkflowCase.objects.select_related(
        "organization", "location", "department", "patient", "subject_user",
        "assigned_to", "appointment", "admission", "invoice", "created_by",
    ).prefetch_related("events", "comments")
    if slug:
        qs = qs.filter(page_slug=slug)
    if is_platform_super_admin(user):
        return qs
    role = active_role(user)
    if role == "patient":
        managed_ids = []
        try:
            managed_ids = list(
                user.managed_patient_relationships.filter(status="active").values_list("patient_id", flat=True)
            )
        except Exception:
            pass
        return qs.filter(Q(patient=user) | Q(subject_user=user) | Q(patient_id__in=managed_ids)).distinct()
    context = active_context_for(user)
    filters = Q(created_by=user) | Q(assigned_to=user) | Q(subject_user=user)
    if context and context.organization_id:
        filters |= Q(organization_id=context.organization_id)
    qs = qs.filter(filters)
    if context and context.location_id:
        qs = qs.filter(Q(location__isnull=True) | Q(location_id=context.location_id))
    if context and context.department_id:
        qs = qs.filter(Q(department__isnull=True) | Q(department_id=context.department_id))
    return qs.distinct()


def available_actions(case, user):
    definition = assert_page_access(user, case.page_slug)
    role = active_role(user)
    actions = {}
    for code, config in (definition.get("actions") or {}).items():
        if case.status not in set(config.get("from", [])):
            continue
        allowed = set(config.get("roles") or [])
        if allowed and not is_platform_super_admin(user) and role not in allowed:
            continue
        # Patients may submit information, check in, join care and withdraw their
        # own requests. They cannot approve, assign or clinically complete cases
        # merely because a generic workflow action omitted a role list.
        if role == "patient" and not allowed and code not in {
            "submit", "cancel", "provide_information", "check_in",
            "mark_ready", "join", "revoke", "request_refill",
            "record_adherence", "acknowledge",
        }:
            continue
        actions[code] = config
    return actions


def _managed_patient_ids(user):
    try:
        return set(user.managed_patient_relationships.filter(status="active").values_list("patient_id", flat=True))
    except Exception:
        return set()


def _validate_case_relations(definition, payload, user):
    """Prevent clients from bypassing lookup scoping with raw relation IDs."""
    from accounts.models import User

    role = active_role(user)
    patient_id = payload.get("patient")
    if patient_id:
        patient = User.objects.filter(pk=patient_id, role="patient", is_active=True).first()
        if not patient:
            raise ValidationError({"patient": "Select an active patient account."})
        if role == "patient":
            allowed = {user.id} | _managed_patient_ids(user)
            if patient.id not in allowed:
                raise PermissionDenied("You may only act for yourself or a currently authorized dependent.")
        elif not is_platform_super_admin(user):
            org = active_organization(user)
            related = False
            try:
                related = patient.care_relationships.filter(practitioner=user, status="active").exists()
            except Exception:
                pass
            if org and not related:
                from appointments.models import Appointment
                from operations.models import Admission
                from workforce.models import PatientVisit
                related = (
                    Appointment.objects.filter(patient=patient, doctor__role_contexts__organization=org, doctor__role_contexts__active=True).exists()
                    or Admission.objects.filter(patient=patient, organization=org).exists()
                    or PatientVisit.objects.filter(patient=patient, organization=org).exists()
                )
            if not related and role not in {"receptionist", "records_officer", "cashier", "insurance_officer", "claims_reviewer"}:
                raise PermissionDenied("The selected patient is outside your active care or organization scope.")

    assigned_to = payload.get("assigned_to")
    if assigned_to and not is_platform_super_admin(user):
        assignee = User.objects.filter(pk=assigned_to, is_active=True).first()
        if not assignee:
            raise ValidationError({"assigned_to": "Select an active staff account."})
        org = active_organization(user)
        if org and not assignee.role_contexts.filter(organization=org, active=True).exists():
            raise PermissionDenied("The assignee is outside the active organization.")

    appointment_id = payload.get("appointment")
    if appointment_id:
        from appointments.models import Appointment
        qs = Appointment.objects.filter(pk=appointment_id)
        if role == "patient":
            qs = qs.filter(Q(patient=user) | Q(patient_id__in=_managed_patient_ids(user)))
        elif patient_id:
            qs = qs.filter(patient_id=patient_id)
        if not qs.exists():
            raise ValidationError({"appointment": "The selected appointment is unavailable in this context."})

    admission_id = payload.get("admission")
    if admission_id:
        from operations.models import Admission
        qs = Admission.objects.filter(pk=admission_id)
        if patient_id:
            qs = qs.filter(patient_id=patient_id)
        if not is_platform_super_admin(user) and active_organization(user):
            qs = qs.filter(organization=active_organization(user))
        if not qs.exists():
            raise ValidationError({"admission": "The selected admission is unavailable in this context."})

    invoice_id = payload.get("invoice")
    if invoice_id:
        from payments.models import Invoice
        qs = Invoice.objects.filter(pk=invoice_id)
        if role == "patient":
            qs = qs.filter(Q(patient=user) | Q(patient_id__in=_managed_patient_ids(user)))
        elif active_organization(user) and not is_platform_super_admin(user):
            qs = qs.filter(organization=active_organization(user))
        if not qs.exists():
            raise ValidationError({"invoice": "The selected invoice is unavailable in this context."})


def _dt(value, *, required=False):
    if isinstance(value, datetime.datetime):
        return value
    parsed = parse_datetime(str(value)) if value else None
    if parsed and timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    if required and not parsed:
        raise ValidationError({"datetime": "Enter a valid date and time."})
    return parsed


def _coerce_schema_value(kind, value):
    if value in (None, ""):
        return value
    if kind == "number":
        number = float(value)
        return int(number) if number.is_integer() else number
    if kind == "boolean" and not isinstance(value, bool):
        return str(value).strip().lower() in {"1", "true", "yes", "on"}
    if kind == "list" and isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def _schema_record_type(case, definition):
    record_types = list(definition.get("recordTypes") or [])
    if not record_types:
        return None
    selected = case.data.get("record_type") or record_types[0]
    if selected not in record_types:
        raise ValidationError({"record_type": "Select a record type supported by this page."})
    return selected


def _create_schema_record(case, definition, user):
    """Persist the validated enterprise record behind a schema-driven page."""
    record_type = _schema_record_type(case, definition)
    if not record_type:
        return None
    from enterprise.models import EnterpriseRecord
    from enterprise.schemas import schema_for

    schema = schema_for(record_type)
    if not schema:
        raise ValidationError({"record_type": f"Unsupported enterprise record type: {record_type}."})
    payload = {}
    for name, spec in (schema.get("fields") or {}).items():
        if name in case.data:
            payload[name] = _coerce_schema_value(spec.get("kind"), case.data[name])
    record = EnterpriseRecord(
        domain=schema["domain"],
        record_type=record_type,
        organization=case.organization,
        location=case.location,
        department=case.department,
        patient=case.patient,
        admission=case.admission,
        appointment=case.appointment,
        owner=user,
        assigned_to=case.assigned_to,
        status=case.status,
        priority=case.priority,
        title=case.title,
        summary=case.summary,
        payload=payload,
        due_at=case.due_at,
        created_by=user,
        updated_by=user,
    )
    record.full_clean()
    record.save()
    return record


def _action_schema_record(case, definition, action_code, user):
    record_id = (case.result or {}).get("enterprise_record_id")
    if not record_id:
        return None
    from enterprise.models import EnterpriseRecord
    from enterprise.schemas import transition_for

    record = EnterpriseRecord.objects.filter(pk=record_id).first()
    if not record:
        raise ValidationError({"action": "The canonical enterprise record is missing."})
    target = transition_for(record.record_type, record.status, action_code) or case.status
    record.status = target
    record.assigned_to = case.assigned_to
    record.updated_by = user
    if target in TERMINAL_STATUSES or target in {"given", "withheld", "omitted", "acknowledged"}:
        record.completed_at = timezone.now()
    record.full_clean()
    record.save(update_fields=["status", "assigned_to", "updated_by", "completed_at", "updated_at"])
    return record


def _inventory_batch_for_case(case):
    from operations.models import InventoryBatch
    qs = InventoryBatch.objects.select_related("item").filter(item__organization=case.organization)
    batch_number = case.data.get("batch_number")
    item_reference = case.data.get("item_reference") or case.data.get("sku") or case.data.get("item")
    if batch_number:
        qs = qs.filter(batch_number=batch_number)
    if item_reference:
        qs = qs.filter(Q(item__sku__iexact=str(item_reference)) | Q(item__name__icontains=str(item_reference)))
    return qs.first()


def _apply_stock_movement(case, user, movement_type, *, quantity=None, reason=""):
    from operations.models import StockMovement
    batch = _inventory_batch_for_case(case)
    if not batch:
        raise ValidationError({"batch_number": "Select an inventory batch in the active organization."})
    quantity = int(float(quantity if quantity is not None else case.data.get("quantity") or 0))
    if quantity == 0:
        raise ValidationError({"quantity": "Enter a non-zero stock quantity."})
    inbound = movement_type in {StockMovement.Type.RECEIPT, StockMovement.Type.RETURN}
    delta = abs(quantity) if inbound else -abs(quantity)
    if batch.quantity_available + delta < 0:
        raise ValidationError({"quantity": "The transaction would make stock negative."})
    batch.quantity_available += delta
    if inbound:
        batch.quantity_received = max(batch.quantity_received, batch.quantity_available)
    batch.save(update_fields=["quantity_available", "quantity_received"])
    return StockMovement.objects.create(
        batch=batch, movement_type=movement_type, quantity=delta, balance_after=batch.quantity_available,
        reason=reason or case.data.get("reason") or case.summary, reference=case.reference, created_by=user,
    )


def _coordinate(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _route_summary(pickup, destination, *, average_speed_kmh=35):
    """Return a deterministic geographic distance/ETA estimate.

    This is deliberately a fallback, not a claim of live traffic routing.  A
    configured routing provider may replace the estimate while keeping the same
    response contract.
    """
    lat1 = _coordinate((pickup or {}).get("latitude"))
    lon1 = _coordinate((pickup or {}).get("longitude"))
    lat2 = _coordinate((destination or {}).get("latitude"))
    lon2 = _coordinate((destination or {}).get("longitude"))
    if None in {lat1, lon1, lat2, lon2}:
        return {}
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    distance = radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(max(1 - value, 0)))
    eta_minutes = max(1, round((distance / max(float(average_speed_kmh), 1)) * 60))
    return {
        "distance_km": round(distance, 2),
        "eta_minutes": eta_minutes,
        "routing_mode": "geodesic_estimate",
        "routing_note": "Estimated without live traffic; configure a routing provider for road-aware ETA.",
    }


def _lab_result_value(raw):
    if isinstance(raw, (int, float, Decimal)):
        return Decimal(str(raw)), ""
    text = str(raw or "").strip()
    if not text:
        return None, ""
    try:
        return Decimal(text), ""
    except (InvalidOperation, ValueError):
        return None, text


def _normalize_case_payload(definition, payload, user):
    payload = dict(payload or {})
    data = dict(payload.get("data") or {})
    # Accept defined fields at the top level for a simpler API and move custom
    # values into ``data`` while keeping relational fields queryable.
    relational = {
        "patient", "subject_user", "assigned_to", "appointment", "admission",
        "invoice", "parent", "title", "summary", "priority", "due_at",
    }
    for spec in definition.get("fields", []):
        name = spec["name"]
        if name in payload and name not in relational:
            data[name] = payload[name]
    role = active_role(user)
    if role == "patient" and not payload.get("patient"):
        payload["patient"] = user.id
    errors = validate_payload(definition, {**data, **payload})
    if definition.get("patient_required") and not payload.get("patient"):
        errors["patient"] = "A patient is required for this workflow."
    if errors:
        raise ValidationError(errors)
    payload["data"] = data
    _validate_case_relations(definition, payload, user)
    return payload


def create_case(*, user, slug, payload, request=None):
    definition = assert_page_access(user, slug)
    values = _normalize_case_payload(definition, payload, user)
    context = active_context_for(user)
    patient_id = values.get("patient")
    with transaction.atomic():
        case = WorkflowCase.objects.create(
            page_slug=slug,
            category=definition.get("category") or definition.get("group", "workflow"),
            organization=active_organization(user),
            location=active_location(user),
            department=active_department(user),
            patient_id=patient_id or None,
            subject_user_id=values.get("subject_user") or None,
            assigned_to_id=values.get("assigned_to") or None,
            appointment_id=values.get("appointment") or None,
            admission_id=values.get("admission") or None,
            invoice_id=values.get("invoice") or None,
            parent_id=values.get("parent") or None,
            title=values.get("title") or definition.get("label", slug.replace("-", " ").title()),
            summary=values.get("summary", ""),
            status=definition.get("initial_status", "draft"),
            priority=values.get("priority") or WorkflowCase.Priority.ROUTINE,
            data=values.get("data") or {},
            due_at=values.get("due_at") or None,
            created_by=user,
            updated_by=user,
        )
        WorkflowActionEvent.objects.create(
            case=case,
            action="create",
            actor=user,
            actor_role=active_role(user),
            from_status="",
            to_status=case.status,
            data={"context_id": getattr(context, "id", None)},
            correlation_id=getattr(request, "correlation_id", "") if request else "",
            ip_address=request_ip(request) if request else None,
        )
        _adapter_on_create(case, definition, user, request)
        audit(
            actor=user,
            patient=case.patient,
            action=f"workflow.{slug}.created",
            resource=case,
            purpose="workflow_execution",
            decision=AuditEvent.Decision.ALLOW,
            metadata={"status": case.status, "active_role": active_role(user)},
            request=request,
        )
    return case


def perform_action(*, case, user, action_code, payload=None, request=None):
    payload = dict(payload or {})
    actions = available_actions(case, user)
    config = actions.get(action_code)
    if not config:
        raise ValidationError({"action": f"Action '{action_code}' is not allowed from status '{case.status}'."})
    note = str(payload.get("note") or "").strip()
    if config.get("note_required") and len(note) < 3:
        raise ValidationError({"note": "A meaningful note is required for this action."})
    for spec in config.get("fields") or []:
        value = payload.get(spec["name"])
        if spec.get("required") and value in (None, "", [], {}):
            raise ValidationError({spec["name"]: "This field is required."})
    definition = definition_for(case.page_slug)
    if definition.get("adapter") == "medication_administration" and action_code == "administer":
        checks = ["right_patient", "right_medication", "right_dose", "right_route", "right_time"]
        missing = [name for name in checks if not bool(case.data.get(name))]
        if missing:
            raise ValidationError({name: "Confirm this medication-administration safety check." for name in missing})
    old_status = case.status
    new_status = config["to"]
    with transaction.atomic():
        if payload.get("assigned_to"):
            case.assigned_to_id = payload["assigned_to"]
        case.status = new_status
        case.updated_by = user
        case.version += 1
        if new_status in {"in_progress", "processing"} and not case.started_at:
            case.started_at = timezone.now()
        if new_status in TERMINAL_STATUSES:
            case.completed_at = timezone.now()
        result_updates = dict(payload.get("result") or {})
        if note:
            result_updates["last_note"] = note
        if result_updates:
            case.result = {**(case.result or {}), **result_updates}
        case.save()
        event = WorkflowActionEvent.objects.create(
            case=case,
            action=action_code,
            actor=user,
            actor_role=active_role(user),
            from_status=old_status,
            to_status=new_status,
            note=note,
            data={key: value for key, value in payload.items() if key not in {"note"}},
            correlation_id=getattr(request, "correlation_id", "") if request else "",
            ip_address=request_ip(request) if request else None,
        )
        _adapter_on_action(case, definition, action_code, payload, user, request)
        audit(
            actor=user,
            patient=case.patient,
            action=f"workflow.{case.page_slug}.{action_code}",
            resource=case,
            purpose="workflow_execution",
            decision=AuditEvent.Decision.ALLOW,
            metadata={"from": old_status, "to": new_status, "event_id": event.id},
            request=request,
        )
    return case


def _adapter_on_create(case, definition, user, request):
    """Create the canonical domain transaction behind a journey case."""
    adapter = definition.get("adapter")
    result = dict(case.result or {})
    schema_record = _create_schema_record(case, definition, user)
    if schema_record:
        result.update({
            "enterprise_record_id": schema_record.id,
            "enterprise_reference": schema_record.reference,
            "record_type": schema_record.record_type,
        })

    operational_action = _create_operational_action(case, definition, user)
    if operational_action:
        result.update({
            "operational_action_id": operational_action.id,
            "operational_action_public_id": str(operational_action.public_id),
            "operational_state": operational_action.state,
        })

    if adapter in {None, "enterprise_record"} or adapter in OPERATIONAL_ADAPTERS:
        pass
    elif adapter == "waiting_room":
        from .models import WaitingRoomEntry

        appointment = case.appointment
        if not appointment:
            raise ValidationError({"appointment": "A waiting-room entry requires an appointment."})
        entry, _ = WaitingRoomEntry.objects.get_or_create(
            appointment=appointment,
            defaults={
                "patient": appointment.patient,
                "organization": case.organization,
                "workflow_case": case,
                "device_status": {
                    "device_ready": bool(case.data.get("device_ready")),
                    "consent_confirmed": bool(case.data.get("consent_confirmed")),
                },
            },
        )
        if not entry.workflow_case_id:
            entry.workflow_case = case
            entry.save(update_fields=["workflow_case", "last_seen_at"])
        result.update({"waiting_room_entry_id": entry.id, "queue_position": entry.queue_position})

    elif adapter == "consent":
        from governance.models import Consent

        consent = Consent.objects.create(
            patient=case.patient,
            consent_type=case.data.get("consent_type", Consent.Type.TREATMENT),
            purpose=case.data.get("purpose", "treatment"),
            data_categories=case.data.get("data_categories") or [],
            valid_until=_dt(case.data.get("valid_until")),
            source="patient_portal",
        )
        result["consent_id"] = consent.id

    elif adapter == "medication_renewal":
        from prescriptions.models import Prescription
        from .models import MedicationRenewalRequest

        prescription = Prescription.objects.select_related("patient", "doctor").filter(
            pk=case.data.get("prescription"), patient=case.patient
        ).first()
        if not prescription:
            raise ValidationError({"prescription": "Select a prescription belonging to the patient."})
        renewal = MedicationRenewalRequest.objects.create(
            workflow_case=case, prescription=prescription, patient=case.patient,
            prescriber=prescription.doctor, reason=case.data.get("reason") or case.summary or "Medication renewal",
        )
        case.assigned_to = prescription.doctor
        result.update({"renewal_request_id": renewal.id, "prescriber_id": prescription.doctor_id})

    elif adapter == "medication_adherence":
        from prescriptions.models import Prescription, PrescriptionItem
        from .models import MedicationAdherenceEntry

        prescription = Prescription.objects.filter(pk=case.data.get("prescription"), patient=case.patient).first()
        if not prescription:
            raise ValidationError({"prescription": "Select a prescription belonging to the patient."})
        item = None
        if case.data.get("prescription_item"):
            item = PrescriptionItem.objects.filter(pk=case.data["prescription_item"], prescription=prescription).first()
            if not item:
                raise ValidationError({"prescription_item": "The medicine item is not part of this prescription."})
        status_value = case.data.get("dose_status")
        taken_at = _dt(case.data.get("taken_at"))
        if status_value in {"taken", "late"} and not taken_at:
            taken_at = timezone.now()
        entry = MedicationAdherenceEntry.objects.create(
            workflow_case=case, patient=case.patient, prescription=prescription, prescription_item=item,
            scheduled_for=_dt(case.data.get("scheduled_for"), required=True), taken_at=taken_at,
            status=status_value, note=case.data.get("note", ""),
        )
        result["adherence_entry_id"] = entry.id

    elif adapter == "privacy_request":
        from operations.models import PrivacyRequest

        privacy = PrivacyRequest.objects.create(
            organization=case.organization, requester=case.patient or user,
            request_type=case.data.get("request_type"), details=case.data.get("details") or case.summary,
            assigned_to=case.assigned_to, due_at=case.due_at or timezone.now() + datetime.timedelta(days=30),
        )
        result.update({"privacy_request_id": privacy.id, "request_number": privacy.request_number})

    elif adapter == "caregiver_invitation":
        from accounts.models import PatientRelationship, User

        caregiver = User.objects.filter(pk=case.data.get("caregiver"), is_active=True).first()
        if not caregiver or caregiver.id == case.patient_id:
            raise ValidationError({"caregiver": "Select a different active account as caregiver."})
        relationship, created = PatientRelationship.objects.update_or_create(
            caregiver=caregiver, patient=case.patient,
            defaults={
                "relationship": case.data.get("relationship"), "status": PatientRelationship.Status.PENDING,
                "can_book": bool(case.data.get("can_book")),
                "can_view_records": bool(case.data.get("can_view_records")),
                "can_manage_billing": bool(case.data.get("can_manage_billing")),
                "can_receive_notifications": bool(case.data.get("can_receive_notifications")),
                "expires_at": _dt(case.data.get("expires_at")), "notes": case.data.get("notes", ""),
            },
        )
        case.subject_user = caregiver
        result.update({"relationship_id": relationship.id, "created": created})
        try:
            from communication.services import notify
            notify(caregiver, "Caregiver access invitation", f"{case.patient.display_name} invited you to manage selected healthcare activities.", kind="account", action_url=f"/patient/family-access?case={case.public_id}")
        except Exception:
            pass

    elif adapter == "patient_feedback":
        from operations.models import QualityIncident, SupportTicket

        severity = case.data.get("severity", "moderate")
        ticket = SupportTicket.objects.create(
            requester=case.patient or user, organization=case.organization, category=case.data.get("category", "general"),
            priority={"low": "low", "moderate": "normal", "high": "high", "critical": "urgent"}.get(severity, "normal"),
            subject=case.data.get("subject") or case.title, description=case.data.get("details") or case.summary,
            assigned_to=case.assigned_to,
        )
        result.update({"support_ticket_id": ticket.id, "ticket_number": ticket.number})
        if severity in {"high", "critical"} and case.organization:
            incident = QualityIncident.objects.create(
                organization=case.organization, patient=case.patient, category=case.data.get("category", "other") if case.data.get("category") in {"medication","clinical","infection","fall","privacy","equipment","service","other"} else "service",
                severity=severity, title=case.data.get("subject") or case.title,
                description=case.data.get("details") or case.summary, reported_by=user, assigned_to=case.assigned_to,
            )
            result.update({"quality_incident_id": incident.id, "incident_number": incident.incident_number})

    elif adapter == "clinical_task":
        from .models import ClinicalTask

        task = ClinicalTask.objects.create(
            workflow_case=case, patient=case.patient, task_type=case.data.get("task_type", "other"),
            instructions=case.data.get("instructions") or case.summary, assigned_to=case.assigned_to,
            due_at=_dt(case.data.get("due_at")) or case.due_at, created_by=user,
        )
        result["clinical_task_id"] = task.id

    elif adapter == "care_conference":
        from accounts.models import User
        from .models import CareConference

        conference = CareConference.objects.create(
            workflow_case=case, patient=case.patient, organization=case.organization, title=case.title,
            scheduled_at=_dt(case.data.get("scheduled_at"), required=True),
            agenda=case.data.get("agenda") or case.summary, chair=user,
        )
        participant_ids = case.data.get("participants") or []
        if isinstance(participant_ids, str):
            participant_ids = [value.strip() for value in participant_ids.split(",") if value.strip()]
        participants = User.objects.filter(pk__in=participant_ids, is_active=True)
        conference.participants.set(participants)
        result["care_conference_id"] = conference.id

    elif adapter == "on_call_shift":
        from operations.models import StaffShift

        shift = StaffShift.objects.create(
            organization=case.organization, staff=case.subject_user or user, department=case.department,
            shift_type="on_call", starts_at=_dt(case.data.get("starts_at") or case.data.get("scheduled_at"), required=True),
            ends_at=_dt(case.data.get("ends_at"), required=True), location=case.data.get("location", ""),
            notes=case.data.get("notes") or case.summary, created_by=user,
        )
        shift.full_clean()
        shift.save()
        result["staff_shift_id"] = shift.id

    elif adapter == "appointment_create":
        from appointments.models import Appointment
        from accounts.models import User

        provider = User.objects.filter(pk=case.data.get("provider"), is_active=True).first()
        if not provider:
            raise ValidationError({"provider": "Select an active healthcare provider."})
        date_value = parse_date(str(case.data.get("appointment_date") or ""))
        start_value = parse_time(str(case.data.get("start_time") or ""))
        end_value = parse_time(str(case.data.get("end_time") or ""))
        if not date_value or not start_value or not end_value or end_value <= start_value:
            raise ValidationError({"appointment_date": "Enter a valid date and time range."})
        kind = case.data.get("appointment_type")
        appointment = Appointment.objects.create(
            patient=case.patient, doctor=provider, booked_by=user, date=date_value, start_time=start_value, end_time=end_value,
            type=Appointment.Type.ONLINE if kind in {"video", "phone"} else Appointment.Type.OFFLINE,
            reason=case.data.get("reason", ""), status=Appointment.Status.PENDING,
        )
        case.appointment = appointment
        case.assigned_to = provider
        result["appointment_id"] = appointment.id

    elif adapter == "queue_ticket":
        from .models import QueueTicket

        if not case.organization:
            raise ValidationError({"organization": "An active organization is required to issue a queue ticket."})
        ticket = QueueTicket.objects.create(
            organization=case.organization, department=case.department, patient=case.patient, appointment=case.appointment,
            workflow_case=case, counter=case.data.get("counter", ""), issued_by=user,
        )
        result.update({"queue_ticket_id": ticket.id, "queue_number": ticket.number})

    elif adapter == "call_centre_callback":
        from .models import CallCentreCallback

        callback = CallCentreCallback.objects.create(
            workflow_case=case, patient=case.patient, phone=case.data.get("phone"),
            reason=case.data.get("reason") or case.summary, scheduled_for=_dt(case.data.get("scheduled_for"), required=True),
            assigned_to=case.assigned_to,
        )
        result["callback_id"] = callback.id

    elif adapter == "sms_confirmation":
        result["delivery_status"] = "queued"

    elif adapter == "finance_operation":
        from payments.models import (
            ApprovalLimit, DepartmentBudget, Expense, FinancialPeriod, InvoiceAdjustment,
            PayerAllocation, ReconciliationRun, SupplierInvoice,
        )

        if not case.organization:
            raise ValidationError({"organization": "An active organization is required for financial operations."})
        record_type = (result or {}).get("record_type") or case.data.get("record_type")
        slug_operations = {
            "expense-register": "expense", "supplier-invoices": "supplier_invoice",
            "accounts-payable": "supplier_invoice", "bank-reconciliation": "reconciliation",
            "mobile-money-reconciliation": "reconciliation", "gateway-reconciliation": "reconciliation",
            "credit-notes": "credit_note", "debit-notes": "debit_note",
            "deposit-collection": "deposit", "split-payment": "split_payment",
            "multiple-payment-methods": "split_payment", "patient-insurer-split": "payer_allocation",
            "department-budgets": "budget", "budget-management": "budget",
            "approval-limits": "approval_limit", "period-closing": "period_close",
            "period-close": "period_close",
        }
        schema_operations = {
            "expense": "expense", "supplier_bill": "supplier_invoice",
            "reconciliation": "reconciliation", "credit_note": "credit_note",
            "debit_note": "debit_note", "financial_period": "period_close",
            "settlement": "reconciliation",
        }
        operation = case.data.get("operation_type") or schema_operations.get(record_type) or slug_operations.get(case.page_slug)
        amount = int(float(case.data.get("amount") or case.data.get("total") or case.data.get("gross_amount") or 0))
        currency = case.data.get("currency") or "UGX"
        reference = case.data.get("reference") or case.data.get("invoice_number") or case.data.get("settlement_reference") or ""
        details = case.data.get("details") or case.data.get("description") or case.data.get("reason") or case.summary or case.title
        if operation == "expense":
            row = Expense.objects.create(
                organization=case.organization, department=case.department,
                vendor=case.data.get("vendor", ""), category=case.data.get("category") or "operating",
                description=details, amount=amount, currency=currency,
                incurred_on=parse_date(str(case.data.get("incurred_on") or case.data.get("transaction_date") or "")) or timezone.localdate(),
                reference=reference, requested_by=user,
            )
            result.update({"expense_id": row.id, "expense_number": row.number})
        elif operation == "supplier_invoice":
            row = SupplierInvoice.objects.create(
                organization=case.organization,
                supplier_name=case.data.get("supplier") or case.data.get("supplier_name") or "Supplier",
                invoice_number=case.data.get("invoice_number") or reference or case.reference,
                amount=amount, currency=currency,
                invoice_date=parse_date(str(case.data.get("invoice_date") or "")) or timezone.localdate(),
                due_date=parse_date(str(case.data.get("due_date") or "")),
                reference=case.data.get("purchase_order_reference") or reference,
                notes=details, created_by=user,
            )
            result["supplier_invoice_id"] = row.id
        elif operation == "reconciliation":
            kind_by_slug = {
                "mobile-money-reconciliation": ReconciliationRun.Kind.MOBILE_MONEY,
                "gateway-reconciliation": ReconciliationRun.Kind.GATEWAY,
                "insurance-settlement": ReconciliationRun.Kind.INSURANCE,
                "cash-drawer": ReconciliationRun.Kind.CASH,
            }
            now = timezone.now()
            start_date = parse_date(str(case.data.get("statement_from") or ""))
            end_date = parse_date(str(case.data.get("statement_to") or ""))
            start_dt = timezone.make_aware(datetime.datetime.combine(start_date, datetime.time.min)) if start_date else now - datetime.timedelta(days=1)
            end_dt = timezone.make_aware(datetime.datetime.combine(end_date, datetime.time.max)) if end_date else now
            expected = int(float(case.data.get("opening_balance") or case.data.get("expected_amount") or amount))
            actual = int(float(case.data.get("closing_balance") or case.data.get("actual_amount") or case.data.get("net_amount") or amount))
            row = ReconciliationRun.objects.create(
                organization=case.organization, kind=case.data.get("reconciliation_kind") or kind_by_slug.get(case.page_slug, ReconciliationRun.Kind.BANK),
                period_start=start_dt, period_end=end_dt, expected_amount=expected, actual_amount=actual,
                evidence={"workflow_case": str(case.public_id), "record_type": record_type}, notes=details, created_by=user,
            )
            result.update({"reconciliation_id": row.id, "reconciliation_number": row.number})
        elif operation in {"credit_note", "debit_note"}:
            invoice = case.invoice
            if not invoice and case.data.get("invoice_id"):
                from payments.models import Invoice
                invoice = Invoice.objects.filter(pk=case.data.get("invoice_id"), organization=case.organization).first()
            if not invoice:
                raise ValidationError({"invoice": "Select an invoice for the adjustment."})
            row = InvoiceAdjustment.objects.create(
                invoice=invoice,
                adjustment_type=InvoiceAdjustment.Type.CREDIT if operation == "credit_note" else InvoiceAdjustment.Type.DEBIT,
                amount=amount, reason=details, requested_by=user,
            )
            case.invoice = invoice
            result.update({"invoice_adjustment_id": row.id, "adjustment_number": row.number})
        elif operation in {"split_payment", "payer_allocation", "deposit"}:
            if not case.invoice_id:
                raise ValidationError({"invoice": "Select an invoice for the payer allocation."})
            payer_type = case.data.get("payer_type") or (PayerAllocation.PayerType.PATIENT if operation == "deposit" else PayerAllocation.PayerType.INSURANCE)
            row = PayerAllocation.objects.create(
                invoice=case.invoice, payer_type=payer_type, payer_reference=reference,
                allocated_amount=amount, created_by=user,
            )
            result["payer_allocation_id"] = row.id
        elif operation == "approval_limit":
            row = ApprovalLimit.objects.create(
                organization=case.organization, role_code=case.data.get("role_code") or "finance_manager",
                operation_type=case.data.get("limit_operation_type") or "expense",
                maximum_amount=amount, currency=currency,
                requires_second_approval=bool(case.data.get("requires_second_approval")),
            )
            result["approval_limit_id"] = row.id
        elif operation == "budget":
            today = timezone.localdate()
            period, _ = FinancialPeriod.objects.get_or_create(
                organization=case.organization, name=case.data.get("period_name") or f"FY {today.year}",
                defaults={"starts_on": today.replace(month=1, day=1), "ends_on": today.replace(month=12, day=31), "created_by": user},
            )
            row = DepartmentBudget.objects.create(
                organization=case.organization, department=case.department, period=period,
                category=case.data.get("budget_category") or case.data.get("category") or "operating",
                amount=amount, notes=details, approved_by=user if active_role(user) == "finance_manager" else None,
            )
            result["department_budget_id"] = row.id
        elif operation == "period_close":
            starts = parse_date(str(case.data.get("starts_on") or ""))
            ends = parse_date(str(case.data.get("ends_on") or ""))
            today = timezone.localdate()
            period, _ = FinancialPeriod.objects.get_or_create(
                organization=case.organization, name=case.data.get("name") or f"FY {today.year}",
                defaults={
                    "starts_on": starts or today.replace(month=1, day=1),
                    "ends_on": ends or today.replace(month=12, day=31),
                    "status": case.data.get("status") or FinancialPeriod.Status.OPEN,
                    "created_by": user,
                },
            )
            result["financial_period_id"] = period.id
        result["finance_operation"] = operation or "ledger_only"

    elif adapter == "inventory_operation":
        # Schema-backed inventory pages already create an EnterpriseRecord.  For
        # pages tied to an actual stock batch, preserve the canonical batch link
        # so later approval/execute actions can adjust stock atomically.
        batch = _inventory_batch_for_case(case)
        if batch:
            result.update({"inventory_batch_id": batch.id, "inventory_item_id": batch.item_id})

    elif adapter == "laboratory_operation":
        from services.models import LabOrder, LabResult, SpecimenEvent

        reference = str(case.data.get("specimen_reference") or "").strip()
        order = None
        if reference:
            lookup = Q(specimen_id__iexact=reference)
            if reference.isdigit():
                lookup |= Q(pk=int(reference))
            order_qs = LabOrder.objects.select_related("patient", "lab", "test").filter(lookup)
            if case.patient_id:
                order_qs = order_qs.filter(patient=case.patient)
            order = order_qs.first()
            if not order:
                raise ValidationError({"specimen_reference": "No laboratory order matches this specimen reference."})
            result["lab_order_id"] = order.id
            event_by_slug = {
                "collection-worklist": SpecimenEvent.Type.COLLECTED,
                "phlebotomy-queue": SpecimenEvent.Type.COLLECTED,
                "accessioning": SpecimenEvent.Type.RECEIVED,
                "barcode-labels": SpecimenEvent.Type.LABELLED,
                "barcode-scanner": SpecimenEvent.Type.RECEIVED,
                "rejected-specimens": SpecimenEvent.Type.REJECTED,
                "transport-manifest": SpecimenEvent.Type.TRANSFERRED,
                "aliquot-creation": SpecimenEvent.Type.ALIQUOTED,
                "storage-locations": SpecimenEvent.Type.STORED,
            }
            event_type = event_by_slug.get(case.page_slug)
            if event_type:
                event = SpecimenEvent.objects.create(
                    order=order, event_type=event_type,
                    barcode=case.data.get("barcode") or order.specimen_id,
                    location=case.data.get("location", ""),
                    notes=case.data.get("result") or case.summary,
                    metadata=case.data.get("quality_data") or {}, performed_by=user,
                )
                result["specimen_event_id"] = event.id
            if case.page_slug in {"result-entry", "microbiology", "sensitivity-grid", "histopathology"}:
                numeric, text = _lab_result_value(case.data.get("result"))
                interpretation = LabResult.Interpretation.CRITICAL if case.data.get("critical") else LabResult.Interpretation.UNKNOWN
                name = case.data.get("test_name") or order.test.name
                lab_result, _ = LabResult.objects.update_or_create(
                    order=order, code=str(case.data.get("result_code") or ""), name=name,
                    defaults={
                        "value_numeric": numeric, "value_text": text,
                        "unit": case.data.get("unit", ""),
                        "reference_low": case.data.get("reference_low") or None,
                        "reference_high": case.data.get("reference_high") or None,
                        "interpretation": interpretation, "status": LabResult.Status.PRELIMINARY,
                        "entered_by": user,
                    },
                )
                order.status = LabOrder.Status.AWAITING_VALIDATION
                order.result_notes = case.summary or order.result_notes
                order.save(update_fields=["status", "result_notes", "updated_at"])
                result["lab_result_id"] = lab_result.id

    elif adapter == "emergency_operation":
        from operations.models import AmbulanceDispatch, EmergencyCase

        severity = case.data.get("severity", "high")
        if case.page_slug in {"call-intake", "incident-detail", "emergency-triage"} and case.patient_id:
            acuity_map = {
                "critical": EmergencyCase.Acuity.RESUSCITATION,
                "high": EmergencyCase.Acuity.EMERGENT,
                "moderate": EmergencyCase.Acuity.URGENT,
                "low": EmergencyCase.Acuity.LESS_URGENT,
            }
            emergency = EmergencyCase.objects.create(
                organization=case.organization, patient=case.patient,
                arrival_mode="ambulance" if case.page_slug == "call-intake" else "walk_in",
                acuity=acuity_map.get(severity, EmergencyCase.Acuity.URGENT),
                chief_complaint=case.data.get("notes") or case.summary or case.title,
                triage_notes=str(case.data.get("clinical_observations") or ""),
                assigned_clinician=case.assigned_to, created_by=user,
            )
            result.update({"emergency_case_id": emergency.id, "emergency_case_number": emergency.case_number})
        if case.page_slug in {"call-intake", "dispatch-map", "ambulance-detail", "route-eta", "live-telemetry", "paramedic-workspace"}:
            pickup_coordinates = {"latitude": case.data.get("latitude"), "longitude": case.data.get("longitude")}
            destination_coordinates = {"latitude": case.data.get("destination_latitude"), "longitude": case.data.get("destination_longitude")}
            dispatch = AmbulanceDispatch.objects.create(
                organization=case.organization, patient=case.patient,
                caller_name=case.data.get("caller_name") or (case.patient.display_name if case.patient_id else user.display_name),
                caller_phone=case.data.get("caller_phone") or getattr(case.patient, "phone", "") or getattr(user, "phone", ""),
                pickup_location=case.data.get("incident_location") or case.summary or "Pickup location pending",
                destination=case.data.get("destination", ""), priority="critical" if severity == "critical" else "urgent",
                dispatcher=user if active_role(user) == "ambulance_dispatcher" else None,
                paramedic=case.assigned_to if case.assigned_to and active_role(case.assigned_to) == "paramedic" else None,
                pickup_coordinates=pickup_coordinates, destination_coordinates=destination_coordinates,
                clinical_notes=case.data.get("notes", ""),
            )
            result.update({"ambulance_dispatch_id": dispatch.id, "dispatch_number": dispatch.dispatch_number})
            result.update(_route_summary(pickup_coordinates, destination_coordinates))

    elif adapter == "theatre_operation":
        from operations.models import SurgicalCase, SurgicalChecklist

        reference = case.data.get("surgical_case_reference")
        surgical = SurgicalCase.objects.filter(case_number=reference, organization=case.organization).first() if reference else None
        if not surgical and case.patient_id and case.data.get("procedure"):
            scheduled_start = _dt(case.data.get("scheduled_at"))
            scheduled_end = _dt(case.data.get("scheduled_end"))
            if scheduled_start and not scheduled_end:
                scheduled_end = scheduled_start + datetime.timedelta(hours=2)
            if scheduled_start and scheduled_end and scheduled_end <= scheduled_start:
                raise ValidationError({"scheduled_end": "Expected end must be after the scheduled start."})
            theatre_name = case.data.get("theatre_room", "")
            if scheduled_start and theatre_name:
                candidates = SurgicalCase.objects.filter(
                    organization=case.organization, theatre_name=theatre_name,
                    status__in=[SurgicalCase.Status.SCHEDULED, SurgicalCase.Status.PRE_OP, SurgicalCase.Status.IN_THEATRE],
                    scheduled_start__lt=scheduled_end or scheduled_start + datetime.timedelta(hours=2),
                ).exclude(scheduled_start__isnull=True)
                conflict = False
                for candidate in candidates.only("scheduled_start", "scheduled_end"):
                    candidate_end = candidate.scheduled_end or (candidate.scheduled_start + datetime.timedelta(hours=2))
                    if candidate_end > scheduled_start:
                        conflict = True
                        break
                if conflict:
                    raise ValidationError({"scheduled_at": "This operating room has an overlapping surgical case."})
            surgical = SurgicalCase.objects.create(
                organization=case.organization, patient=case.patient, admission=case.admission,
                procedure_name=case.data.get("procedure"),
                preoperative_diagnosis=case.data.get("notes") or case.summary or "Pending pre-operative diagnosis",
                theatre_name=theatre_name, scheduled_start=scheduled_start, scheduled_end=scheduled_end,
                status=SurgicalCase.Status.SCHEDULED if scheduled_start else SurgicalCase.Status.REQUESTED,
                created_by=user,
            )
        if surgical:
            SurgicalChecklist.objects.get_or_create(surgical_case=surgical)
            result.update({"surgical_case_id": surgical.id, "surgical_case_number": surgical.case_number})

    elif adapter == "maternity_operation":
        from operations.models import MaternityEpisode

        reference = case.data.get("episode_reference")
        episode = MaternityEpisode.objects.filter(episode_number=reference, organization=case.organization).first() if reference else None
        if not episode and case.patient_id:
            episode = MaternityEpisode.objects.filter(patient=case.patient, organization=case.organization).exclude(status=MaternityEpisode.Status.DISCHARGED).order_by("-created_at").first()
        if not episode and case.patient_id:
            episode = MaternityEpisode.objects.create(
                organization=case.organization, patient=case.patient, admission=case.admission,
                assigned_midwife=user if active_role(user) == "midwife" else None,
                assigned_clinician=case.assigned_to, created_by=user,
            )
        if episode:
            record_type = result.get("record_type") or case.data.get("record_type")
            changed = []
            if record_type == "antenatal_visit":
                gestation = case.data.get("gestation_weeks")
                if gestation not in (None, ""):
                    episode.gestational_age_weeks = int(float(gestation)); changed.append("gestational_age_weeks")
            if record_type == "partograph_observation" or case.page_slug in {"visual-partograph", "labour-ward"}:
                episode.status = MaternityEpisode.Status.IN_LABOUR; changed.append("status")
                if not episode.labour_started_at:
                    episode.labour_started_at = timezone.now(); changed.append("labour_started_at")
            if record_type == "delivery_record" or case.page_slug in {"delivery-suite", "birth-record"}:
                episode.status = MaternityEpisode.Status.DELIVERED; changed.append("status")
                episode.delivered_at = _dt(case.data.get("delivered_at")) or episode.delivered_at or timezone.now(); changed.append("delivered_at")
                episode.delivery_method = case.data.get("delivery_mode") or episode.delivery_method; changed.append("delivery_method")
            if record_type == "newborn_assessment" or case.page_slug in {"newborn-assessment", "apgar-chart", "mother-baby-linking"}:
                weight = case.data.get("birth_weight_kg")
                if weight not in (None, ""):
                    episode.newborn_weight_grams = int(float(weight) * 1000); changed.append("newborn_weight_grams")
                if case.data.get("apgar_1") not in (None, ""):
                    episode.apgar_one_minute = int(float(case.data.get("apgar_1"))); changed.append("apgar_one_minute")
                if case.data.get("apgar_5") not in (None, ""):
                    episode.apgar_five_minutes = int(float(case.data.get("apgar_5"))); changed.append("apgar_five_minutes")
                episode.newborn_notes = case.data.get("resuscitation") or case.data.get("assessment") or episode.newborn_notes; changed.append("newborn_notes")
            if changed:
                episode.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))
            result.update({"maternity_episode_id": episode.id, "maternity_episode_number": episode.episode_number})

    elif adapter == "admin_operation":
        # Creation records intent; execution performs the privileged mutation.
        result["admin_operation"] = case.page_slug

    elif adapter == "records_management":
        from enterprise.models import RecordsRequest

        request_type = str(case.data.get("request_type", "correction")).lower().replace(" ", "_")
        aliases = {"merge": "correction", "unmerge": "correction", "restriction": "legal_hold", "classification": "scan", "archive": "retention", "destruction": "deletion", "movement": "release"}
        request_type = aliases.get(request_type, request_type)
        valid_types = {choice[0] for choice in RecordsRequest.Type.choices}
        if request_type not in valid_types:
            request_type = RecordsRequest.Type.CORRECTION
        if not case.patient:
            raise ValidationError({"patient": "Select the patient whose record is being managed."})
        record_request = RecordsRequest.objects.create(
            request_type=request_type, patient=case.patient, organization=case.organization,
            reason=case.data.get("reason") or case.summary or case.title, details=case.data,
            due_at=case.due_at, requested_by=user, assigned_to=case.assigned_to,
        )
        result.update({"records_request_id": record_request.id, "request_number": record_request.request_number})
        original_operation = case.data.get("request_type")
        if original_operation in {"merge", "unmerge"} and case.data.get("secondary_patient"):
            from enterprise.models import MasterPatientIndex, PatientMerge
            survivor = MasterPatientIndex.objects.filter(patient=case.patient).first()
            duplicate = MasterPatientIndex.objects.filter(patient_id=case.data.get("secondary_patient")).first()
            if not survivor or not duplicate or survivor.id == duplicate.id:
                raise ValidationError({"secondary_patient": "Select a distinct patient with a Master Patient Index record."})
            merge = PatientMerge.objects.create(
                survivor=survivor, duplicate=duplicate, field_decisions=case.data.get("details") or {},
                status="reversal_requested" if original_operation == "unmerge" else "proposed",
                reason=case.data.get("reason") or case.summary or case.title, requested_by=user,
            )
            result["patient_merge_id"] = merge.id

    case.result = result
    case.save(update_fields=["result", "assigned_to", "subject_user", "appointment", "updated_at"])


def _adapter_on_action(case, definition, action_code, payload, user, request):
    adapter = definition.get("adapter")
    if adapter in OPERATIONAL_ADAPTERS:
        _sync_operational_action(case, definition, action_code, payload, user)
        return
    _action_schema_record(case, definition, action_code, user)

    if adapter in {None, "enterprise_record"}:
        return
    if adapter == "waiting_room":
        from .models import WaitingRoomEntry

        entry = WaitingRoomEntry.objects.select_related("appointment").filter(workflow_case=case).first()
        if not entry:
            raise ValidationError({"action": "The live waiting-room entry is missing."})
        now = timezone.now()
        mapping = {
            "check_in": (entry.Status.CHECKED_IN, "checked_in_at"),
            "mark_ready": (entry.Status.READY, "ready_at"),
            "call_next": (entry.Status.CALLED, "called_at"),
            "join": (entry.Status.IN_PROGRESS, "joined_at"),
            "complete": (entry.Status.COMPLETED, "completed_at"),
        }
        if action_code in mapping:
            entry.status, timestamp_field = mapping[action_code]
            setattr(entry, timestamp_field, now)
            entry.save(update_fields=["status", timestamp_field, "last_seen_at"])
            case.result = {**case.result, "queue_position": entry.queue_position, "waiting_room_status": entry.status}
            case.save(update_fields=["result", "updated_at"])

    elif adapter == "medication_renewal":
        from .models import MedicationRenewalRequest

        renewal = MedicationRenewalRequest.objects.select_related("prescription").filter(workflow_case=case).first()
        if not renewal:
            raise ValidationError({"action": "The medication renewal record is missing."})
        state = {"start_review": "under_review", "approve": "approved", "reject": "rejected", "complete": "completed", "cancel": "cancelled"}.get(action_code)
        if state:
            renewal.status = state
            renewal.decision_note = payload.get("note", "")
            if action_code in {"approve", "reject", "complete"}:
                renewal.decided_by = user
                renewal.decided_at = timezone.now()
            renewal.save()
        if action_code == "complete":
            from prescriptions.models import Prescription, PrescriptionItem

            source = renewal.prescription
            new_rx = Prescription.objects.create(
                appointment=source.appointment, encounter=source.encounter, doctor=user, patient=source.patient,
                notes=f"Renewal of {source.number}. {payload.get('note', '')}".strip(), status=Prescription.Status.ISSUED,
            )
            for item in source.items.all():
                PrescriptionItem.objects.create(
                    prescription=new_rx, medicine_name=item.medicine_name, generic_name=item.generic_name,
                    dosage=item.dosage, frequency=item.frequency, route=item.route, duration=item.duration,
                    quantity=item.quantity, refills_allowed=max(item.refills_allowed - 1, 0), instructions=item.instructions,
                )
            case.result = {**case.result, "renewed_prescription_id": new_rx.id, "renewed_prescription_number": new_rx.number}
            case.save(update_fields=["result", "updated_at"])

    elif adapter == "medication_adherence":
        if action_code == "correct":
            from .models import MedicationAdherenceEntry
            entry = MedicationAdherenceEntry.objects.filter(workflow_case=case).first()
            if entry:
                entry.note = (entry.note + "\nCorrection requested: " + payload.get("note", "")).strip()
                entry.save(update_fields=["note"])

    elif adapter == "privacy_request":
        from operations.models import PrivacyRequest

        privacy = PrivacyRequest.objects.filter(pk=(case.result or {}).get("privacy_request_id")).first()
        if not privacy:
            raise ValidationError({"action": "The privacy request record is missing."})
        state = {"verify_identity": PrivacyRequest.Status.VERIFYING, "start": PrivacyRequest.Status.IN_PROGRESS,
                 "request_information": PrivacyRequest.Status.WAITING, "provide_information": PrivacyRequest.Status.IN_PROGRESS,
                 "complete": PrivacyRequest.Status.COMPLETED, "decline": PrivacyRequest.Status.DECLINED}.get(action_code)
        if state:
            privacy.status = state
        if action_code == "verify_identity":
            privacy.identity_verified = True
        if action_code in {"complete", "decline"}:
            privacy.resolution = payload.get("note", "")
            privacy.completed_at = timezone.now()
        privacy.assigned_to = privacy.assigned_to or (user if active_role(user) != "patient" else None)
        privacy.save()

    elif adapter == "caregiver_invitation":
        from accounts.models import PatientRelationship

        relationship = PatientRelationship.objects.filter(pk=(case.result or {}).get("relationship_id")).first()
        if not relationship:
            raise ValidationError({"action": "The caregiver authority record is missing."})
        state = {"accept": PatientRelationship.Status.PENDING, "verify": PatientRelationship.Status.ACTIVE,
                 "reject": PatientRelationship.Status.REVOKED, "revoke": PatientRelationship.Status.REVOKED}.get(action_code)
        if state:
            relationship.status = state
        if action_code == "verify":
            relationship.verified_by = user
            relationship.verified_at = timezone.now()
        relationship.notes = (relationship.notes + "\n" + payload.get("note", "")).strip()
        relationship.save()

    elif adapter == "patient_feedback":
        from operations.models import QualityIncident, SupportTicket

        ticket = SupportTicket.objects.filter(pk=(case.result or {}).get("support_ticket_id")).first()
        if ticket:
            ticket_state = {"acknowledge": "in_progress", "investigate": "in_progress", "request_information": "waiting_user",
                            "provide_information": "in_progress", "resolve": "resolved", "close": "closed"}.get(action_code)
            if ticket_state:
                ticket.status = ticket_state
            if action_code in {"resolve", "close"}:
                ticket.resolution = payload.get("note", "")
            ticket.assigned_to = ticket.assigned_to or (user if active_role(user) != "patient" else None)
            ticket.save()
        incident = QualityIncident.objects.filter(pk=(case.result or {}).get("quality_incident_id")).first()
        if incident:
            incident_state = {"investigate": QualityIncident.Status.INVESTIGATING, "resolve": QualityIncident.Status.RESOLVED, "close": QualityIncident.Status.CLOSED}.get(action_code)
            if incident_state:
                incident.status = incident_state
            if action_code in {"resolve", "close"}:
                incident.corrective_actions = payload.get("note", "")
                incident.closed_at = timezone.now()
            incident.assigned_to = incident.assigned_to or (user if active_role(user) != "patient" else None)
            incident.save()

    elif adapter == "clinical_task":
        from .models import ClinicalTask

        task = ClinicalTask.objects.filter(workflow_case=case).first()
        if not task:
            raise ValidationError({"action": "The clinical task record is missing."})
        state = {"assign": ClinicalTask.Status.OPEN, "start": ClinicalTask.Status.IN_PROGRESS,
                 "complete": ClinicalTask.Status.COMPLETED, "cancel": ClinicalTask.Status.CANCELLED}.get(action_code)
        if state:
            task.status = state
        if payload.get("assigned_to"):
            task.assigned_to_id = payload["assigned_to"]
        if action_code == "complete":
            task.completed_at = timezone.now()
        task.save()

    elif adapter == "care_conference":
        from .models import CareConference

        conference = CareConference.objects.filter(workflow_case=case).first()
        if not conference:
            raise ValidationError({"action": "The care-conference record is missing."})
        state = {"start": CareConference.Status.IN_PROGRESS, "complete": CareConference.Status.COMPLETED, "cancel": CareConference.Status.CANCELLED}.get(action_code)
        if state:
            conference.status = state
        if action_code in {"complete", "acknowledge"} and payload.get("note"):
            conference.minutes = (conference.minutes + "\n" + user.display_name + ": " + payload["note"]).strip()
        conference.save()

    elif adapter == "on_call_shift":
        from operations.models import StaffShift

        shift = StaffShift.objects.filter(pk=(case.result or {}).get("staff_shift_id")).first()
        if shift:
            state = {"confirm": StaffShift.Status.CONFIRMED, "start": StaffShift.Status.IN_PROGRESS,
                     "complete": StaffShift.Status.COMPLETED, "cancel": StaffShift.Status.CANCELLED}.get(action_code)
            if state:
                shift.status = state
                shift.save(update_fields=["status", "updated_at"])

    elif adapter == "appointment_create" and case.appointment_id:
        if action_code == "confirm":
            case.appointment.transition_to(case.appointment.Status.CONFIRMED, actor=user, reason=payload.get("note", ""))
        elif action_code == "cancel":
            case.appointment.transition_to(case.appointment.Status.CANCELLED, actor=user, reason=payload.get("note", ""))

    elif adapter == "queue_ticket":
        from .models import QueueTicket

        ticket = QueueTicket.objects.filter(workflow_case=case).first()
        if not ticket:
            raise ValidationError({"action": "The queue ticket is missing."})
        state = {"call": QueueTicket.Status.CALLED, "serve": QueueTicket.Status.SERVING,
                 "complete": QueueTicket.Status.COMPLETED, "cancel": QueueTicket.Status.CANCELLED}.get(action_code)
        if state:
            ticket.status = state
        if action_code == "call":
            ticket.called_at = timezone.now()
        if action_code == "complete":
            ticket.completed_at = timezone.now()
        ticket.save()

    elif adapter == "call_centre_callback":
        from .models import CallCentreCallback

        callback = CallCentreCallback.objects.filter(workflow_case=case).first()
        if not callback:
            raise ValidationError({"action": "The callback record is missing."})
        state = {"attempt": CallCentreCallback.Status.ATTEMPTED, "reached": CallCentreCallback.Status.REACHED,
                 "no_answer": CallCentreCallback.Status.NO_ANSWER, "complete": CallCentreCallback.Status.COMPLETED}.get(action_code)
        if state:
            callback.status = state
        if action_code in {"attempt", "reached", "no_answer"}:
            callback.attempts += 1
        callback.outcome = payload.get("note", callback.outcome)
        callback.save()

    elif adapter == "sms_confirmation" and action_code in {"send", "retry"}:
        from communication.services import notify
        from accounts.models import User

        recipient = case.patient or User.objects.filter(phone=case.data.get("phone")).first()
        if not recipient:
            raise ValidationError({"phone": "No account could be matched to the recipient phone number."})
        notification = notify(
            recipient, "Appointment confirmation", case.data.get("message") or payload.get("note", ""),
            kind="appointment", priority="normal", channels=["in_app", "sms"],
            metadata={"appointment_id": case.appointment_id, "workflow_case": str(case.public_id)},
        )
        case.result = {**case.result, "notification_id": notification.id, "delivery_status": "queued"}
        case.save(update_fields=["result", "updated_at"])

    elif adapter == "inventory_operation":
        from operations.models import InventoryBatch, StockMovement

        if action_code in {"execute", "quarantine", "recall"}:
            batch = _inventory_batch_for_case(case)
            if not batch:
                # Schema-only safety records such as cold-chain readings remain
                # canonical EnterpriseRecords and do not mutate stock quantities.
                if not (definition.get("recordTypes") or []):
                    raise ValidationError({"batch_number": "Select a stock batch before executing this transaction."})
            else:
                if action_code == "recall" or case.page_slug in {"product-recall", "product-recalls"}:
                    batch.recalled = True
                    batch.recall_reason = payload.get("note") or case.data.get("reason") or case.summary
                    batch.save(update_fields=["recalled", "recall_reason"])
                    movement = _apply_stock_movement(case, user, StockMovement.Type.RECALL, quantity=case.data.get("quantity") or batch.quantity_available, reason=batch.recall_reason)
                    case.result = {**case.result, "stock_movement_id": movement.id, "balance_after": movement.balance_after}
                elif action_code == "quarantine" or case.page_slug in {"quarantine-stock", "damaged-stock"}:
                    movement_type = StockMovement.Type.DAMAGE if case.page_slug == "damaged-stock" else StockMovement.Type.ADJUSTMENT
                    movement = _apply_stock_movement(case, user, movement_type, reason=payload.get("note") or case.data.get("reason"))
                    case.result = {**case.result, "stock_movement_id": movement.id, "balance_after": movement.balance_after, "quarantined": True}
                elif action_code == "execute":
                    movement_map = {
                        "goods-received": StockMovement.Type.RECEIPT,
                        "drug-return": StockMovement.Type.RETURN,
                        "stock-transfer": StockMovement.Type.TRANSFER,
                        "stock-adjustment": StockMovement.Type.ADJUSTMENT,
                        "stock-count": StockMovement.Type.ADJUSTMENT,
                        "variance-investigation": StockMovement.Type.ADJUSTMENT,
                    }
                    movement_type = movement_map.get(case.page_slug)
                    if movement_type:
                        movement = _apply_stock_movement(case, user, movement_type, reason=payload.get("note") or case.data.get("reason"))
                        case.result = {**case.result, "stock_movement_id": movement.id, "balance_after": movement.balance_after}
                case.save(update_fields=["result", "updated_at"])

    elif adapter == "laboratory_operation":
        from services.models import LabOrder, LabResult, SpecimenEvent

        order = LabOrder.objects.filter(pk=(case.result or {}).get("lab_order_id")).first()
        if order:
            now = timezone.now()
            status_map = {
                "receive": LabOrder.Status.SAMPLE_RECEIVED,
                "process": LabOrder.Status.PROCESSING,
                "validate": LabOrder.Status.VALIDATED,
                "release": LabOrder.Status.COMPLETED,
                "reject": LabOrder.Status.REJECTED,
                "escalate": LabOrder.Status.AMENDED if order.status == LabOrder.Status.COMPLETED else order.status,
            }
            order.status = status_map.get(action_code, order.status)
            if action_code == "receive":
                order.received_at = now
                SpecimenEvent.objects.create(order=order, event_type=SpecimenEvent.Type.RECEIVED, barcode=order.specimen_id, notes=payload.get("note", ""), performed_by=user)
            elif action_code == "process":
                SpecimenEvent.objects.create(order=order, event_type=SpecimenEvent.Type.PROCESSING, barcode=order.specimen_id, notes=payload.get("note", ""), performed_by=user)
            elif action_code == "validate":
                if not order.results.exists():
                    raise ValidationError({"action": "Enter at least one result before validation."})
                LabResult.objects.filter(order=order).update(verified_by=user, verified_at=now, status=LabResult.Status.FINAL)
            elif action_code == "release":
                if not order.results.filter(verified_at__isnull=False).exists():
                    raise ValidationError({"action": "At least one verified result is required before release."})
                order.result_released = True
                order.released_at = now
                LabResult.objects.filter(order=order).update(released_by=user, released_at=now)
                try:
                    from communication.services import notify
                    notify(
                        order.patient, "Laboratory result released",
                        f"Your {order.test.name} result is now available in MyDoctor.",
                        kind="laboratory", priority="high", channels=["in_app", "email"],
                        metadata={"lab_order_id": order.id, "workflow_case": str(case.public_id)},
                    )
                    if order.referring_doctor_id:
                        notify(
                            order.referring_doctor, "Laboratory result ready",
                            f"{order.patient.display_name}: {order.test.name} has been released.",
                            kind="clinical_result", priority="high", channels=["in_app"],
                            metadata={"lab_order_id": order.id, "patient_id": order.patient_id},
                        )
                except Exception as exc:
                    case.result = {**case.result, "notification_warning": str(exc)}
                    case.save(update_fields=["result", "updated_at"])
            elif action_code == "reject":
                order.rejection_reason = payload.get("note", "")
                SpecimenEvent.objects.create(order=order, event_type=SpecimenEvent.Type.REJECTED, barcode=order.specimen_id, notes=payload.get("note", ""), performed_by=user)
            elif action_code == "escalate":
                critical_results = list(order.results.filter(interpretation=LabResult.Interpretation.CRITICAL))
                if not critical_results:
                    raise ValidationError({"action": "Only a result marked critical can be escalated."})
                recipient = order.referring_doctor or case.assigned_to
                if not recipient:
                    raise ValidationError({"assigned_to": "Assign a clinician before escalating this critical result."})
                try:
                    from communication.services import notify
                    notification = notify(
                        recipient, "CRITICAL laboratory result",
                        f"Immediate review required for {order.patient.display_name}: {order.test.name}. {payload.get('note', '')}".strip(),
                        kind="critical_result", priority="critical", channels=["in_app", "sms"],
                        metadata={"lab_order_id": order.id, "patient_id": order.patient_id, "result_ids": [row.id for row in critical_results]},
                    )
                    case.result = {**case.result, "critical_notification_id": notification.id}
                    case.save(update_fields=["result", "updated_at"])
                except Exception as exc:
                    raise ValidationError({"action": f"Critical-result notification could not be queued: {exc}"})
            order.save()

    elif adapter == "emergency_operation":
        from operations.models import AmbulanceDispatch, EmergencyCase

        emergency = EmergencyCase.objects.filter(pk=(case.result or {}).get("emergency_case_id")).first()
        dispatch = AmbulanceDispatch.objects.filter(pk=(case.result or {}).get("ambulance_dispatch_id")).first()
        now = timezone.now()
        if emergency:
            emergency_map = {
                "triage": EmergencyCase.Status.TRIAGED,
                "arrive": EmergencyCase.Status.IN_TREATMENT,
                "transport": EmergencyCase.Status.REFERRED,
                "handover": EmergencyCase.Status.ADMITTED,
                "complete": EmergencyCase.Status.DISCHARGED,
                "cancel": EmergencyCase.Status.LEFT,
            }
            if action_code in emergency_map:
                emergency.status = emergency_map[action_code]
                if action_code == "arrive" and not emergency.treatment_started_at:
                    emergency.treatment_started_at = now
                if action_code in {"handover", "complete", "cancel"}:
                    emergency.closed_at = now
                emergency.triage_notes = "\n".join(filter(None, [emergency.triage_notes, payload.get("note", "")]))
                emergency.save()
        if dispatch:
            dispatch_map = {
                "dispatch": AmbulanceDispatch.Status.ASSIGNED,
                "en_route": AmbulanceDispatch.Status.EN_ROUTE,
                "arrive": AmbulanceDispatch.Status.ON_SCENE,
                "transport": AmbulanceDispatch.Status.TRANSPORTING,
                "handover": AmbulanceDispatch.Status.ARRIVED,
                "complete": AmbulanceDispatch.Status.COMPLETED,
                "cancel": AmbulanceDispatch.Status.CANCELLED,
            }
            if action_code in dispatch_map:
                dispatch.status = dispatch_map[action_code]
                if action_code == "dispatch":
                    dispatch.dispatched_at = now
                    dispatch.dispatcher = user if active_role(user) == "ambulance_dispatcher" else dispatch.dispatcher
                elif action_code == "arrive":
                    dispatch.arrived_scene_at = now
                elif action_code == "handover":
                    dispatch.completed_at = None
                elif action_code in {"complete", "cancel"}:
                    dispatch.completed_at = now
                dispatch.clinical_notes = "\n".join(filter(None, [dispatch.clinical_notes, payload.get("note", "")]))
                dispatch.save()

    elif adapter == "theatre_operation":
        from operations.models import SurgicalCase, SurgicalChecklist

        surgical = SurgicalCase.objects.filter(pk=(case.result or {}).get("surgical_case_id")).first()
        if surgical:
            now = timezone.now()
            status_map = {
                "check_in": SurgicalCase.Status.PRE_OP,
                "anaesthesia_start": SurgicalCase.Status.PRE_OP,
                "procedure_start": SurgicalCase.Status.IN_THEATRE,
                "count_signoff": SurgicalCase.Status.IN_THEATRE,
                "recovery": SurgicalCase.Status.RECOVERY,
                "complete": SurgicalCase.Status.COMPLETED,
                "cancel": SurgicalCase.Status.CANCELLED,
            }
            surgical.status = status_map.get(action_code, surgical.status)
            checklist, _ = SurgicalChecklist.objects.get_or_create(surgical_case=surgical)
            if action_code == "check_in":
                checklist.patient_identity_confirmed = True
                checklist.procedure_confirmed = True
                checklist.consent_confirmed = bool(surgical.consent_obtained or case.data.get("consent_confirmed"))
                checklist.allergies_reviewed = True
                checklist.completed_by = user
                checklist.notes = "\n".join(filter(None, [checklist.notes, payload.get("note", "")]))
                checklist.save()
            if action_code == "anaesthesia_start":
                surgical.anaesthetist = user
                surgical.anaesthesia_notes = "\n".join(filter(None, [surgical.anaesthesia_notes, payload.get("note", "")]))
                checklist.anaesthesia_safety_check = True
                checklist.completed_by = user
                checklist.save()
            if action_code == "procedure_start":
                if not all([checklist.patient_identity_confirmed, checklist.procedure_confirmed, checklist.consent_confirmed, checklist.allergies_reviewed, checklist.anaesthesia_safety_check]):
                    raise ValidationError({"action": "Complete patient identity, procedure, consent, allergy and anaesthesia safety checks before starting the procedure."})
                surgical.actual_start = surgical.actual_start or now
            if action_code == "count_signoff":
                checklist.instrument_count_complete = True
                checklist.completed_by = user
                checklist.notes = "\n".join(filter(None, [checklist.notes, payload.get("note", "")]))
                checklist.save()
            if action_code == "recovery":
                if not checklist.instrument_count_complete:
                    raise ValidationError({"action": "Instrument and swab counts must be signed before transfer to recovery."})
                checklist.recovery_plan_confirmed = True
                checklist.completed_by = user
                checklist.save()
            if action_code == "complete":
                required = [
                    checklist.patient_identity_confirmed, checklist.procedure_confirmed,
                    checklist.consent_confirmed, checklist.allergies_reviewed,
                    checklist.anaesthesia_safety_check, checklist.instrument_count_complete,
                    checklist.recovery_plan_confirmed,
                ]
                if not all(required):
                    raise ValidationError({"action": "The surgical safety checklist is incomplete; the case cannot be closed."})
                surgical.actual_end = now
            elif action_code == "cancel":
                surgical.actual_end = now
            surgical.save()
            case.result = {**case.result, "surgical_status": surgical.status, "checklist_completion": checklist.completion_percent}
            case.save(update_fields=["result", "updated_at"])

    elif adapter == "maternity_operation":
        from operations.models import InventoryBatch, MaternityEpisode, StockMovement

        episode = MaternityEpisode.objects.filter(pk=(case.result or {}).get("maternity_episode_id")).first()
        if not episode:
            raise ValidationError({"action": "The maternity episode is missing."})
        record = None
        try:
            from enterprise.models import EnterpriseRecord
            record = EnterpriseRecord.objects.filter(pk=(case.result or {}).get("enterprise_record_id")).first()
        except Exception:
            record = None
        record_type = (record.record_type if record else None) or (case.result or {}).get("record_type") or case.data.get("record_type")
        source = (record.payload if record else {}) or case.data
        now = timezone.now()
        changed = []
        if action_code == "record":
            if record_type == "partograph_observation" or case.page_slug in {"visual-partograph", "labour-ward"}:
                episode.status = MaternityEpisode.Status.IN_LABOUR
                episode.labour_started_at = episode.labour_started_at or now
                changed.extend(["status", "labour_started_at"])
            note = source.get("assessment") or payload.get("note", "")
            if note:
                episode.risk_notes = "\n".join(filter(None, [episode.risk_notes, note]))
                changed.append("risk_notes")
        elif action_code == "escalate":
            episode.risk_level = "high"
            episode.risk_notes = "\n".join(filter(None, [episode.risk_notes, payload.get("note", "")]))
            changed.extend(["risk_level", "risk_notes"])
            recipient = episode.assigned_clinician or episode.assigned_midwife
            if recipient:
                try:
                    from communication.services import notify
                    notification = notify(
                        recipient,
                        "Maternal danger sign escalated",
                        f"{episode.patient.display_name}: {payload.get('note') or 'Urgent maternity review required.'}",
                        kind="clinical_alert",
                        priority="critical",
                        channels=["in_app", "sms"],
                        metadata={"maternity_episode_id": episode.id, "workflow_case": str(case.public_id)},
                    )
                    case.result = {**case.result, "escalation_notification_id": notification.id}
                except Exception as exc:
                    case.result = {**case.result, "notification_warning": str(exc)}
        elif action_code == "complete":
            if record_type in {"delivery_record", "birth_record"} or case.page_slug in {"delivery-suite", "birth-record"}:
                episode.status = MaternityEpisode.Status.POSTNATAL
                episode.delivered_at = _dt(source.get("delivered_at")) or episode.delivered_at or now
                episode.delivery_method = source.get("delivery_mode") or source.get("delivery_method") or episode.delivery_method
                episode.birth_outcome = source.get("birth_outcome") or episode.birth_outcome or "live_birth"
                changed.extend(["status", "delivered_at", "delivery_method", "birth_outcome"])
            elif record_type == "newborn_assessment" or case.page_slug in {"newborn-assessment", "apgar-chart", "mother-baby-linking"}:
                episode.status = MaternityEpisode.Status.POSTNATAL
                episode.apgar_one_minute = source.get("apgar_1") or episode.apgar_one_minute
                episode.apgar_five_minutes = source.get("apgar_5") or episode.apgar_five_minutes
                weight = source.get("birth_weight_kg") or source.get("weight_kg")
                if weight not in (None, ""):
                    episode.newborn_weight_grams = int(float(weight) * 1000)
                episode.newborn_notes = "\n".join(filter(None, [episode.newborn_notes, source.get("assessment", ""), source.get("resuscitation", "")]))
                changed.extend(["status", "apgar_one_minute", "apgar_five_minutes", "newborn_weight_grams", "newborn_notes"])
            elif record_type in {"immunization", "vaccination_administration"} or case.page_slug == "vaccination-administration":
                batch_id = source.get("inventory_batch") or source.get("batch_id")
                batch = InventoryBatch.objects.select_for_update().filter(pk=batch_id, item__organization=case.organization).first() if batch_id else None
                if batch:
                    if batch.recalled:
                        raise ValidationError({"inventory_batch": "The selected vaccine batch has been recalled."})
                    if batch.expiry_date and batch.expiry_date < timezone.localdate():
                        raise ValidationError({"inventory_batch": "The selected vaccine batch is expired."})
                    if batch.quantity_available < 1:
                        raise ValidationError({"inventory_batch": "The selected vaccine batch is out of stock."})
                    batch.quantity_available -= 1
                    batch.save(update_fields=["quantity_available"])
                    movement = StockMovement.objects.create(
                        batch=batch, movement_type=StockMovement.Type.ISSUE, quantity=-1,
                        balance_after=batch.quantity_available, reason="Vaccination administration",
                        reference=case.reference, created_by=user,
                    )
                    case.result = {**case.result, "stock_movement_id": movement.id, "vaccine_balance_after": batch.quantity_available}
            elif case.page_slug in {"postnatal-monitoring", "child-health-visit"} and episode.status == MaternityEpisode.Status.DELIVERED:
                episode.status = MaternityEpisode.Status.POSTNATAL
                changed.append("status")
        if changed:
            episode.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))
        case.result = {**case.result, "maternity_episode_id": episode.id, "maternity_status": episode.status}
        case.save(update_fields=["result", "updated_at"])

    elif adapter == "admin_operation":
        if action_code == "execute":
            if case.page_slug == "event-replay":
                from enterprise.models import DeadLetterEvent, ReplayRequest
                dead = DeadLetterEvent.objects.select_related("delivery__endpoint").filter(pk=case.data.get("dead_letter_id"), resolved_at__isnull=True).first()
                if not dead:
                    raise ValidationError({"dead_letter_id": "Select an unresolved dead-letter event."})
                replay = ReplayRequest.objects.create(endpoint=dead.delivery.endpoint, filters={"dead_letter_id": dead.id}, requested_by=user)
                case.result = {**case.result, "replay_request_id": replay.id}
                case.save(update_fields=["result", "updated_at"])
            elif case.page_slug in {"feature-flags", "localization", "maintenance-mode"}:
                from enterprise.models import FeatureConfiguration
                key = case.data.get("configuration_key")
                value = case.data.get("configuration") or {}
                config, _ = FeatureConfiguration.objects.update_or_create(
                    key=key, defaults={"value": value, "enabled": bool(value.get("enabled", True)) if isinstance(value, dict) else True, "updated_by": user}
                )
                case.result = {**case.result, "feature_configuration_id": config.id}
                case.save(update_fields=["result", "updated_at"])

    elif adapter == "records_management":
        from enterprise.models import PatientMerge, RecordsRequest

        record_request = RecordsRequest.objects.filter(pk=(case.result or {}).get("records_request_id")).first()
        if not record_request:
            raise ValidationError({"action": "The records request is missing."})
        state = {"review": "under_review", "approve": "approved", "reject": "rejected",
                 "execute": "completed", "reverse": "reversal_requested"}.get(action_code)
        if state:
            record_request.status = state
        if action_code in {"approve", "reject", "execute", "reverse"}:
            record_request.decision_by = user
            record_request.decision = payload.get("note", "")
        if action_code == "execute":
            record_request.completed_at = timezone.now()
            operation = case.data.get("request_type")
            if operation == "correction":
                from accounts.models import PatientProfile
                profile = PatientProfile.objects.filter(user=case.patient).first()
                changes = case.data.get("details") or {}
                if profile and isinstance(changes, dict):
                    allowed = {"phone", "address", "location", "date_of_birth", "gender", "blood_group", "emergency_contact"}
                    changed_fields = []
                    for field_name, value in changes.items():
                        if field_name in allowed and hasattr(profile, field_name):
                            setattr(profile, field_name, value)
                            changed_fields.append(field_name)
                    if changed_fields:
                        profile.save(update_fields=changed_fields)
            merge = PatientMerge.objects.filter(pk=(case.result or {}).get("patient_merge_id")).select_related("survivor", "duplicate").first()
            if merge:
                if case.data.get("request_type") == "unmerge":
                    merge.status = "reversed"
                    merge.reversed_at = timezone.now()
                    merge.duplicate.status = "active"
                    merge.duplicate.save(update_fields=["status", "updated_at"])
                else:
                    merge.status = "completed"
                    merge.approved_by = merge.approved_by or user
                    merge.completed_at = timezone.now()
                    merge.duplicate.status = "merged"
                    merge.duplicate.save(update_fields=["status", "updated_at"])
                merge.save()
        elif action_code == "approve":
            merge = PatientMerge.objects.filter(pk=(case.result or {}).get("patient_merge_id")).first()
            if merge:
                merge.status = "approved"
                merge.approved_by = user
                merge.save(update_fields=["status", "approved_by"])
        record_request.save()

    elif adapter == "appointment_reschedule" and action_code == "approve" and case.appointment_id:
        appointment = case.appointment
        new_date = datetime.date.fromisoformat(case.data["new_date"])
        new_start = datetime.time.fromisoformat(case.data["new_start_time"])
        old_start = datetime.datetime.combine(appointment.date, appointment.start_time)
        old_end = datetime.datetime.combine(appointment.date, appointment.end_time)
        duration = old_end - old_start
        new_start_dt = datetime.datetime.combine(new_date, new_start)
        appointment.date = new_date
        appointment.start_time = new_start
        appointment.end_time = (new_start_dt + duration).time()
        appointment.save(update_fields=["date", "start_time", "end_time", "updated_at"])
        case.result = {**case.result, "appointment_date": new_date.isoformat(), "appointment_start_time": new_start.isoformat()}
        case.save(update_fields=["result", "updated_at"])
    elif adapter == "appointment_cancel_refund":
        if action_code == "approve" and case.appointment_id:
            appointment = case.appointment
            if appointment.status not in {appointment.Status.CANCELLED, appointment.Status.COMPLETED}:
                appointment.transition_to(appointment.Status.CANCELLED, actor=user, reason=payload.get("note") or case.data.get("reason", ""))
        if action_code == "process_refund" and case.invoice_id:
            from payments.models import RefundRequest

            payment = case.invoice.transactions.filter(status="success").order_by("-created_at").first()
            if payment:
                refund, _ = RefundRequest.objects.get_or_create(
                    payment=payment,
                    reason=case.data.get("refund_reason") or case.data.get("reason") or "Appointment cancellation",
                    defaults={"amount": min(payment.amount, case.invoice.total), "requested_by": case.created_by, "approved_by": user, "approved_at": timezone.now(), "status": RefundRequest.Status.APPROVED},
                )
                case.result = {**case.result, "refund_request_id": refund.id, "refund_number": refund.number}
                case.save(update_fields=["result", "updated_at"])
    elif adapter == "consent" and action_code == "revoke":
        from governance.models import Consent

        consent = Consent.objects.filter(pk=(case.result or {}).get("consent_id"), patient=case.patient).first()
        if consent:
            consent.revoke(payload.get("note", ""))
    elif adapter == "result_review" and action_code in {"acknowledge", "escalate", "close"}:
        result_type = case.data.get("result_type", "laboratory")
        selected_result_id = case.data.get("lab_result") if result_type == "laboratory" else case.data.get("imaging_result")
        selected_result_id = selected_result_id or case.data.get("result_id")
        if not selected_result_id:
            raise ValidationError({"result": "Select the clinical result to review."})
        ResultReview.objects.create(
            result_type=result_type,
            result_id=int(selected_result_id),
            patient=case.patient,
            reviewer=user,
            action="acknowledge" if action_code == "acknowledge" else ("escalate" if action_code == "escalate" else "close"),
            note=payload.get("note", ""),
            escalated_to_id=payload.get("assigned_to") or None,
        )
        if result_type == "laboratory" and action_code == "acknowledge":
            try:
                from services.models import CriticalResultAcknowledgement, LabResult

                result = LabResult.objects.get(pk=selected_result_id, order__patient=case.patient)
                CriticalResultAcknowledgement.objects.get_or_create(result=result, defaults={"acknowledged_by": user, "notes": payload.get("note", "")})
            except Exception:
                pass
    elif adapter == "clinical_document":
        if action_code == "sign":
            document = GeneratedClinicalDocument.objects.filter(workflow_case=case).first()
            if not document:
                document = GeneratedClinicalDocument.objects.create(
                    document_type=case.data.get("document_type") or case.page_slug,
                    title=case.title,
                    patient=case.patient,
                    organization=case.organization,
                    workflow_case=case,
                    content=case.data,
                    created_by=case.created_by,
                )
            document.status = GeneratedClinicalDocument.Status.SIGNED
            document.signed_by = user
            document.signed_at = timezone.now()
            document.file.save(f"{document.verification_code}.pdf", ContentFile(render_document_pdf(document)), save=False)
            document.save()
            case.result = {**case.result, "document_id": document.id, "verification_code": document.verification_code, "file": document.file.url if document.file else ""}
            case.save(update_fields=["result", "updated_at"])
        elif action_code == "revoke":
            document = GeneratedClinicalDocument.objects.filter(workflow_case=case).first()
            if document:
                document.status = GeneratedClinicalDocument.Status.REVOKED
                document.revoked_at = timezone.now()
                document.save(update_fields=["status", "revoked_at", "updated_at"])
    elif adapter == "medication_administration" and action_code in {"administer", "omit"}:
        try:
            from workforce.models import MedicationAdministration, PatientVisit

            visit = PatientVisit.objects.filter(patient=case.patient).order_by("-checked_in_at").first()
            if visit:
                status_value = MedicationAdministration.Status.GIVEN if action_code == "administer" else MedicationAdministration.Status.MISSED
                MedicationAdministration.objects.create(
                    visit=visit,
                    nurse=user,
                    medication=case.data.get("medication", "Medication"),
                    dose=case.data.get("dose", ""),
                    route=case.data.get("route", ""),
                    scheduled_for=case.data.get("scheduled_at") or None,
                    status=status_value,
                    notes=payload.get("note", ""),
                )
        except Exception as exc:
            case.result = {**case.result, "adapter_warning": str(exc)}
            case.save(update_fields=["result", "updated_at"])
    elif adapter == "finance_operation":
        from payments.models import (
            ApprovalLimit, DepartmentBudget, Expense, FinancialPeriod, InvoiceAdjustment,
            JournalEntry, LedgerAccount, Posting, ReconciliationRun, SupplierInvoice,
        )

        result = dict(case.result or {})
        expense = Expense.objects.filter(pk=result.get("expense_id")).first()
        supplier_invoice = SupplierInvoice.objects.filter(pk=result.get("supplier_invoice_id")).first()
        reconciliation = ReconciliationRun.objects.filter(pk=result.get("reconciliation_id")).first()
        adjustment = InvoiceAdjustment.objects.select_related("invoice").filter(pk=result.get("invoice_adjustment_id")).first()
        budget = DepartmentBudget.objects.filter(pk=result.get("department_budget_id")).first()
        approval_limit = ApprovalLimit.objects.filter(pk=result.get("approval_limit_id")).first()
        period = FinancialPeriod.objects.filter(pk=result.get("financial_period_id")).first()
        amount = int(float(case.data.get("amount") or 0))
        role = active_role(user)

        if action_code == "approve":
            limit = ApprovalLimit.objects.filter(
                organization=case.organization, role_code=role,
                operation_type=case.data.get("operation_type") or result.get("finance_operation") or "expense",
                currency=case.data.get("currency") or "UGX", active=True,
            ).first()
            if limit and amount > limit.maximum_amount and role not in {"finance_manager", "platform_super_admin", "admin"}:
                raise ValidationError({"action": f"This amount exceeds the {role} approval limit."})
            if expense:
                expense.status = Expense.Status.APPROVED; expense.approved_by = user; expense.save(update_fields=["status", "approved_by", "updated_at"])
            if supplier_invoice:
                supplier_invoice.status = SupplierInvoice.Status.APPROVED; supplier_invoice.approved_by = user; supplier_invoice.save(update_fields=["status", "approved_by", "updated_at"])
            if adjustment:
                adjustment.status = InvoiceAdjustment.Status.APPROVED; adjustment.approved_by = user; adjustment.approved_at = timezone.now(); adjustment.save(update_fields=["status", "approved_by", "approved_at"])
            if budget:
                budget.approved_by = user; budget.save(update_fields=["approved_by", "updated_at"])
            if approval_limit:
                approval_limit.active = True; approval_limit.save(update_fields=["active"])
        elif action_code == "reject":
            if expense:
                expense.status = Expense.Status.REJECTED; expense.save(update_fields=["status", "updated_at"])
            if supplier_invoice:
                supplier_invoice.status = SupplierInvoice.Status.DISPUTED; supplier_invoice.notes = "\n".join(filter(None, [supplier_invoice.notes, payload.get("note", "")])) ; supplier_invoice.save(update_fields=["status", "notes", "updated_at"])
            if adjustment:
                adjustment.status = InvoiceAdjustment.Status.REJECTED; adjustment.approved_by = user; adjustment.approved_at = timezone.now(); adjustment.save(update_fields=["status", "approved_by", "approved_at"])
            if approval_limit:
                approval_limit.active = False; approval_limit.save(update_fields=["active"])
        elif action_code == "reconcile":
            if not reconciliation:
                raise ValidationError({"action": "The reconciliation record is missing."})
            reconciliation.status = ReconciliationRun.Status.CLOSED
            reconciliation.completed_by = user
            reconciliation.completed_at = timezone.now()
            reconciliation.notes = "\n".join(filter(None, [reconciliation.notes, payload.get("note", "")]))
            reconciliation.save()
            result.update({"reconciliation_status": reconciliation.status, "variance": reconciliation.variance})
        elif action_code == "post":
            if amount <= 0:
                raise ValidationError({"amount": "A positive amount is required before posting."})
            debit, _ = LedgerAccount.objects.get_or_create(
                code=case.data.get("account_code") or "1100",
                defaults={"name": "Workflow clearing", "account_type": LedgerAccount.Type.ASSET},
            )
            credit, _ = LedgerAccount.objects.get_or_create(
                code=case.data.get("offset_account_code") or "4900",
                defaults={"name": "Workflow offset", "account_type": LedgerAccount.Type.REVENUE},
            )
            journal, created = JournalEntry.objects.get_or_create(
                reference=case.reference,
                defaults={
                    "description": case.data.get("details") or case.title,
                    "source_type": "workflow_case", "source_id": str(case.public_id),
                    "currency": case.data.get("currency") or "UGX",
                },
            )
            if created:
                Posting.objects.create(entry=journal, account=debit, direction=Posting.Direction.DEBIT, amount=amount, memo=case.title)
                Posting.objects.create(entry=journal, account=credit, direction=Posting.Direction.CREDIT, amount=amount, memo=case.title)
            if not journal.is_balanced:
                raise ValidationError({"action": "The journal entry is not balanced."})
            if expense:
                expense.status = Expense.Status.PAID; expense.paid_at = timezone.now(); expense.save(update_fields=["status", "paid_at", "updated_at"])
            if adjustment and adjustment.status in {InvoiceAdjustment.Status.APPROVED, InvoiceAdjustment.Status.REQUESTED}:
                invoice = adjustment.invoice
                if adjustment.adjustment_type in {InvoiceAdjustment.Type.CREDIT, InvoiceAdjustment.Type.DISCOUNT, InvoiceAdjustment.Type.WRITE_OFF}:
                    invoice.discount += adjustment.amount
                else:
                    invoice.amount += adjustment.amount
                invoice.recalculate_amount()
                adjustment.status = InvoiceAdjustment.Status.APPLIED
                adjustment.approved_by = adjustment.approved_by or user
                adjustment.approved_at = adjustment.approved_at or timezone.now()
                adjustment.save(update_fields=["status", "approved_by", "approved_at"])
            result["journal_entry_id"] = journal.id
        elif action_code == "reverse":
            journal = JournalEntry.objects.filter(pk=result.get("journal_entry_id")).first()
            if not journal:
                raise ValidationError({"action": "Post the transaction before creating a reversal."})
            reversal_reference = f"REV-{journal.reference}"
            reversal, created = JournalEntry.objects.get_or_create(
                reference=reversal_reference,
                defaults={"description": f"Reversal: {journal.description}", "source_type": "workflow_reversal", "source_id": str(case.public_id), "currency": journal.currency},
            )
            if created:
                for posting in journal.postings.select_related("account"):
                    Posting.objects.create(
                        entry=reversal, account=posting.account,
                        direction=Posting.Direction.CREDIT if posting.direction == Posting.Direction.DEBIT else Posting.Direction.DEBIT,
                        amount=posting.amount, memo=f"Reversal of {journal.reference}",
                    )
            if not reversal.is_balanced:
                raise ValidationError({"action": "The reversal entry is not balanced."})
            if expense and expense.status == Expense.Status.PAID:
                expense.status = Expense.Status.VOID; expense.save(update_fields=["status", "updated_at"])
            result["reversal_journal_entry_id"] = reversal.id
        elif action_code == "complete" and period:
            period.status = FinancialPeriod.Status.CLOSED; period.closed_by = user; period.closed_at = timezone.now(); period.save(update_fields=["status", "closed_by", "closed_at"])
        case.result = result
        case.save(update_fields=["result", "updated_at"])


def render_document_pdf(document):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing

    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("MyDoctor HealthOS", styles["Title"]), Paragraph(document.title, styles["Heading1"]), Spacer(1, 8)]
    story.append(Paragraph(f"Patient: {document.patient.display_name}", styles["BodyText"]))
    story.append(Paragraph(f"Document type: {document.document_type.replace('_', ' ').title()}", styles["BodyText"]))
    story.append(Paragraph(f"Verification code: {document.verification_code}", styles["BodyText"]))
    story.append(Spacer(1, 10))
    rows = []
    for key, value in (document.content or {}).items():
        if value in (None, "", [], {}):
            continue
        rows.append([key.replace("_", " ").title(), str(value)])
    if rows:
        table = Table(rows, colWidths=[45 * mm, 115 * mm])
        table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 6)]))
        story.append(table)
    story.append(Spacer(1, 12))
    if document.signed_by:
        story.append(Paragraph(f"Electronically signed by {document.signed_by.display_name} on {timezone.localtime(document.signed_at):%d %b %Y %H:%M}", styles["BodyText"]))
    drawing = Drawing(45 * mm, 45 * mm)
    widget = qr.QrCodeWidget(document.verification_code)
    bounds = widget.getBounds()
    scale = min((45 * mm) / (bounds[2] - bounds[0]), (45 * mm) / (bounds[3] - bounds[1]))
    widget.barWidth = (bounds[2] - bounds[0]) * scale
    widget.barHeight = (bounds[3] - bounds[1]) * scale
    drawing.add(widget)
    story.append(drawing)
    story.append(Paragraph("Verify this document in the MyDoctor verification portal. Any alteration invalidates the signature.", styles["Italic"]))
    doc.build(story)
    return stream.getvalue()
