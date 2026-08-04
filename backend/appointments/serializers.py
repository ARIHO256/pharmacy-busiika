from django.contrib.auth import get_user_model
from rest_framework import serializers

from accounts.roles import BOOKABLE_PROVIDER_ROLES

from .models import Appointment, AppointmentStatusHistory, Availability

User = get_user_model()


def _full_name(user):
    if not user:
        return ""
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


def _doctor_specialization(doctor):
    """Read specialization from accounts.DoctorProfile without hard dependency."""
    profile = getattr(doctor, "doctor_profile", None)
    if profile is not None:
        return getattr(profile, "specialization", "") or ""
    staff = getattr(doctor, "staff_profile", None)
    return getattr(staff, "specialty", "") or ""


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Availability
        fields = [
            "id",
            "doctor",
            "weekday",
            "start_time",
            "end_time",
            "slot_minutes",
            "breaks",
            "holidays",
            "is_active",
        ]
        read_only_fields = ["doctor"]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"detail": "end_time must be after start_time"}
            )
        slot_minutes = attrs.get(
            "slot_minutes", getattr(self.instance, "slot_minutes", 30)
        )
        if slot_minutes is not None and slot_minutes <= 0:
            raise serializers.ValidationError(
                {"detail": "slot_minutes must be positive"}
            )
        return attrs




class AppointmentStatusHistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AppointmentStatusHistory
        fields = ["id", "actor", "actor_name", "from_status", "to_status", "reason", "metadata", "created_at"]

    def get_actor_name(self, obj):
        if not obj.actor:
            return None
        return _full_name(obj.actor)


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    doctor_specialization = serializers.SerializerMethodField()
    status_history = AppointmentStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient",
            "doctor",
            "booked_by",
            "patient_name",
            "doctor_name",
            "doctor_specialization",
            "date",
            "start_time",
            "end_time",
            "type",
            "status",
            "reason",
            "notes",
            "cancellation_reason",
            "created_at",
            "updated_at",
            "status_history",
        ]
        read_only_fields = fields

    def get_patient_name(self, obj):
        return _full_name(obj.patient)

    def get_doctor_name(self, obj):
        return _full_name(obj.doctor)

    def get_doctor_specialization(self, obj):
        return _doctor_specialization(obj.doctor)


class AppointmentCreateSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    patient_id = serializers.IntegerField(required=False)
    date = serializers.DateField()
    start_time = serializers.TimeField()
    type = serializers.ChoiceField(
        choices=Appointment.Type.choices, default=Appointment.Type.OFFLINE
    )
    reason = serializers.CharField(
        required=False, allow_blank=True, default=""
    )
    consent_acknowledged = serializers.BooleanField(write_only=True)

    def validate_consent_acknowledged(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Treatment data-access consent must be acknowledged to book."
            )
        return value

    def validate_doctor_id(self, value):
        try:
            doctor = User.objects.get(pk=value, role__in=BOOKABLE_PROVIDER_ROLES)
        except User.DoesNotExist:
            raise serializers.ValidationError("Bookable healthcare professional not found")
        return doctor
