from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from governance.services import audit

from . import models as m, serializers as s, services
from .access import organizations, patient_is_valid, require_organization, require_patient_access, require_role


def validated(cls, request):
    serializer = cls(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def model_save(serializer, **extra):
    obj = serializer.Meta.model(**serializer.validated_data, **extra)
    try:
        obj.full_clean()
        obj.save()
    except DjangoValidationError as exc:
        raise ValidationError(getattr(exc, "message_dict", exc.messages))
    return obj


class Pagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 200


class BaseView(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = Pagination
    roles = set()
    model = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        require_role(request.user, self.get_roles())

    def get_roles(self):
        return self.roles

    def get_queryset(self):
        qs = self.model.objects.filter(organization__in=organizations(self.request.user)).order_by("-pk")
        org_id = self.request.query_params.get("organization")
        if org_id:
            org = require_organization(self.request.user, org_id)
            qs = qs.filter(organization=org)
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        organization = serializer.validated_data.get("organization")
        require_organization(request.user, organization.pk, self.roles)
        try:
            with transaction.atomic():
                obj = self.create_record(serializer)
        except IntegrityError:
            raise ValidationError("A conflicting record already exists. Refresh before retrying.")
        services.event(obj, request.user, f"{self.model.__name__.lower()}.created")
        return Response(self.get_serializer(obj).data, status=201)

    def create_record(self, serializer):
        return model_save(serializer, created_by=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        audit(actor=request.user, action="operations.record.read", resource=obj,
              patient=getattr(obj, "patient", None), purpose="operations", request=request)
        return Response(self.get_serializer(obj).data)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        audit(actor=request.user, action="operations.records.listed", resource_type=self.model.__name__, purpose="operations", request=request)
        return response


class AdmissionView(BaseView):
    model, serializer_class = m.Admission, s.AdmissionSerializer
    roles = {"hospital", "doctor", "nurse", "receptionist", "facility_manager"}

    def create_record(self, serializer):
        return services.admit(actor=self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        obj = services.admission_action(self.get_object(), request.user, **validated(s.VersionAction, request))
        return Response(self.get_serializer(obj).data)


class MedicationScheduleView(BaseView):
    model, serializer_class = m.MedicationSchedule, s.MedicationScheduleSerializer
    roles = {"doctor", "nurse", "facility_manager"}

    @action(detail=True, methods=["post"])
    def administer(self, request, pk=None):
        obj = services.record_dose(self.get_object(), request.user, **validated(s.Transition, request))
        return Response(self.get_serializer(obj).data)


class ProcedureView(BaseView):
    model, serializer_class = m.ProcedureBooking, s.ProcedureSerializer
    roles = {"doctor", "nurse", "hospital", "facility_manager"}

    def create_record(self, serializer):
        values = serializer.validated_data
        # Lock the facility as a scheduling mutex; an overlap check alone races.
        type(values["organization"]).objects.select_for_update().get(pk=values["organization"].pk)
        list(User.objects.select_for_update().filter(pk__in=sorted({values["surgeon"].pk, values["patient"].pk})).order_by("pk"))
        require_role(self.request.user, {"doctor", "hospital", "facility_manager"})
        overlap = self.model.objects.filter(starts_at__lt=values["ends_at"], ends_at__gt=values["starts_at"]).exclude(status="cancelled")
        if overlap.filter(Q(organization=values["organization"], theatre=values["theatre"]) | Q(surgeon=values["surgeon"]) | Q(patient=values["patient"])).exists():
            raise ValidationError("The theatre, surgeon or patient already has a booking during this period.")
        return super().create_record(serializer)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        obj = services.procedure_action(self.get_object(), request.user, **validated(s.Transition, request))
        return Response(self.get_serializer(obj).data)


class BatchView(BaseView):
    model, serializer_class = m.MedicineBatch, s.BatchSerializer
    roles = {"pharmacy", "pharmacist", "storekeeper", "facility_manager"}

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("medicine"):
            field = serializers.IntegerField(min_value=1)
            qs = qs.filter(medicine_id=field.run_validation(self.request.query_params["medicine"]))
        return qs

    def create_record(self, serializer):
        from services.models import Medicine
        medicine = Medicine.objects.select_for_update().get(pk=serializer.validated_data["medicine"].pk)
        if not medicine.batches.exists() and medicine.stock:
            raise ValidationError("Reconcile existing untracked stock to zero before enabling batch tracking; then receive it into identified batches.")
        quantity = serializer.validated_data.pop("opening_quantity", 0)
        witness = serializer.validated_data.pop("opening_witness", None)
        batch = super().create_record(serializer)
        if quantity:
            movement = services.move_stock(
                batch, self.request.user, quantity=quantity, kind="received",
                reason="Opening physical stock count", reference=uuid4(), witness=witness,
            )
            batch.quantity = movement.balance
        return batch

    @action(detail=True, methods=["post"])
    def movement(self, request, pk=None):
        movement = services.move_stock(self.get_object(), request.user, **validated(s.MovementInput, request))
        cls = s.serializer_for(m.StockMovement)
        return Response(cls(movement).data)

    @action(detail=True, methods=["get"])
    def register(self, request, pk=None):
        batch = self.get_object()
        cls = s.serializer_for(m.StockMovement)
        page = self.paginate_queryset(batch.movements.order_by("pk"))
        return self.get_paginated_response(cls(page, many=True).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        obj = services.batch_action(self.get_object(), request.user, **validated(s.BatchAction, request))
        return Response(self.get_serializer(obj).data)


class ReferralView(BaseView):
    model, serializer_class = m.ReferralRoute, s.RouteSerializer
    roles = {"doctor", "facility_manager"}

    def get_queryset(self):
        qs = self.model.objects.filter(Q(organization__in=organizations(self.request.user)) | Q(referral__referring_provider=self.request.user)).distinct().order_by("-pk")
        if self.request.query_params.get("organization"):
            org_id = serializers.IntegerField(min_value=1).run_validation(self.request.query_params["organization"])
            qs = qs.filter(organization_id=org_id)
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = model_save(serializer, created_by=request.user)
        services.event(obj, request.user, "referral.routed")
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        obj = services.referral_action(self.get_object(), request.user, **validated(s.ReferralTransition, request))
        return Response(self.get_serializer(obj).data)


class BenefitView(BaseView):
    model, serializer_class = m.BenefitRule, s.BenefitSerializer
    roles = {"insurance", "insurance_officer"}

    @action(detail=True, methods=["patch"])
    @transaction.atomic
    def configure(self, request, pk=None):
        class Input(s.StrictSerializer):
            coverage_percent = serializers.IntegerField(min_value=0, max_value=100, required=False)
            annual_limit = serializers.IntegerField(min_value=0, required=False)
            requires_authorization = serializers.BooleanField(required=False)
            active = serializers.BooleanField(required=False)
        data = validated(Input, request)
        obj = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        for key, value in data.items():
            setattr(obj, key, value)
        obj.save()
        services.event(obj, request.user, "benefit.configured", **data)
        return Response(self.get_serializer(obj).data)


class AuthorizationView(BaseView):
    model, serializer_class = m.Preauthorization, s.AuthorizationSerializer
    roles = {"insurance", "insurance_officer"}

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        obj = services.decide_authorization(self.get_object(), request.user, **validated(s.AuthorizationDecision, request))
        return Response(self.get_serializer(obj).data)


class AssessmentView(BaseView):
    model, serializer_class = m.ClaimAssessment, s.AssessmentSerializer
    roles = {"insurance", "insurance_officer"}

    @action(detail=True, methods=["post"])
    def assess(self, request, pk=None):
        obj = services.assess_claim(self.get_object(), request.user)
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["get"])
    def reconciliation(self, request):
        qs = self.get_queryset().exclude(decision="pending")
        totals = qs.aggregate(covered=Sum("covered_amount"), patient=Sum("patient_amount"))
        return Response({"claim_count": qs.count(), **{key: value or 0 for key, value in totals.items()}})


class PersonView(BaseView):
    model = m.Person
    serializer_class = s.serializer_for(m.Person, ("public_id", "merged_into", "version"))

    def get_queryset(self):
        return self.model.objects.all().order_by("pk")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = model_save(serializer)
        services.event(obj, request.user, "identity.created")
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["get"])
    def candidates(self, request, pk=None):
        person = self.get_object()
        # Suggested matches only; never automatically merge people from demographics.
        candidates = self.model.objects.filter(merged_into__isnull=True, birth_date=person.birth_date, family_name__iexact=person.family_name).exclude(pk=person.pk)
        if person.birth_date is None:
            candidates = candidates.none()
        return Response(self.get_serializer(candidates[:100], many=True).data)

    @action(detail=True, methods=["post"])
    def link(self, request, pk=None):
        class Input(s.StrictSerializer):
            patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role="patient", is_active=True))
        data = validated(Input, request)
        person = self.get_object()
        if person.merged_into_id:
            raise ValidationError("Link the canonical identity instead.")
        identity, created = m.PatientIdentity.objects.get_or_create(patient=data["patient"], defaults={"person": person})
        if identity.person_id != person.pk:
            raise ValidationError("Patient already belongs to another identity.")
        services.event(person, request.user, "identity.linked", patient_id=data["patient"].pk)
        return Response({"id": identity.pk, "person": person.pk, "patient": identity.patient_id}, status=201 if created else 200)

    @action(detail=True, methods=["post"])
    def identifier(self, request, pk=None):
        class Input(s.StrictSerializer):
            system = serializers.CharField(max_length=200)
            value = serializers.CharField(max_length=150)
        person = self.get_object()
        obj = m.PatientIdentifier(person=person, **validated(Input, request))
        try:
            obj.full_clean()
            obj.save()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict)
        services.event(person, request.user, "identity.identifier_added", identifier_id=obj.pk)
        return Response({"id": obj.pk, "system": obj.system, "value": obj.value}, status=201)

    @action(detail=True, methods=["post"])
    def merge(self, request, pk=None):
        class Input(s.StrictSerializer):
            target = serializers.PrimaryKeyRelatedField(queryset=m.Person.objects.all())
            reason = serializers.CharField(max_length=2000)
        obj = services.merge_identity(self.get_object(), actor=request.user, **validated(Input, request))
        return Response({"merge_id": obj.pk, "source": obj.source_id, "target": obj.target_id})

    @action(detail=True, methods=["post"])
    def unmerge(self, request, pk=None):
        class Input(s.StrictSerializer):
            reason = serializers.CharField(max_length=2000)
        obj = get_object_or_404(m.IdentityMerge, source=self.get_object(), reversed_at__isnull=True)
        services.unmerge_identity(obj, actor=request.user, **validated(Input, request))
        return Response({"reversed": True})


