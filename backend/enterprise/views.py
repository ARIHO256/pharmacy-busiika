from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import request_role

from .access import (
    EnterpriseAuthenticated, EnterpriseResourcePermission, PlatformAdminOnly,
    active_context_for, active_organization, active_role, can_manage_org,
    can_manage_platform, record_queryset_for,
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
from .schemas import public_schema_catalog, schema_for, transition_for
from .serializers import (
    ActiveRoleContextSerializer, AmbulanceTelemetrySerializer, AmbulanceVehicleSerializer,
    ClinicalCodeSerializer, CommunicationConsentSerializer, ContentEntrySerializer,
    DeadLetterEventSerializer, DuplicatePatientCandidateSerializer, EnterpriseRecordSerializer,
    EscalationPolicySerializer, EscalationStepSerializer, EventDeliverySerializer,
    EventSchemaSerializer, FeatureConfigurationSerializer, FHIRResourceSerializer,
    FHIRSubscriptionSerializer, ImagingStudySerializer, IntegrationEndpointSerializer,
    MasterPatientIndexSerializer, MedicationInteractionSerializer, MedicationKnowledgeSerializer,
    MessageReceiptSerializer, NotificationProviderSerializer, PACSNodeSerializer,
    PartnerApplicationSerializer, PatientMergeSerializer, PayerContractSerializer,
    PresenceStateSerializer, RecordsRequestSerializer, RegulatorConnectorSerializer,
    ReplayRequestSerializer, ReportRunSerializer, ReportScheduleSerializer,
    ResourceAttachmentSerializer, RoleContextSerializer, RoleDelegationSerializer,
    SavedReportSerializer, SecurityOperationSerializer, TariffScheduleSerializer,
    TelemedicineParticipantSerializer, TelemedicineSessionSerializer,
    VerificationAutomationSerializer,
)


def audit(request, action_name, resource, metadata=None, patient=None):
    try:
        from governance.services import audit as governance_audit
        governance_audit(
            actor=request.user,
            action=action_name,
            resource=resource,
            patient=patient,
            metadata=metadata or {},
            request=request,
        )
    except Exception:
        pass
    try:
        from interoperability.services import emit_event
        emit_event(
            action_name,
            resource,
            metadata or {"id": resource.pk},
            actor=request.user,
            patient=patient,
            request=request,
        )
    except Exception:
        pass


class SchemaCatalogView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request):
        role = active_role(request.user)
        catalog = public_schema_catalog()
        if not can_manage_platform(request.user):
            catalog = {key: value for key, value in catalog.items() if role in value.get("roles", [])}
        return Response({"active_role": role, "schemas": catalog})


class EnterpriseSummaryView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request):
        queryset = record_queryset_for(request.user, EnterpriseRecord.objects.all())
        domain_counts = list(queryset.values("domain").annotate(total=Count("id")).order_by("domain"))
        status_counts = list(queryset.values("status").annotate(total=Count("id")).order_by("status"))
        due = timezone.now()
        return Response({
            "active_context": RoleContextSerializer(active_context_for(request.user)).data if active_context_for(request.user) else None,
            "domains": domain_counts,
            "statuses": status_counts,
            "overdue": queryset.filter(due_at__lt=due).exclude(status__in=["completed", "cancelled", "closed", "resolved"]).count(),
            "critical": queryset.filter(priority="critical").exclude(status__in=["completed", "cancelled", "closed", "resolved"]).count(),
            "assigned_to_me": queryset.filter(assigned_to=request.user).exclude(status__in=["completed", "cancelled", "closed", "resolved"]).count(),
            "recent": EnterpriseRecordSerializer(queryset[:12], many=True).data,
        })


class RoleContextViewSet(viewsets.ModelViewSet):
    serializer_class = RoleContextSerializer
    permission_classes = [EnterpriseAuthenticated]
    queryset = RoleContext.objects.select_related("user", "organization", "location", "department", "created_by")
    filterset_fields = ["user", "organization", "location", "department", "role_code", "active"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if can_manage_platform(self.request.user):
            return queryset
        org = active_organization(self.request.user)
        return queryset.filter(Q(user=self.request.user) | Q(organization=org)).distinct() if org else queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        organization = serializer.validated_data.get("organization")
        if serializer.validated_data.get("user") != self.request.user and not can_manage_org(self.request.user, organization):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot create role contexts outside your managed organization.")
        obj = serializer.save(created_by=self.request.user)
        audit(self.request, "role_context.created", obj)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        context = self.get_object()
        if context.user_id != request.user.id:
            return Response({"detail": "You can activate only your own role context."}, status=status.HTTP_403_FORBIDDEN)
        if not context.is_current:
            return Response({"detail": "This context is inactive or expired."}, status=status.HTTP_409_CONFLICT)
        active, _ = ActiveRoleContext.objects.update_or_create(user=request.user, defaults={"context": context})
        PresenceState.objects.update_or_create(user=request.user, defaults={"current_context": context, "status": "online", "last_seen_at": timezone.now()})
        audit(request, "role_context.activated", context)
        return Response(ActiveRoleContextSerializer(active).data)


class CurrentContextView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request):
        context = active_context_for(request.user)
        contexts = request.user.role_contexts.select_related("organization", "location", "department").filter(active=True)
        return Response({
            "active": RoleContextSerializer(context).data if context else None,
            "available": RoleContextSerializer(contexts, many=True).data,
            "legacy_role": request_role(request),
        })


