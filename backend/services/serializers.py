from rest_framework import serializers

from .models import (
    Bed,
    CartItem,
    HospitalBooking,
    HospitalService,
    InsuranceClaim,
    InsurancePolicy,
    CriticalResultAcknowledgement,
    LabOrder,
    LabResult,
    LabTest,
    Medicine,
    MedicineTaxonomyNode,
    Order,
    OrderItem,
    PatientCoverage,
    PharmacyOrder,
    Supplier,
    SupplierProduct,
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
    parent_facility_name = serializers.CharField(required=False)
    parent_facility_type = serializers.CharField(required=False)

    id = serializers.IntegerField()
    org_name = serializers.CharField()
    address = serializers.CharField()


# ---------------------------------------------------------------------------
# PHARMACY
# ---------------------------------------------------------------------------
class MedicineSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    available_online = serializers.SerializerMethodField()
    taxonomy_node = serializers.PrimaryKeyRelatedField(
        queryset=MedicineTaxonomyNode.objects.filter(
            level=MedicineTaxonomyNode.Level.SUBCATEGORY,
            parent__level=MedicineTaxonomyNode.Level.CATEGORY,
            parent__parent__level=MedicineTaxonomyNode.Level.FAMILY,
        ),
        required=False, allow_null=True,
    )

    class Meta:
        model = Medicine
        fields = ["id", "pharmacy", "name", "description", "price", "stock", "image", "sale_type", "taxonomy_node", "product_attributes", "available_online"]
        read_only_fields = ["id", "pharmacy"]

    def get_available_online(self, obj):
        from operations.services import online_orderable_batches
        return online_orderable_batches(obj).filter(quantity__gt=0).exists()

    def validate_catalogue_attributes(self, attrs):
        from .taxonomy import attribute_fields, is_archived

        previous = getattr(self.instance, "taxonomy_node_id", None)
        node = attrs.get("taxonomy_node", getattr(self.instance, "taxonomy_node", None))
        node_id = node.pk if node else None
        pharmacy_id = self.context.get("pharmacy_id", getattr(self.instance, "pharmacy_id", None))
        if node_id != previous and node:
            if node.pharmacy_id not in (None, pharmacy_id) or is_archived(node, pharmacy_id):
                raise serializers.ValidationError({"taxonomy_node": "Select an active subcategory from your pharmacy catalogue."})
        if "product_attributes" not in attrs:
            if node_id != previous:
                attrs["product_attributes"] = {}
            return

        data = attrs["product_attributes"]
        if not isinstance(data, dict):
            raise serializers.ValidationError({"product_attributes": "Provide an object of catalogue field values."})
        definitions = {field["key"]: field for field in attribute_fields(node)}
        clean = {}
        errors = {}
        for key, value in data.items():
            field = definitions.get(key)
            if field is None:
                errors[key] = "This field does not belong to the selected subcategory."
                continue
            if value in (None, ""):
                continue
            if field["type"] == "integer":
                validator = serializers.IntegerField(min_value=field["min"], max_value=1000000)
            else:
                validator = serializers.CharField(max_length=250)
                if not isinstance(value, str):
                    errors[key] = "Enter text."
                    continue
                if not value.strip():
                    continue
            try:
                clean[key] = validator.run_validation(value)
            except serializers.ValidationError as error:
                errors[key] = error.detail
        if errors:
            raise serializers.ValidationError({"product_attributes": errors})
        attrs["product_attributes"] = clean

    def validate(self, attrs):
        self.validate_catalogue_attributes(attrs)
        if "sale_type" in attrs:
            from operations.access import require_role
            require_role(self.context["request"].user, {"pharmacy", "pharmacist", "facility_manager"})
            if self.instance and attrs["sale_type"] == "otc" and self.instance.batches.filter(controlled=True).exists():
                raise serializers.ValidationError({"sale_type": "A product with controlled batch history cannot be classified OTC."})
        if attrs.get("price", 0) < 0 or attrs.get("stock", 0) < 0:
            raise serializers.ValidationError("Price and stock cannot be negative.")
        if self.instance and self.instance.batches.exists() and "stock" in attrs:
            current = self._available_stock(self.instance)
            if attrs["stock"] != current:
                raise serializers.ValidationError({"stock": "Batch-tracked stock must be changed through audited batch movements."})
        return attrs

    def _available_stock(self, obj):
        from django.db.models import Sum
        from django.utils import timezone
        return obj.batches.filter(status="available", expires_on__gt=timezone.localdate()).aggregate(total=Sum("quantity"))["total"] or 0

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.batches.exists():
            data["stock"] = self._available_stock(instance)
        return data


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
    payment_recorded = serializers.SerializerMethodField()
    pharmacy_name = serializers.SerializerMethodField()
    dispensed_batches = serializers.SerializerMethodField()
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
            "payment_recorded",
            "delivery",
            "address",
            "handed_over_at",
            "created_at",
            "items",
            "dispensed_batches",
        ]

    def get_payment_recorded(self, obj):
        return obj.invoice_id is not None

    def get_dispensed_batches(self, obj):
        request = self.context.get("request")
        if obj.status != "delivered" or not request or request.user.role != "pharmacist":
            return []
        return [{
            "id": movement.pk, "medicine": movement.batch.medicine.name,
            "batch": movement.batch.batch_number, "quantity": -movement.quantity,
        } for movement in obj.stock_movements.filter(kind="dispensed").select_related("batch__medicine")]

    def get_pharmacy_name(self, obj):
        return _user_display(obj.pharmacy)

    def get_patient_name(self, obj):
        return _user_display(obj.patient) if obj.patient_id else "Walk-in customer"


