from django.db.models import Q
from django.utils import timezone

from .models import AuditEvent, BreakGlassAccess, Consent


def _request_meta(request):
    if request is None:
        return {}
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return {
        "ip_address": ip or None,
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:1000],
        "correlation_id": request.META.get("HTTP_X_REQUEST_ID", "")[:100],
    }


def audit(
    *,
    actor=None,
    action,
    patient=None,
    resource=None,
    resource_type="",
    resource_id="",
    purpose="",
    decision=AuditEvent.Decision.NOT_APPLICABLE,
    metadata=None,
    emergency_access=False,
    request=None,
):
    if resource is not None:
        resource_type = resource.__class__.__name__
        resource_id = str(getattr(resource, "pk", ""))
    meta = _request_meta(request)
    return AuditEvent.objects.create(
        actor=actor,
        patient=patient,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        purpose=purpose,
        decision=decision,
        metadata=metadata or {},
        emergency_access=emergency_access,
        **meta,
    )


def current_consent(patient, consent_types, recipient=None):
    now = timezone.now()
    qs = Consent.objects.filter(
        patient=patient,
        status=Consent.Status.ACTIVE,
        consent_type__in=list(consent_types),
        valid_from__lte=now,
    ).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=now))
    if recipient is not None:
        qs = qs.filter(Q(granted_to__isnull=True) | Q(granted_to=recipient))
    return qs.order_by("-granted_at").first()


def active_break_glass(requester, patient):
    return BreakGlassAccess.objects.filter(
        requester=requester,
        patient=patient,
        status=BreakGlassAccess.Status.ACTIVE,
        expires_at__gt=timezone.now(),
    ).order_by("-started_at").first()
