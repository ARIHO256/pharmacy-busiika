from rest_framework import serializers

from .models import (
    Allergy,
    CarePlan,
    ClinicalEncounter,
    Condition,
    EncounterRevision,
    MedicationStatement,
    Observation,
    Referral,
)


class EncounterRevisionSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = EncounterRevision
        fields = ["id", "version", "snapshot", "reason", "author", "author_name", "created_at"]

    def get_author_name(self, obj):
        if not obj.author:
            return None
        return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.email


class ClinicalEncounterSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    revisions = EncounterRevisionSerializer(many=True, read_only=True)

    class Meta:
        model = ClinicalEncounter
        fields = [
            "id",
            "appointment",
            "patient",
            "patient_name",
            "doctor",
            "doctor_name",
            "status",
            "chief_complaint",
            "history_of_present_illness",
            "examination",
            "assessment",
            "treatment_plan",
            "safety_net_advice",
            "telemedicine_limitations",
            "follow_up_date",
            "version",
            "signed_at",
            "created_at",
            "updated_at",
            "revisions",
        ]
        read_only_fields = [
            "patient",
            "doctor",
            "status",
            "version",
            "signed_at",
            "created_at",
            "updated_at",
            "revisions",
        ]

    def _name(self, user):
        return f"{user.first_name} {user.last_name}".strip() or user.email

    def get_patient_name(self, obj):
        return self._name(obj.patient)

    def get_doctor_name(self, obj):
        return self._name(obj.doctor)


class AllergySerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Allergy
        fields = "__all__"
        read_only_fields = ["patient", "recorded_by", "verification", "created_at", "updated_at"]

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return None
        return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip() or obj.recorded_by.email


class ConditionSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Condition
        fields = "__all__"
        read_only_fields = ["patient", "recorded_by", "verification", "created_at", "updated_at"]

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return None
        return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip() or obj.recorded_by.email


class MedicationStatementSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = MedicationStatement
        fields = "__all__"
        read_only_fields = ["patient", "recorded_by", "source", "created_at", "updated_at"]

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return None
        return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip() or obj.recorded_by.email


class ObservationSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Observation
        fields = "__all__"
        read_only_fields = ["patient", "recorded_by", "created_at"]

    def validate(self, attrs):
        numeric = attrs.get("value_numeric", getattr(self.instance, "value_numeric", None))
        text = attrs.get("value_text", getattr(self.instance, "value_text", ""))
        if numeric is None and not str(text).strip():
            raise serializers.ValidationError("Provide value_numeric or value_text.")
        return attrs

    def get_recorded_by_name(self, obj):
        if not obj.recorded_by:
            return None
        return f"{obj.recorded_by.first_name} {obj.recorded_by.last_name}".strip() or obj.recorded_by.email


class ReferralSerializer(serializers.ModelSerializer):
    provider_name = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = "__all__"
        read_only_fields = ["patient", "referring_provider", "created_at", "updated_at"]

    def get_provider_name(self, obj):
        user = obj.referring_provider
        return f"{user.first_name} {user.last_name}".strip() or user.email


class CarePlanSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = CarePlan
        fields = "__all__"
        read_only_fields = ["patient", "author", "created_at", "updated_at"]

    def get_author_name(self, obj):
        return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.email


class EncounterAmendSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=10, max_length=1000)
    chief_complaint = serializers.CharField(required=False, allow_blank=True)
    history_of_present_illness = serializers.CharField(required=False, allow_blank=True)
    examination = serializers.CharField(required=False, allow_blank=True)
    assessment = serializers.CharField(required=False, allow_blank=True)
    treatment_plan = serializers.CharField(required=False, allow_blank=True)
    safety_net_advice = serializers.CharField(required=False, allow_blank=True)
    telemedicine_limitations = serializers.CharField(required=False, allow_blank=True)
    follow_up_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        clinical_fields = set(attrs) - {"reason"}
        if not clinical_fields:
            raise serializers.ValidationError("Provide at least one clinical field to amend.")
        attrs["reason"] = attrs["reason"].strip()
        return attrs
