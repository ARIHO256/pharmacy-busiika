from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole
from appointments.models import Appointment
from governance.models import AuditEvent
from governance.services import audit

from .models import (
    Allergy,
    CarePlan,
    ClinicalEncounter,
    Condition,
    MedicationStatement,
    Observation,
    Referral,
)
from .serializers import (
    AllergySerializer,
    CarePlanSerializer,
    ClinicalEncounterSerializer,
    EncounterAmendSerializer,
    ConditionSerializer,
    MedicationStatementSerializer,
    ObservationSerializer,
    ReferralSerializer,
)
from .services import resolve_patient_access

User = get_user_model()


def _patient_from_request(request):
    if request.user.role == User.Role.PATIENT:
        return request.user
    patient_id = request.query_params.get("patient_id") or request.data.get("patient_id")
    if not patient_id:
        return None
    return get_object_or_404(User, pk=patient_id, role=User.Role.PATIENT)


def _authorize(request, patient):
    if patient is None:
        return Response({"detail": "patient_id is required."}, status=400)
    allowed, _emergency, reason = resolve_patient_access(request, patient)
    if not allowed:
        return Response({"detail": reason}, status=403)
    return None


def _verification_for(user):
    return "clinician_verified" if user.role == User.Role.DOCTOR else "patient_reported"


class HealthSummaryView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]

    def get(self, request):
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        latest_observations = []
        seen = set()
        for obs in Observation.objects.filter(patient=patient).order_by("-observed_at"):
            key = obs.code or obs.display.lower()
            if key in seen:
                continue
            seen.add(key)
            latest_observations.append(obs)
            if len(latest_observations) >= 8:
                break
        return Response(
            {
                "patient": {
                    "id": patient.id,
                    "name": f"{patient.first_name} {patient.last_name}".strip() or patient.email,
                    "email": patient.email,
                    "phone": patient.phone,
                },
                "allergies": AllergySerializer(
                    Allergy.objects.filter(patient=patient, status=Allergy.Status.ACTIVE), many=True
                ).data,
                "conditions": ConditionSerializer(
                    Condition.objects.filter(patient=patient).exclude(
                        clinical_status=Condition.ClinicalStatus.RESOLVED
                    ),
                    many=True,
                ).data,
                "medications": MedicationStatementSerializer(
                    MedicationStatement.objects.filter(
                        patient=patient, status=MedicationStatement.Status.ACTIVE
                    ),
                    many=True,
                ).data,
                "latest_observations": ObservationSerializer(latest_observations, many=True).data,
                "active_care_plans": CarePlanSerializer(
                    CarePlan.objects.filter(patient=patient, status=CarePlan.Status.ACTIVE), many=True
                ).data,
                "open_referrals": ReferralSerializer(
                    Referral.objects.filter(patient=patient).exclude(
                        status__in=[Referral.Status.COMPLETED, Referral.Status.CANCELLED]
                    ),
                    many=True,
                ).data,
            }
        )


class TimelineView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]

    def get(self, request):
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        events = []
        for encounter in ClinicalEncounter.objects.filter(patient=patient).select_related("doctor"):
            events.append(
                {
                    "id": f"encounter-{encounter.id}",
                    "type": "encounter",
                    "title": "Clinical consultation",
                    "subtitle": encounter.assessment or encounter.chief_complaint,
                    "status": encounter.status,
                    "occurred_at": encounter.signed_at or encounter.created_at,
                    "source_id": encounter.id,
                }
            )
        for obs in Observation.objects.filter(patient=patient):
            value = obs.value_text or (
                f"{obs.value_numeric} {obs.unit}" if obs.value_numeric is not None else ""
            )
            events.append(
                {
                    "id": f"observation-{obs.id}",
                    "type": "observation",
                    "title": obs.display,
                    "subtitle": value.strip(),
                    "status": obs.interpretation,
                    "occurred_at": obs.observed_at,
                    "source_id": obs.id,
                }
            )
        for referral in Referral.objects.filter(patient=patient):
            events.append(
                {
                    "id": f"referral-{referral.id}",
                    "type": "referral",
                    "title": f"Referral to {referral.target_specialty}",
                    "subtitle": referral.reason,
                    "status": referral.status,
                    "occurred_at": referral.created_at,
                    "source_id": referral.id,
                }
            )
        try:
            from prescriptions.models import Prescription

            for rx in Prescription.objects.filter(patient=patient):
                events.append(
                    {
                        "id": f"prescription-{rx.id}",
                        "type": "prescription",
                        "title": "Prescription issued",
                        "subtitle": rx.notes,
                        "status": "issued",
                        "occurred_at": rx.created_at,
                        "source_id": rx.id,
                    }
                )
        except Exception:
            pass
        events.sort(key=lambda event: event["occurred_at"], reverse=True)
        return Response(events[:300])


class PatientRecordListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]
    model = None
    serializer_class = None

    def get_queryset(self, patient):
        return self.model.objects.filter(patient=patient)

    def get(self, request):
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        return Response(self.serializer_class(self.get_queryset(patient), many=True).data)

    def post(self, request):
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        extras = {"patient": patient, "recorded_by": request.user}
        if self.model in (Allergy, Condition):
            extras["verification"] = _verification_for(request.user)
        if self.model is MedicationStatement:
            extras["source"] = (
                "clinician_documented"
                if request.user.role == User.Role.DOCTOR
                else "patient_reported"
            )
        obj = serializer.save(**extras)
        audit(
            actor=request.user,
            patient=patient,
            action=f"clinical.{self.model.__name__.lower()}.created",
            resource=obj,
            purpose="treatment",
            decision=AuditEvent.Decision.ALLOW,
            request=request,
        )
        return Response(self.serializer_class(obj).data, status=status.HTTP_201_CREATED)


class PatientRecordDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]
    model = None
    serializer_class = None

    def patch(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        denied = _authorize(request, obj.patient)
        if denied:
            return denied
        if request.user.role == User.Role.PATIENT and obj.recorded_by_id not in [None, request.user.id]:
            return Response(
                {"detail": "A clinician-authored record cannot be overwritten by the patient. Request a correction."},
                status=409,
            )
        serializer = self.serializer_class(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        audit(
            actor=request.user,
            patient=obj.patient,
            action=f"clinical.{self.model.__name__.lower()}.updated",
            resource=obj,
            purpose="treatment",
            request=request,
        )
        return Response(self.serializer_class(obj).data)


class AllergyListCreateView(PatientRecordListCreateView):
    model = Allergy
    serializer_class = AllergySerializer


class AllergyDetailView(PatientRecordDetailView):
    model = Allergy
    serializer_class = AllergySerializer


class ConditionListCreateView(PatientRecordListCreateView):
    model = Condition
    serializer_class = ConditionSerializer


class ConditionDetailView(PatientRecordDetailView):
    model = Condition
    serializer_class = ConditionSerializer


class MedicationListCreateView(PatientRecordListCreateView):
    model = MedicationStatement
    serializer_class = MedicationStatementSerializer


class MedicationDetailView(PatientRecordDetailView):
    model = MedicationStatement
    serializer_class = MedicationStatementSerializer


class ObservationListCreateView(PatientRecordListCreateView):
    model = Observation
    serializer_class = ObservationSerializer

    def get_queryset(self, patient):
        qs = super().get_queryset(patient)
        category = self.request.query_params.get("category")
        return qs.filter(category=category) if category else qs


class EncounterListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]

    def get(self, request):
        if request.user.role == User.Role.PATIENT:
            qs = ClinicalEncounter.objects.filter(patient=request.user).exclude(
                status=ClinicalEncounter.Status.DRAFT
            )
        elif request.user.role == User.Role.DOCTOR:
            qs = ClinicalEncounter.objects.filter(doctor=request.user)
            patient_id = request.query_params.get("patient_id")
            if patient_id:
                patient = get_object_or_404(User, pk=patient_id, role=User.Role.PATIENT)
                denied = _authorize(request, patient)
                if denied:
                    return denied
                qs = qs.filter(patient=patient)
        else:
            qs = ClinicalEncounter.objects.all()
        return Response(
            ClinicalEncounterSerializer(
                qs.select_related("patient", "doctor", "appointment").prefetch_related("revisions"),
                many=True,
            ).data
        )

    @transaction.atomic
    def post(self, request):
        if request.user.role != User.Role.DOCTOR:
            return Response({"detail": "Only doctors can create encounters."}, status=403)
        appointment_id = request.data.get("appointment")
        appointment = get_object_or_404(
            Appointment,
            pk=appointment_id,
            doctor=request.user,
        )
        if appointment.status not in [
            Appointment.Status.CONFIRMED,
            Appointment.Status.COMPLETED,
        ]:
            return Response(
                {"detail": "Encounter requires a confirmed or completed appointment."},
                status=400,
            )
        denied = _authorize(request, appointment.patient)
        if denied:
            return denied
        encounter, created = ClinicalEncounter.objects.get_or_create(
            appointment=appointment,
            defaults={
                "patient": appointment.patient,
                "doctor": request.user,
                "chief_complaint": appointment.reason,
            },
        )
        if not created and encounter.status == ClinicalEncounter.Status.FINAL:
            return Response(
                {"detail": "Finalized encounter cannot be edited. Create an amendment."},
                status=409,
            )
        serializer = ClinicalEncounterSerializer(
            encounter, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        encounter = serializer.save()
        audit(
            actor=request.user,
            patient=appointment.patient,
            action="clinical.encounter.created" if created else "clinical.encounter.updated",
            resource=encounter,
            purpose="treatment",
            request=request,
        )
        return Response(
            ClinicalEncounterSerializer(encounter).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class EncounterDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]

    def get(self, request, pk):
        encounter = get_object_or_404(ClinicalEncounter, pk=pk)
        denied = _authorize(request, encounter.patient)
        if denied:
            return denied
        if request.user.role == User.Role.PATIENT and encounter.status == ClinicalEncounter.Status.DRAFT:
            return Response({"detail": "Draft note is not available to the patient."}, status=403)
        return Response(ClinicalEncounterSerializer(encounter).data)

    def patch(self, request, pk):
        encounter = get_object_or_404(ClinicalEncounter, pk=pk)
        if request.user.id != encounter.doctor_id:
            return Response({"detail": "Only the authoring doctor can edit this note."}, status=403)
        denied = _authorize(request, encounter.patient)
        if denied:
            return denied
        if encounter.status == ClinicalEncounter.Status.FINAL:
            return Response({"detail": "Final note is immutable. Use amendment."}, status=409)
        serializer = ClinicalEncounterSerializer(
            encounter, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        encounter = serializer.save()
        audit(
            actor=request.user,
            patient=encounter.patient,
            action="clinical.encounter.updated",
            resource=encounter,
            purpose="treatment",
            request=request,
        )
        return Response(ClinicalEncounterSerializer(encounter).data)


class EncounterFinalizeView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["doctor"]

    def post(self, request, pk):
        encounter = get_object_or_404(ClinicalEncounter, pk=pk, doctor=request.user)
        denied = _authorize(request, encounter.patient)
        if denied:
            return denied
        try:
            encounter.finalize(request.user)
        except DjangoValidationError as exc:
            return Response({"detail": "; ".join(exc.messages)}, status=400)
        if encounter.appointment.status != Appointment.Status.COMPLETED:
            encounter.appointment.status = Appointment.Status.COMPLETED
            encounter.appointment.save(update_fields=["status"])
        audit(
            actor=request.user,
            patient=encounter.patient,
            action="clinical.encounter.finalized",
            resource=encounter,
            purpose="treatment",
            request=request,
        )
        try:
            from interoperability.services import emit_event

            emit_event(
                "clinical.encounter.finalized", encounter,
                {
                    "appointment_id": encounter.appointment_id,
                    "patient_id": encounter.patient_id,
                    "doctor_id": encounter.doctor_id,
                    "version": encounter.version,
                    "signed_at": encounter.signed_at.isoformat() if encounter.signed_at else None,
                },
                actor=request.user, patient=encounter.patient, request=request,
            )
        except Exception:
            pass
        return Response(ClinicalEncounterSerializer(encounter).data)


class EncounterAmendView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["doctor"]

    @transaction.atomic
    def post(self, request, pk):
        encounter = get_object_or_404(ClinicalEncounter, pk=pk, doctor=request.user)
        denied = _authorize(request, encounter.patient)
        if denied:
            return denied
        serializer = EncounterAmendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        reason = data.pop("reason")
        try:
            encounter.amend(request.user, reason, data)
        except DjangoValidationError as exc:
            return Response({"detail": "; ".join(exc.messages)}, status=400)
        audit(
            actor=request.user,
            patient=encounter.patient,
            action="clinical.encounter.amended",
            resource=encounter,
            purpose="treatment",
            metadata={"version": encounter.version, "reason": reason},
            request=request,
        )
        try:
            from interoperability.services import emit_event

            emit_event(
                "clinical.encounter.amended",
                encounter,
                {
                    "appointment_id": encounter.appointment_id,
                    "patient_id": encounter.patient_id,
                    "doctor_id": encounter.doctor_id,
                    "version": encounter.version,
                    "reason": reason,
                },
                actor=request.user,
                patient=encounter.patient,
                request=request,
            )
        except Exception:
            pass
        return Response(ClinicalEncounterSerializer(encounter).data)


class ReferralListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]

    def get(self, request):
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        return Response(ReferralSerializer(Referral.objects.filter(patient=patient), many=True).data)

    def post(self, request):
        if request.user.role != User.Role.DOCTOR:
            return Response({"detail": "Only doctors can create referrals."}, status=403)
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        serializer = ReferralSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        referral = serializer.save(patient=patient, referring_provider=request.user)
        audit(
            actor=request.user,
            patient=patient,
            action="clinical.referral.created",
            resource=referral,
            purpose="treatment",
            request=request,
        )
        return Response(ReferralSerializer(referral).data, status=201)


class CarePlanListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", "doctor", "admin"]

    def get(self, request):
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        return Response(CarePlanSerializer(CarePlan.objects.filter(patient=patient), many=True).data)

    def post(self, request):
        if request.user.role != User.Role.DOCTOR:
            return Response({"detail": "Only doctors can create care plans."}, status=403)
        patient = _patient_from_request(request)
        denied = _authorize(request, patient)
        if denied:
            return denied
        serializer = CarePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save(patient=patient, author=request.user)
        audit(
            actor=request.user,
            patient=patient,
            action="clinical.care_plan.created",
            resource=plan,
            purpose="treatment",
            request=request,
        )
        return Response(CarePlanSerializer(plan).data, status=201)
