from rest_framework import serializers

from .models import Review


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["rating", "comment"]


class ReviewPublicSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "patient", "rating", "comment", "created_at"]

    def get_patient(self, obj):
        return obj.patient.first_name or obj.patient.email


class ReviewAdminSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "patient", "patient_name", "doctor", "doctor_name",
            "appointment", "rating", "comment", "status",
            "moderated_by", "moderated_at", "moderation_note", "created_at",
        ]

    def get_patient_name(self, obj):
        full = f"{obj.patient.first_name} {obj.patient.last_name}".strip()
        return full or obj.patient.email

    def get_doctor_name(self, obj):
        full = f"{obj.doctor.first_name} {obj.doctor.last_name}".strip()
        return full or obj.doctor.email