class RoleDelegationViewSet(viewsets.ModelViewSet):
    serializer_class = RoleDelegationSerializer
    permission_classes = [EnterpriseAuthenticated]
    queryset = RoleDelegation.objects.select_related("delegator_context", "delegatee_context", "approved_by")
    filterset_fields = ["delegator_context", "delegatee_context"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if can_manage_platform(self.request.user):
            return queryset
        return queryset.filter(Q(delegator_context__user=self.request.user) | Q(delegatee_context__user=self.request.user))

    def perform_create(self, serializer):
        delegator = serializer.validated_data["delegator_context"]
        if delegator.user_id != self.request.user.id and not can_manage_org(self.request.user, delegator.organization):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You cannot delegate this context.")
        obj = serializer.save(approved_by=self.request.user)
        audit(self.request, "role_delegation.created", obj)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        delegation = self.get_object()
        delegation.revoked_at = timezone.now()
        delegation.save(update_fields=["revoked_at"])
        audit(request, "role_delegation.revoked", delegation)
        return Response(self.get_serializer(delegation).data)


class EnterpriseRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EnterpriseRecordSerializer
    permission_classes = [EnterpriseAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    queryset = EnterpriseRecord.objects.select_related(
        "organization", "location", "department", "patient", "admission", "appointment",
        "owner", "assigned_to", "parent", "created_by", "updated_by",
    ).prefetch_related("transitions", "attachments")
    filterset_fields = ["domain", "record_type", "organization", "location", "department", "patient", "admission", "appointment", "assigned_to", "status", "priority"]

    def get_queryset(self):
        queryset = record_queryset_for(self.request.user, super().get_queryset())
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = queryset.filter(Q(reference__icontains=query) | Q(title__icontains=query) | Q(summary__icontains=query))
        return queryset

    def _authorize_schema(self, record_type):
        schema = schema_for(record_type)
        if not schema:
            return False
        return can_manage_platform(self.request.user) or active_role(self.request.user) in schema.get("roles", [])

    def perform_create(self, serializer):
        record_type = serializer.validated_data["record_type"]
        if not self._authorize_schema(record_type):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Your active role cannot create this record type.")
        organization = serializer.validated_data.get("organization") or active_organization(self.request.user)
        owner = serializer.validated_data.get("owner") or self.request.user
        obj = serializer.save(organization=organization, owner=owner, created_by=self.request.user, updated_by=self.request.user)
        WorkflowTransition.objects.create(record=obj, action="create", to_status=obj.status, actor=self.request.user)
        audit(self.request, f"enterprise.{obj.record_type}.created", obj, patient=obj.patient)

    def perform_update(self, serializer):
        if not self._authorize_schema(serializer.instance.record_type):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Your active role cannot update this record type.")
        obj = serializer.save(updated_by=self.request.user)
        audit(self.request, f"enterprise.{obj.record_type}.updated", obj, patient=obj.patient)

    def perform_destroy(self, instance):
        if instance.status not in {"draft", "cancelled"} and not can_manage_platform(self.request.user):
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only draft or cancelled records may be deleted. Use an amendment or cancellation workflow instead.")
        audit(self.request, f"enterprise.{instance.record_type}.deleted", instance, patient=instance.patient)
        instance.delete()

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def transition(self, request, pk=None):
        record = self.get_object()
        if not self._authorize_schema(record.record_type):
            return Response({"detail": "Your active role cannot transition this record."}, status=status.HTTP_403_FORBIDDEN)
        action_name = request.data.get("action", "")
        target = transition_for(record.record_type, record.status, action_name)
        if not target:
            return Response({"detail": f"Action '{action_name}' is not valid from '{record.status}'."}, status=status.HTTP_409_CONFLICT)
        previous = record.status
        record.status = target
        if target in {"completed", "closed", "resolved", "acknowledged", "given"}:
            record.completed_at = timezone.now()
        record.updated_by = request.user
        record.save(update_fields=["status", "completed_at", "updated_by", "updated_at"])
        transition = WorkflowTransition.objects.create(
            record=record,
            action=action_name,
            from_status=previous,
            to_status=target,
            reason=request.data.get("reason", ""),
            metadata=request.data.get("metadata", {}),
            actor=request.user,
        )
        audit(request, f"enterprise.{record.record_type}.{action_name}", record, {"from": previous, "to": target}, patient=record.patient)
        return Response({"record": self.get_serializer(record).data, "transition_id": transition.id})

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def attachments(self, request, pk=None):
        record = self.get_object()
        serializer = ResourceAttachmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = serializer.save(record=record, uploaded_by=request.user)
        try:
            from .tasks import scan_resource_attachment
            scan_resource_attachment.delay(attachment.id)
        except Exception:
            pass
        audit(request, "enterprise.attachment.uploaded", attachment, patient=record.patient)
        return Response(ResourceAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


class BaseEnterpriseViewSet(viewsets.ModelViewSet):
    permission_classes = [EnterpriseResourcePermission]
    filterset_fields = []
    organization_field = None
    user_field = None
    resource_roles = []
    read_roles = []

    def get_queryset(self):
        queryset = super().get_queryset()
        if can_manage_platform(self.request.user):
            return queryset
        org = active_organization(self.request.user)
        if self.organization_field and org:
            organization_fields = [item.strip() for item in str(self.organization_field).split("|") if item.strip()]
            if len(organization_fields) == 1:
                queryset = queryset.filter(**{organization_fields[0]: org})
            else:
                scope = Q()
                for field_name in organization_fields:
                    scope |= Q(**{field_name: org})
                queryset = queryset.filter(scope)
        elif self.user_field:
            queryset = queryset.filter(**{self.user_field: self.request.user})
        return queryset

    def perform_create(self, serializer):
        kwargs = {}
        fields = {field.name for field in serializer.Meta.model._meta.fields}
        org = active_organization(self.request.user)
        if self.organization_field and org:
            organization_fields = [item.strip() for item in str(self.organization_field).split("|") if item.strip()]
            if len(organization_fields) == 1 and organization_fields[0] in fields and organization_fields[0] not in serializer.validated_data:
                kwargs[organization_fields[0]] = org
        for field_name in ("created_by", "requested_by", "updated_by", "owner"):
            if field_name in fields and field_name not in serializer.validated_data:
                kwargs[field_name] = self.request.user
        obj = serializer.save(**kwargs)
        audit(self.request, f"enterprise.{obj._meta.model_name}.created", obj)

    def perform_update(self, serializer):
        fields = {field.name for field in serializer.Meta.model._meta.fields}
        kwargs = {"updated_by": self.request.user} if "updated_by" in fields else {}
        obj = serializer.save(**kwargs)
        audit(self.request, f"enterprise.{obj._meta.model_name}.updated", obj)


RESOURCE_CONFIG = {
    "clinical-codes": (ClinicalCode, ClinicalCodeSerializer, ["admin", "medical_director", "lab_technician", "radiologist", "insurance_officer", "claims_reviewer"], None, None),
    "tariffs": (TariffSchedule, TariffScheduleSerializer, ["insurance", "insurance_officer", "claims_reviewer", "finance_manager", "accountant"], "payer|provider", None),
    "payer-contracts": (PayerContract, PayerContractSerializer, ["insurance", "insurance_officer", "claims_reviewer", "finance_manager", "facility_manager"], "payer|provider", None),
    "medication-knowledge": (MedicationKnowledge, MedicationKnowledgeSerializer, ["pharmacist", "doctor", "clinical_officer", "medical_director", "admin"], None, None),
    "medication-interactions": (MedicationInteraction, MedicationInteractionSerializer, ["pharmacist", "doctor", "clinical_officer", "medical_director", "admin"], None, None),
    "pacs-nodes": (PACSNode, PACSNodeSerializer, ["radiologist", "radiographer", "it_support", "admin"], "organization", None),
    "imaging-studies": (ImagingStudy, ImagingStudySerializer, ["radiologist", "radiographer", "doctor", "clinical_officer", "medical_director"], "organization", None),
    "ambulance-vehicles": (AmbulanceVehicle, AmbulanceVehicleSerializer, ["ambulance_dispatcher", "paramedic", "facility_manager", "admin"], "organization", None),
    "ambulance-telemetry": (AmbulanceTelemetry, AmbulanceTelemetrySerializer, ["ambulance_dispatcher", "paramedic", "facility_manager", "admin"], None, None),
    "presence": (PresenceState, PresenceStateSerializer, [], None, "user"),
    "message-receipts": (MessageReceipt, MessageReceiptSerializer, [], None, "user"),
    "telemedicine-sessions": (TelemedicineSession, TelemedicineSessionSerializer, ["doctor", "clinical_officer", "dentist", "patient", "receptionist", "admin"], None, None),
    "telemedicine-participants": (TelemedicineParticipant, TelemedicineParticipantSerializer, ["doctor", "clinical_officer", "dentist", "patient", "receptionist", "admin"], None, "user"),
    "notification-providers": (NotificationProvider, NotificationProviderSerializer, ["it_support", "admin"], None, None),
    "communication-consents": (CommunicationConsent, CommunicationConsentSerializer, [], None, "user"),
    "escalation-policies": (EscalationPolicy, EscalationPolicySerializer, ["facility_manager", "medical_director", "quality_officer", "it_support", "admin"], "organization", None),
    "escalation-steps": (EscalationStep, EscalationStepSerializer, ["facility_manager", "medical_director", "quality_officer", "it_support", "admin"], None, None),
    "event-schemas": (EventSchema, EventSchemaSerializer, ["it_support", "admin"], None, None),
    "integration-endpoints": (IntegrationEndpoint, IntegrationEndpointSerializer, ["it_support", "admin"], None, None),
    "event-deliveries": (EventDelivery, EventDeliverySerializer, ["it_support", "admin"], None, None),
    "dead-letters": (DeadLetterEvent, DeadLetterEventSerializer, ["it_support", "admin"], None, None),
    "replay-requests": (ReplayRequest, ReplayRequestSerializer, ["it_support", "admin"], None, None),
    "content": (ContentEntry, ContentEntrySerializer, ["admin", "it_support"], None, None),
    "feature-config": (FeatureConfiguration, FeatureConfigurationSerializer, ["admin", "it_support"], None, None),
    "patient-index": (MasterPatientIndex, MasterPatientIndexSerializer, ["records_officer", "compliance_officer", "admin"], None, None),
    "duplicate-patients": (DuplicatePatientCandidate, DuplicatePatientCandidateSerializer, ["records_officer", "compliance_officer", "admin"], None, None),
    "patient-merges": (PatientMerge, PatientMergeSerializer, ["records_officer", "compliance_officer", "admin"], None, None),
    "records-requests": (RecordsRequest, RecordsRequestSerializer, ["records_officer", "compliance_officer", "patient", "admin"], "organization", None),
    "fhir-resources": (FHIRResource, FHIRResourceSerializer, ["it_support", "medical_director", "compliance_officer", "admin"], "organization", None),
    "partner-apps": (PartnerApplication, PartnerApplicationSerializer, ["it_support", "admin"], "organization", None),
    "fhir-subscriptions": (FHIRSubscription, FHIRSubscriptionSerializer, ["it_support", "admin"], None, None),
    "regulator-connectors": (RegulatorConnector, RegulatorConnectorSerializer, ["compliance_officer", "admin", "it_support"], None, None),
    "verification-automation": (VerificationAutomation, VerificationAutomationSerializer, ["compliance_officer", "admin"], "organization", None),
    "security-operations": (SecurityOperation, SecurityOperationSerializer, ["it_support", "compliance_officer", "quality_officer", "medical_director", "admin"], None, None),
    "saved-reports": (SavedReport, SavedReportSerializer, ["facility_manager", "medical_director", "finance_manager", "accountant", "quality_officer", "compliance_officer", "admin"], "organization", None),
    "report-runs": (ReportRun, ReportRunSerializer, ["facility_manager", "medical_director", "finance_manager", "accountant", "quality_officer", "compliance_officer", "admin"], None, None),
    "report-schedules": (ReportSchedule, ReportScheduleSerializer, ["facility_manager", "medical_director", "finance_manager", "accountant", "quality_officer", "compliance_officer", "admin"], None, None),
}


def _viewset_for(name, model, serializer, roles, organization_field, user_field):
    attrs = {
        "queryset": model.objects.all(),
        "serializer_class": serializer,
        "resource_roles": roles,
        "read_roles": roles,
        "organization_field": organization_field,
        "user_field": user_field,
        "__module__": __name__,
    }
    return type(f"{model.__name__}ViewSet", (BaseEnterpriseViewSet,), attrs)


RESOURCE_VIEWSETS = {
    route: _viewset_for(route, model, serializer, roles, org_field, user_field)
    for route, (model, serializer, roles, org_field, user_field) in RESOURCE_CONFIG.items()
}


class PublicContentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.now()
        queryset = ContentEntry.objects.filter(status="published").filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        content_type = request.query_params.get("type")
        placement = request.query_params.get("placement")
        locale = request.query_params.get("locale", "en-UG")
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        if placement:
            queryset = queryset.filter(placement=placement)
        queryset = queryset.filter(locale=locale)
        return Response(ContentEntrySerializer(queryset.order_by("content_type", "slug", "-version"), many=True).data)


class ContentPublishView(APIView):
    permission_classes = [PlatformAdminOnly]

    def post(self, request, pk):
        entry = get_object_or_404(ContentEntry, pk=pk)
        entry.status = "published"
        entry.published_at = timezone.now()
        entry.save(update_fields=["status", "published_at", "updated_at"])
        audit(request, "cms.content.published", entry)
        return Response(ContentEntrySerializer(entry).data)


class PatientMergeActionView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        merge = get_object_or_404(PatientMerge, pk=pk)
        if active_role(request.user) not in {"records_officer", "compliance_officer", "admin"} and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        action_name = request.data.get("action")
        if action_name == "approve":
            merge.status = "approved"
            merge.approved_by = request.user
        elif action_name == "complete":
            if merge.status != "approved":
                return Response({"detail": "Merge must be approved first."}, status=status.HTTP_409_CONFLICT)
            merge.status = "completed"
            merge.completed_at = timezone.now()
            merge.duplicate.status = "merged"
            merge.duplicate.save(update_fields=["status", "updated_at"])
        elif action_name == "reverse":
            if merge.status != "completed":
                return Response({"detail": "Only a completed merge can be reversed."}, status=status.HTTP_409_CONFLICT)
            merge.status = "reversed"
            merge.reversed_at = timezone.now()
            merge.duplicate.status = "active"
            merge.duplicate.save(update_fields=["status", "updated_at"])
        else:
            return Response({"detail": "Unsupported action."}, status=status.HTTP_400_BAD_REQUEST)
        merge.save()
        audit(request, f"records.patient_merge.{action_name}", merge)
        return Response(PatientMergeSerializer(merge).data)


class TelemedicineActionView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def post(self, request, pk):
        session = get_object_or_404(TelemedicineSession, pk=pk)
        participant = session.participants.filter(user=request.user).first()
        if not participant and not can_manage_platform(request.user) and active_role(request.user) not in {"doctor", "clinical_officer", "dentist", "receptionist"}:
            return Response({"detail": "You are not a participant."}, status=status.HTTP_403_FORBIDDEN)
        action_name = request.data.get("action")
        now = timezone.now()
        if action_name == "admit":
            target = get_object_or_404(session.participants, pk=request.data.get("participant_id"))
            target.waiting_status = "admitted"
            target.save(update_fields=["waiting_status"])
        elif action_name == "join":
            participant = participant or TelemedicineParticipant.objects.create(session=session, user=request.user, role=active_role(request.user))
            participant.waiting_status = "joined"
            participant.joined_at = now
            participant.save(update_fields=["waiting_status", "joined_at"])
            if not session.started_at:
                session.started_at = now
                session.status = "in_progress"
                session.save(update_fields=["started_at", "status"])
        elif action_name == "leave":
            if participant:
                participant.left_at = now
                participant.waiting_status = "left"
                participant.save(update_fields=["left_at", "waiting_status"])
        elif action_name == "consent_recording":
            if not participant:
                return Response({"detail": "Participant record not found."}, status=status.HTTP_404_NOT_FOUND)
            participant.recording_consent = bool(request.data.get("consent"))
            participant.consented_at = now
            participant.save(update_fields=["recording_consent", "consented_at"])
        elif action_name == "end":
            session.status = "completed"
            session.ended_at = now
            session.save(update_fields=["status", "ended_at"])
        else:
            return Response({"detail": "Unsupported action."}, status=status.HTTP_400_BAD_REQUEST)
        audit(request, f"telemedicine.{action_name}", session)
        return Response(TelemedicineSessionSerializer(session).data)


class EventDeliveryActionView(APIView):
    permission_classes = [PlatformAdminOnly]

    def post(self, request, pk):
        delivery = get_object_or_404(EventDelivery, pk=pk)
        action_name = request.data.get("action")
        if action_name == "retry":
            delivery.status = "pending"
            delivery.next_attempt_at = timezone.now()
            delivery.save(update_fields=["status", "next_attempt_at"])
            try:
                from .tasks import deliver_event
                deliver_event.delay(delivery.id)
            except Exception:
                pass
        elif action_name == "quarantine":
            delivery.status = "dead_letter"
            delivery.save(update_fields=["status"])
            DeadLetterEvent.objects.get_or_create(delivery=delivery, defaults={"reason": request.data.get("reason", "Manually quarantined"), "payload_snapshot": delivery.event.payload})
        else:
            return Response({"detail": "Unsupported action."}, status=status.HTTP_400_BAD_REQUEST)
        audit(request, f"integration.delivery.{action_name}", delivery)
        return Response(EventDeliverySerializer(delivery).data)


class VerificationRunView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def post(self, request, pk):
        scan = get_object_or_404(VerificationAutomation, pk=pk)
        if active_role(request.user) not in {"compliance_officer", "admin"} and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        action_name = request.data.get("action", "run")
        if action_name == "run":
            scan.status = "queued"
            scan.save(update_fields=["status"])
            try:
                from .tasks import run_verification_scan
                run_verification_scan.delay(scan.id)
            except Exception:
                from .services import execute_verification_scan
                execute_verification_scan(scan)
        elif action_name == "decide":
            decision = request.data.get("decision")
            if decision not in {"approve", "reject", "request_information", "suspend"}:
                return Response({"detail": "Invalid decision."}, status=status.HTTP_400_BAD_REQUEST)
            scan.human_decision = decision
            scan.reviewed_by = request.user
            scan.reviewed_at = timezone.now()
            scan.save(update_fields=["human_decision", "reviewed_by", "reviewed_at"])
        else:
            return Response({"detail": "Unsupported action."}, status=status.HTTP_400_BAD_REQUEST)
        audit(request, f"verification.automation.{action_name}", scan)
        return Response(VerificationAutomationSerializer(scan).data)


class ReportRunActionView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def post(self, request, pk):
        report = get_object_or_404(SavedReport, pk=pk)
        org = active_organization(request.user)
        if report.organization_id and (not org or report.organization_id != org.id) and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        run = ReportRun.objects.create(report=report, parameters=request.data.get("parameters", {}), requested_by=request.user)
        try:
            from .tasks import execute_report_run
            execute_report_run.delay(run.id)
        except Exception:
            from .services import execute_report
            execute_report(run)
        audit(request, "report.run.requested", run)
        return Response(ReportRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class PartnerTokenView(APIView):
    permission_classes = [PlatformAdminOnly]

    def post(self, request, pk):
        app = get_object_or_404(PartnerApplication, pk=pk, active=True)
        scopes = request.data.get("scopes") or app.scopes
        token, raw = app.tokens.model.issue(app, scopes, ttl_minutes=int(request.data.get("ttl_minutes", 60)))
        return Response({"token": raw, "token_type": "Bearer", "expires_at": token.expires_at, "scopes": token.scopes}, status=status.HTTP_201_CREATED)


class MedicationSafetyCheckView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def post(self, request):
        allowed = {
            "doctor", "clinical_officer", "dentist", "medical_director", "pharmacist",
            "nurse", "midwife", "anaesthetist", "admin",
        }
        if active_role(request.user) not in allowed and not can_manage_platform(request.user):
            return Response({"detail": "Medication safety checks are limited to authorised clinical staff."}, status=status.HTTP_403_FORBIDDEN)
        from .services import medication_safety_check
        result = medication_safety_check(
            request.data.get("medicine_ids", []),
            allergy_terms=request.data.get("allergies", []),
            condition_terms=request.data.get("conditions", []),
            pregnant=bool(request.data.get("pregnant")),
            renal_impairment=bool(request.data.get("renal_impairment")),
            hepatic_impairment=bool(request.data.get("hepatic_impairment")),
        )
        audit(request, "medication.safety.checked", request.user, {"medicine_ids": request.data.get("medicine_ids", []), "warning_count": len(result["warnings"])})
        return Response(result)


class PACSHealthView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def post(self, request, pk):
        node = get_object_or_404(PACSNode, pk=pk)
        role = active_role(request.user)
        org = active_organization(request.user)
        if not can_manage_platform(request.user) and role not in {"radiologist", "radiographer", "it_support", "medical_director"}:
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        if not can_manage_platform(request.user) and (not org or node.organization_id != org.id):
            return Response({"detail": "PACS node is outside the active organization."}, status=status.HTTP_403_FORBIDDEN)
        from .services import pacs_health_check
        result = pacs_health_check(node)
        audit(request, "pacs.health.checked", node, result)
        return Response(result, status=status.HTTP_200_OK if result["ok"] else status.HTTP_503_SERVICE_UNAVAILABLE)


class ImagingViewerConfigView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request, pk):
        study = get_object_or_404(ImagingStudy.objects.select_related("organization", "patient", "pacs_node"), pk=pk)
        org = active_organization(request.user)
        role = active_role(request.user)
        allowed_roles = {"radiologist", "radiographer", "doctor", "clinical_officer", "medical_director", "patient", "admin"}
        if role not in allowed_roles and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        if role == "patient" and study.patient_id != request.user.id:
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        if role != "patient" and not can_manage_platform(request.user) and (not org or study.organization_id != org.id):
            return Response({"detail": "Study is outside the active organization."}, status=status.HTTP_403_FORBIDDEN)
        node = study.pacs_node
        return Response({
            "study_id": study.id,
            "study_instance_uid": study.study_instance_uid,
            "accession_number": study.accession_number,
            "modality": study.modality,
            "description": study.description,
            "viewer_url": study.viewer_url,
            "dicomweb_base_url": node.dicomweb_base_url if node else "",
            "viewer": (node.configuration or {}).get("viewer", "ohif") if node else "ohif",
            "token_required": True,
            "metadata": study.metadata,
        })


class NearestAmbulanceView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request):
        if active_role(request.user) not in {"ambulance_dispatcher", "paramedic", "facility_manager", "medical_director", "admin"} and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        try:
            latitude = float(request.query_params["latitude"])
            longitude = float(request.query_params["longitude"])
        except (KeyError, TypeError, ValueError):
            return Response({"detail": "latitude and longitude are required numeric query parameters."}, status=status.HTTP_400_BAD_REQUEST)
        from .services import nearest_ambulances
        rows = nearest_ambulances(latitude, longitude, active_organization(request.user), request.query_params.get("limit", 10))
        return Response({"origin": {"latitude": latitude, "longitude": longitude}, "results": rows, "count": len(rows)})


class DuplicatePatientScanView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def post(self, request):
        if active_role(request.user) not in {"records_officer", "compliance_officer", "admin"} and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        from .services import scan_duplicate_patients
        result = scan_duplicate_patients(request.data.get("minimum_score", 70))
        audit(request, "records.duplicate_scan.completed", request.user, result)
        return Response(result)


class NotificationProviderHealthView(APIView):
    permission_classes = [PlatformAdminOnly]

    def post(self, request, pk):
        provider = get_object_or_404(NotificationProvider, pk=pk)
        from .services import provider_health_check
        result = provider_health_check(provider)
        audit(request, "notification.provider.health_checked", provider, result)
        return Response(result, status=status.HTTP_200_OK if result["ok"] else status.HTTP_503_SERVICE_UNAVAILABLE)


class PatientFHIRExportView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request, patient_id=None):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_id = patient_id or request.user.id
        patient = get_object_or_404(User, pk=target_id, role="patient")
        role = active_role(request.user)
        if patient.id != request.user.id and role not in {"doctor", "clinical_officer", "medical_director", "records_officer", "compliance_officer", "admin"} and not can_manage_platform(request.user):
            return Response({"detail": "Not permitted."}, status=status.HTTP_403_FORBIDDEN)
        if patient.id != request.user.id and role in {"doctor", "clinical_officer"}:
            relationship = patient.care_relationships.filter(practitioner=request.user, status="active").exists()
            if not relationship:
                return Response({"detail": "No active care relationship."}, status=status.HTTP_403_FORBIDDEN)
        from .services import fhir_bundle_for_patient
        bundle = fhir_bundle_for_patient(patient, active_organization(request.user) if patient.id != request.user.id else None)
        audit(request, "fhir.patient_bundle.exported", patient, {"resource_count": bundle["total"]}, patient=patient)
        return Response(bundle, content_type="application/fhir+json")


class EventReplayActionView(APIView):
    permission_classes = [PlatformAdminOnly]

    def post(self, request, pk):
        replay = get_object_or_404(ReplayRequest, pk=pk)
        if replay.status not in {"pending", "failed"}:
            return Response({"detail": "Replay request is already running or completed."}, status=status.HTTP_409_CONFLICT)
        replay.status = "running"
        replay.started_at = timezone.now()
        replay.save(update_fields=["status", "started_at"])
        filters = replay.filters or {}
        deliveries = EventDelivery.objects.filter(endpoint=replay.endpoint)
        if filters.get("status"):
            deliveries = deliveries.filter(status=filters["status"])
        if filters.get("event_type"):
            deliveries = deliveries.filter(event__event_type=filters["event_type"])
        if filters.get("from"):
            deliveries = deliveries.filter(created_at__gte=filters["from"])
        count = 0
        for delivery in deliveries[:10000]:
            delivery.status = "pending"
            delivery.next_attempt_at = timezone.now()
            delivery.save(update_fields=["status", "next_attempt_at"])
            count += 1
            try:
                from .tasks import deliver_event
                deliver_event.delay(delivery.id)
            except Exception:
                pass
        replay.status = "completed"
        replay.replayed_count = count
        replay.completed_at = timezone.now()
        replay.save(update_fields=["status", "replayed_count", "completed_at"])
        audit(request, "integration.replay.completed", replay, {"replayed_count": count})
        return Response(ReplayRequestSerializer(replay).data)


class EnterpriseMetricsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.conf import settings
        from django.http import HttpResponse
        expected = getattr(settings, "METRICS_TOKEN", "")
        provided = request.headers.get("X-Metrics-Token", "") or request.query_params.get("token", "")
        authenticated_admin = bool(getattr(request, "user", None) and request.user.is_authenticated and can_manage_platform(request.user))
        if expected and provided != expected and not authenticated_admin:
            return Response({"detail": "Invalid metrics token."}, status=status.HTTP_403_FORBIDDEN)
        from .services import platform_metrics
        metrics = platform_metrics()
        lines = ["# HELP healthpilot_platform_info HealthPilot platform operational counters", "# TYPE healthpilot_platform_info gauge"]
        for name, value in metrics.items():
            lines.append(f"healthpilot_{name} {int(value)}")
        lines.append("")
        return HttpResponse("\n".join(lines), content_type="text/plain; version=0.0.4")


class EnterpriseReadinessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        from django.db import connection
        checks = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                checks["database"] = cursor.fetchone()[0] == 1
        except Exception as exc:
            checks["database"] = False
            checks["database_error"] = str(exc)
        try:
            from django.core.cache import cache
            cache.set("enterprise-readiness", "ok", timeout=10)
            checks["cache"] = cache.get("enterprise-readiness") == "ok"
        except Exception as exc:
            checks["cache"] = False
            checks["cache_error"] = str(exc)
        checks["event_pipeline"] = True
        checks["private_storage_configured"] = bool(__import__("os").getenv("AWS_STORAGE_BUCKET_NAME"))
        checks["malware_scanner_configured"] = bool(__import__("os").getenv("CLAMAV_HOST"))
        checks["telemedicine_provider"] = __import__("os").getenv("TELEMEDICINE_PROVIDER", "jitsi")
        ready = bool(checks.get("database") and checks.get("cache"))
        return Response({"ready": ready, "checks": checks, "checked_at": timezone.now()}, status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE)


class EnterpriseEntityLookupView(APIView):
    """Searchable entity selectors used by clinical and operational forms.

    This endpoint intentionally returns compact display-safe records instead of
    exposing whole user, appointment or admission serializers. Results are
    scoped to the active role and organization context.
    """

    permission_classes = [EnterpriseAuthenticated]

    def get(self, request):
        from appointments.models import Appointment
        from operations.models import Admission
        from workforce.models import StaffMembership

        kind = str(request.query_params.get("kind", "patient")).strip().lower()
        query = str(request.query_params.get("q", "")).strip()
        limit = min(max(int(request.query_params.get("limit", 20) or 20), 1), 50)
        role = active_role(request.user)
        organization = active_organization(request.user)

        if kind == "patient":
            qs = User.objects.filter(role="patient", is_active=True).select_related("patient_profile")
            if role == "patient":
                qs = qs.filter(pk=request.user.pk)
            elif organization:
                qs = qs.filter(
                    Q(admissions__organization=organization)
                    | Q(facility_visits__organization=organization)
                    | Q(patient_appointments__doctor__staff_memberships__organization=organization)
                    | Q(care_relationships__practitioner__staff_memberships__organization=organization)
                ).distinct()
            if query:
                qs = qs.filter(
                    Q(first_name__icontains=query) | Q(last_name__icontains=query)
                    | Q(email__icontains=query) | Q(phone__icontains=query)
                )
            rows = []
            for user in qs.order_by("first_name", "last_name")[:limit]:
                profile = getattr(user, "patient_profile", None)
                rows.append({
                    "id": user.id,
                    "label": user.display_name,
                    "subtitle": " · ".join(filter(None, [user.phone, user.email])),
                    "meta": {
                        "date_of_birth": str(getattr(profile, "date_of_birth", "") or ""),
                        "location": getattr(profile, "location", "") or "",
                        "role": user.role,
                    },
                })
            return Response({"kind": kind, "results": rows})

        if kind == "staff":
            qs = User.objects.exclude(role="patient").filter(is_active=True)
            if organization:
                qs = qs.filter(staff_memberships__organization=organization, staff_memberships__status="active").distinct()
            role_filter = str(request.query_params.get("role", "")).strip()
            if role_filter:
                qs = qs.filter(Q(role=role_filter) | Q(role_contexts__role_code=role_filter)).distinct()
            if query:
                qs = qs.filter(
                    Q(first_name__icontains=query) | Q(last_name__icontains=query)
                    | Q(email__icontains=query) | Q(phone__icontains=query)
                    | Q(staff_memberships__job_title__icontains=query)
                ).distinct()
            rows = []
            memberships = StaffMembership.objects.filter(user__in=qs)
            if organization:
                memberships = memberships.filter(organization=organization)
            membership_map = {row.user_id: row for row in memberships.select_related("department")}
            for user in qs.order_by("first_name", "last_name")[:limit]:
                membership = membership_map.get(user.id)
                rows.append({
                    "id": user.id,
                    "label": user.display_name,
                    "subtitle": " · ".join(filter(None, [getattr(membership, "job_title", ""), user.get_role_display(), user.email])),
                    "meta": {
                        "role": getattr(membership, "role", "") or user.role,
                        "department": getattr(getattr(membership, "department", None), "name", "") or "",
                    },
                })
            return Response({"kind": kind, "results": rows})

        if kind == "admission":
            qs = Admission.objects.select_related("patient", "ward", "organization").exclude(status__in=["discharged", "cancelled"])
            if role == "patient":
                qs = qs.filter(patient=request.user)
            elif organization:
                qs = qs.filter(organization=organization)
            if query:
                qs = qs.filter(
                    Q(admission_number__icontains=query) | Q(patient__first_name__icontains=query)
                    | Q(patient__last_name__icontains=query) | Q(ward__name__icontains=query)
                )
            rows = [{
                "id": row.id,
                "label": f"{row.admission_number} · {row.patient.display_name}",
                "subtitle": f"{row.ward.name} · {row.get_status_display()}",
                "meta": {"patient_id": row.patient_id, "ward": row.ward.name, "status": row.status},
            } for row in qs.order_by("-admitted_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "appointment":
            qs = Appointment.objects.select_related("patient", "doctor")
            if role == "patient":
                qs = qs.filter(patient=request.user)
            elif role in {"doctor", "clinical_officer", "dentist", "physiotherapist", "nutritionist", "psychologist", "medical_director"}:
                qs = qs.filter(doctor=request.user)
            elif organization:
                qs = qs.filter(doctor__staff_memberships__organization=organization).distinct()
            if query:
                qs = qs.filter(
                    Q(patient__first_name__icontains=query) | Q(patient__last_name__icontains=query)
                    | Q(doctor__first_name__icontains=query) | Q(doctor__last_name__icontains=query)
                    | Q(reason__icontains=query)
                )
            rows = [{
                "id": row.id,
                "label": f"{row.patient.display_name} · {row.date:%d %b %Y} {row.start_time:%H:%M}",
                "subtitle": f"{row.doctor.display_name} · {row.get_type_display()} · {row.get_status_display()}",
                "meta": {"patient_id": row.patient_id, "doctor_id": row.doctor_id, "status": row.status},
            } for row in qs.order_by("-date", "-start_time")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "lab_result":
            from services.models import LabResult

            qs = LabResult.objects.select_related("order__patient", "order__test", "order__referring_doctor")
            if role == "patient":
                qs = qs.filter(order__patient=request.user, order__result_released=True)
            elif role in {"doctor", "clinical_officer", "dentist", "medical_director"}:
                qs = qs.filter(Q(order__referring_doctor=request.user) | Q(order__patient__care_relationships__practitioner=request.user)).distinct()
            elif organization:
                qs = qs.filter(Q(order__lab__staff_memberships__organization=organization) | Q(order__referring_doctor__staff_memberships__organization=organization)).distinct()
            if query:
                qs = qs.filter(Q(name__icontains=query) | Q(order__test__name__icontains=query) | Q(order__patient__first_name__icontains=query) | Q(order__patient__last_name__icontains=query))
            rows = [{
                "id": row.id,
                "label": f"{row.name} · {row.order.patient.display_name}",
                "subtitle": f"{row.value_numeric if row.value_numeric is not None else row.value_text} {row.unit} · {row.get_interpretation_display()} · {row.get_status_display()}",
                "meta": {"patient_id": row.order.patient_id, "order_id": row.order_id, "critical": row.interpretation == row.Interpretation.CRITICAL},
            } for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "imaging_result":
            from operations.models import ImagingReport

            qs = ImagingReport.objects.select_related("order__patient", "order__organization", "order__ordering_clinician")
            if role == "patient":
                qs = qs.filter(order__patient=request.user, status__in=[ImagingReport.Status.VERIFIED, ImagingReport.Status.RELEASED])
            elif role in {"doctor", "clinical_officer", "dentist", "medical_director", "radiologist", "radiographer"}:
                qs = qs.filter(Q(order__ordering_clinician=request.user) | Q(order__radiologist=request.user) | Q(order__radiographer=request.user) | Q(order__patient__care_relationships__practitioner=request.user)).distinct()
            elif organization:
                qs = qs.filter(order__organization=organization)
            if query:
                qs = qs.filter(Q(order__study_name__icontains=query) | Q(order__order_number__icontains=query) | Q(order__patient__first_name__icontains=query) | Q(order__patient__last_name__icontains=query))
            rows = [{
                "id": row.id,
                "label": f"{row.order.study_name} · {row.order.patient.display_name}",
                "subtitle": f"{row.order.get_modality_display()} · {row.get_status_display()}",
                "meta": {"patient_id": row.order.patient_id, "order_id": row.order_id, "critical": row.critical},
            } for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "invoice":
            from payments.models import Invoice

            qs = Invoice.objects.select_related("patient", "organization")
            if role == "patient":
                qs = qs.filter(patient=request.user)
            elif organization:
                qs = qs.filter(organization=organization)
            if query:
                qs = qs.filter(Q(number__icontains=query) | Q(patient__first_name__icontains=query) | Q(patient__last_name__icontains=query) | Q(gateway_ref__icontains=query))
            rows = [{
                "id": row.id,
                "label": f"{row.number} · {row.patient.display_name}",
                "subtitle": f"{row.currency} {row.amount:,} · {row.get_status_display()} · balance {row.balance:,}",
                "meta": {"patient_id": row.patient_id, "status": row.status, "balance": row.balance},
            } for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "prescription":
            from prescriptions.models import Prescription

            qs = Prescription.objects.select_related("patient", "doctor", "appointment")
            if role == "patient":
                qs = qs.filter(patient=request.user)
            elif role in {"doctor", "clinical_officer", "dentist", "medical_director"}:
                qs = qs.filter(doctor=request.user)
            elif organization:
                qs = qs.filter(doctor__staff_memberships__organization=organization).distinct()
            if query:
                qs = qs.filter(Q(number__icontains=query) | Q(patient__first_name__icontains=query) | Q(patient__last_name__icontains=query) | Q(doctor__first_name__icontains=query) | Q(doctor__last_name__icontains=query))
            rows = [{
                "id": row.id,
                "label": f"{row.number} · {row.patient.display_name}",
                "subtitle": f"{row.doctor.display_name} · {row.get_status_display()} · expires {row.expires_at:%d %b %Y}",
                "meta": {"patient_id": row.patient_id, "doctor_id": row.doctor_id, "status": row.status},
            } for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "claim":
            from services.models import InsuranceClaim

            qs = InsuranceClaim.objects.select_related("patient", "provider", "policy")
            if role == "patient":
                qs = qs.filter(patient=request.user)
            elif role in {"insurance", "insurance_officer", "claims_reviewer"}:
                if organization:
                    qs = qs.filter(Q(policy__provider__staff_memberships__organization=organization) | Q(policy__provider__owned_health_organizations=organization)).distinct()
            elif organization:
                qs = qs.filter(provider__staff_memberships__organization=organization).distinct()
            if query:
                qs = qs.filter(Q(claim_number__icontains=query) | Q(patient__first_name__icontains=query) | Q(patient__last_name__icontains=query) | Q(policy__name__icontains=query))
            rows = [{"id": row.id, "label": f"{row.claim_number} · {row.patient.display_name}", "subtitle": f"{row.policy.name} · {row.get_status_display()} · {row.amount:,}", "meta": {"patient_id": row.patient_id, "status": row.status, "approved_amount": row.approved_amount}} for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "payment":
            from payments.models import PaymentTransaction

            qs = PaymentTransaction.objects.select_related("invoice__patient", "invoice__organization")
            if role == "patient":
                qs = qs.filter(invoice__patient=request.user)
            elif organization:
                qs = qs.filter(invoice__organization=organization)
            if query:
                qs = qs.filter(Q(reference__icontains=query) | Q(invoice__number__icontains=query) | Q(invoice__patient__first_name__icontains=query) | Q(invoice__patient__last_name__icontains=query))
            rows = [{"id": row.id, "label": f"{row.reference} · {row.invoice.patient.display_name}", "subtitle": f"{row.currency} {row.amount:,} · {row.get_status_display()}", "meta": {"invoice_id": row.invoice_id, "status": row.status}} for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "dispensing_record":
            from services.models import DispensingRecord

            qs = DispensingRecord.objects.select_related("pharmacy_order__patient", "pharmacy_order__pharmacy", "pharmacist")
            if role == "patient":
                qs = qs.filter(pharmacy_order__patient=request.user)
            elif organization:
                qs = qs.filter(Q(pharmacy_order__pharmacy__staff_memberships__organization=organization) | Q(pharmacy_order__pharmacy__owned_health_organizations=organization) | Q(pharmacist__staff_memberships__organization=organization)).distinct()
            if query:
                qs = qs.filter(Q(pharmacy_order__order_number__icontains=query) | Q(pharmacy_order__patient__first_name__icontains=query) | Q(pharmacy_order__patient__last_name__icontains=query))
            rows = [{"id": row.id, "label": f"Dispensing #{row.id} · {row.pharmacy_order.patient.display_name}", "subtitle": f"{row.get_status_display()} · {row.pharmacist.display_name}", "meta": {"patient_id": row.pharmacy_order.patient_id, "order_id": row.pharmacy_order_id}} for row in qs.order_by("-created_at")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "inventory_batch":
            from operations.models import InventoryBatch

            qs = InventoryBatch.objects.select_related("item__organization")
            if organization:
                qs = qs.filter(item__organization=organization)
            elif not is_platform_super_admin(request.user):
                qs = qs.none()
            if query:
                qs = qs.filter(Q(batch_number__icontains=query) | Q(item__name__icontains=query) | Q(item__sku__icontains=query))
            rows = [{"id": row.id, "label": f"{row.item.name} · {row.batch_number}", "subtitle": f"{row.quantity_available} available · expires {row.expiry_date or 'not set'}", "meta": {"item_id": row.item_id, "quantity_available": row.quantity_available, "recalled": row.recalled}} for row in qs.order_by("expiry_date", "batch_number")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "organization":
            from registry.models import Organization

            qs = Organization.objects.filter(active=True)
            if organization and not is_platform_super_admin(request.user):
                qs = qs.filter(pk=organization.pk)
            if query:
                qs = qs.filter(Q(legal_name__icontains=query) | Q(trading_name__icontains=query) | Q(license_number__icontains=query))
            rows = [{"id": row.id, "label": row.trading_name or row.legal_name, "subtitle": f"{row.get_organization_type_display()} · {row.get_status_display()}", "meta": {"status": row.status, "type": row.organization_type}} for row in qs.order_by("legal_name")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "branch":
            from registry.models import OrganizationLocation

            qs = OrganizationLocation.objects.select_related("organization").filter(active=True)
            if organization:
                qs = qs.filter(organization=organization)
            elif not is_platform_super_admin(request.user):
                qs = qs.none()
            if query:
                qs = qs.filter(Q(name__icontains=query) | Q(address__icontains=query) | Q(district__icontains=query))
            rows = [{"id": row.id, "label": row.name, "subtitle": f"{row.organization} · {row.district or row.address}", "meta": {"organization_id": row.organization_id, "latitude": row.latitude, "longitude": row.longitude}} for row in qs.order_by("name")[:limit]]
            return Response({"kind": kind, "results": rows})

        if kind == "department":
            from workforce.models import Department

            qs = Department.objects.select_related("organization", "location").filter(active=True)
            if organization:
                qs = qs.filter(organization=organization)
            elif not is_platform_super_admin(request.user):
                qs = qs.none()
            if query:
                qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))
            rows = [{"id": row.id, "label": row.name, "subtitle": f"{row.organization} · {row.location or 'All locations'}", "meta": {"organization_id": row.organization_id, "location_id": row.location_id}} for row in qs.order_by("name")[:limit]]
            return Response({"kind": kind, "results": rows})

        return Response({"detail": "Unsupported lookup kind."}, status=status.HTTP_400_BAD_REQUEST)


ROLE_DASHBOARD_BLUEPRINTS = {
    "medical_director": {
        "headline": "Clinical command and quality oversight",
        "metrics": [
            ("Patients admitted", ["care_plan", "observation_chart"], "hospital"),
            ("Critical results", ["critical_imaging_alert", "blood_bank"], "alert"),
            ("Clinical incidents", ["clinical_safety_case", "medical_director_review"], "shield"),
            ("Documentation gaps", ["handover", "record_correction"], "file"),
        ],
        "focus": ["medical_director_review", "clinical_safety_case", "critical_imaging_alert", "quality_control"],
    },
    "clinical_officer": {
        "headline": "Outpatient care, follow-up and clinical task control",
        "metrics": [("Active consultations", ["care_plan"], "doctor"), ("Results to review", ["analyzer_result", "structured_report"], "flask"), ("Referrals", ["handover"], "activity"), ("Discharge work", ["care_plan", "handover"], "hospital")],
        "focus": ["care_plan", "analyzer_result", "structured_report", "handover"],
    },
    "dentist": {
        "headline": "Dental care planning and procedure coordination",
        "metrics": [("Dental charts", ["dental_chart"], "clipboard"), ("Imaging requests", ["modality_worklist"], "activity"), ("Treatment follow-ups", ["care_plan"], "calendar"), ("Safety alerts", ["medication_safety_check"], "shield")],
        "focus": ["dental_chart", "modality_worklist", "care_plan", "medication_safety_check"],
    },
    "physiotherapist": {
        "headline": "Rehabilitation sessions and outcome tracking",
        "metrics": [("Active plans", ["physiotherapy_plan"], "activity"), ("Assessments due", ["risk_assessment"], "clipboard"), ("Care handovers", ["handover"], "refresh"), ("Discharge readiness", ["care_plan"], "hospital")],
        "focus": ["physiotherapy_plan", "risk_assessment", "handover", "care_plan"],
    },
    "nutritionist": {
        "headline": "Nutrition risk, meal plans and growth follow-up",
        "metrics": [("Nutrition plans", ["nutrition_plan"], "clipboard"), ("Growth follow-up", ["growth_measurement"], "activity"), ("Maternal nutrition", ["antenatal_visit"], "users"), ("Inpatient diet work", ["care_plan"], "hospital")],
        "focus": ["nutrition_plan", "growth_measurement", "antenatal_visit", "care_plan"],
    },
    "psychologist": {
        "headline": "Therapy, safeguarding and confidential care planning",
        "metrics": [("Therapy sessions", ["psychology_session"], "message"), ("Active care plans", ["care_plan"], "clipboard"), ("Risk alerts", ["risk_assessment"], "alert"), ("Follow-ups", ["handover"], "calendar")],
        "focus": ["psychology_session", "risk_assessment", "care_plan", "handover"],
    },
    "midwife": {
        "headline": "Labour ward, maternal safety and newborn care",
        "metrics": [("Women in labour", ["partograph_observation"], "activity"), ("High-risk pregnancies", ["antenatal_visit", "risk_assessment"], "alert"), ("Deliveries", ["delivery_record"], "users"), ("Newborn follow-up", ["newborn_assessment", "immunization"], "heart")],
        "focus": ["partograph_observation", "antenatal_visit", "delivery_record", "newborn_assessment"],
    },
    "records_officer": {
        "headline": "Patient identity, disclosure and record integrity",
        "metrics": [("Corrections", ["record_correction"], "file"), ("Release requests", ["release_information"], "send"), ("Legal holds", ["legal_hold"], "shield"), ("Scans to classify", ["scanned_document"], "clipboard")],
        "focus": ["record_correction", "release_information", "legal_hold", "scanned_document"],
    },
    "accountant": {
        "headline": "Daily finance, reconciliation and ledger control",
        "metrics": [("Bank items", ["bank_transaction"], "money"), ("Reconciliations", ["reconciliation"], "refresh"), ("Supplier liabilities", ["supplier_bill"], "file"), ("Expenses", ["expense"], "wallet")],
        "focus": ["bank_transaction", "reconciliation", "supplier_bill", "expense"],
    },
    "finance_manager": {
        "headline": "Revenue assurance, budgets and financial governance",
        "metrics": [("Open periods", ["financial_period"], "calendar"), ("Settlements", ["settlement"], "money"), ("Disputes", ["payment_dispute"], "alert"), ("Adjustments", ["credit_note", "debit_note"], "audit")],
        "focus": ["financial_period", "settlement", "payment_dispute", "credit_note", "debit_note"],
    },
    "procurement_officer": {
        "headline": "Replenishment, supplier performance and stock assurance",
        "metrics": [("Stock counts", ["stock_count"], "box"), ("Cold-chain alerts", ["cold_chain"], "activity"), ("Recalls", ["recall"], "alert"), ("Supplier bills", ["supplier_bill"], "file")],
        "focus": ["stock_count", "cold_chain", "recall", "supplier_bill"],
    },
    "quality_officer": {
        "headline": "Patient safety, incidents and accreditation readiness",
        "metrics": [("Safety cases", ["clinical_safety_case"], "shield"), ("Quality failures", ["quality_control"], "flask"), ("Medication incidents", ["adverse_drug_reaction"], "pill"), ("Open reviews", ["medical_director_review"], "audit")],
        "focus": ["clinical_safety_case", "quality_control", "adverse_drug_reaction", "medical_director_review"],
    },
    "compliance_officer": {
        "headline": "Privacy, access oversight and regulatory assurance",
        "metrics": [("Security alerts", ["security_alert"], "alert"), ("Privacy actions", ["dpia", "release_information"], "shield"), ("Legal holds", ["legal_hold"], "file"), ("Verification scans", ["verification_scan"], "verified")],
        "focus": ["security_alert", "dpia", "legal_hold", "verification_scan"],
    },
    "hr_officer": {
        "headline": "Workforce capacity, credentials and staff lifecycle",
        "metrics": [("Handovers", ["handover"], "refresh"), ("Safety cases", ["clinical_safety_case"], "shield"), ("Role delegations", [], "users"), ("Credential risks", ["verification_scan"], "verified")],
        "focus": ["handover", "clinical_safety_case", "verification_scan"],
    },
    "it_support": {
        "headline": "Platform reliability, integrations and security operations",
        "metrics": [("Security alerts", ["security_alert"], "alert"), ("Vulnerability scans", ["vulnerability_scan"], "shield"), ("Backup & restore", ["backup_restore"], "refresh"), ("Integration work", ["upload_scan"], "globe")],
        "focus": ["security_alert", "vulnerability_scan", "backup_restore", "upload_scan"],
    },
    "claims_reviewer": {
        "headline": "Medical claims review, appeals and fraud control",
        "metrics": [("Claim events", ["claim_event"], "insurance"), ("Appeals", ["claim_appeal"], "refresh"), ("Fraud flags", ["fraud_flag"], "alert"), ("Queries", ["claim_message"], "message")],
        "focus": ["claim_event", "claim_appeal", "fraud_flag", "claim_message"],
    },
    "anaesthetist": {
        "headline": "Perioperative risk, anaesthesia and recovery",
        "metrics": [("Pre-op assessments", ["pre_anaesthetic_assessment"], "clipboard"), ("Anaesthesia charts", ["anaesthesia_chart"], "activity"), ("Intraoperative alerts", ["intraoperative_observation"], "heart"), ("Recovery patients", ["recovery_observation"], "refresh")],
        "focus": ["pre_anaesthetic_assessment", "anaesthesia_chart", "intraoperative_observation", "recovery_observation"],
    },
    "ambulance_dispatcher": {
        "headline": "Live fleet coordination and emergency response",
        "metrics": [("Pre-hospital cases", ["prehospital_record"], "truck"), ("Trauma activations", ["trauma_assessment"], "alert"), ("Resuscitations", ["resuscitation_event"], "heart"), ("Mass casualty", ["mass_casualty"], "users")],
        "focus": ["prehospital_record", "trauma_assessment", "resuscitation_event", "mass_casualty"],
    },
    "paramedic": {
        "headline": "Pre-hospital care and receiving-facility handover",
        "metrics": [("Active incidents", ["prehospital_record"], "truck"), ("Trauma records", ["trauma_assessment"], "alert"), ("Resuscitation events", ["resuscitation_event"], "heart"), ("Observations", ["emergency_observation"], "activity")],
        "focus": ["prehospital_record", "trauma_assessment", "resuscitation_event", "emergency_observation"],
    },
    "radiographer": {
        "headline": "Modality worklist, acquisition and radiation safety",
        "metrics": [("Modality worklist", ["modality_worklist"], "clipboard"), ("Dose records", ["radiation_dose"], "shield"), ("Critical alerts", ["critical_imaging_alert"], "alert"), ("Reports", ["structured_report"], "file")],
        "focus": ["modality_worklist", "radiation_dose", "critical_imaging_alert", "structured_report"],
    },
    "storekeeper": {
        "headline": "Inventory safety, counts, cold chain and recalls",
        "metrics": [("Stock counts", ["stock_count"], "box"), ("Cold chain", ["cold_chain"], "activity"), ("Product recalls", ["recall"], "alert"), ("Controlled medicines", ["controlled_drug_entry"], "shield")],
        "focus": ["stock_count", "cold_chain", "recall", "controlled_drug_entry"],
    },
    "insurance_officer": {
        "headline": "Eligibility, claims, appeals and settlement",
        "metrics": [("Claims", ["claim_event"], "insurance"), ("Appeals", ["claim_appeal"], "refresh"), ("Queries", ["claim_message"], "message"), ("Settlements", ["settlement_import"], "money")],
        "focus": ["claim_event", "claim_appeal", "claim_message", "settlement_import"],
    },
}


class RoleDashboardView(APIView):
    permission_classes = [EnterpriseAuthenticated]

    def get(self, request):
        role = active_role(request.user)
        queryset = record_queryset_for(request.user, EnterpriseRecord.objects.all())
        blueprint = ROLE_DASHBOARD_BLUEPRINTS.get(role, {
            "headline": "Role-specific operational workspace",
            "metrics": [("Open work", [], "activity"), ("Critical", [], "alert"), ("Assigned", [], "user"), ("Completed", [], "verified")],
            "focus": [],
        })
        closed = ["completed", "closed", "cancelled", "resolved", "released", "approved", "paid"]
        open_qs = queryset.exclude(status__in=closed)
        metrics = []
        for label, types, icon in blueprint["metrics"]:
            scope = queryset.filter(record_type__in=types) if types else open_qs
            metrics.append({
                "label": label,
                "value": scope.count(),
                "critical": scope.filter(priority="critical").exclude(status__in=closed).count(),
                "icon": icon,
            })
        focus = blueprint.get("focus") or []
        queues = []
        for record_type in focus:
            rows = queryset.filter(record_type=record_type).exclude(status__in=closed)
            schema = schema_for(record_type) or {}
            queues.append({
                "record_type": record_type,
                "label": schema.get("label", record_type.replace("_", " ").title()),
                "total": rows.count(),
                "critical": rows.filter(priority="critical").count(),
                "overdue": rows.filter(due_at__lt=timezone.now()).count(),
            })
        recent = EnterpriseRecordSerializer(queryset.order_by("-updated_at")[:10], many=True).data
        return Response({
            "role": role,
            "headline": blueprint["headline"],
            "metrics": metrics,
            "queues": queues,
            "recent": recent,
            "open_total": open_qs.count(),
            "critical_total": open_qs.filter(priority="critical").count(),
            "overdue_total": open_qs.filter(due_at__lt=timezone.now()).count(),
            "assigned_total": open_qs.filter(assigned_to=request.user).count(),
        })
