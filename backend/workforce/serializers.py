from datetime import date

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import DoctorProfile, StaffProfile, User
from accounts.roles import FACILITY_OPERATIONS_ROLES

from .models import (
    Department,
    MedicationAdministration,
    NursingNote,
    PatientVisit,
    StaffInvitation,
    StaffMembership,
    TriageRecord,
)


def display_name(user):
    return user.display_name if user else None


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "organization", "location", "name", "code", "description", "active", "created_at"]
        read_only_fields = ["organization", "created_at"]


class StaffMembershipSerializer(serializers.ModelSerializer):
    custom_role_name = serializers.CharField(source="custom_role.name", read_only=True, default=None)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_phone = serializers.CharField(source="user.phone", read_only=True)
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = StaffMembership
        fields = [
            "id", "user", "user_name", "user_email", "user_phone", "organization",
            "organization_name", "department", "department_name", "role", "job_title", "custom_role", "custom_role_name",
            "employee_number", "status", "is_primary", "starts_on", "ends_on",
            "verification_status", "created_at", "updated_at",
        ]
        read_only_fields = ["user", "organization", "created_at", "updated_at"]

    def get_user_name(self, obj):
        return display_name(obj.user)

    def get_verification_status(self, obj):
        if obj.user.role == "doctor":
            return getattr(getattr(obj.user, "doctor_profile", None), "status", "pending")
        return getattr(getattr(obj.user, "staff_profile", None), "status", "not_required")


