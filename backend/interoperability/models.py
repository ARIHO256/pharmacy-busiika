import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

AUTH_USER = settings.AUTH_USER_MODEL


class TerminologyConcept(models.Model):
    """Versioned local or standard clinical concept.

    The system URI and code are preserved exactly as received.  Mappings can be
    added without replacing the source concept, protecting clinical provenance.
    """

    system = models.CharField(max_length=300)
    version = models.CharField(max_length=80, blank=True, default="")
    code = models.CharField(max_length=120)
    display = models.CharField(max_length=300)
    category = models.CharField(max_length=80, blank=True, default="")
    aliases = models.JSONField(default=list, blank=True)
    definition = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["system", "display"]
        constraints = [
            models.UniqueConstraint(
                fields=["system", "version", "code"], name="unique_terminology_concept"
            )
        ]
        indexes = [
            models.Index(fields=["system", "code"]),
            models.Index(fields=["category", "active"]),
        ]

    def __str__(self):
        return f"{self.system}|{self.code} — {self.display}"


class ConceptMapping(models.Model):
    class Relationship(models.TextChoices):
        EQUIVALENT = "equivalent", "Equivalent"
        BROADER = "broader", "Broader"
        NARROWER = "narrower", "Narrower"
        RELATED = "related", "Related"
        UNMATCHED = "unmatched", "No reliable match"

    source = models.ForeignKey(
        TerminologyConcept, on_delete=models.CASCADE, related_name="outgoing_mappings"
    )
    target = models.ForeignKey(
        TerminologyConcept, on_delete=models.CASCADE, related_name="incoming_mappings"
    )
    relationship = models.CharField(
        max_length=20, choices=Relationship.choices, default=Relationship.EQUIVALENT
    )
    mapping_version = models.CharField(max_length=80, blank=True, default="")
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_concept_mappings",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target", "mapping_version"],
                name="unique_concept_mapping_version",
            ),
            models.CheckConstraint(
                condition=~models.Q(source=models.F("target")),
                name="concept_mapping_source_not_target",
            ),
        ]

    def __str__(self):
        return f"{self.source} {self.relationship} {self.target}"


class OutboxEvent(models.Model):
    """Transactional integration event awaiting delivery to external systems."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"
        DEAD_LETTER = "dead_letter", "Dead letter"

    event_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    event_type = models.CharField(max_length=160)
    event_version = models.PositiveIntegerField(default=1)
    aggregate_type = models.CharField(max_length=100)
    aggregate_id = models.CharField(max_length=120)
    actor = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emitted_platform_events",
    )
    patient = models.ForeignKey(
        AUTH_USER,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_platform_events",
    )
    correlation_id = models.CharField(max_length=120, blank=True, default="")
    causation_id = models.CharField(max_length=120, blank=True, default="")
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveIntegerField(default=0)
    occurred_at = models.DateTimeField(auto_now_add=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["occurred_at"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at", "occurred_at"]),
            models.Index(fields=["aggregate_type", "aggregate_id"]),
            models.Index(fields=["event_type", "occurred_at"]),
            models.Index(fields=["patient", "occurred_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} {self.event_id} ({self.status})"