class PharmacyOrderSerializer(serializers.ModelSerializer):
    pharmacy_name = serializers.CharField(source="pharmacy.display_name")
    patient_name = serializers.SerializerMethodField()
    prescription_items = serializers.SerializerMethodField()
    prescription_status = serializers.SerializerMethodField()
    reversible_dispenses = serializers.SerializerMethodField()
    review = serializers.SerializerMethodField()
    substitutions = serializers.SerializerMethodField()
    dispensed_batches = serializers.SerializerMethodField()

    class Meta:
        model = PharmacyOrder
        fields = [
            "id",
            "pharmacy",
            "prescription_id",
            "pharmacy_name",
            "patient",
            "patient_name",
            "status",
            "created_at",
            "prescription_items",
            "prescription_status",
            "reversible_dispenses",
            "handed_over_at",
            "review",
            "substitutions",
            "dispensed_batches",
        ]

    def get_review(self, obj):
        if not hasattr(obj, "safety_review") or not obj.safety_review.prescription_version:
            return None
        review = obj.safety_review
        return {"notes": review.notes, "counselling": review.counselling, "medication_check": review.medication_check,
                "product_ids": review.product_ids}

    def get_substitutions(self, obj):
        from .pharmacy_prescription_views import SubstitutionSerializer
        return SubstitutionSerializer(obj.substitutions.select_related("replacement", "item"), many=True).data

    def get_dispensed_batches(self, obj):
        return [{
            "id": movement.pk, "item": movement.prescription_item_id,
            "medicine": movement.batch.medicine.name, "batch": movement.batch.batch_number,
            "quantity": -movement.quantity, "dispensed_at": movement.occurred_at,
        } for movement in obj.dispensing_movements.filter(kind="dispensed", reversal__isnull=True).select_related("batch__medicine")]

    def get_patient_name(self, obj):
        return _user_display(obj.patient)

    def get_reversible_dispenses(self, obj):
        request = self.context.get("request")
        if obj.status != PharmacyOrder.Status.PREPARED or not request or request.user.role != "pharmacist":
            return []
        return [{
            "id": movement.pk, "medicine": movement.batch.medicine.name, "batch": movement.batch.batch_number,
            "quantity": -movement.quantity, "controlled": movement.batch.controlled,
        } for movement in obj.dispensing_movements.filter(kind="dispensed", reversal__isnull=True).select_related("batch__medicine")]

    def get_prescription_status(self, obj):
        prescription = obj.get_prescription()
        return prescription.status if prescription else None

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
                "id": it.pk,
                "dispensed_quantity": it.dispensed_quantity,
                "medicine_name": getattr(it, "medicine_name", ""),
                "dosage": getattr(it, "dosage", ""),
                "frequency": getattr(it, "frequency", ""),
                "duration": getattr(it, "duration", ""),
                "route": it.route,
                "instructions": it.instructions,
                "quantity": getattr(it, "quantity", 0),
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
            "qualification_reference",
            "qualified_until",
            "contact",
            "email",
            "address",
            "supply_date",
            "products",
        ]
        read_only_fields = ["id", "pharmacy", "supply_date"]

    def validate(self, attrs):
        reference = attrs.get("qualification_reference", getattr(self.instance, "qualification_reference", ""))
        expiry = attrs.get("qualified_until", getattr(self.instance, "qualified_until", None))
        if bool(reference) != bool(expiry):
            raise serializers.ValidationError("Provide both the qualification reference and expiry date.")
        if "qualification_reference" in attrs or "qualified_until" in attrs:
            from operations.access import require_role
            require_role(self.context["request"].user, {"pharmacy", "pharmacist", "facility_manager"})
        return attrs

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


