from datetime import timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from accounts.models import User
from appointments.models import Appointment
from governance.models import Consent
from governance.services import audit, current_consent
from interoperability.fhir import patient_summary_bundle

from . import integrations
from .access import require_patient_access, require_role
from .models import VideoQualityEvent, VideoSession
from .serializers import StrictSerializer
from .views import validated


class DocumentAccess(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        from django.core import signing
        from .access import require_organization
        from .models import PrivateDocument
        try:
            data = signing.loads(request.query_params.get("ticket", ""), salt="private-document-access", max_age=60)
        except signing.BadSignature:
            raise PermissionDenied("Document link is invalid or expired.")
        user = get_object_or_404(User, pk=data["user"], is_active=True)
        document = get_object_or_404(PrivateDocument, pk=data["document"], status="clean")
        require_organization(user, document.organization_id)
        if document.patient_id:
            require_patient_access(user, document.patient)
        audit(actor=user, patient=document.patient, action="operations.document.downloaded", resource=document, purpose="operations")
        return integrations.private_download(document)


class NotificationCallback(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        import hashlib
        import hmac
        import time
        from communication.models import NotificationDelivery
        secret = settings.NOTIFICATION_CALLBACK_SECRET
        timestamp = request.headers.get("X-MyDoctor-Timestamp", "")
        signature = request.headers.get("X-MyDoctor-Signature", "")
        try:
            valid_time = abs(time.time() - int(timestamp)) <= 300
        except ValueError:
            valid_time = False
        expected = hmac.new(secret.encode(), timestamp.encode() + b"." + request.body, hashlib.sha256).hexdigest()
        if not secret or not valid_time or not hmac.compare_digest(signature, expected):
            raise PermissionDenied("Invalid delivery callback signature.")
        class Input(StrictSerializer):
            provider_reference = serializers.CharField(max_length=180)
            status = serializers.ChoiceField(choices=["delivered", "failed"])
        data = validated(Input, request)
        delivery = NotificationDelivery.objects.select_for_update().filter(provider_reference=data["provider_reference"]).exclude(provider_reference="").first()
        if delivery is None:
            return Response({"accepted": True})
        if delivery.status in {"sent", "processing"}:
            delivery.status = data["status"]
            delivery.last_error = "Provider reported unsuccessful delivery." if data["status"] == "failed" else ""
            delivery.save(update_fields=["status", "last_error"])
        return Response({"accepted": True})


class TerminologyLookup(APIView):
    def get(self, request):
        require_role(request.user, {"doctor", "nurse", "pharmacist", "lab_technician"})
        class Input(StrictSerializer):
            system = serializers.URLField(max_length=300)
            code = serializers.CharField(max_length=120)
            version = serializers.CharField(max_length=80, required=False, default="")
        serializer = Input(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(integrations.terminology_lookup(**serializer.validated_data))


class OperationsContext(APIView):
    def get(self, request):
        from django.db.models import Q
        from .access import organizations
        from registry.models import PractitionerRole
        from workforce.models import PatientVisit, StaffMembership
        from services.models import Bed, InsuranceClaim, InsurancePolicy, Medicine, PatientCoverage, Supplier
        require_role(request.user, {"doctor", "nurse", "facility_manager", "hospital", "lab_technician", "pharmacy", "pharmacist", "storekeeper", "insurance", "insurance_officer"})
        scoped = organizations(request.user).select_related("parent_facility")
        org_id = request.query_params.get("organization")
        if org_id:
            from .access import require_organization
            scoped = scoped.filter(pk=require_organization(request.user, org_id).pk)
        member_ids = StaffMembership.objects.filter(organization__in=scoped, status="active").values("user_id")
        practitioner_ids = PractitionerRole.objects.filter(organization__in=scoped, active=True).values("practitioner_id")
        doctors = User.objects.filter(Q(pk__in=member_ids) | Q(pk__in=practitioner_ids), role="doctor", is_verified=True, is_active=True)
        beds = Bed.objects.filter(hospital_id__in=scoped.filter(organization_type="hospital").values("owner_id"))
        audit(actor=request.user, action="operations.context.read", purpose="operations", request=request)
        patient_search = request.query_params.get("patient_search")
        if patient_search is not None:
            require_role(request.user, {"doctor", "nurse", "facility_manager", "hospital"})
            if not org_id:
                raise serializers.ValidationError({"organization": "Select a facility to search its patients."})
            visit_patients = PatientVisit.objects.filter(organization__in=scoped).exclude(
                status=PatientVisit.Status.CANCELLED
            ).values("patient_id")
            patients = User.objects.filter(pk__in=visit_patients, role="patient", is_active=True)
            for term in patient_search.strip()[:120].split():
                patients = patients.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term))
            audit(actor=request.user, action="operations.patient_lookup", purpose="care", request=request)
            return Response({"patients": [
                {"id": patient.pk, "name": patient.display_name}
                for patient in patients.order_by("last_name", "first_name", "pk")[:50]
            ]})
        return Response({
            "organizations": [{
                "id": org.pk, "name": org.legal_name, "type": org.organization_type,
                "parent_facility_name": org.parent_facility.legal_name if org.parent_facility else None,
            } for org in scoped],
            "doctors": [{"id": user.pk, "name": user.display_name} for user in doctors],
            "beds": [{"id": bed.pk, "name": f"{bed.ward} / {bed.label}", "is_occupied": bed.is_occupied} for bed in beds],
            "can_prescribe": request.user.role in {"doctor", "admin"},
            "can_administer": request.user.role in {"doctor", "nurse", "admin"},
            "can_review_offline": request.user.role in {"doctor", "nurse", "admin"},
            "can_close_referrals": request.user.role in {"doctor", "admin"},
            "can_acquire_imaging": request.user.role in {"doctor", "lab_technician", "admin"},
            "can_report_imaging": request.user.role in {"doctor", "admin"},
            "can_discharge": request.user.role in {"doctor", "admin"},
            "medicines": [{"id": med.pk, "name": med.name} for med in Medicine.objects.filter(pharmacy_id__in=scoped.values("owner_id"))[:200]],
            "pharmacy_suppliers": [
                {"id": supplier.pk, "name": supplier.suppliername}
                for supplier in Supplier.objects.filter(pharmacy_id__in=scoped.values("owner_id")).order_by("suppliername", "pk")
            ],
            "policies": [{"id": policy.pk, "name": policy.name} for policy in InsurancePolicy.objects.filter(provider_id__in=scoped.values("owner_id"))[:200]],
            "coverages": [{"id": coverage.pk, "name": f"{coverage.member_id} — {coverage.patient.display_name}"} for coverage in PatientCoverage.objects.filter(provider_id__in=scoped.values("owner_id"), active=True).select_related("patient")[:200]],
            "claims": [{"id": claim.pk, "name": f"#{claim.pk} — {claim.patient.display_name}"} for claim in InsuranceClaim.objects.filter(provider_id__in=scoped.values("owner_id"), status="submitted").select_related("patient")[:200]],
            "copilot_adapters": settings.COPILOT_ALLOWED_ADAPTERS if request.user.role == "admin" else [],
        })


class TerminologyExpand(APIView):
    def get(self, request):
        require_role(request.user, {"doctor", "nurse", "pharmacist", "lab_technician"})
        class Input(StrictSerializer):
            url = serializers.URLField(max_length=300)
            query = serializers.CharField(max_length=120, required=False, default="", allow_blank=True)
        serializer = Input(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return Response(integrations.terminology_expand(**serializer.validated_data))


class HIEExport(APIView):
    def post(self, request, patient_id):
        require_role(request.user, {"doctor"})
        patient = get_object_or_404(User, pk=patient_id, role="patient")
        require_patient_access(request.user, patient)
        if not current_consent(patient, [Consent.Type.DATA_SHARING], recipient=request.user):
            raise PermissionDenied("Active data-sharing consent is required for external export.")
        # This adapter exports only the existing summary contract. It is not a national-HIE certification.
        result = integrations.request_json("POST", settings.HIE_SERVER_URL, token=settings.HIE_SERVER_TOKEN,
            data=patient_summary_bundle(patient, viewer=request.user), headers={"Content-Type": "application/fhir+json"})
        audit(actor=request.user, patient=patient, action="operations.hie.exported", purpose="data_sharing", request=request)
        return Response({"accepted": True, "receipt": result})


def video_session(user, pk):
    appointment = get_object_or_404(Appointment, pk=pk)
    if user.pk not in {appointment.patient_id, appointment.doctor_id}:
        raise PermissionDenied("Not an appointment participant.")
    if appointment.status != "confirmed":
        raise ValidationError("Appointment is not confirmed.")
    if not appointment.doctor.is_verified:
        raise PermissionDenied("Clinician verification is required.")
    session, _ = VideoSession.objects.get_or_create(appointment=appointment)
    if session.ended_at:
        raise ValidationError("Video session has ended.")
    return session


def video_join(user, pk):
    import jwt
    session = video_session(user, pk)
    base = settings.JITSI_BASE_URL.rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "https":
        raise integrations.IntegrationUnavailable("The video service must use HTTPS.")
    room = f"mydoctor-{session.room_id}"
    result = {"room": room, "url": f"{base}/{room}", "recording_allowed": session.patient_recording_consent and session.doctor_recording_consent}
    if settings.JITSI_JWT_SECRET and settings.JITSI_APP_ID:
        now = timezone.now()
        token = jwt.encode({"aud": "jitsi", "iss": settings.JITSI_APP_ID, "sub": parsed.hostname,
            "room": room, "iat": int(now.timestamp()), "nbf": int(now.timestamp()) - 5,
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "context": {"user": {"id": str(user.pk), "name": "MyDoctor participant", "moderator": user.role == "doctor"},
                        "features": {"recording": result["recording_allowed"]}}}, settings.JITSI_JWT_SECRET, algorithm="HS256")
        result["jwt"] = token
        result["url"] += f"?jwt={token}"
    elif not settings.DEBUG:
        raise integrations.IntegrationUnavailable("Private video authentication is not configured.")
    audit(actor=user, patient=session.appointment.patient, action="operations.video.joined", resource=session, purpose="telemedicine")
    return result


class VideoControl(APIView):
    def get(self, request, pk):
        return Response(video_join(request.user, pk))

    @transaction.atomic
    def post(self, request, pk):
        class Input(StrictSerializer):
            action = serializers.ChoiceField(choices=["recording_consent", "quality", "end"])
            consent = serializers.BooleanField(required=False)
            packet_loss = serializers.FloatField(min_value=0, max_value=100, required=False)
            round_trip_ms = serializers.IntegerField(min_value=0, max_value=60000, required=False)
        data = validated(Input, request)
        session = video_session(request.user, pk)
        session = VideoSession.objects.select_for_update().get(pk=session.pk)
        if data["action"] == "recording_consent":
            if "consent" not in data:
                raise ValidationError("consent is required.")
            field = "patient_recording_consent" if request.user.pk == session.appointment.patient_id else "doctor_recording_consent"
            setattr(session, field, data["consent"])
            session.save()
        elif data["action"] == "quality":
            if "packet_loss" not in data or "round_trip_ms" not in data:
                raise ValidationError("Packet loss and round-trip time are required.")
            VideoQualityEvent.objects.create(session=session, actor=request.user, packet_loss=data["packet_loss"], round_trip_ms=data["round_trip_ms"])
        else:
            require_role(request.user, {"doctor"})
            session.ended_at = timezone.now()
            session.save()
        audit(actor=request.user, patient=session.appointment.patient, action=f"operations.video.{data['action']}", resource=session, metadata={"consent": data.get("consent")}, purpose="telemedicine")
        return Response({"ended": bool(session.ended_at), "recording_allowed": session.patient_recording_consent and session.doctor_recording_consent})
