from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from clinical.models import Observation
from prescriptions.models import PrescriptionItem
from workforce.models import NursingNote, PatientVisit

from . import models as m
from .access import clinician_at, patient_is_valid, require_patient_access


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: "Unknown field." for key in unknown})
        return super().to_internal_value(data)


class VersionAction(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    action = serializers.CharField(max_length=30)
    bed = serializers.IntegerField(min_value=1, required=False)
    summary = serializers.CharField(required=False, max_length=20000)
    follow_up = serializers.CharField(required=False, max_length=10000, allow_blank=True)


class Transition(StrictSerializer):
    status = serializers.CharField(max_length=30)
    notes = serializers.CharField(required=False, default="", max_length=20000, allow_blank=True)


class ModelSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        # Reject attempts to bypass workflow actions with read-only state fields.
        for key in self.Meta.read_only_fields:
            if key in self.initial_data:
                raise serializers.ValidationError({key: "This field is managed by the server."})
        return attrs


COMMON_READ_ONLY = ("id", "created_at", "updated_at", "created_by")


def serializer_for(model, readonly=(), exclude=()):
    meta = type("Meta", (), {"model": model, "exclude": exclude, "read_only_fields": COMMON_READ_ONLY + tuple(readonly)})
    return type(f"{model.__name__}Serializer", (ModelSerializer,), {"Meta": meta})


class AdmissionSerializer(serializer_for(m.Admission, ("status", "discharged_at", "discharge_summary", "follow_up", "version"))):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("admitted_at", timezone.now()) > timezone.now():
            raise serializers.ValidationError("Admission time cannot be in the future.")
        return attrs


class MedicationScheduleSerializer(serializer_for(m.MedicationSchedule, ("status", "administered_by", "administered_at", "notes"))):
    patient_name = serializers.CharField(source="admission.patient.display_name", read_only=True)
    def validate(self, attrs):
        attrs = super().validate(attrs)
        admission, prescription = attrs["admission"], attrs["prescription"]
        actor = self.context["request"].user
        clinician_at(actor, attrs["organization"])
        if actor.role not in {"doctor", "admin"}:
            raise serializers.ValidationError("Only a doctor can prescribe scheduled doses.")
        if admission.organization_id != attrs["organization"].pk or admission.status != "admitted":
            raise serializers.ValidationError("An active admission in this facility is required.")
        if prescription.patient_id != admission.patient_id or prescription.status not in {"issued", "partially_dispensed", "dispensed"} or prescription.expires_at <= timezone.now():
            raise serializers.ValidationError("A valid prescription for this patient is required.")
        if not prescription.items.filter(medicine_name__iexact=attrs["medication_name"], dosage=attrs["dose"], route=attrs["route"]).exists():
            raise serializers.ValidationError("Medication, dose and route must match a signed prescription item.")
        return attrs


class ProcedureSerializer(serializer_for(m.ProcedureBooking, ("status", "notes"))):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    def validate(self, attrs):
        attrs = super().validate(attrs)
        patient_is_valid(attrs["patient"])
        clinician_at(attrs["surgeon"], attrs["organization"])
        if attrs["surgeon"].role != "doctor":
            raise serializers.ValidationError("Surgeon must be a doctor.")
        if attrs["ends_at"] <= attrs["starts_at"] or attrs["starts_at"] <= timezone.now():
            raise serializers.ValidationError("A future start and later end are required.")
        if attrs.get("admission") and (attrs["admission"].patient_id != attrs["patient"].pk or attrs["admission"].organization_id != attrs["organization"].pk or attrs["admission"].status != "admitted"):
            raise serializers.ValidationError("Admission does not match this patient/facility.")
        return attrs


class BatchSerializer(serializer_for(m.MedicineBatch, ("quantity", "status"))):
    medicine_name = serializers.CharField(source="medicine.name", read_only=True)
    opening_quantity = serializers.IntegerField(min_value=0, max_value=2147483647, required=False, write_only=True)
    opening_packs = serializers.IntegerField(min_value=0, max_value=2147483647, required=False, write_only=True)
    opening_witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, write_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        organization = attrs["organization"]
        if organization.owner_id != attrs["medicine"].pharmacy_id or organization.organization_type != "pharmacy":
            raise serializers.ValidationError("Medicine belongs to a different pharmacy.")
        if attrs.get("supplier") and attrs["supplier"].pharmacy_id != organization.owner_id:
            raise serializers.ValidationError("Supplier belongs to a different pharmacy.")
        if attrs["expires_on"] <= timezone.localdate():
            raise serializers.ValidationError("New stock must have a future expiry date.")
        if attrs.get("opening_witness") and not ((attrs.get("opening_quantity") or attrs.get("opening_packs")) and attrs.get("controlled")):
            raise serializers.ValidationError("A witness is only needed when recording opening stock for a controlled batch.")
        low, high = attrs.get("min_temperature"), attrs.get("max_temperature")
        if (low is None) != (high is None) or low is not None and low >= high:
            raise serializers.ValidationError("Both temperature limits are required, with minimum below maximum.")
        return attrs


class MovementInput(StrictSerializer):
    packs = serializers.BooleanField(required=False, default=False)
    prescription_item = serializers.PrimaryKeyRelatedField(queryset=PrescriptionItem.objects.all(), required=False)
    quantity = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=["received", "dispensed", "returned", "adjusted", "destroyed"])
    reason = serializers.CharField(max_length=2000)
    reference = serializers.UUIDField()
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role="patient"), required=False, allow_null=True)
    witness = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)


