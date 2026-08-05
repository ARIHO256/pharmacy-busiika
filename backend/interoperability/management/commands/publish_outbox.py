"""Reliably publish transactional outbox events.

Production deployments normally configure OUTBOX_WEBHOOK_URL to point to the
integration gateway (which may then fan out to Kafka, RabbitMQ, analytics or
partner APIs).  Events are acknowledged only after a successful 2xx response.
"""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from interoperability.models import OutboxEvent


class Command(BaseCommand):
    help = "Publish pending transactional outbox events through the configured integration gateway."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument(
            "--mark-published",
            action="store_true",
            help="Legacy local mode: acknowledge stdout events only when OUTBOX_ALLOW_STDOUT_ACK=true.",
        )
        parser.add_argument("--max-attempts", type=int, default=int(os.getenv("OUTBOX_MAX_ATTEMPTS", "10")))

    def handle(self, *args, **options):
        limit = min(max(options["limit"], 1), 1000)
        max_attempts = max(1, options["max_attempts"])
        now = timezone.now()
        processed = published = failed = dead = 0

        with transaction.atomic():
            events = list(
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status__in=[OutboxEvent.Status.PENDING, OutboxEvent.Status.FAILED])
                .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
                .order_by("occurred_at")[:limit]
            )
            for event in events:
                processed += 1
                envelope = self._envelope(event)
                event.attempts += 1
                try:
                    acknowledged = self._publish(envelope, options["mark_published"])
                    if acknowledged:
                        event.status = OutboxEvent.Status.PUBLISHED
                        event.published_at = timezone.now()
                        event.next_attempt_at = None
                        event.last_error = ""
                        published += 1
                    else:
                        # Local inspection mode: retain the event for the actual publisher.
                        event.status = OutboxEvent.Status.PENDING
                        event.next_attempt_at = timezone.now() + timedelta(minutes=5)
                        event.last_error = "No publisher acknowledged the event."
                except Exception as exc:  # noqa: BLE001 - provider failures are persisted
                    event.last_error = str(exc)[:4000]
                    if event.attempts >= max_attempts:
                        event.status = OutboxEvent.Status.DEAD_LETTER
                        event.next_attempt_at = None
                        dead += 1
                    else:
                        event.status = OutboxEvent.Status.FAILED
                        delay_seconds = min(3600, 30 * (2 ** min(event.attempts - 1, 7)))
                        event.next_attempt_at = timezone.now() + timedelta(seconds=delay_seconds)
                        failed += 1
                event.save(
                    update_fields=[
                        "status", "attempts", "published_at", "next_attempt_at", "last_error"
                    ]
                )

        self.stderr.write(
            self.style.SUCCESS(
                f"Outbox run: processed={processed} published={published} "
                f"failed={failed} dead_letter={dead}."
            )
        )

    @staticmethod
    def _envelope(event):
        return {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "event_version": event.event_version,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "occurred_at": event.occurred_at.isoformat(),
            "correlation_id": event.correlation_id,
            "causation_id": event.causation_id,
            "actor_id": event.actor_id,
            "patient_id": event.patient_id,
            "payload": event.payload,
        }

    def _publish(self, envelope, stdout_ack):
        body = json.dumps(envelope, default=str, separators=(",", ":")).encode("utf-8")
        url = os.getenv("OUTBOX_WEBHOOK_URL", "").strip()
        if not url:
            self.stdout.write(body.decode("utf-8"))
            return stdout_ack and os.getenv("OUTBOX_ALLOW_STDOUT_ACK", "false").lower() in {
                "1", "true", "yes", "on"
            }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "HealthPilot-Outbox/1.0",
            "Idempotency-Key": envelope["event_id"],
            "X-HealthPilot-Event-Type": envelope["event_type"],
        }
        token = os.getenv("OUTBOX_WEBHOOK_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        signing_secret = os.getenv("OUTBOX_SIGNING_SECRET", "").encode("utf-8")
        if signing_secret:
            headers["X-HealthPilot-Signature"] = hmac.new(
                signing_secret, body, hashlib.sha256
            ).hexdigest()

        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        timeout = int(os.getenv("OUTBOX_WEBHOOK_TIMEOUT", "20"))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Integration gateway returned HTTP {response.status}.")
                return True
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Integration gateway returned HTTP {exc.code}: {response_body[:500]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Integration gateway connection failed: {exc.reason}") from exc
