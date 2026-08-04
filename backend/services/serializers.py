from rest_framework import serializers

from config.uploads import validate_image_upload

from .models import (
    Bed,
    CartItem,
    HospitalBooking,
    HospitalService,
    InsuranceClaim,
    InsuranceClaimItem,
    InsuranceBenefitRule,
    InsuranceEligibilityCheck,
    InsurancePreauthorization,
    InsuranceRemittance,
    InsurancePolicy,
    CriticalResultAcknowledgement,
    DispensingItem,
    DispensingRecord,
    LabOrder,
    LabTestPanel,
    LabTestPanelItem,
    LabResult,
    LabTest,
    Medicine,
    Order,
    OrderItem,
    PatientCoverage,
    PharmacyOrder,
    Supplier,
    SupplierProduct,
    SpecimenEvent,
)


def _abs_url(request, file_field):
    if not file_field:
        return None
    try:
        url = file_field.url
    except Exception:
        return None
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def _user_display(user):
    if user is None:
        return ""
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


# ---------------------------------------------------------------------------
# Provider directory (public)
# ---------------------------------------------------------------------------
class ProviderDirectorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    org_name = serializers.CharField()
    address = serializers.CharField()


# ---------------------------------------------------------------------------
# PHARMACY
# ---------------------------------------------------------------------------
class MedicineSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True, validators=[validate_image_upload])

    class Meta:
        model = Medicine
        fields = ["id", "pharmacy", "name", "description", "price", "stock", "image"]
        read_only_fields = ["id", "pharmacy"]


class CartItemSerializer(serializers.ModelSerializer):
    medicine = MedicineSerializer(read_only=True)
    medicine_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "medicine", "medicine_id", "qty"]


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "medicine", "name", "price", "qty"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    pharmacy_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "patient",
            "patient_name",
            "pharmacy",
            "pharmacy_name",
            "status",
            "total",
            "delivery",
            "address",
            "created_at",
            "items",
        ]

    def get_pharmacy_name(self, obj):
        return _user_display(obj.pharmacy)

    def get_patient_name(self, obj):
        return _user_display(obj.patient)


class PharmacyOrderSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    prescription_items = serializers.SerializerMethodField()
    dispensing_records = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyOrder
        fields = [
            "id",
            "pharmacy",
            "prescription_id",
            "patient",
            "patient_name",
            "status",
            "created_at",
            "prescription_items",
            "dispensing_records",
        ]

    def get_patient_name(self, obj):
        return _user_display(obj.patient)

    def get_dispensing_records(self, obj):
        return DispensingRecordSerializer(obj.dispensing_records.all(), many=True).data

    def get_prescription_items(self, obj):
        prescription = obj.get_prescription()
        if prescription is None:
            return []
        try:
            items = prescription.items.all()
        except Exception:
            return []
        return [
            {
                "id": getattr(it, "id", None),
                "medicine_name": getattr(it, "medicine_name", ""),
                "dosage": getattr(it, "dosage", ""),
                "frequency": getattr(it, "frequency", ""),
                "duration": getattr(it, "duration", ""),
                "quantity": getattr(it, "quantity", 0),
                "dispensed_quantity": getattr(it, "dispensed_quantity", 0),
                "instructions": getattr(it, "instructions", ""),
            }
            for it in items
        ]


class SupplierProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierProduct
        fields = ["id", "name", "qty", "price"]


class SupplierSerializer(serializers.ModelSerializer):
    products = SupplierProductSerializer(many=True, required=False)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "pharmacy",
            "suppliername",
            "contact",
            "email",
            "address",
            "supply_date",
            "products",
        ]
        read_only_fields = ["id", "pharmacy", "supply_date"]

    def create(self, validated_data):
        products = validated_data.pop("products", [])
        supplier = Supplier.objects.create(**validated_data)
        for p in products:
            SupplierProduct.objects.create(supplier=supplier, **p)
        return supplier

    def update(self, instance, validated_data):
        products = validated_data.pop("products", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if products is not None:
            instance.products.all().delete()
            for p in products:
                SupplierProduct.objects.create(supplier=instance, **p)
        return instance




class DispensingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DispensingItem
        fields = [
            "id", "prescription_item_id", "medicine_name", "prescribed_quantity",
            "dispensed_quantity", "batch_number", "expiry_date",
            "substituted_product", "label_instructions",
        ]
        read_only_fields = ["id"]


class DispensingRecordSerializer(serializers.ModelSerializer):
    pharmacist_name = serializers.SerializerMethodField()
    items = DispensingItemSerializer(many=True)

    class Meta:
        model = DispensingRecord
        fields = [
            "id", "pharmacy_order", "pharmacist", "pharmacist_name", "status",
            "clarification_note", "substitution_authorised_by",
            "counselling_notes", "dispensed_at", "created_at", "updated_at", "items",
        ]
        read_only_fields = [
            "id", "pharmacy_order", "pharmacist", "dispensed_at",
            "created_at", "updated_at",
        ]

    def get_pharmacist_name(self, obj):
        return _user_display(obj.pharmacist)

    def validate(self, attrs):
        items = attrs.get("items", [])
        status = attrs.get("status", DispensingRecord.Status.REVIEWED)
        if status in {DispensingRecord.Status.PARTIAL, DispensingRecord.Status.DISPENSED}:
            if not items or not any(item.get("dispensed_quantity", 0) > 0 for item in items):
                raise serializers.ValidationError("At least one dispensed item is required.")
        if status == DispensingRecord.Status.CLARIFICATION and not attrs.get("clarification_note", "").strip():
            raise serializers.ValidationError({"clarification_note": "Explain what requires clarification."})
        return attrs


# ---------------------------------------------------------------------------
# LAB
# ---------------------------------------------------------------------------


class LabTestPanelItemSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)

    class Meta:
        model = LabTestPanelItem
        fields = ["id", "test", "test_name", "sequence", "required"]
        read_only_fields = ["id"]


