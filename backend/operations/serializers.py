from rest_framework import serializers

from config.uploads import validate_clinical_document_upload

from .models import (
    AccountSubscription, Admission, AdmissionTransfer, Announcement, BedAllocation,
    ClinicalRound, Complaint, DischargeSummary, FacilityBed, ImagingOrder, ImagingReport,
    InventoryBatch, InventoryItem, PurchaseOrder, PurchaseOrderItem, StockMovement,
    SubscriptionPlan, SupportTicket, Ward, WardTask,
)


def user_name(user):
    return user.display_name if user else ""


class WardSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    beds_total = serializers.IntegerField(source="beds.count", read_only=True)
    beds_available = serializers.SerializerMethodField()

    class Meta:
        model = Ward
        fields = "__all__"
        read_only_fields = ["organization", "created_at"]

    def get_beds_available(self, obj):
        return obj.beds.filter(status=FacilityBed.Status.AVAILABLE, active=True).count()


class FacilityBedSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="ward.name", read_only=True)

    class Meta:
        model = FacilityBed
        fields = "__all__"


class BedAllocationSerializer(serializers.ModelSerializer):
    bed_label = serializers.CharField(source="bed.label", read_only=True)
    ward_name = serializers.CharField(source="bed.ward.name", read_only=True)

    class Meta:
        model = BedAllocation
        fields = "__all__"
        read_only_fields = ["assigned_by", "assigned_at", "released_at"]


class AdmissionSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    patient_email = serializers.EmailField(source="patient.email", read_only=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    admitting_clinician_name = serializers.SerializerMethodField()
    attending_clinician_name = serializers.SerializerMethodField()
    current_bed = serializers.SerializerMethodField()
    open_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Admission
        fields = "__all__"
        read_only_fields = ["admission_number", "organization", "created_by", "created_at", "updated_at", "discharged_at"]

    def get_admitting_clinician_name(self, obj):
        return user_name(obj.admitting_clinician)

    def get_attending_clinician_name(self, obj):
        return user_name(obj.attending_clinician)

    def get_current_bed(self, obj):
        row = obj.bed_allocations.filter(released_at__isnull=True).select_related("bed__ward").first()
        return {"id": row.bed_id, "label": row.bed.label, "ward": row.bed.ward.name} if row else None

    def get_open_tasks(self, obj):
        return obj.tasks.exclude(status__in=[WardTask.Status.COMPLETED, WardTask.Status.CANCELLED]).count()


class AdmissionTransferSerializer(serializers.ModelSerializer):
    from_ward_name = serializers.CharField(source="from_ward.name", read_only=True)
    to_ward_name = serializers.CharField(source="to_ward.name", read_only=True)

    class Meta:
        model = AdmissionTransfer
        fields = "__all__"
        read_only_fields = ["requested_by", "transferred_at"]


class WardTaskSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="admission.patient.display_name", read_only=True)
    admission_number = serializers.CharField(source="admission.admission_number", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = WardTask
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "completed_by", "completed_at"]

    def get_assigned_to_name(self, obj):
        return user_name(obj.assigned_to)


class ClinicalRoundSerializer(serializers.ModelSerializer):
    clinician_name = serializers.CharField(source="clinician.display_name", read_only=True)
    patient_name = serializers.CharField(source="admission.patient.display_name", read_only=True)

    class Meta:
        model = ClinicalRound
        fields = "__all__"
        read_only_fields = ["clinician", "recorded_at"]


class DischargeSummarySerializer(serializers.ModelSerializer):
    clinician_name = serializers.CharField(source="clinician.display_name", read_only=True)
    patient_name = serializers.CharField(source="admission.patient.display_name", read_only=True)

    class Meta:
        model = DischargeSummary
        fields = "__all__"
        read_only_fields = ["clinician", "finalized_at", "created_at", "updated_at"]


class ImagingReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True)
    report_file = serializers.FileField(required=False, allow_null=True, validators=[validate_clinical_document_upload])
    verified_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ImagingReport
        fields = "__all__"
        read_only_fields = ["created_by", "verified_by", "verified_at", "released_at", "created_at", "updated_at"]

    def get_verified_by_name(self, obj):
        return user_name(obj.verified_by)


class ImagingOrderSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    ordering_clinician_name = serializers.SerializerMethodField()
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    report = ImagingReportSerializer(read_only=True)

    class Meta:
        model = ImagingOrder
        fields = "__all__"
        read_only_fields = ["order_number", "organization", "ordering_clinician", "created_at", "updated_at"]

    def get_ordering_clinician_name(self, obj):
        return user_name(obj.ordering_clinician)


class InventoryItemSerializer(serializers.ModelSerializer):
    quantity_on_hand = serializers.IntegerField(read_only=True)
    low_stock = serializers.SerializerMethodField()
    expiring_batches = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = "__all__"
        read_only_fields = ["organization", "created_at"]

    def get_low_stock(self, obj):
        return obj.quantity_on_hand <= obj.reorder_level

    def get_expiring_batches(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        return obj.batches.filter(expiry_date__isnull=False, expiry_date__lte=timezone.localdate() + timedelta(days=90), quantity_available__gt=0).count()


class InventoryBatchSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    sku = serializers.CharField(source="item.sku", read_only=True)

    class Meta:
        model = InventoryBatch
        fields = "__all__"


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="batch.item.name", read_only=True)
    batch_number = serializers.CharField(source="batch.batch_number", read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = StockMovement
        fields = "__all__"
        read_only_fields = ["balance_after", "created_by", "created_at"]

    def get_created_by_name(self, obj):
        return user_name(obj.created_by)


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"
        read_only_fields = ["purchase_order"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    total_amount = serializers.IntegerField(read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = "__all__"
        read_only_fields = ["number", "organization", "created_by", "approved_by", "approved_at", "created_at", "updated_at"]

    def get_created_by_name(self, obj):
        return user_name(obj.created_by)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"


class AccountSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = AccountSubscription
        fields = "__all__"
        read_only_fields = ["user", "organization", "provider_reference", "cancelled_at", "created_at"]

    def get_owner_name(self, obj):
        if obj.organization_id:
            return obj.organization.legal_name
        return user_name(obj.user)


class SupportTicketSerializer(serializers.ModelSerializer):
    requester_name = serializers.CharField(source="requester.display_name", read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = "__all__"
        read_only_fields = ["number", "requester", "organization", "assigned_to", "created_at", "updated_at"]

    def get_assigned_to_name(self, obj):
        return user_name(obj.assigned_to)


class ComplaintSerializer(serializers.ModelSerializer):
    complainant_name = serializers.CharField(source="complainant.display_name", read_only=True)
    against_user_name = serializers.SerializerMethodField()
    handled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = "__all__"
        read_only_fields = ["complainant", "status", "resolution_notes", "handled_by", "created_at", "updated_at"]

    def get_against_user_name(self, obj):
        return user_name(obj.against_user)

    def get_handled_by_name(self, obj):
        return user_name(obj.handled_by)


class AnnouncementSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)

    class Meta:
        model = Announcement
        fields = "__all__"
        read_only_fields = ["organization", "created_by", "created_at"]


from .models import (
    AmbulanceDispatch, EmergencyCase, LeaveRequest, MaternityEpisode,
    PrivacyRequest, QualityIncident, StaffShift, SurgicalCase, SurgicalChecklist,
)


def _user_name(user):
    if not user:
        return None
    return getattr(user, "display_name", None) or user.email


class EmergencyCaseSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    clinician_name = serializers.SerializerMethodField()

    class Meta:
        model = EmergencyCase
        fields = "__all__"
        read_only_fields = ["case_number", "organization", "created_by", "arrival_at", "treatment_started_at", "closed_at", "created_at", "updated_at"]

    def get_patient_name(self, obj):
        return _user_name(obj.patient)

    def get_clinician_name(self, obj):
        return _user_name(obj.assigned_clinician)


class AmbulanceDispatchSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    dispatcher_name = serializers.SerializerMethodField()
    paramedic_name = serializers.SerializerMethodField()

    class Meta:
        model = AmbulanceDispatch
        fields = "__all__"
        read_only_fields = ["dispatch_number", "organization", "dispatcher", "requested_at", "dispatched_at", "arrived_scene_at", "completed_at", "created_at", "updated_at"]

    def get_patient_name(self, obj):
        return _user_name(obj.patient)

    def get_dispatcher_name(self, obj):
        return _user_name(obj.dispatcher)

    def get_paramedic_name(self, obj):
        return _user_name(obj.paramedic)


class SurgicalChecklistSerializer(serializers.ModelSerializer):
    completion_percent = serializers.IntegerField(read_only=True)
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SurgicalChecklist
        fields = "__all__"
        read_only_fields = ["surgical_case", "completed_by", "updated_at", "completion_percent"]

    def get_completed_by_name(self, obj):
        return _user_name(obj.completed_by)


class SurgicalCaseSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    surgeon_name = serializers.SerializerMethodField()
    anaesthetist_name = serializers.SerializerMethodField()
    theatre_nurse_name = serializers.SerializerMethodField()
    checklist = SurgicalChecklistSerializer(read_only=True)

    class Meta:
        model = SurgicalCase
        fields = "__all__"
        read_only_fields = ["case_number", "organization", "created_by", "actual_start", "actual_end", "created_at", "updated_at"]

    def get_patient_name(self, obj):
        return _user_name(obj.patient)

    def get_surgeon_name(self, obj):
        return _user_name(obj.surgeon)

    def get_anaesthetist_name(self, obj):
        return _user_name(obj.anaesthetist)

    def get_theatre_nurse_name(self, obj):
        return _user_name(obj.theatre_nurse)


class MaternityEpisodeSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    midwife_name = serializers.SerializerMethodField()
    clinician_name = serializers.SerializerMethodField()

    class Meta:
        model = MaternityEpisode
        fields = "__all__"
        read_only_fields = ["episode_number", "organization", "created_by", "labour_started_at", "delivered_at", "created_at", "updated_at"]

    def get_patient_name(self, obj):
        return _user_name(obj.patient)

    def get_midwife_name(self, obj):
        return _user_name(obj.assigned_midwife)

    def get_clinician_name(self, obj):
        return _user_name(obj.assigned_clinician)


class StaffShiftSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = StaffShift
        fields = "__all__"
        read_only_fields = ["organization", "created_by", "created_at", "updated_at"]

    def get_staff_name(self, obj):
        return _user_name(obj.staff)

    def validate(self, attrs):
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "Shift must end after it starts."})
        return attrs


class LeaveRequestSerializer(serializers.ModelSerializer):
    staff_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = "__all__"
        read_only_fields = ["organization", "reviewed_by", "reviewed_at", "created_at"]

    def get_staff_name(self, obj):
        return _user_name(obj.staff)

    def get_reviewed_by_name(self, obj):
        return _user_name(obj.reviewed_by)

    def validate(self, attrs):
        starts_on = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends_on = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts_on and ends_on and ends_on < starts_on:
            raise serializers.ValidationError({"ends_on": "Leave must end on or after its start date."})
        return attrs


class QualityIncidentSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = QualityIncident
        fields = "__all__"
        read_only_fields = ["incident_number", "organization", "reported_by", "closed_at", "created_at", "updated_at"]

    def get_patient_name(self, obj):
        return _user_name(obj.patient)

    def get_reporter_name(self, obj):
        return _user_name(obj.reported_by)

    def get_assignee_name(self, obj):
        return _user_name(obj.assigned_to)


class PrivacyRequestSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    assignee_name = serializers.SerializerMethodField()

    class Meta:
        model = PrivacyRequest
        fields = "__all__"
        read_only_fields = ["request_number", "organization", "requester", "completed_at", "created_at", "updated_at"]

    def get_requester_name(self, obj):
        return _user_name(obj.requester) or obj.requester_email

    def get_assignee_name(self, obj):
        return _user_name(obj.assigned_to)