class StaffInvitationSerializer(serializers.ModelSerializer):
    custom_role_name = serializers.CharField(source="custom_role.name", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    invitation_url = serializers.SerializerMethodField()

    class Meta:
        model = StaffInvitation
        fields = [
            "id", "token", "organization", "organization_name", "department", "department_name",
            "email", "phone", "first_name", "last_name", "role", "job_title",
            "employee_number", "custom_role", "custom_role_name", "status", "expires_at", "accepted_at", "created_at",
            "invitation_url",
        ]
        read_only_fields = [
            "token", "organization", "status", "expires_at", "accepted_at", "created_at",
            "invitation_url",
        ]

    def validate_role(self, value):
        if value not in FACILITY_OPERATIONS_ROLES:
            raise serializers.ValidationError("Unsupported facility role.")
        return value

    def get_invitation_url(self, obj):
        request = self.context.get("request")
        path = f"/accept-invitation/{obj.token}"
        return request.build_absolute_uri(path) if request else path


class InvitationAcceptSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, min_length=10, trim_whitespace=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    university = serializers.CharField(max_length=220, required=False, allow_blank=True)
    year_of_completion = serializers.IntegerField(required=False, min_value=1950, max_value=2100)
    qualification = serializers.CharField(max_length=220, required=False, allow_blank=True)
    registration_number = serializers.CharField(max_length=140, required=False, allow_blank=True)
    license_issuer = serializers.CharField(max_length=180, required=False, allow_blank=True)
    license_expires_on = serializers.DateField(required=False, allow_null=True)
    license_document = serializers.FileField(required=False, allow_null=True)

    def validate_license_document(self, value):
        if not value:
            return value
        allowed = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
        content_type = getattr(value, "content_type", "")
        if content_type and content_type not in allowed:
            raise serializers.ValidationError(
                "Licence document must be a JPG, PNG, WEBP or PDF file."
            )
        if getattr(value, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Licence document cannot exceed 10 MB.")
        return value

    def validate_license_expires_on(self, value):
        if value and value <= date.today():
            raise serializers.ValidationError("A current practising licence is required.")
        return value

    def validate(self, attrs):
        invitation = self.context["invitation"]
        candidate = User(
            email=invitation.email,
            first_name=attrs.get("first_name") or invitation.first_name,
            last_name=attrs.get("last_name") or invitation.last_name,
            role=invitation.role,
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        first_name = (attrs.get("first_name") or invitation.first_name or "").strip()
        last_name = (attrs.get("last_name") or invitation.last_name or "").strip()
        if not first_name or not last_name:
            raise serializers.ValidationError(
                {"first_name": "The staff member's full legal name is required."}
            )
        if invitation.role in {"doctor", "nurse", "pharmacist", "lab_technician"}:
            for field in ["registration_number", "license_document"]:
                if not attrs.get(field):
                    raise serializers.ValidationError({field: "Professional licence information is required."})
            number = attrs.get("registration_number", "").strip()
            duplicate_doctor = DoctorProfile.objects.filter(
                license_number__iexact=number
            ).exists()
            duplicate_staff = StaffProfile.objects.filter(
                registration_number__iexact=number
            ).exists()
            if number and (duplicate_doctor or duplicate_staff):
                raise serializers.ValidationError(
                    {"registration_number": "This professional registration number is already in use."}
                )
        return attrs


class PatientVisitSerializer(serializers.ModelSerializer):
    laboratory_handoffs = serializers.SerializerMethodField()
    admission = serializers.SerializerMethodField()

    def get_admission(self, obj):
        admissions = sorted(obj.admissions.all(), key=lambda row: row.admitted_at, reverse=True)
        record = next((row for row in admissions if row.status == "admitted"), admissions[0] if admissions else None)
        if record:
            return {"id": record.pk, "status": record.status, "bed": str(record.bed) if record.bed else None}
        return None

    def get_laboratory_handoffs(self, obj):
        return [{
            "id": order.pk, "destination": order.lab.display_name,
            "status": order.status, "arrived_at": order.arrived_at,
        } for order in obj.lab_orders.all()]

    patient_name = serializers.SerializerMethodField()
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    patient_phone = serializers.CharField(source="patient.phone", read_only=True)
    assigned_doctor_name = serializers.SerializerMethodField()
    assigned_nurse_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    triage_level = serializers.CharField(source="triage.level", read_only=True)

    class Meta:
        model = PatientVisit
        fields = [
            "id", "visit_number", "queue_number", "organization", "organization_name",
            "location", "patient", "patient_name", "patient_email", "patient_phone",
            "appointment", "registered_by", "assigned_doctor", "assigned_doctor_name",
            "assigned_nurse", "assigned_nurse_name", "visit_type", "status", "priority",
            "reason", "triage_level", "checked_in_at", "checked_out_at", "updated_at", "laboratory_handoffs", "admission",
        ]
        read_only_fields = [
            "visit_number", "queue_number", "organization", "registered_by", "checked_in_at",
            "checked_out_at", "updated_at",
        ]

    def get_patient_name(self, obj):
        return display_name(obj.patient)

    def get_assigned_doctor_name(self, obj):
        return display_name(obj.assigned_doctor)

    def get_assigned_nurse_name(self, obj):
        return display_name(obj.assigned_nurse)


class TriageRecordSerializer(serializers.ModelSerializer):
    nurse_name = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source="visit.patient.display_name", read_only=True)
    visit_number = serializers.CharField(source="visit.visit_number", read_only=True)

    class Meta:
        model = TriageRecord
        fields = "__all__"
        read_only_fields = ["nurse", "recorded_at", "updated_at"]

    def get_nurse_name(self, obj):
        return display_name(obj.nurse)

    def validate_pain_score(self, value):
        if value is not None and value > 10:
            raise serializers.ValidationError("Pain score must be between 0 and 10.")
        return value

    def validate_oxygen_saturation(self, value):
        if value is not None and value > 100:
            raise serializers.ValidationError("Oxygen saturation cannot exceed 100%.")
        return value


class NursingHandoverSerializer(serializers.Serializer):
    situation = serializers.CharField(max_length=2000)
    background = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    assessment = serializers.CharField(max_length=2000)
    next_actions = serializers.CharField(max_length=2000)


class NursingNoteSerializer(serializers.ModelSerializer):
    handover = serializers.JSONField(required=False)
    nurse_name = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source="visit.patient.display_name", read_only=True)
    visit_number = serializers.CharField(source="visit.visit_number", read_only=True)

    class Meta:
        model = NursingNote
        fields = ["id", "visit", "visit_number", "patient_name", "nurse", "nurse_name", "note_type", "note", "handover", "recorded_at"]
        read_only_fields = ["nurse", "recorded_at"]

    def validate(self, attrs):
        if attrs.get("handover") and attrs.get("note_type") != NursingNote.Type.HANDOVER:
            raise serializers.ValidationError({"handover": "Structured fields require a handover note."})
        if "handover" in attrs:
            structured = NursingHandoverSerializer(data=attrs["handover"])
            structured.is_valid(raise_exception=True)
            attrs["handover"] = dict(structured.validated_data)
        return attrs

    def get_nurse_name(self, obj):
        return display_name(obj.nurse)


class MedicationAdministrationSerializer(serializers.ModelSerializer):
    nurse_name = serializers.SerializerMethodField()
    patient_name = serializers.CharField(source="visit.patient.display_name", read_only=True)
    visit_number = serializers.CharField(source="visit.visit_number", read_only=True)

    class Meta:
        model = MedicationAdministration
        fields = "__all__"
        read_only_fields = ["nurse"]

    def get_nurse_name(self, obj):
        return display_name(obj.nurse)