class ImagingView(BaseView):
    model, serializer_class = m.ImagingOrder, s.ImagingSerializer
    roles = {"doctor", "lab_technician", "facility_manager"}

    def get_queryset(self):
        qs = self.model.objects.filter(Q(organization__in=organizations(self.request.user)) | Q(referring_doctor=self.request.user)).distinct().order_by("-pk")
        if self.request.query_params.get("organization"):
            org_id = serializers.IntegerField(min_value=1).run_validation(self.request.query_params["organization"])
            qs = qs.filter(organization_id=org_id)
        return qs

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        require_role(request.user, {"doctor"})
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["organization"].status != "verified":
            raise ValidationError("Receiving imaging facility must be verified.")
        obj = model_save(serializer, created_by=request.user)
        services.event(obj, request.user, "imaging.ordered")
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        obj = services.imaging_action(self.get_object(), request.user, **validated(s.ImagingTransition, request))
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["get"])
    def study(self, request, pk=None):
        from .integrations import dicom_study
        record = self.get_object()
        if not record.study_uid:
            raise ValidationError("No acquired study is linked to this order.")
        data = dicom_study(record.study_uid)
        services.event(record, request.user, "imaging.study_read")
        return Response(data)


class RuleView(PersonView):
    model = m.ClinicalRule
    serializer_class = s.serializer_for(m.ClinicalRule, ("active", "approved_by", "submitted_by"))
    # Do not inherit identity actions on a different resource.
    candidates = link = identifier = merge = unmerge = None

    def get_roles(self):
        return {"doctor", "nurse", "pharmacist"} if self.action == "evaluate" else set()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = model_save(serializer, submitted_by=request.user)
        services.event(obj, request.user, "governed_model.submitted")
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        obj = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        if obj.submitted_by_id == request.user.pk:
            raise ValidationError("A different administrator must review and approve this version.")
        if self.model == m.ClinicalRule:
            self.model.objects.filter(code=obj.code, active=True).exclude(pk=obj.pk).update(active=False)
        obj.active, obj.approved_by = True, request.user
        obj.save()
        services.event(obj, request.user, "clinical_rule.approved", version=obj.version)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        obj.active = False
        obj.save()
        services.event(obj, request.user, "clinical_rule.deactivated")
        return Response(self.get_serializer(obj).data)

    @action(detail=False, methods=["post"])
    def evaluate(self, request):
        class Input(s.StrictSerializer):
            medicines = serializers.ListField(child=serializers.CharField(max_length=250), max_length=100)
        result = services.evaluate_medications(validated(Input, request)["medicines"])
        audit(actor=request.user, action="operations.medication_check", purpose="treatment")
        return Response(result)


