from django.db import transaction

from .models import OutboxEvent


def _request_ids(request):
    if request is None:
        return "", ""
    return (
        request.META.get("HTTP_X_REQUEST_ID", "")[:120],
        request.META.get("HTTP_X_CAUSATION_ID", "")[:120],
    )


@transaction.atomic
def emit_event(
    event_type,
    aggregate,
    payload,
    *,
    actor=None,
    patient=None,
    event_version=1,
    correlation_id="",
    causation_id="",
    request=None,
):
    """Write an event to the database in the caller's transaction.

    A separate worker can deliver these rows to Kafka, RabbitMQ, a partner API,
    or another transport.  Business transactions therefore do not depend on a
    broker being online.
    """

    request_correlation, request_causation = _request_ids(request)
    return OutboxEvent.objects.create(
        event_type=event_type,
        event_version=event_version,
        aggregate_type=aggregate.__class__.__name__,
        aggregate_id=str(getattr(aggregate, "pk", aggregate)),
        actor=actor,
        patient=patient,
        correlation_id=correlation_id or request_correlation,
        causation_id=causation_id or request_causation,
        payload=payload,
    )
