from datetime import timedelta

from celery import shared_task
from django.core.management import call_command
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from interoperability.models import OutboxEvent


@shared_task
def deliver_events(limit=100, max_attempts=8):
    from .integrations import deliver_outbox
    now = timezone.now()
    ready = Q(status__in=["pending", "failed"]) & (Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
    stale = Q(status="processing", locked_at__lt=now - timedelta(minutes=10))
    ids = list(OutboxEvent.objects.filter(ready | stale).order_by("occurred_at").values_list("id", flat=True)[:min(max(limit, 1), 1000)])
    sent = failed = 0
    for pk in ids:
        with transaction.atomic():
            event = OutboxEvent.objects.select_for_update().filter(pk=pk).filter(ready | stale).first()
            if not event:
                continue
            if event.attempts >= max_attempts:
                event.status = "dead_letter"
                event.save(update_fields=["status"])
                continue
            event.status, event.locked_at = "processing", timezone.now()
            event.attempts += 1
            event.save(update_fields=["status", "locked_at", "attempts"])
        try:
            deliver_outbox(event)
            values = {"status": "published", "published_at": timezone.now(), "last_error": "", "next_attempt_at": None}
            sent += 1
        except Exception:
            values = {"status": "dead_letter" if event.attempts >= max_attempts else "failed",
                      "next_attempt_at": timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** event.attempts)),
                      "last_error": "Delivery failed; inspect the configured integration and worker logs."}
            failed += 1
        OutboxEvent.objects.filter(pk=event.pk, status="processing", locked_at=event.locked_at).update(**values)
    return {"sent": sent, "failed": failed}


@shared_task
def deliver_notifications():
    call_command("dispatch_notifications", limit=100, max_attempts=5)


@shared_task
def appointment_reminders():
    call_command("send_appointment_reminders", hours=24)


@shared_task
def credential_expiry():
    call_command("notify_expiring_credentials")


@shared_task
def refresh_inventory():
    from services.models import Medicine
    from .services import refresh_stock
    count = 0
    for pk in Medicine.objects.filter(batches__isnull=False).values_list("pk", flat=True).distinct():
        with transaction.atomic():
            medicine = Medicine.objects.select_for_update().get(pk=pk)
            refresh_stock(medicine)
            count += 1
    return count


@shared_task
def escalate_critical_lab_results():
    from django.conf import settings

    from communication.services import notify
    from services.models import LabResult

    minutes = settings.LAB_CRITICAL_ESCALATION_MINUTES
    if not minutes:
        return 0
    overdue = dict(
        interpretation=LabResult.Interpretation.CRITICAL, released_at__lte=timezone.now() - timedelta(minutes=minutes),
        acknowledgement__isnull=True, replacement__isnull=True, escalated_at__isnull=True,
    )
    ids = list(LabResult.objects.filter(**overdue).order_by("released_at").values_list("pk", flat=True)[:100])
    count = 0
    for pk in ids:
        with transaction.atomic():
            result = LabResult.objects.select_for_update(of=("self",)).filter(pk=pk, **overdue).first()
            if result is None:
                continue
            order = result.order
            if order.lab.is_active:
                notify(order.lab, "Critical result overdue for review",
                       "Open the laboratory worklist and contact the responsible care team.",
                       kind="laboratory", priority="critical", channels=["in_app"],
                       action_url="/lab/orders", metadata={"order_id": order.pk, "result_id": result.pk})
            recipients = {}
            if order.referring_doctor_id and order.referring_doctor.is_active:
                recipients[order.referring_doctor_id] = order.referring_doctor
            if order.visit_id and order.visit.assigned_doctor_id:
                from .access import organizations
                assigned = order.visit.assigned_doctor
                if assigned.is_active and assigned.is_verified and organizations(assigned).filter(pk=order.visit.organization_id).exists():
                    recipients[assigned.pk] = assigned
            for clinician in recipients.values():
                notify(clinician, "Critical result acknowledgement overdue",
                       "Open laboratory referrals to review the result and record follow-up.",
                       kind="laboratory", priority="critical", channels=["in_app"],
                       action_url="/doctor/lab-referrals", metadata={"order_id": order.pk, "result_id": result.pk})
            result.escalated_at = timezone.now()
            result.save(update_fields=["escalated_at"])
            count += 1
    return count