class OfflineNodeView(BaseView):
    model = m.OfflineNode
    serializer_class = s.serializer_for(m.OfflineNode, ("public_id",))
    roles = {"doctor", "nurse", "facility_manager"}

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        record = services.submit_offline(self.get_object(), request.user, **validated(s.OfflineInput, request))
        return Response({"id": record.pk, "change_id": str(record.change_id), "status": record.status}, status=201)

    @action(detail=True, methods=["get"])
    def changes(self, request, pk=None):
        qs = m.OfflineChange.objects.filter(node=self.get_object()).order_by("id")
        cls = s.serializer_for(m.OfflineChange, exclude=("encrypted_payload",))
        return self.get_paginated_response(cls(self.paginate_queryset(qs), many=True).data)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        import json
        require_role(request.user, {"doctor", "nurse"})
        node = self.get_object()
        change_id = serializers.IntegerField(min_value=1).run_validation(request.query_params.get("change"))
        record = get_object_or_404(m.OfflineChange, node=node, pk=change_id)
        payload = json.loads(services.offline_cipher().decrypt(bytes(record.encrypted_payload)))
        services.event(node, request.user, "offline.previewed", change_id=str(record.change_id))
        return Response({"change": record.pk, "patient": record.patient_id, "kind": record.kind, "payload": payload})

    @action(detail=True, methods=["post"], url_path="review")
    def review_change(self, request, pk=None):
        class Input(s.StrictSerializer):
            change = serializers.IntegerField(min_value=1)
            decision = serializers.ChoiceField(choices=["apply", "reject"])
            reason = serializers.CharField(max_length=2000)
        data = validated(Input, request)
        record = get_object_or_404(m.OfflineChange, node=self.get_object(), pk=data.pop("change"))
        services.review_offline(record, request.user, **data)
        return Response({"id": record.pk, "status": m.OfflineChange.objects.get(pk=record.pk).status})


