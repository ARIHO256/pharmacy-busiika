from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from config.uploads import (
    validate_clinical_document_upload,
    validate_report_output,
)

from .models import (
    ActiveRoleContext, AmbulanceTelemetry, AmbulanceVehicle, ClinicalCode, CommunicationConsent,
    ContentEntry, DeadLetterEvent, DuplicatePatientCandidate, EnterpriseRecord, EscalationPolicy,
    EscalationStep, EventDelivery, EventSchema, FeatureConfiguration, FHIRResource, FHIRSubscription,
    ImagingStudy, IntegrationEndpoint, MasterPatientIndex, MedicationInteraction, MedicationKnowledge,
    MessageReceipt, NotificationProvider, PACSNode, PartnerApplication, PatientMerge, PayerContract,
    PresenceState, RecordsRequest, RegulatorConnector, ReplayRequest, ReportRun, ReportSchedule,
    ResourceAttachment, RoleContext, RoleDelegation, SavedReport, SecurityOperation, TariffSchedule,
    TelemedicineParticipant, TelemedicineSession, VerificationAutomation, WorkflowTransition,
)
from .schemas import schema_for


class UserMiniSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    display_name = serializers.CharField()
    role = serializers.CharField()


class RoleContextSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    is_current = serializers.BooleanField(read_only=True)

    class Meta:
        model = RoleContext
        fields = "__all__"
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = self.instance or RoleContext(**attrs)
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return attrs


class ActiveRoleContextSerializer(serializers.ModelSerializer):
    context_detail = RoleContextSerializer(source="context", read_only=True)

    class Meta:
        model = ActiveRoleContext
        fields = "__all__"
        read_only_fields = ["user", "activated_at"]


class RoleDelegationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleDelegation
        fields = "__all__"
        read_only_fields = ["approved_by", "revoked_at", "created_at"]


class WorkflowTransitionSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", read_only=True)

    class Meta:
        model = WorkflowTransition
        fields = "__all__"
        read_only_fields = ["record", "actor", "created_at"]


class ResourceAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.display_name", read_only=True)
    file = serializers.FileField(validators=[validate_clinical_document_upload])

    class Meta:
        model = ResourceAttachment
        fields = "__all__"
        read_only_fields = ["record", "checksum_sha256", "malware_status", "uploaded_by", "uploaded_at"]


class EnterpriseRecordSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    owner_name = serializers.CharField(source="owner.display_name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.display_name", read_only=True)
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    transitions = WorkflowTransitionSerializer(many=True, read_only=True)
    attachments = ResourceAttachmentSerializer(many=True, read_only=True)
    schema = serializers.SerializerMethodField()

    class Meta:
        model = EnterpriseRecord
        fields = "__all__"
        read_only_fields = ["public_id", "reference", "created_by", "updated_by", "created_at", "updated_at", "completed_at"]

    def get_schema(self, obj):
        return schema_for(obj.record_type)

    def validate(self, attrs):
        instance = self.instance or EnterpriseRecord()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return attrs


class SimpleModelSerializer(serializers.ModelSerializer):
    """Base used by the generated enterprise resource serializers."""

    def validate(self, attrs):
        instance = self.instance or self.Meta.model()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except (DjangoValidationError, AttributeError) as exc:
            if isinstance(exc, DjangoValidationError):
                raise serializers.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        return attrs


def serializer_for(model, read_only_fields=()):
    meta = type("Meta", (), {"model": model, "fields": "__all__", "read_only_fields": tuple(read_only_fields)})
    return type(f"{model.__name__}Serializer", (SimpleModelSerializer,), {"Meta": meta})


