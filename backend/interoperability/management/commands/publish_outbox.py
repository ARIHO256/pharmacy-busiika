import json

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from interoperability.models import OutboxEvent


class Command(BaseCommand):
    help = "Print pending outbox events for an external publisher; optionally mark them published."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--mark-published", action="store_true")

    def handle(self, *args, **options):
        limit = min(max(options["limit"], 1), 1000)
        with transaction.atomic():
            events = list(
                OutboxEvent.objects.select_for_update(skip_locked=True)
                .filter(status=OutboxEvent.Status.PENDING)
                .order_by("occurred_at")[:limit]
            )
            for event in events:
                self.stdout.write(
                    json.dumps(
                        {
                            "event_id": str(event.event_id),
                            "event_type": event.event_type,
                            "event_version": event.event_version,
                            "aggregate_type": event.aggregate_type,
                            "aggregate_id": event.aggregate_id,
                            "occurred_at": event.occurred_at.isoformat(),
                            "correlation_id": event.correlation_id,
                            "causation_id": event.causation_id,
                            "payload": event.payload,
                        },
                        default=str,
                    )
                )
                if options["mark_published"]:
                    event.status = OutboxEvent.Status.PUBLISHED
                    event.attempts += 1
                    event.published_at = timezone.now()
                    event.last_error = ""
                    event.save(update_fields=["status", "attempts", "published_at", "last_error"])
        self.stderr.write(self.style.SUCCESS(f"Processed {len(events)} event(s)."))
