from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.db import transaction
from datetime import timedelta
from django.utils import timezone

from communication.models import Notification, NotificationDelivery, NotificationPreference


def _in_quiet_hours(preference, current_time):
    start = preference.quiet_hours_start
    end = preference.quiet_hours_end
    if not start or not end or start == end:
        return False
    if start < end:
        return start <= current_time < end
    return current_time >= start or current_time < end


class Command(BaseCommand):
    help = "Dispatch queued notification deliveries with bounded retries and quiet-hour handling."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--max-attempts", type=int, default=3)

    def handle(self, *args, **options):
        max_attempts = max(int(options["max_attempts"]), 1)
        deliveries = (
            NotificationDelivery.objects.filter(
                Q(status=NotificationDelivery.Status.PENDING)
                | Q(status=NotificationDelivery.Status.FAILED)
                | Q(status=NotificationDelivery.Status.PROCESSING, last_attempted_at__lt=timezone.now() - timedelta(minutes=10)),
                attempts__lt=max_attempts,
            )
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()))
            .select_related("notification__user")
            .order_by("created_at")[: options["limit"]]
        )
        sent = failed = skipped = deferred = 0
        for delivery in deliveries:
            with transaction.atomic():
                delivery = NotificationDelivery.objects.select_for_update().select_related("notification__user").get(pk=delivery.pk)
                if delivery.status in {"sent", "delivered", "skipped"} or delivery.attempts >= max_attempts:
                    continue
                if delivery.status == "processing" and delivery.last_attempted_at and delivery.last_attempted_at > timezone.now() - timedelta(minutes=10):
                    continue
                if delivery.next_attempt_at and delivery.next_attempt_at > timezone.now():
                    continue
                delivery.status = NotificationDelivery.Status.PROCESSING
                delivery.last_attempted_at = timezone.now()
                delivery.save(update_fields=["status", "last_attempted_at"])
            notification = delivery.notification
            preference = NotificationPreference.objects.filter(
                user=notification.user
            ).first()
            if preference and not getattr(preference, f"{delivery.channel}_enabled", False):
                delivery.status = NotificationDelivery.Status.SKIPPED
                delivery.last_error = "Delivery channel disabled by user preferences."
                delivery.save(update_fields=["status", "last_error"])
                skipped += 1
                continue
            if (
                preference
                and notification.priority != Notification.Priority.CRITICAL
                and _in_quiet_hours(preference, timezone.localtime().time())
            ):
                delivery.status = NotificationDelivery.Status.PENDING
                delivery.next_attempt_at = timezone.now() + timedelta(minutes=15)
                delivery.save(update_fields=["status", "next_attempt_at"])
                deferred += 1
                continue

            delivery.status = NotificationDelivery.Status.PROCESSING
            delivery.attempts += 1
            delivery.last_attempted_at = timezone.now()
            delivery.last_error = ""
            delivery.save(
                update_fields=["status", "attempts", "last_attempted_at", "last_error"]
            )
            try:
                if delivery.channel == NotificationDelivery.Channel.EMAIL:
                    if not delivery.recipient:
                        raise ValueError("No email recipient is configured.")
                    send_mail(
                        notification.title,
                        notification.body,
                        getattr(settings, "DEFAULT_FROM_EMAIL", None),
                        [delivery.recipient],
                        fail_silently=False,
                    )
                    delivery.status = NotificationDelivery.Status.SENT
                    delivery.sent_at = timezone.now()
                    sent += 1
                elif delivery.channel in {
                    NotificationDelivery.Channel.SMS,
                    NotificationDelivery.Channel.PUSH,
                }:
                    configured = settings.SMS_WEBHOOK_URL if delivery.channel == "sms" else settings.PUSH_WEBHOOK_URL
                    if configured:
                        from operations.integrations import send_notification
                        delivery.provider_reference = send_notification(delivery)
                        delivery.status = NotificationDelivery.Status.SENT
                        delivery.sent_at = timezone.now()
                        sent += 1
                    else:
                        delivery.status = NotificationDelivery.Status.SKIPPED
                        delivery.last_error = f"{delivery.channel} provider is not configured."
                        skipped += 1
                else:
                    delivery.status = NotificationDelivery.Status.DELIVERED
                    delivery.sent_at = timezone.now()
                    sent += 1
            except Exception as exc:
                delivery.status = NotificationDelivery.Status.FAILED
                delivery.last_error = "Delivery failed; verify the configured provider."
                delivery.next_attempt_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** delivery.attempts))
                failed += 1
            delivery.save(
                update_fields=[
                    "attempts",
                    "last_attempted_at",
                    "status",
                    "last_error",
                    "sent_at",
                    "provider_reference",
                    "next_attempt_at",
                ]
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"sent={sent} failed={failed} skipped={skipped} deferred={deferred}"
            )
        )
