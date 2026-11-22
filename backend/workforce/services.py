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
