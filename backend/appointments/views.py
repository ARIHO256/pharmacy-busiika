import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole, request_role
from accounts.professionals import professional_is_verified
from accounts.roles import BOOKABLE_PROVIDER_ROLES
from enterprise.access import active_role

from .models import Appointment, AppointmentStatusHistory, Availability
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AvailabilitySerializer,
)
from .services import find_slot

User = get_user_model()


def _doctor_is_verified(user):
    # Backward-compatible name used throughout the appointment module.
    return professional_is_verified(user, require_bookable=True)


def _managed_patient(user, patient_id=None, permission="can_book"):
    """Resolve the user's own patient identity or an active delegated patient."""
    if active_role(user) != User.Role.PATIENT:
        return None
    if not patient_id or str(patient_id) == str(user.pk):
        return user
    from accounts.models import PatientRelationship

    relationship = (
        PatientRelationship.objects.select_related("patient")
        .filter(
            caregiver=user,
            patient_id=patient_id,
            status=PatientRelationship.Status.ACTIVE,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        .first()
    )
    if relationship is None or not getattr(relationship, permission, False):
        return None
    return relationship.patient


def _can_manage_appointment(user, appointment):
    if appointment.patient_id == user.id:
        return True
    return _managed_patient(user, appointment.patient_id, "can_book") is not None


def _notify(user, title, body, kind="reminder"):
    try:
        from communication.services import notify

        notify(user, title, body, kind)
    except Exception:
        return None


def _create_care_relationship(appointment, actor=None):
    from registry.models import CareRelationship

    relationship, _ = CareRelationship.objects.get_or_create(
        patient=appointment.patient,
        practitioner=appointment.doctor,
        appointment=appointment,
        defaults={
            "relationship_type": CareRelationship.Type.TREATMENT,
            "purpose": "treatment",
            "created_by": actor,
        },
    )
    return relationship


def _audit(request, action, appointment, decision="n/a", metadata=None):
    try:
        from governance.services import audit

        audit(
            actor=request.user,
            patient=appointment.patient,
            action=action,
            resource=appointment,
            purpose="treatment",
            decision=decision,
            metadata=metadata or {},
            request=request,
        )
    except Exception:
        return None


class AvailabilityListCreateView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(BOOKABLE_PROVIDER_ROLES)

    def get(self, request):
        rows = Availability.objects.filter(doctor=request.user)
        return Response(AvailabilitySerializer(rows, many=True).data)

    def post(self, request):
        if not _doctor_is_verified(request.user):
            return Response({"detail": "Your professional profile must be verified before publishing availability."}, status=403)
        serializer = AvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = serializer.save(doctor=request.user)
        except IntegrityError:
            return Response({"detail": "This availability window already exists."}, status=409)
        return Response(AvailabilitySerializer(row).data, status=status.HTTP_201_CREATED)


class AvailabilityDetailView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(BOOKABLE_PROVIDER_ROLES)

    def get_object(self, request, pk):
        return get_object_or_404(Availability, pk=pk, doctor=request.user)

    def put(self, request, pk):
        row = self.get_object(request, pk)
        serializer = AvailabilitySerializer(row, data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(AvailabilitySerializer(serializer.save()).data)

    def patch(self, request, pk):
        row = self.get_object(request, pk)
        serializer = AvailabilitySerializer(row, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(AvailabilitySerializer(serializer.save()).data)

    def delete(self, request, pk):
        row = self.get_object(request, pk)
        row.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorSlotsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, doctor_id):
        date_param = request.query_params.get("date")
        if not date_param:
            return Response(
                {"detail": "date query parameter is required (YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            date = datetime.date.fromisoformat(date_param)
        except ValueError:
            return Response(
                {"detail": "Invalid date format, expected YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        doctor = get_object_or_404(User, pk=doctor_id, role__in=BOOKABLE_PROVIDER_ROLES)
        if not _doctor_is_verified(doctor):
            return Response({"detail": "Professional is not available for public booking."}, status=404)
        from .services import compute_free_slots

        return Response({"date": date.isoformat(), "slots": compute_free_slots(doctor, date)})


class AppointmentListCreateView(APIView):
    def get_permissions(self):
        self.allowed_roles = ["patient"] if self.request.method == "POST" else ["patient", *sorted(BOOKABLE_PROVIDER_ROLES)]
        return [IsRole()]

    def get(self, request):
        if request_role(request) in BOOKABLE_PROVIDER_ROLES:
            qs = Appointment.objects.filter(doctor=request.user)
        else:
            requested_patient = request.query_params.get("patient_id")
            if requested_patient:
                patient = _managed_patient(request.user, requested_patient, "can_book")
                if patient is None:
                    return Response({"detail": "You are not authorized to manage this patient's appointments."}, status=403)
                qs = Appointment.objects.filter(patient=patient)
            else:
                from accounts.models import PatientRelationship
                dependent_ids = PatientRelationship.objects.filter(
                    caregiver=request.user,
                    status=PatientRelationship.Status.ACTIVE,
                    can_book=True,
                ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).values_list("patient_id", flat=True)
                qs = Appointment.objects.filter(Q(patient=request.user) | Q(patient_id__in=dependent_ids))
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs.select_related("patient", "doctor").prefetch_related("status_history")
        return Response(AppointmentSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        doctor = data["doctor_id"]
        patient = _managed_patient(request.user, data.get("patient_id"), "can_book")
        if patient is None:
            return Response({"detail": "You are not authorized to book for this patient."}, status=403)
        if not _doctor_is_verified(doctor):
            return Response({"detail": "This professional is not verified or enabled for bookings."}, status=403)
        date = data["date"]
        start_time = data["start_time"]
        slot = find_slot(doctor, date, start_time)
        if slot is None:
            return Response({"detail": "Slot not available"}, status=400)
        end_time = datetime.datetime.strptime(slot["end"], "%H:%M").time()
        try:
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                booked_by=request.user,
                date=date,
                start_time=start_time,
                end_time=end_time,
                type=data["type"],
                reason=data.get("reason", ""),
                status=Appointment.Status.PENDING,
            )
        except IntegrityError:
            return Response({"detail": "Slot not available"}, status=400)
        AppointmentStatusHistory.objects.create(
            appointment=appointment,
            actor=request.user,
            from_status="",
            to_status=Appointment.Status.PENDING,
            reason="Appointment booked by patient",
        )
        # Booking establishes narrow, named treatment/telemedicine consent for this doctor.
        # Consent and relationship evidence are part of the same transaction as
        # the booking; a partial booking without access governance is not allowed.
        from governance.models import Consent

        Consent.objects.create(
            patient=patient,
            granted_to=doctor,
            consent_type=(
                Consent.Type.TELEMEDICINE
                if appointment.type == Appointment.Type.ONLINE
                else Consent.Type.TREATMENT
            ),
            purpose="treatment",
            data_categories=[
                "patient_summary",
                "allergies",
                "medications",
                "conditions",
                "consultation_record",
            ],
            recipient_class="doctor",
            source="appointment_booking",
            valid_until=timezone.now() + datetime.timedelta(days=365),
        )
        _create_care_relationship(appointment, actor=request.user)
        _audit(
            request,
            "appointment.booked",
            appointment,
            decision="allow",
            metadata={"booked_by": request.user.id, "patient_id": patient.id},
        )
        if patient.id != request.user.id:
            _notify(
                request.user,
                "Dependent appointment booked",
                f"Appointment #{appointment.id} was booked for {patient.display_name}.",
                kind="appointment",
            )
        try:
            from interoperability.services import emit_event

            emit_event(
                "appointment.booked",
                appointment,
                {
                    "patient_id": appointment.patient_id,
                    "doctor_id": appointment.doctor_id,
                    "date": appointment.date.isoformat(),
                    "start_time": appointment.start_time.isoformat(),
                    "type": appointment.type,
                    "booked_by": request.user.id,
                },
                actor=request.user,
                patient=appointment.patient,
                request=request,
            )
        except Exception:
            pass
        return Response(AppointmentSerializer(appointment).data, status=201)


class AppointmentActionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(BOOKABLE_PROVIDER_ROLES)]
    ACTIONS = {"confirm", "cancel", "complete", "miss"}
    action = None

    def post(self, request, pk, action=None):
        action = action or self.action
        if action not in self.ACTIONS:
            return Response({"detail": "Unknown action"}, status=404)
        appointment = get_object_or_404(Appointment, pk=pk)
        is_doctor = appointment.doctor_id == request.user.id
        is_patient = appointment.patient_id == request.user.id
        is_authorized_caregiver = request_role(request) == User.Role.PATIENT and _can_manage_appointment(request.user, appointment)
        reason = str(request.data.get("reason", "")).strip()

        if action == "confirm" and not is_doctor:
            return Response({"detail": "Only the assigned professional can confirm"}, status=403)
        if action == "cancel" and not (is_doctor or is_patient or is_authorized_caregiver):
            return Response({"detail": "Only the patient, authorized caregiver or assigned professional can cancel"}, status=403)
        if action in {"complete", "miss"} and not is_doctor:
            return Response({"detail": f"Only the assigned professional can {action}"}, status=403)

        target = {
            "confirm": Appointment.Status.CONFIRMED,
            "cancel": Appointment.Status.CANCELLED,
            "complete": Appointment.Status.COMPLETED,
            "miss": Appointment.Status.MISSED,
        }[action]
        try:
            appointment.transition_to(target, actor=request.user, reason=reason)
        except DjangoValidationError as exc:
            return Response({"detail": "; ".join(exc.messages)}, status=409)

        if action == "confirm":
            _notify(
                appointment.patient,
                "Appointment confirmed",
                f"Your appointment on {appointment.date} at {appointment.start_time.strftime('%H:%M')} was confirmed.",
            )
        elif action == "cancel":
            other = appointment.doctor if (is_patient or is_authorized_caregiver) else appointment.patient
            _notify(
                other,
                "Appointment cancelled",
                f"Appointment #{appointment.id} was cancelled. {reason}".strip(),
                kind="appointment",
            )
        _audit(
            request,
            f"appointment.{action}",
            appointment,
            decision="allow",
            metadata={"reason": reason},
        )
        try:
            from interoperability.services import emit_event

            emit_event(
                f"appointment.{action}",
                appointment,
                {
                    "patient_id": appointment.patient_id,
                    "doctor_id": appointment.doctor_id,
                    "status": appointment.status,
                    "reason": reason,
                },
                actor=request.user,
                patient=appointment.patient,
                request=request,
            )
        except Exception:
            pass
        return Response(AppointmentSerializer(appointment).data)
