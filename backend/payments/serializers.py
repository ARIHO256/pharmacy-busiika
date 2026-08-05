from rest_framework import serializers

from accounts.models import User
from appointments.models import Appointment

from .models import (
    CashierShift,
    CommissionRule,
    Invoice,
    InvoiceItem,
    PaymentTransaction,
    Payout,
    Receipt,
    Subscription,
    WalletTransaction,
)


def _display_name(user):
    if user is None:
        return None
    name = f"{user.first_name} {user.last_name}".strip()
    return name or user.email


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "code",
            "description",
            "quantity",
            "unit_price",
            "discount_amount",
            "line_total",
            "service_type",
            "source_id",
            "created_at",
        ]
        read_only_fields = ["id", "line_total", "created_at"]


class PaymentTransactionSerializer(serializers.ModelSerializer):
    received_by_name = serializers.SerializerMethodField()
    receipt_number = serializers.CharField(source="receipt.number", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "number",
            "invoice",
            "amount",
            "method",
            "reference",
            "status",
            "received_by",
            "received_by_name",
            "notes",
            "receipt_number",
            "created_at",
            "confirmed_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "invoice",
            "status",
            "received_by",
            "created_at",
            "confirmed_at",
            "receipt_number",
        ]

    def get_received_by_name(self, obj):
        return _display_name(obj.received_by)


class InvoiceSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    appointment_info = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    issued_by_name = serializers.SerializerMethodField()
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentTransactionSerializer(many=True, read_only=True)
    paid_amount = serializers.IntegerField(read_only=True)
    balance = serializers.IntegerField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "patient",
            "patient_name",
            "organization",
            "organization_name",
            "appointment",
            "appointment_info",
            "issued_by",
            "issued_by_name",
            "amount",
            "discount_amount",
            "tax_amount",
            "currency",
            "status",
            "gateway",
            "gateway_ref",
            "notes",
            "due_at",
            "items",
            "payments",
            "paid_amount",
            "balance",
            "created_at",
            "updated_at",
            "paid_at",
        ]
        read_only_fields = [
            "id",
            "number",
            "organization",
            "issued_by",
            "amount",
            "status",
            "gateway_ref",
            "created_at",
            "updated_at",
            "paid_at",
        ]

    def get_patient_name(self, obj):
        return _display_name(obj.patient)

    def get_issued_by_name(self, obj):
        return _display_name(obj.issued_by)

    def get_appointment_info(self, obj):
        appointment = obj.appointment
        if appointment is None:
            return None
        return {
            "id": appointment.id,
            "doctor_name": _display_name(appointment.doctor),
            "date": appointment.date,
            "start_time": appointment.start_time,
            "status": appointment.status,
        }


class CashierInvoiceCreateSerializer(serializers.Serializer):
    patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=User.Role.PATIENT))
    appointment = serializers.PrimaryKeyRelatedField(
        queryset=Appointment.objects.all(),
        required=False,
        allow_null=True,
    )
    discount_amount = serializers.IntegerField(required=False, min_value=0, default=0)
    tax_amount = serializers.IntegerField(required=False, min_value=0, default=0)
    currency = serializers.CharField(max_length=3, required=False, default="UGX")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    due_at = serializers.DateTimeField(required=False, allow_null=True)
    items = InvoiceItemSerializer(many=True, min_length=1)

    def validate(self, attrs):
        appointment = attrs.get("appointment")
        patient = attrs["patient"]
        if appointment and appointment.patient_id != patient.id:
            raise serializers.ValidationError({"appointment": "Appointment belongs to another patient."})
        return attrs


class ReceiptSerializer(serializers.ModelSerializer):
    payment = PaymentTransactionSerializer(read_only=True)
    invoice_number = serializers.CharField(source="payment.invoice.number", read_only=True)
    patient_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="payment.invoice.organization.legal_name", read_only=True)
    issued_by_name = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    balance = serializers.IntegerField(source="payment.invoice.balance", read_only=True)
    currency = serializers.CharField(source="payment.invoice.currency", read_only=True)

    class Meta:
        model = Receipt
        fields = [
            "id",
            "number",
            "payment",
            "invoice_number",
            "patient_name",
            "organization_name",
            "issued_by_name",
            "items",
            "balance",
            "currency",
            "created_at",
        ]

    def get_patient_name(self, obj):
        return _display_name(obj.payment.invoice.patient)

    def get_issued_by_name(self, obj):
        return _display_name(obj.issued_by)

    def get_items(self, obj):
        return InvoiceItemSerializer(obj.payment.invoice.items.all(), many=True).data


class CashierShiftSerializer(serializers.ModelSerializer):
    cashier_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)

    class Meta:
        model = CashierShift
        fields = [
            "id",
            "cashier",
            "cashier_name",
            "organization",
            "organization_name",
            "opening_float",
            "expected_cash",
            "closing_cash",
            "variance",
            "status",
            "opened_at",
            "closed_at",
            "notes",
        ]
        read_only_fields = [
            "cashier",
            "organization",
            "expected_cash",
            "variance",
            "status",
            "opened_at",
            "closed_at",
        ]

    def get_cashier_name(self, obj):
        return _display_name(obj.cashier)


class PayoutSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Payout
        fields = [
            "id",
            "doctor",
            "doctor_name",
            "amount",
            "status",
            "method",
            "account_number",
            "account_name",
            "reference",
            "notes",
            "processed_by",
            "processed_by_name",
            "processed_at",
            "created_at",
        ]
        read_only_fields = ["id", "doctor", "status", "reference", "processed_by", "processed_at", "created_at"]

    def get_doctor_name(self, obj):
        return _display_name(obj.doctor)

    def get_processed_by_name(self, obj):
        return _display_name(obj.processed_by)


class WalletTransactionSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            "id",
            "direction",
            "kind",
            "amount",
            "invoice",
            "invoice_number",
            "reference",
            "created_at",
        ]
        read_only_fields = fields


class CommissionRuleSerializer(serializers.ModelSerializer):
    doctor_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)

    class Meta:
        model = CommissionRule
        fields = [
            "id",
            "doctor",
            "doctor_name",
            "organization",
            "organization_name",
            "rate",
            "active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_doctor_name(self, obj):
        return _display_name(obj.doctor)

    def validate(self, attrs):
        doctor = attrs.get("doctor", getattr(self.instance, "doctor", None))
        organization = attrs.get("organization", getattr(self.instance, "organization", None))
        if not doctor and not organization:
            raise serializers.ValidationError("A commission rule targets a doctor or an organization.")
        rate = attrs.get("rate", getattr(self.instance, "rate", None))
        if rate is not None and not (0 <= rate < 1):
            raise serializers.ValidationError({"rate": "Rate must be between 0 and 1 (exclusive)."})
        return attrs


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "user", "plan", "active", "started_at", "expires_at"]


from .models import InvoiceAdjustment, RefundRequest


class InvoiceAdjustmentSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.display_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.display_name", read_only=True)

    class Meta:
        model = InvoiceAdjustment
        fields = "__all__"
        read_only_fields = ["number", "requested_by", "approved_by", "approved_at", "created_at"]


class RefundRequestSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source="requested_by.display_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.display_name", read_only=True)
    invoice_number = serializers.CharField(source="payment.invoice.number", read_only=True)

    class Meta:
        model = RefundRequest
        fields = "__all__"
        read_only_fields = ["number", "requested_by", "approved_by", "approved_at", "completed_at", "gateway_reference", "error", "created_at"]