class LabTestPanelSerializer(serializers.ModelSerializer):
    items = LabTestPanelItemSerializer(many=True)
    lab_name = serializers.SerializerMethodField()

    class Meta:
        model = LabTestPanel
        fields = [
            "id", "lab", "lab_name", "name", "code", "description", "price",
            "active", "created_at", "updated_at", "items",
        ]
        read_only_fields = ["id", "lab", "created_at", "updated_at"]

    def get_lab_name(self, obj):
        return _user_display(obj.lab)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("A panel must contain at least one test.")
        test_ids = [item["test"].id for item in value]
        if len(test_ids) != len(set(test_ids)):
            raise serializers.ValidationError("A test cannot appear twice in the same panel.")
        return value

    def create(self, validated_data):
        items = validated_data.pop("items", [])
        panel = LabTestPanel.objects.create(**validated_data)
        for index, item in enumerate(items, start=1):
            item.setdefault("sequence", index)
            LabTestPanelItem.objects.create(panel=panel, **item)
        return panel

    def update(self, instance, validated_data):
        items = validated_data.pop("items", None)
        for name, value in validated_data.items():
            setattr(instance, name, value)
        instance.save()
        if items is not None:
            instance.items.all().delete()
            for index, item in enumerate(items, start=1):
                item.setdefault("sequence", index)
                LabTestPanelItem.objects.create(panel=instance, **item)
        return instance


class SpecimenEventSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SpecimenEvent
        fields = [
            "id", "order", "event_type", "barcode", "location", "notes",
            "metadata", "performed_by", "performed_by_name", "occurred_at",
        ]
        read_only_fields = ["id", "order", "performed_by", "occurred_at"]

    def get_performed_by_name(self, obj):
        return _user_display(obj.performed_by)


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ["id", "lab", "name", "description", "price", "sample_type"]
        read_only_fields = ["id", "lab"]


