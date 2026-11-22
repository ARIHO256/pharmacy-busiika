from rest_framework import serializers

from .models import Prescription, PrescriptionItem


class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = [
            "id",
            "medicine_name",
            "generic_name",
            "dosage",
            "frequency",
            "route",
            "duration",
            "quantity",
            "refills_allowed",
            "dispensed_quantity",
            "instructions",
        ]


class PrescriptionItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = [
            "medicine_name",
            "generic_name",
            "dosage",
            "frequency",
            "route",
            "duration",
            "quantity",
            "refills_allowed",
            "instructions",
        ]
        extra_kwargs = {
            "generic_name": {"required": False},
            "route": {"required": False},
            "refills_allowed": {"required": False},
            "instructions": {"required": False},
        }


class PrescriptionCreateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    encounter_id = serializers.IntegerField(required=False, allow_null=True)
    items = PrescriptionItemWriteSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("at least one item is required")
        names = [item["medicine_name"].strip().lower() for item in value]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Duplicate medicines are not allowed.")
        return value


def _name(user):
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.email


class PrescriptionListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            "id",
            "number",
            "appointment",
            "visit",
            "encounter",
            "doctor",
            "doctor_name",
            "patient",
            "patient_name",
            "notes",
            "status",
            "version",
            "signed_at",
            "expires_at",
            "item_count",
            "created_at",
        ]

    def get_doctor_name(self, obj):
        return _name(obj.doctor)

    def get_patient_name(self, obj):
        return _name(obj.patient)

    def get_item_count(self, obj):
        return obj.items.count()


class PrescriptionDetailSerializer(PrescriptionListSerializer):
    items = PrescriptionItemSerializer(many=True, read_only=True)

    class Meta(PrescriptionListSerializer.Meta):
        fields = PrescriptionListSerializer.Meta.fields + ["items"]
