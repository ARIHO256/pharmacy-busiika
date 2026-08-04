from django.conf import settings
from django.db import models


def default_notification_channels():
    return ["in_app"]


class Conversation(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_conversations",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_conversations",
    )
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("patient", "doctor")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conversation {self.patient_id} <-> {self.doctor_id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    text = models.TextField(blank=True, default="")
    attachment = models.FileField(upload_to="chat/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.pk} in conversation {self.conversation_id}"


class Notification(models.Model):
    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True, default="")
    kind = models.CharField(max_length=50, default="general")
    priority = models.CharField(
        max_length=20, choices=Priority.choices, default=Priority.NORMAL
    )
    action_url = models.CharField(max_length=300, blank=True, default="")
    channels = models.JSONField(default=default_notification_channels, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["kind", "created_at"]),
        ]

    def __str__(self):
        return f"Notification for {self.user_id}: {self.title}"


class NotificationDelivery(models.Model):
    class Channel(models.TextChoices):
        IN_APP = "in_app", "In application"
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        PUSH = "push", "Push notification"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    channel = models.CharField(max_length=20, choices=Channel.choices)
    recipient = models.CharField(max_length=220, blank=True, default="")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    provider_reference = models.CharField(max_length=160, blank=True, default="")
    last_error = models.TextField(blank=True, default="")
    last_attempted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "channel"],
                name="unique_notification_delivery_channel",
            )
        ]
        indexes = [models.Index(fields=["channel", "status", "created_at"])]

    def __str__(self):
        return f"{self.notification_id} via {self.channel}: {self.status}"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    appointment_reminders = models.BooleanField(default=True)
    clinical_updates = models.BooleanField(default=True)
    payment_updates = models.BooleanField(default=True)
    marketing_updates = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification preferences for {self.user_id}"


class NotificationTemplate(models.Model):
    code = models.CharField(max_length=100, unique=True)
    title_template = models.CharField(max_length=220)
    body_template = models.TextField()
    kind = models.CharField(max_length=50, default="general")
    default_priority = models.CharField(
        max_length=20,
        choices=Notification.Priority.choices,
        default=Notification.Priority.NORMAL,
    )
    default_channels = models.JSONField(default=default_notification_channels, blank=True)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code


class DeviceRegistration(models.Model):
    class Platform(models.TextChoices):
        WEB = "web", "Web"
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_devices")
    platform = models.CharField(max_length=20, choices=Platform.choices)
    token = models.CharField(max_length=500, unique=True)
    device_name = models.CharField(max_length=160, blank=True, default="")
    active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_seen_at"]
        indexes = [models.Index(fields=["user", "active", "last_seen_at"])]
