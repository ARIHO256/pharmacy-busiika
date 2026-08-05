from datetime import timedelta

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import PatientVisit, StaffInvitation


def audit_workforce(request, action, resource, patient=None, metadata=None):
    try:
        from governance.services import audit

        audit(
            actor=getattr(request, "user", None),
            patient=patient,
            action=action,
            resource=resource,
            purpose="facility_operations",
            metadata=metadata or {},
            request=request,
        )
    except Exception:
        pass


def emit_workforce_event(name, resource, payload, request=None, patient=None):
    try:
        from interoperability.services import emit_event

        emit_event(
            name,
            resource,
            payload,
            actor=getattr(request, "user", None),
            patient=patient,
            request=request,
        )
    except Exception:
        pass


def create_invitation(*, organization, invited_by, email, role, department=None, **extra):
    return StaffInvitation.objects.create(
        organization=organization,
        department=department,
        invited_by=invited_by,
        email=email,
        role=role,
        expires_at=timezone.now() + timedelta(days=7),
        **extra,
    )


@transaction.atomic
def assign_queue_number(visit):
    today = timezone.localdate()
    current = (
        PatientVisit.objects.select_for_update()
        .filter(organization=visit.organization, checked_in_at__date=today)
        .aggregate(value=Max("queue_number"))["value"]
        or 0
    )
    visit.queue_number = current + 1
    visit.save(update_fields=["queue_number"])
    return visit.queue_number


# Forward-only stage order for the outpatient flow. Terminal states are never
# advanced out of, and a hook never moves a visit backwards.
_STAGE_ORDER = [
    PatientVisit.Status.REGISTERED,
    PatientVisit.Status.WAITING_TRIAGE,
    PatientVisit.Status.TRIAGED,
    PatientVisit.Status.WAITING_CLINICIAN,
    PatientVisit.Status.IN_CONSULTATION,
    PatientVisit.Status.LABORATORY,
    PatientVisit.Status.PHARMACY,
    PatientVisit.Status.BILLING,
    PatientVisit.Status.COMPLETED,
]
_TERMINAL = {PatientVisit.Status.COMPLETED, PatientVisit.Status.CANCELLED}


def advance_active_visit(patient, to_status, *, actor=None, reason=""):
    """Advance the patient's newest active visit to ``to_status`` if that moves
    the care flow forward. Cross-app events (lab orders, prescriptions,
    dispensing, payments) call this so the visit engine reflects real work
    instead of going stale at check-in.
    """
    visit = (
        PatientVisit.objects.filter(patient=patient)
        .exclude(status__in=_TERMINAL)
        .order_by("-checked_in_at")
        .first()
    )
    if visit is None:
        return None
    try:
        current = _STAGE_ORDER.index(visit.status)
        target = _STAGE_ORDER.index(to_status)
    except ValueError:
        return None
    if target <= current:
        return None
    visit.status = to_status
    if to_status == PatientVisit.Status.COMPLETED:
        visit.checked_out_at = timezone.now()
    visit.save(update_fields=["status", "checked_out_at"] if to_status == PatientVisit.Status.COMPLETED else ["status"])
    try:
        from governance.services import audit

        audit(
            actor=actor,
            patient=patient,
            action=f"visit.{to_status}",
            resource=visit,
            purpose="facility_operations",
            metadata={"reason": reason or f"Auto-advanced to {to_status}"},
        )
    except Exception:
        pass
    return visit
