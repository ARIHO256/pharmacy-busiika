from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q


class Availability(models.Model):
    """Weekly recurring availability window for a doctor."""

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    weekday = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(6)],
        help_text="0=Monday ... 6=Sunday",
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveIntegerField(default=30)
    breaks = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {"start": "13:00", "end": "14:00"} windows.',
    )
    holidays = models.JSONField(
        default=list,
        blank=True,
        help_text='List of "YYYY-MM-DD" date strings.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "weekday", "start_time", "end_time"],
                name="unique_doctor_availability_window",
            )
        ]

    def __str__(self):
        return f"{self.doctor} — weekday {self.weekday} {self.start_time}-{self.end_time}"


class Appointment(models.Model):
    class Type(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        MISSED = "missed", "Missed"

    ALLOWED_TRANSITIONS = {
        Status.PENDING: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.COMPLETED, Status.CANCELLED, Status.MISSED},
        Status.CANCELLED: set(),
        Status.COMPLETED: set(),
        Status.MISSED: set(),
    }

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_appointments",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_appointments",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.OFFLINE)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    reason = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    cancellation_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=models.F("start_time")),
                name="appointment_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                condition=~Q(status="cancelled"),
                name="unique_active_doctor_slot",
            ),
        ]
        indexes = [
            models.Index(fields=["doctor", "date", "status"]),
            models.Index(fields=["patient", "date", "status"]),
        ]

    def transition_to(self, target_status, *, actor=None, reason="", metadata=None):
        target_status = str(target_status)
        if target_status == self.status:
            return self
        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if target_status not in allowed:
            raise ValidationError(
                f"Cannot transition appointment from {self.status} to {target_status}."
            )
        previous = self.status
        with transaction.atomic():
            self.status = target_status
            if target_status == self.Status.CANCELLED:
                self.cancellation_reason = reason or self.cancellation_reason
                fields = ["status", "cancellation_reason", "updated_at"]
            else:
                fields = ["status", "updated_at"]
            self.save(update_fields=fields)
            AppointmentStatusHistory.objects.create(
                appointment=self,
                actor=actor,
                from_status=previous,
                to_status=target_status,
                reason=reason,
                metadata=metadata or {},
            )
        return self

    def __str__(self):
        return f"{self.patient} with {self.doctor} on {self.date} {self.start_time}"


class AppointmentStatusHistory(models.Model):
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="status_history"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointment_status_changes",
    )
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20, choices=Appointment.Status.choices)
    reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["appointment", "created_at"])]

    def __str__(self):
        return f"Appointment {self.appointment_id}: {self.from_status}->{self.to_status}"
