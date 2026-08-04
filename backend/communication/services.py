from django.db import transaction

from enterprise.access import has_role_identity

from .models import Notification, NotificationDelivery, NotificationPreference


TRANSACTIONAL_KINDS = {
    "account",
    "appointment",
    "appointment_reminder",
    "clinical",
    "credential_expiry",
    "lab",
    "payment",
    "prescription",
    "reminder",
    "verification",
    "workforce",
}


def _default_channels(kind, priority):
    channels = ["in_app"]
    if kind in TRANSACTIONAL_KINDS:
        channels.append("email")
    if priority in {Notification.Priority.HIGH, Notification.Priority.CRITICAL, "high", "critical"}:
        channels.extend(["sms", "push"])
    return channels


def _allowed_channels(user, requested):
    preferences, _ = NotificationPreference.objects.get_or_create(user=user)
    enabled = {
        "in_app": preferences.in_app_enabled,
        "email": preferences.email_enabled,
        "sms": preferences.sms_enabled,
        "push": preferences.push_enabled,
        "whatsapp": preferences.whatsapp_enabled,
    }
    return [channel for channel in requested if channel in enabled and enabled[channel]]


@transaction.atomic
def notify(
    user,
    title,
    body,
    kind="general",
    *,
    priority="normal",
    action_url="",
    channels=None,
    metadata=None,
):
    """Create a notification and one delivery record per enabled channel.

    ``in_app`` is immediate. External channels are queued and processed by the
    ``dispatch_notifications`` management command or a future worker.
    """
    requested = channels or _default_channels(kind, priority)
    selected = _allowed_channels(user, requested)
    notification = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        kind=kind,
        priority=priority,
        action_url=action_url,
        channels=selected,
        metadata=metadata or {},
    )
    for channel in selected:
        recipient = ""
        if channel == NotificationDelivery.Channel.EMAIL:
            recipient = user.email
        elif channel in {NotificationDelivery.Channel.SMS, NotificationDelivery.Channel.WHATSAPP}:
            recipient = user.phone
        elif channel == NotificationDelivery.Channel.PUSH:
            from .models import DeviceRegistration
            device = DeviceRegistration.objects.filter(user=user, active=True).order_by("-last_seen_at").first()
            recipient = device.token if device else ""
        delivery = NotificationDelivery.objects.create(
            notification=notification,
            channel=channel,
            recipient=recipient,
            status=(
                NotificationDelivery.Status.DELIVERED
                if channel == NotificationDelivery.Channel.IN_APP
                else NotificationDelivery.Status.PENDING
            ),
        )
        if channel == NotificationDelivery.Channel.IN_APP:
            from django.utils import timezone

            delivery.sent_at = timezone.now()
            delivery.save(update_fields=["sent_at"])
    try:
        from interoperability.services import emit_event

        emit_event(
            "notification.created",
            notification,
            {
                "notification_id": notification.id,
                "user_id": user.id,
                "kind": kind,
                "priority": priority,
                "channels": selected,
            },
            actor=None,
            patient=user if has_role_identity(user, "patient") else None,
        )
    except Exception:
        pass
    return notification