class LabResultSerializer(serializers.ModelSerializer):
    acknowledged = serializers.SerializerMethodField()
    acknowledged_by_name = serializers.SerializerMethodField()
    entered_by_name = serializers.SerializerMethodField()
    verified_by_name = serializers.SerializerMethodField()
    released_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LabResult
        fields = [
            "id", "order", "code_system", "code", "name", "value_numeric",
            "value_text", "unit", "reference_low", "reference_high",
            "interpretation", "status", "entered_by", "entered_by_name",
            "verified_by", "verified_by_name", "verified_at", "released_by",
            "released_by_name", "released_at", "amendment_reason",
            "acknowledged", "acknowledged_by_name", "created_at", "updated_at",
        ]
        read_only_fields = [
            "order", "entered_by", "verified_by", "verified_at", "released_by",
            "released_at", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        numeric = attrs.get("value_numeric", getattr(self.instance, "value_numeric", None))
        text = attrs.get("value_text", getattr(self.instance, "value_text", ""))
        if numeric is None and not str(text).strip():
            raise serializers.ValidationError("Provide value_numeric or value_text.")
        return attrs

    def get_entered_by_name(self, obj):
        return _user_display(obj.entered_by)

    def get_verified_by_name(self, obj):
        return _user_display(obj.verified_by)

    def get_released_by_name(self, obj):
        return _user_display(obj.released_by)

    def get_acknowledged(self, obj):
        return hasattr(obj, "acknowledgement")

    def get_acknowledged_by_name(self, obj):
        ack = getattr(obj, "acknowledgement", None)
        return _user_display(ack.acknowledged_by) if ack else None


class LabOrderSerializer(serializers.ModelSerializer):
    test_name = serializers.CharField(source="test.name", read_only=True)
    referring_doctor_name = serializers.SerializerMethodField()
    collected_by_name = serializers.SerializerMethodField()
    lab_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    result_file = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()
    has_critical_result = serializers.SerializerMethodField()
    specimen_events = SpecimenEventSerializer(many=True, read_only=True)

    class Meta:
        model = LabOrder
        fields = [
            "id", "patient", "patient_name", "lab", "lab_name", "test",
            "test_name", "referring_doctor", "referring_doctor_name",
            "referring_facility", "clinical_indication", "provisional_diagnosis",
            "priority", "specimen_id", "specimen_type", "collection_notes",
            "rejection_reason", "collected_by", "collected_by_name", "collected_at",
            "received_at", "released_at", "result_released", "prescription_id",
            "status", "result_file", "result_notes", "results",
            "has_critical_result", "specimen_events", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "patient", "lab", "test", "collected_by", "collected_at",
            "received_at", "released_at", "result_released", "created_at", "updated_at",
        ]

    def get_referring_doctor_name(self, obj):
        return _user_display(obj.referring_doctor)

    def get_collected_by_name(self, obj):
        return _user_display(obj.collected_by)

    def get_lab_name(self, obj):
        return _user_display(obj.lab)

    def get_patient_name(self, obj):
        return _user_display(obj.patient)

    def get_result_file(self, obj):
        request = self.context.get("request")
        if request is not None and getattr(request.user, "role", None) == "patient" and not obj.result_released:
            return None
        return _abs_url(request, obj.result_file)

    def get_results(self, obj):
        request = self.context.get("request")
        qs = obj.results.all()
        if request is not None and getattr(request.user, "role", None) == "patient":
            if not obj.result_released:
                return []
            qs = qs.filter(status__in=[
                LabResult.Status.FINAL,
                LabResult.Status.AMENDED,
                LabResult.Status.CORRECTED,
            ])
        return LabResultSerializer(qs, many=True).data

    def get_has_critical_result(self, obj):
        return obj.results.filter(interpretation=LabResult.Interpretation.CRITICAL).exists()


# ---------------------------------------------------------------------------
# HOSPITAL
# ---------------------------------------------------------------------------
class HospitalServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = HospitalService
        fields = ["id", "hospital", "name", "price"]
        read_only_fields = ["id", "hospital"]


class HospitalBookingSerializer(serializers.ModelSerializer):
    hospital_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = HospitalBooking
        fields = [
            "id",
            "patient",
            "patient_name",
            "hospital",
            "hospital_name",
            "service",
            "service_name",
            "date",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "patient", "hospital", "service", "created_at"]

    def get_hospital_name(self, obj):
        return _user_display(obj.hospital)

    def get_patient_name(self, obj):
        return _user_display(obj.patient)


class BedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bed
        fields = ["id", "hospital", "ward", "label", "is_occupied"]
        read_only_fields = ["id", "hospital"]


# ---------------------------------------------------------------------------
# INSURANCE
# ---------------------------------------------------------------------------
class InsurancePolicySerializer(serializers.ModelSerializer):
    benefit_rules = serializers.SerializerMethodField()

    class Meta:
        model = InsurancePolicy
        fields = [
            "id", "provider", "name", "coverage_percent", "premium", "annual_limit",
            "deductible", "copay_percent", "copay_fixed", "waiting_period_days",
            "requires_preauthorization", "network_only", "active", "description",
            "exclusions", "terms_url", "benefit_rules", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "provider"]

    def validate_coverage_percent(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Coverage percent must be between 0 and 100.")
        return value

    def validate_copay_percent(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Copay percent must be between 0 and 100.")
        return value

    def get_benefit_rules(self, obj):
        return InsuranceBenefitRuleSerializer(obj.benefit_rules.filter(active=True), many=True).data


class PatientCoverageSerializer(serializers.ModelSerializer):
    policy_name = serializers.CharField(source="policy.name", read_only=True)
    coverage_percent = serializers.IntegerField(source="policy.coverage_percent", read_only=True)
    policy_requires_preauthorization = serializers.BooleanField(source="policy.requires_preauthorization", read_only=True)
    provider_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = PatientCoverage
        fields = [
            "id",
            "patient",
            "patient_name",
            "provider",
            "provider_name",
            "policy",
            "policy_name",
            "coverage_percent",
            "policy_requires_preauthorization",
            "member_id",
            "active",
            "is_current",
            "effective_from",
            "expires_on",
            "dependant_code",
            "employer_or_group",
            "verified_at",
            "last_eligibility_check_at",
        ]
        read_only_fields = ["id", "patient", "provider", "policy", "is_current", "verified_at", "last_eligibility_check_at"]

    def get_provider_name(self, obj):
        return _user_display(obj.provider)

    def get_patient_name(self, obj):
        return _user_display(obj.patient)


class InsuranceBenefitRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceBenefitRule
        fields = [
            "id", "policy", "service_code", "service_category", "description",
            "coverage_percent", "annual_limit", "per_visit_limit", "copay_percent",
            "copay_fixed", "waiting_period_days", "requires_preauthorization",
            "excluded", "active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "policy", "created_at", "updated_at"]

    def validate_coverage_percent(self, value):
        if value is not None and not 0 <= value <= 100:
            raise serializers.ValidationError("Coverage percent must be between 0 and 100.")
        return value

    def validate_copay_percent(self, value):
        if value is not None and not 0 <= value <= 100:
            raise serializers.ValidationError("Copay percent must be between 0 and 100.")
        return value


class InsuranceEligibilityCheckSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    policy_name = serializers.CharField(source="coverage.policy.name", read_only=True)

    class Meta:
        model = InsuranceEligibilityCheck
        fields = [
            "id", "coverage", "patient", "patient_name", "provider", "member_id",
            "policy_name", "service_code", "service_category", "estimated_amount",
            "result", "coverage_percent", "covered_amount", "patient_responsibility",
            "requires_preauthorization", "reason", "response_snapshot", "requested_by",
            "checked_at",
        ]
        read_only_fields = fields

    def get_patient_name(self, obj):
        return _user_display(obj.patient)


class InsurancePreauthorizationSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    policy_name = serializers.CharField(source="policy.name", read_only=True)
    provider_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = InsurancePreauthorization
        fields = [
            "id", "authorization_number", "patient", "patient_name", "provider",
            "provider_name", "policy", "policy_name", "coverage", "requesting_facility",
            "service_code", "service_name", "clinical_indication", "diagnosis_code",
            "requested_amount", "approved_amount", "status", "decision_reason",
            "reviewed_by", "reviewed_by_name", "reviewed_at", "valid_until",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "authorization_number", "patient", "provider", "policy", "coverage",
            "status", "approved_amount", "decision_reason", "reviewed_by", "reviewed_at",
            "created_at", "updated_at",
        ]

    def get_patient_name(self, obj):
        return _user_display(obj.patient)

    def get_provider_name(self, obj):
        return _user_display(obj.provider)

    def get_reviewed_by_name(self, obj):
        return _user_display(obj.reviewed_by)


class InsuranceClaimItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsuranceClaimItem
        fields = [
            "id", "invoice_item_id", "service_code", "description", "quantity",
            "unit_price", "requested_amount", "approved_amount", "status", "reason",
        ]
        read_only_fields = ["id"]


class InsuranceRemittanceSerializer(serializers.ModelSerializer):
    claim_number = serializers.CharField(source="claim.claim_number", read_only=True)
    patient_name = serializers.CharField(source="claim.patient.display_name", read_only=True)

    class Meta:
        model = InsuranceRemittance
        fields = [
            "id", "provider", "claim", "claim_number", "patient_name",
            "remittance_number", "paid_amount", "payment_reference", "paid_on",
            "notes", "created_by", "created_at",
        ]
        read_only_fields = ["id", "provider", "created_by", "created_at"]


class InsuranceClaimSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    policy_name = serializers.CharField(source="policy.name", read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    items = InsuranceClaimItemSerializer(many=True, read_only=True)
    remittances = InsuranceRemittanceSerializer(many=True, read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            "id",
            "claim_number",
            "patient",
            "patient_name",
            "provider",
            "invoice_id",
            "invoice_number",
            "policy",
            "policy_name",
            "coverage",
            "preauthorization",
            "status",
            "amount",
            "approved_amount",
            "patient_responsibility",
            "diagnosis_code",
            "clinical_summary",
            "decision_reason",
            "requested_by",
            "reviewed_by",
            "reviewed_by_name",
            "submitted_at",
            "reviewed_at",
            "paid_at",
            "items",
            "remittances",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "claim_number", "patient", "provider", "policy", "coverage",
            "preauthorization", "status", "approved_amount", "patient_responsibility",
            "decision_reason", "requested_by", "reviewed_by", "reviewed_at", "paid_at",
            "submitted_at", "created_at", "updated_at",
        ]

    def get_patient_name(self, obj):
        return _user_display(obj.patient)

    def get_invoice_number(self, obj):
        invoice = obj.get_invoice()
        if invoice is None:
            return None
        return getattr(invoice, "number", None)

    def get_reviewed_by_name(self, obj):
        return _user_display(obj.reviewed_by)
