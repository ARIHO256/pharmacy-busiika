from rest_framework import serializers

from accounts.models import User
from .models import (
    GeneratedClinicalDocument, OperationalAction, ReleaseAcceptance, ResultReview,
    WorkflowActionEvent, WorkflowCase, WorkflowComment,
)
from .services import available_actions


class WorkflowActionEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.display_name", read_only=True)

    class Meta:
        model = WorkflowActionEvent
        fields = ["id", "action", "actor", "actor_name", "actor_role", "from_status", "to_status", "note", "data", "correlation_id", "created_at"]


class WorkflowCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = WorkflowComment
        fields = ["id", "author", "author_name", "body", "visibility", "attachment", "created_at"]
        read_only_fields = ["author", "created_at"]


class WorkflowCaseSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    subject_user_name = serializers.CharField(source="subject_user.display_name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.display_name", read_only=True)
    organization_name = serializers.CharField(source="organization.legal_name", read_only=True)
    events = WorkflowActionEventSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowCase
        fields = [
            "id", "public_id", "reference", "page_slug", "category", "organization",
            "organization_name", "location", "department", "patient", "patient_name",
            "subject_user", "subject_user_name", "assigned_to", "assigned_to_name",
            "appointment", "admission", "invoice", "parent", "title", "summary",
            "status", "priority", "data", "result", "due_at", "started_at",
            "completed_at", "archived_at", "version", "created_by", "updated_by",
            "created_at", "updated_at", "events", "comments", "available_actions",
        ]
        read_only_fields = [
            "public_id", "reference", "page_slug", "category", "organization",
            "location", "department", "status", "result", "started_at", "completed_at",
            "archived_at", "version", "created_by", "updated_by", "created_at", "updated_at",
        ]

    def get_comments(self, obj):
        request = self.context.get("request")
        comments = obj.comments.all()
        if request:
            from accounts.permissions import request_role
            if request_role(request) == "patient":
                comments = comments.filter(visibility=WorkflowComment.Visibility.PATIENT)
        return WorkflowCommentSerializer(comments, many=True, context=self.context).data

    def get_available_actions(self, obj):
        request = self.context.get("request")
        if not request:
            return {}
        try:
            return available_actions(obj, request.user)
        except Exception:
            return {}


class WorkflowActionSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=80)
    note = serializers.CharField(required=False, allow_blank=True, max_length=6000)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True), required=False, allow_null=True)
    result = serializers.JSONField(required=False)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        # Keep page-specific fields so the server-side action definition can validate them.
        for key, item in data.items():
            if key not in value:
                value[key] = item
        if isinstance(value.get("assigned_to"), User):
            value["assigned_to"] = value["assigned_to"].id
        return value


class GeneratedClinicalDocumentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    signed_by_name = serializers.CharField(source="signed_by.display_name", read_only=True)
    verification_url = serializers.SerializerMethodField()

    class Meta:
        model = GeneratedClinicalDocument
        fields = ["id", "public_id", "verification_code", "document_type", "title", "patient", "patient_name", "organization", "workflow_case", "content", "status", "file", "created_by", "signed_by", "signed_by_name", "signed_at", "revoked_at", "created_at", "updated_at", "verification_url"]
        read_only_fields = ["public_id", "verification_code", "status", "file", "created_by", "signed_by", "signed_at", "revoked_at", "created_at", "updated_at"]

    def get_verification_url(self, obj):
        request = self.context.get("request")
        path = f"/api/v1/journeys/documents/verify/{obj.verification_code}/"
        return request.build_absolute_uri(path) if request else path


class ResultReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="reviewer.display_name", read_only=True)
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)

    class Meta:
        model = ResultReview
        fields = "__all__"
        read_only_fields = ["reviewer", "created_at"]


class OperationalActionSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="workflow_case.reference", read_only=True)
    title = serializers.CharField(source="workflow_case.title", read_only=True)
    patient_name = serializers.CharField(source="patient.display_name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.display_name", read_only=True)
    executed_by_name = serializers.CharField(source="executed_by.display_name", read_only=True)

    class Meta:
        model = OperationalAction
        fields = [
            "id", "public_id", "workflow_case", "reference", "title", "page_slug",
            "domain", "operation_code", "organization", "location", "department",
            "patient", "patient_name", "subject_user", "appointment", "admission",
            "invoice", "state", "payload", "result", "effect_log",
            "effect_reference_type", "effect_reference_id", "requires_approval",
            "approved_by", "approved_by_name", "approved_at", "executed_by",
            "executed_by_name", "executed_at", "failure_reason", "created_by",
            "created_by_name", "updated_by", "created_at", "updated_at",
        ]
        read_only_fields = fields


class ReleaseAcceptanceSerializer(serializers.ModelSerializer):
    reviewer_account_name = serializers.CharField(source="reviewer.display_name", read_only=True)
    is_currently_accepted = serializers.BooleanField(read_only=True)

    class Meta:
        model = ReleaseAcceptance
        fields = [
            "id", "release_version", "environment", "acceptance_type", "status",
            "reviewer", "reviewer_account_name", "reviewer_name", "reviewer_title",
            "reviewer_email", "statement", "evidence", "evidence_hash", "signed_at",
            "expires_at", "metadata", "is_currently_accepted", "created_at", "updated_at",
        ]
        read_only_fields = ["evidence_hash", "signed_at", "created_at", "updated_at", "is_currently_accepted"]

    def validate(self, attrs):
        status_value = attrs.get("status", getattr(self.instance, "status", ReleaseAcceptance.Status.PENDING))
        reviewer_name = attrs.get("reviewer_name", getattr(self.instance, "reviewer_name", ""))
        statement = attrs.get("statement", getattr(self.instance, "statement", ""))
        evidence = attrs.get("evidence", getattr(self.instance, "evidence", None))
        if status_value == ReleaseAcceptance.Status.ACCEPTED:
            errors = {}
            if len(str(reviewer_name).strip()) < 3:
                errors["reviewer_name"] = "Identify the qualified reviewer accepting this gate."
            if len(str(statement).strip()) < 20:
                errors["statement"] = "Record a meaningful acceptance statement."
            if not evidence:
                errors["evidence"] = "Accepted release gates require uploaded evidence."
            if errors:
                raise serializers.ValidationError(errors)
        return attrs