# ---------------------------------------------------------------------------
# LAB
# ---------------------------------------------------------------------------
class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ["id", "lab", "name", "description", "price", "sample_type"]
        read_only_fields = ["id", "lab"]


class LabResultSerializer(serializers.ModelSerializer):
    is_superseded = serializers.SerializerMethodField()
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
            "released_by_name", "released_at", "escalated_at", "amendment_reason", "supersedes", "is_superseded",
            "acknowledged", "acknowledged_by_name", "created_at", "updated_at",
        ]
        read_only_fields = [
            "order", "entered_by", "verified_by", "verified_at", "released_by",
            "released_at", "escalated_at", "created_at", "updated_at",
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

    def get_is_superseded(self, obj):
        return hasattr(obj, "replacement")

    def get_acknowledged(self, obj):
        return hasattr(obj, "acknowledgement")

    def get_acknowledged_by_name(self, obj):
        ack = getattr(obj, "acknowledgement", None)
        return _user_display(ack.acknowledged_by) if ack else None


class LabOrderSerializer(serializers.ModelSerializer):
    visit_number = serializers.CharField(source="visit.visit_number", read_only=True, default=None)
    test_name = serializers.CharField(source="test.name", read_only=True)
    referring_doctor_name = serializers.SerializerMethodField()
    collected_by_name = serializers.SerializerMethodField()
    lab_name = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    result_file = serializers.SerializerMethodField()
    results = serializers.SerializerMethodField()
    has_critical_result = serializers.SerializerMethodField()
    critical_review_pending = serializers.SerializerMethodField()

    class Meta:
        model = LabOrder
        fields = [
            "id", "visit", "visit_number", "arrived_at", "patient", "patient_name", "lab", "lab_name", "test",
            "test_name", "referring_doctor", "referring_doctor_name",
            "referring_facility", "clinical_indication", "provisional_diagnosis",
            "priority", "specimen_id", "specimen_type", "collection_notes",
            "rejection_reason", "collected_by", "collected_by_name", "collected_at",
            "received_at", "released_at", "result_released", "prescription_id",
            "status", "result_file", "result_notes", "results",
            "has_critical_result", "critical_review_pending", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "visit", "arrived_at", "patient", "lab", "test", "collected_by", "collected_at",
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
        return obj.results.filter(interpretation=LabResult.Interpretation.CRITICAL, released_at__isnull=False, replacement__isnull=True).exists()

    def get_critical_review_pending(self, obj):
        return obj.results.filter(
            interpretation=LabResult.Interpretation.CRITICAL,
            released_at__isnull=False, replacement__isnull=True, acknowledgement__isnull=True,
        ).exists()


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
    class Meta:
        model = InsurancePolicy
        fields = ["id", "provider", "name", "coverage_percent", "premium", "description"]
        read_only_fields = ["id", "provider"]


class PatientCoverageSerializer(serializers.ModelSerializer):
    policy_name = serializers.CharField(source="policy.name", read_only=True)
    coverage_percent = serializers.IntegerField(source="policy.coverage_percent", read_only=True)
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
            "member_id",
            "active",
        ]
        read_only_fields = ["id", "patient", "provider", "policy"]

    def get_provider_name(self, obj):
        return _user_display(obj.provider)

    def get_patient_name(self, obj):
        return _user_display(obj.patient)


class InsuranceClaimSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()
    policy_name = serializers.CharField(source="policy.name", read_only=True)

    class Meta:
        model = InsuranceClaim
        fields = [
            "id",
            "patient",
            "patient_name",
            "provider",
            "invoice_id",
            "invoice_number",
            "policy",
            "policy_name",
            "status",
            "amount",
            "created_at",
        ]
        read_only_fields = ["id", "patient", "provider", "policy", "created_at"]

    def get_patient_name(self, obj):
        return _user_display(obj.patient)

    def get_invoice_number(self, obj):
        invoice = obj.get_invoice()
        if invoice is None:
            return None
        return getattr(invoice, "number", None)