class DocumentView(BaseView):
    model = m.PrivateDocument
    roles = {"doctor", "nurse", "hospital", "facility_manager", "lab_technician"}
    serializer_class = s.serializer_for(m.PrivateDocument, ("filename", "sha256", "status", "scanned_at", "scan_detail"), exclude=("file",))

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        from pathlib import Path
        import hashlib
        import uuid
        from django.conf import settings
        from django.core.files.base import ContentFile
        from .integrations import scan_bytes
        class Input(s.StrictSerializer):
            organization = serializers.IntegerField(min_value=1)
            patient = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role="patient"), required=False)
            file = serializers.FileField()
        data = validated(Input, request)
        organization = require_organization(request.user, data["organization"], self.roles)
        if data.get("patient"):
            require_patient_access(request.user, data["patient"])
        upload = data["file"]
        if upload.size > settings.PRIVATE_DOCUMENT_MAX_BYTES:
            raise ValidationError("Document exceeds the upload size limit.")
        content = upload.read(settings.PRIVATE_DOCUMENT_MAX_BYTES + 1)
        if len(content) > settings.PRIVATE_DOCUMENT_MAX_BYTES:
            raise ValidationError("Document exceeds the upload size limit.")
        clean = scan_bytes(content)  # Fail closed if scanning is not available.
        if not clean:
            raise ValidationError("Document failed malware scanning.")
        name = Path(upload.name).name[:180]
        obj = m.PrivateDocument(organization=organization, created_by=request.user, patient=data.get("patient"),
            filename=name, sha256=hashlib.sha256(content).hexdigest(), status="clean", scanned_at=timezone.now())
        obj.file.save(f"{uuid.uuid4().hex}.bin", ContentFile(content), save=False)
        try:
            obj.save()
        except Exception:
            obj.file.delete(save=False)
            raise
        services.event(obj, request.user, "document.uploaded")
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        from .integrations import private_download
        obj = self.get_object()
        if obj.patient_id:
            require_patient_access(request.user, obj.patient)
        if obj.status != "clean":
            raise PermissionDenied("Document has not passed scanning.")
        services.event(obj, request.user, "document.downloaded")
        return private_download(obj)

    @action(detail=True, methods=["post"], url_path="access-link")
    def access_link(self, request, pk=None):
        from django.core import signing
        obj = self.get_object()
        if obj.patient_id:
            require_patient_access(request.user, obj.patient)
        if obj.status != "clean":
            raise PermissionDenied("Document has not passed scanning.")
        ticket = signing.dumps({"document": obj.pk, "user": request.user.pk}, salt="private-document-access")
        services.event(obj, request.user, "document.link_issued")
        return Response({"url": request.build_absolute_uri(f"/api/v1/operations/document-access/?ticket={ticket}"), "expires_in": 60})


