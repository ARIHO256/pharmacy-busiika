from rest_framework import serializers

from accounts.models import User

from .models import AuditEvent, BreakGlassAccess, Consent


class ConsentSerializer(serializers.ModelSerializer):
    granted_to_name = serializers.SerializerMethodField()
    is_current = serializers.ReadOnlyField()

    class Meta:
        model = Consent
        fields = [
            "id",
            "patient",
            "granted_to",
            "granted_to_name",
            "consent_type",
            "purpose",
            "data_categories",
            "recipient_class",
            "status",
            "source",
            "granted_at",
            "valid_from",
            "valid_until",
            "revoked_at",
            "revocation_reason",
            "version",
            "is_current",
        ]
        read_only_fields = [
            "patient",
            "status",
            "source",
            "granted_at",
            "revoked_at",
            "revocation_reason",
            "version",
        ]

    def get_granted_to_name(self, obj):
        if not obj.granted_to:
            return "Any authorised provider"
        name = f"{obj.granted_to.first_name} {obj.granted_to.last_name}".strip()
        return name or obj.granted_to.email

    def validate_granted_to(self, value):
        if value and value.role not in {
            User.Role.DOCTOR,
            User.Role.PHARMACY,
            User.Role.LAB,
            User.Role.HOSPITAL,
            User.Role.INSURANCE,
        }:
            raise serializers.ValidationError("Recipient must be a healthcare provider.")
        return value


class ConsentRevokeSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class BreakGlassSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    is_current = serializers.ReadOnlyField()

    class Meta:
        model = BreakGlassAccess
        fields = [
            "id",
            "requester",
            "requester_name",
            "patient",
            "patient_name",
            "appointment",
            "reason",
            "status",
            "started_at",
            "expires_at",
            "ended_at",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "is_current",
        ]
        read_only_fields = [
            "requester",
            "status",
            "started_at",
            "ended_at",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
        ]

    def _name(self, user):
        name = f"{user.first_name} {user.last_name}".strip()
        return name or user.email

    def get_requester_name(self, obj):
        return self._name(obj.requester)

    def get_patient_name(self, obj):
        return self._name(obj.patient)

    def validate_patient(self, value):
        if value.role != User.Role.PATIENT:
            raise serializers.ValidationError("Emergency access target must be a patient.")
        return value

    def validate_reason(self, value):
        if len(value.strip()) < 15:
            raise serializers.ValidationError(
                "Provide a specific emergency reason of at least 15 characters."
            )
        return value.strip()


class BreakGlassReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class AuditEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = "__all__"

    def _name(self, user):
        if not user:
            return None
        name = f"{user.first_name} {user.last_name}".strip()
        return name or user.email

    def get_actor_name(self, obj):
        return self._name(obj.actor)

    def get_patient_name(self, obj):
        return self._name(obj.patient)
