from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from communication.models import Notification, NotificationDelivery, NotificationPreference
from communication.providers import send_push, send_sms, send_whatsapp


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
                | Q(status=NotificationDelivery.Status.FAILED),
                attempts__lt=max_attempts,
            )
            .select_related("notification__user")
            .order_by("created_at")[: options["limit"]]
        )
        sent = failed = skipped = deferred = 0
        for delivery in deliveries:
            notification = delivery.notification
            preference = NotificationPreference.objects.filter(
                user=notification.user
            ).first()
            if (
                preference
                and notification.priority != Notification.Priority.CRITICAL
                and _in_quiet_hours(preference, timezone.localtime().time())
            ):
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
                elif delivery.channel == NotificationDelivery.Channel.SMS:
                    if not delivery.recipient:
                        raise ValueError("No SMS recipient is configured.")
                    delivery.provider_reference = send_sms(delivery.recipient, notification.title, notification.body, notification.metadata)
                    delivery.status = NotificationDelivery.Status.SENT
                    delivery.sent_at = timezone.now()
                    sent += 1
                elif delivery.channel == NotificationDelivery.Channel.PUSH:
                    if not delivery.recipient:
                        raise ValueError("No active push device is registered.")
                    delivery.provider_reference = send_push(delivery.recipient, notification.title, notification.body, notification.metadata)
                    delivery.status = NotificationDelivery.Status.SENT
                    delivery.sent_at = timezone.now()
                    sent += 1
                elif delivery.channel == NotificationDelivery.Channel.WHATSAPP:
                    if not delivery.recipient:
                        raise ValueError("No WhatsApp recipient is configured.")
                    delivery.provider_reference = send_whatsapp(delivery.recipient, notification.title, notification.body, notification.metadata)
                    delivery.status = NotificationDelivery.Status.SENT
                    delivery.sent_at = timezone.now()
                    sent += 1
                else:
                    delivery.status = NotificationDelivery.Status.DELIVERED
                    delivery.sent_at = timezone.now()
                    sent += 1
            except Exception as exc:
                delivery.status = NotificationDelivery.Status.FAILED
                delivery.last_error = str(exc)
                failed += 1
            delivery.save(
                update_fields=[
                    "attempts",
                    "last_attempted_at",
                    "status",
                    "last_error",
                    "sent_at",
                    "provider_reference",
                ]
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"sent={sent} failed={failed} skipped={skipped} deferred={deferred}"
            )
        )
