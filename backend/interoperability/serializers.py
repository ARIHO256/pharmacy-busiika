from rest_framework import serializers

from .models import ConceptMapping, OutboxEvent, TerminologyConcept


class TerminologyConceptSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerminologyConcept
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class ConceptMappingSerializer(serializers.ModelSerializer):
    source_display = serializers.CharField(source="source.display", read_only=True)
    target_display = serializers.CharField(source="target.display", read_only=True)

    class Meta:
        model = ConceptMapping
        fields = "__all__"
        read_only_fields = ["approved", "approved_by", "created_at"]


class OutboxEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)

    class Meta:
        model = OutboxEvent
        fields = [
            "id", "event_id", "event_type", "event_version",
            "aggregate_type", "aggregate_id", "actor", "actor_email",
            "patient", "patient_email", "correlation_id", "causation_id",
            "payload", "status", "attempts", "occurred_at",
            "next_attempt_at", "published_at", "last_error",
        ]
        read_only_fields = fields