class ResearchView(PersonView):
    model = m.ResearchExport
    serializer_class = s.serializer_for(m.ResearchExport, ("requested_by", "status", "approved_by", "approved_at", "data"))
    candidates = link = identifier = merge = unmerge = None

    def create_record(self, serializer):
        return model_save(serializer, requested_by=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = self.create_record(serializer)
        services.event(obj, request.user, "research.requested")
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def approve(self, request, pk=None):
        from .integrations import research_aggregate
        obj = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        if obj.requested_by_id == request.user.pk:
            raise ValidationError("Research requests require approval by a different administrator.")
        if obj.status != "requested":
            raise ValidationError("Export is already resolved.")
        obj.data = research_aggregate()
        obj.status, obj.approved_by, obj.approved_at = "approved", request.user, timezone.now()
        obj.save()
        services.event(obj, request.user, "research.approved")
        return Response(self.get_serializer(obj).data)


class CopilotModelView(RuleView):
    model = m.CopilotModel
    serializer_class = s.serializer_for(m.CopilotModel, ("active", "approved_by", "submitted_by"))
    evaluate = None

    def create(self, request, *args, **kwargs):
        from django.conf import settings
        if request.data.get("adapter") not in settings.COPILOT_ALLOWED_ADAPTERS or request.data.get("intended_use", "administrative_draft") != "administrative_draft":
            raise ValidationError("Only configured administrative drafting adapters are supported.")
        return super().create(request, *args, **kwargs)


class CopilotDraftView(PersonView):
    model = m.CopilotDraft
    roles = {"doctor", "facility_manager"}
    serializer_class = s.serializer_for(m.CopilotDraft, ("author", "output", "status", "reviewed_by", "review_note"))
    candidates = link = identifier = merge = unmerge = None

    def get_queryset(self):
        qs = self.model.objects.all()
        if self.request.user.role != "admin":
            qs = qs.filter(author=self.request.user)
        return qs.order_by("-pk")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        from .integrations import generate_draft
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model = serializer.validated_data["model"]
        if not model.active or not model.approved_by_id:
            raise ValidationError("Model has not been approved for use.")
        text = serializer.validated_data["source_text"]
        if len(text) > 20000:
            raise ValidationError("Source text exceeds the drafting limit.")
        output = generate_draft(model, text)
        obj = model_save(serializer, author=request.user, output=output)
        services.event(obj, request.user, "copilot.drafted", model_version=model.version)
        return Response(self.get_serializer(obj).data, status=201)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def review(self, request, pk=None):
        class Input(s.StrictSerializer):
            decision = serializers.ChoiceField(choices=["accepted", "rejected"])
            note = serializers.CharField(max_length=5000)
        data = validated(Input, request)
        obj = self.model.objects.select_for_update().get(pk=self.get_object().pk)
        if obj.status != "draft":
            raise ValidationError("Draft is already reviewed.")
        obj.status, obj.review_note, obj.reviewed_by = data["decision"], data["note"], request.user
        obj.save()
        services.event(obj, request.user, "copilot.reviewed", decision=obj.status)
        # Accepted drafts never write into signed clinical records.
        return Response(self.get_serializer(obj).data)