ClinicalCodeSerializer = serializer_for(ClinicalCode)
TariffScheduleSerializer = serializer_for(TariffSchedule, ("created_at",))
PayerContractSerializer = serializer_for(PayerContract, ("created_at",))
MedicationKnowledgeSerializer = serializer_for(MedicationKnowledge, ("updated_at",))
MedicationInteractionSerializer = serializer_for(MedicationInteraction)
PACSNodeSerializer = serializer_for(PACSNode, ("last_echo_at", "last_echo_ok"))
ImagingStudySerializer = serializer_for(ImagingStudy, ("created_at",))
AmbulanceVehicleSerializer = serializer_for(AmbulanceVehicle)
AmbulanceTelemetrySerializer = serializer_for(AmbulanceTelemetry)
PresenceStateSerializer = serializer_for(PresenceState)
MessageReceiptSerializer = serializer_for(MessageReceipt)
TelemedicineSessionSerializer = serializer_for(TelemedicineSession, ("public_id", "created_at"))
TelemedicineParticipantSerializer = serializer_for(TelemedicineParticipant)
NotificationProviderSerializer = serializer_for(NotificationProvider, ("last_health_check_at", "health_status"))
CommunicationConsentSerializer = serializer_for(CommunicationConsent, ("granted_at", "revoked_at"))
EscalationPolicySerializer = serializer_for(EscalationPolicy, ("created_at",))
EscalationStepSerializer = serializer_for(EscalationStep)
EventSchemaSerializer = serializer_for(EventSchema, ("created_at",))
IntegrationEndpointSerializer = serializer_for(IntegrationEndpoint, ("health_status", "last_health_check_at"))
EventDeliverySerializer = serializer_for(EventDelivery, ("attempt_count", "delivered_at", "response_code", "response_body", "created_at"))
DeadLetterEventSerializer = serializer_for(DeadLetterEvent, ("quarantined_at", "resolved_at", "resolved_by"))
ReplayRequestSerializer = serializer_for(ReplayRequest, ("status", "requested_by", "requested_at", "started_at", "completed_at", "replayed_count", "failed_count"))
class ContentEntrySerializer(SimpleModelSerializer):
    media = serializers.FileField(required=False, allow_null=True, validators=[validate_clinical_document_upload])

    class Meta:
        model = ContentEntry
        fields = "__all__"
        read_only_fields = ("published_at", "created_by", "updated_at")

FeatureConfigurationSerializer = serializer_for(FeatureConfiguration, ("updated_by", "updated_at"))
MasterPatientIndexSerializer = serializer_for(MasterPatientIndex, ("enterprise_id", "created_at", "updated_at"))
DuplicatePatientCandidateSerializer = serializer_for(DuplicatePatientCandidate, ("reviewed_by", "reviewed_at", "created_at"))
PatientMergeSerializer = serializer_for(PatientMerge, ("requested_by", "approved_by", "requested_at", "completed_at", "reversed_at"))
RecordsRequestSerializer = serializer_for(RecordsRequest, ("request_number", "requested_by", "decision_by", "created_at", "completed_at"))
FHIRResourceSerializer = serializer_for(FHIRResource, ("logical_id", "version_id", "last_updated", "created_at"))
PartnerApplicationSerializer = serializer_for(PartnerApplication, ("client_id", "created_at"))
FHIRSubscriptionSerializer = serializer_for(FHIRSubscription, ("last_delivery_at", "error_count"))
RegulatorConnectorSerializer = serializer_for(RegulatorConnector, ("last_checked_at",))
VerificationAutomationSerializer = serializer_for(VerificationAutomation, ("status", "reviewed_by", "reviewed_at", "created_at", "completed_at"))
SecurityOperationSerializer = serializer_for(SecurityOperation, ("reference", "created_at"))
SavedReportSerializer = serializer_for(SavedReport, ("created_by", "created_at", "updated_at"))
class ReportRunSerializer(SimpleModelSerializer):
    output_file = serializers.FileField(required=False, allow_null=True, validators=[validate_report_output])

    class Meta:
        model = ReportRun
        fields = "__all__"
        read_only_fields = ("status", "requested_by", "requested_at", "started_at", "completed_at", "error")

ReportScheduleSerializer = serializer_for(ReportSchedule, ("next_run_at", "last_run_at", "created_by"))
