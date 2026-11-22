from datetime import timedelta

from django.conf import settings
from django.db import models
import uuid
from django.utils import timezone


def default_expiry():
    return timezone.now() + timedelta(days=30)


class Prescription(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIALLY_DISPENSED = "partially_dispensed", "Partially dispensed"
        DISPENSED = "dispensed", "Dispensed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    number = models.CharField(max_length=24, unique=True, blank=True)
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="prescriptions", null=True, blank=True,
    )
    visit = models.ForeignKey("workforce.PatientVisit", on_delete=models.PROTECT, null=True, blank=True, related_name="prescriptions")
    encounter = models.ForeignKey(
        "clinical.ClinicalEncounter",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prescriptions",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prescriptions_given",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="prescriptions_received",
    )
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.ISSUED
    )
    version = models.PositiveIntegerField(default=1)
    signed_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(default=default_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["patient", "status", "created_at"]),
            models.Index(fields=["doctor", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = f"RX-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} ({self.status})"


class PrescriptionItem(models.Model):
    prescription = models.ForeignKey(
        Prescription, on_delete=models.CASCADE, related_name="items"
    )
    medicine_name = models.CharField(max_length=200)
    generic_name = models.CharField(max_length=200, blank=True, default="")
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    route = models.CharField(max_length=100, blank=True, default="oral")
    duration = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    refills_allowed = models.PositiveSmallIntegerField(default=0)
    dispensed_quantity = models.PositiveIntegerField(default=0)
    instructions = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.medicine_name} x{self.quantity}"