class BatchAction(StrictSerializer):
    action = serializers.ChoiceField(choices=["recall", "quarantine", "release", "temperature"])
    reason = serializers.CharField(max_length=2000, required=False, default="", allow_blank=True)
    temperature = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)

    def validate(self, attrs):
        if attrs["action"] == "temperature" and "temperature" not in attrs:
            raise serializers.ValidationError("temperature is required.")
        return attrs


class RouteSerializer(serializer_for(m.ReferralRoute, ("outcome", "version", "assigned_to", "scheduled_at"))):
    status = serializers.CharField(source="referral.status", read_only=True)
    patient_name = serializers.CharField(source="referral.patient.display_name", read_only=True)
    specialty = serializers.CharField(source="referral.target_specialty", read_only=True)
    reason = serializers.CharField(source="referral.reason", read_only=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        referral = attrs["referral"]
        actor = self.context["request"].user
        if actor.pk != referral.referring_provider_id and actor.role != "admin":
            raise serializers.ValidationError("Only the referring provider can route this referral.")
        require_patient_access(actor, referral.patient)
        if referral.status != "sent" or attrs["organization"].status != "verified":
            raise serializers.ValidationError("A sent referral and verified receiving organization are required.")
        return attrs


class ReferralTransition(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=["accepted", "declined", "in_progress", "completed", "cancelled"])
    outcome = serializers.CharField(required=False, default="", max_length=20000, allow_blank=True)
    scheduled_at = serializers.DateTimeField(required=False)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role="doctor", is_verified=True), required=False)


class BenefitSerializer(serializer_for(m.BenefitRule)):
    coverage_percent = serializers.IntegerField(min_value=0, max_value=100)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["policy"].provider_id != attrs["organization"].owner_id:
            raise serializers.ValidationError("Policy belongs to a different insurer.")
        return attrs


class AuthorizationSerializer(serializer_for(m.Preauthorization, ("approved_amount", "status", "reason", "decided_by"))):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        coverage = attrs["coverage"]
        if coverage.provider_id != attrs["organization"].owner_id or coverage.policy.provider_id != coverage.provider_id or not coverage.active:
            raise serializers.ValidationError("Active coverage from this insurer is required.")
        if attrs["expires_on"] < timezone.localdate() or attrs["requested_amount"] <= 0:
            raise serializers.ValidationError("A positive amount and current/future expiry are required.")
        return attrs


class AuthorizationDecision(StrictSerializer):
    status = serializers.ChoiceField(choices=["approved", "rejected"])
    approved_amount = serializers.IntegerField(min_value=0, default=0)
    reason = serializers.CharField(max_length=2000)


class AssessmentSerializer(serializer_for(m.ClaimAssessment, ("covered_amount", "patient_amount", "decision", "rule_snapshot", "reason"))):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        claim = attrs["claim"]
        if claim.provider_id != attrs["organization"].owner_id or claim.policy.provider_id != claim.provider_id or claim.amount <= 0:
            raise serializers.ValidationError("A positive claim belonging to this insurer is required.")
        auth = attrs.get("authorization")
        if auth and (auth.organization_id != attrs["organization"].pk or auth.coverage.patient_id != claim.patient_id or auth.coverage.policy_id != claim.policy_id):
            raise serializers.ValidationError("Authorization does not match the claim.")
        return attrs


class ImagingSerializer(serializer_for(m.ImagingOrder, ("accession_number", "study_uid", "status", "scheduled_at", "report", "reported_by", "reported_at", "version"))):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    def validate(self, attrs):
        attrs = super().validate(attrs)
        actor = self.context["request"].user
        patient_is_valid(attrs["patient"])
        if attrs["referring_doctor"] != actor and actor.role != "admin":
            raise serializers.ValidationError("Referring doctor must be the requesting clinician.")
        require_patient_access(actor, attrs["patient"])
        return attrs


class ImagingTransition(StrictSerializer):
    version = serializers.IntegerField(min_value=1)
    status = serializers.ChoiceField(choices=["scheduled", "acquired", "reported", "cancelled"])
    study_uid = serializers.CharField(required=False, max_length=64)
    report = serializers.CharField(required=False, max_length=30000)
    scheduled_at = serializers.DateTimeField(required=False)


class OfflineObservationSerializer(StrictSerializer):
    category = serializers.ChoiceField(choices=Observation.Category.choices)
    display = serializers.CharField(max_length=250)
    code = serializers.CharField(max_length=80, required=False, default="", allow_blank=True)
    code_system = serializers.CharField(max_length=100, required=False, default="local")
    value_numeric = serializers.DecimalField(max_digits=12, decimal_places=3, required=False)
    value_text = serializers.CharField(max_length=500, required=False, allow_blank=True)
    unit = serializers.CharField(max_length=50, required=False, allow_blank=True)
    observed_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["observed_at"] > timezone.now():
            raise serializers.ValidationError("Observation time cannot be in the future.")
        if "value_numeric" not in attrs and not attrs.get("value_text"):
            raise serializers.ValidationError("An observation value is required.")
        return attrs


class OfflineNoteSerializer(StrictSerializer):
    visit = serializers.PrimaryKeyRelatedField(queryset=PatientVisit.objects.all())
    note_type = serializers.ChoiceField(choices=NursingNote.Type.choices)
    note = serializers.CharField(max_length=20000)


class OfflineInput(StrictSerializer):
    change_id = serializers.UUIDField()
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role="patient"))
    kind = serializers.ChoiceField(choices=["observation", "nursing_note"])
    payload = serializers.JSONField()

    def validate(self, attrs):
        serializer = (OfflineObservationSerializer if attrs["kind"] == "observation" else OfflineNoteSerializer)(data=attrs["payload"])
        serializer.is_valid(raise_exception=True)
        return attrs
