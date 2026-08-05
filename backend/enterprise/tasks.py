"""Asynchronous enterprise operations.

Every task is idempotent or records its own execution state. The same functions
can be invoked by management commands during incident recovery when Celery is
unavailable.
"""
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from .models import (
    EventDelivery,
    NotificationProvider,
    PACSNode,
    ReportRun,
    ReportSchedule,
    ResourceAttachment,
    SecurityOperation,
    VerificationAutomation,
)
from .services import (
    deliver_event_delivery,
    execute_report,
    execute_verification_scan,
    pacs_health_check,
    provider_health_check,
    scan_attachment,
    scan_duplicate_patients,
)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 4})
def scan_resource_attachment(self, attachment_id):
    return scan_attachment(ResourceAttachment.objects.get(pk=attachment_id))


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 4})
def run_verification_scan(self, scan_id):
    return execute_verification_scan(VerificationAutomation.objects.get(pk=scan_id)).id


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={"max_retries": 5})
def deliver_event(self, delivery_id):
    return deliver_event_delivery(EventDelivery.objects.get(pk=delivery_id))


@shared_task
def deliver_pending_enterprise_events(limit=200):
    ids = list(
        EventDelivery.objects.filter(
            status__in=["pending", "retry"], next_attempt_at__lte=timezone.now()
        ).values_list("id", flat=True)[:limit]
    )
    for delivery_id in ids:
        deliver_event.delay(delivery_id)
    return len(ids)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def execute_report_run(self, run_id):
    run = execute_report(ReportRun.objects.get(pk=run_id))
    if run.status == "completed" and run.output_file:
        recipients = list(run.parameters.get("recipients") or [])
        if recipients:
            message = EmailMessage(
                subject=f"HealthPilot report: {run.report.name}",
                body="The requested HealthPilot operational report is attached.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            try:
                run.output_file.open("rb")
                message.attach(
                    run.output_file.name.rsplit("/", 1)[-1],
                    run.output_file.read(),
                    "text/csv",
                )
                message.send(fail_silently=False)
            finally:
                run.output_file.close()
    return run.id


def _next_cron_time(expression, base):
    """Resolve the next cron occurrence, with a conservative daily fallback."""
    try:
        from croniter import croniter

        return croniter(expression, base).get_next(type(base))
    except Exception:
        return base + timedelta(days=1)


@shared_task
def dispatch_due_report_schedules(limit=100):
    now = timezone.now()
    schedule_ids = list(
        ReportSchedule.objects.filter(active=True, next_run_at__lte=now)
        .order_by("next_run_at")
        .values_list("id", flat=True)[:limit]
    )
    dispatched = 0
    for schedule_id in schedule_ids:
        with transaction.atomic():
            schedule = (
                ReportSchedule.objects.select_for_update()
                .select_related("report")
                .get(pk=schedule_id)
            )
            if not schedule.active or not schedule.next_run_at or schedule.next_run_at > now:
                continue
            run = ReportRun.objects.create(
                report=schedule.report,
                requested_by=schedule.created_by,
                parameters={
                    "recipients": schedule.recipients,
                    "formats": schedule.formats,
                    "scheduled": True,
                },
            )
            schedule.last_run_at = now
            schedule.next_run_at = _next_cron_time(schedule.cron_expression, now)
            schedule.save(update_fields=["last_run_at", "next_run_at"])
        execute_report_run.delay(run.id)
        dispatched += 1
    return dispatched


@shared_task
def check_enterprise_provider_health():
    results = {"notifications": [], "pacs": []}
    for provider in NotificationProvider.objects.filter(active=True):
        results["notifications"].append(provider_health_check(provider))
    for node in PACSNode.objects.filter(active=True):
        results["pacs"].append(pacs_health_check(node))
    return results


@shared_task
def scan_master_patient_index(min_score=70):
    return scan_duplicate_patients(min_score=min_score)


@shared_task
def create_daily_security_operations():
    """Create auditable maintenance controls without pretending they ran.

    External scanners and backup jobs update these operations with evidence via
    the API or the supplied management commands.
    """
    now = timezone.now()
    rows = [
        ("backup", "Daily encrypted database backup", "high", 1),
        ("vulnerability_scan", "Daily dependency and container scan", "high", 1),
        ("restore_test", "Monthly backup restoration exercise", "high", 30),
        ("clinical_safety", "Quarterly clinical safety review", "critical", 90),
        ("dpia", "Annual data protection impact review", "high", 365),
        ("pen_test", "Annual independent penetration test", "critical", 365),
    ]
    created = []
    for operation_type, title, severity, interval_days in rows:
        due = not SecurityOperation.objects.filter(
            operation_type=operation_type,
            created_at__gte=now - timedelta(days=interval_days),
        ).exists()
        if due:
            row = SecurityOperation.objects.create(
                operation_type=operation_type,
                title=title,
                severity=severity,
                status="planned",
                description="Automatically scheduled control. Attach externally generated evidence before approval.",
                scope={"environment": "production", "automated_schedule": True},
                next_due_at=now + timedelta(days=interval_days),
            )
            created.append(row.reference)
    return created
