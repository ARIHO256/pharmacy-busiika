import datetime

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole

from .models import Appointment, AppointmentStatusHistory, Availability
from .serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    AvailabilitySerializer,
)
from .services import find_slot

User = get_user_model()


def _doctor_is_verified(user):
    profile = getattr(user, "doctor_profile", None)
    return bool(user.is_active and user.is_verified and profile and profile.status == "verified")


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
    allowed_roles = ["doctor"]

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
    allowed_roles = ["doctor"]

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
        doctor = get_object_or_404(User, pk=doctor_id, role=User.Role.DOCTOR)
        if not _doctor_is_verified(doctor):
            return Response({"detail": "Doctor is not available for public booking."}, status=404)
        from .services import compute_free_slots

        return Response({"date": date.isoformat(), "slots": compute_free_slots(doctor, date)})


class AppointmentListCreateView(APIView):
    def get_permissions(self):
        self.allowed_roles = ["patient"] if self.request.method == "POST" else ["patient", "doctor"]
        return [IsRole()]

    def get(self, request):
        qs = (
            Appointment.objects.filter(doctor=request.user)
            if request.user.role == User.Role.DOCTOR
            else Appointment.objects.filter(patient=request.user)
        )
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
        if not _doctor_is_verified(doctor):
            return Response({"detail": "This doctor is not verified for bookings."}, status=403)
        date = data["date"]
        start_time = data["start_time"]
        slot = find_slot(doctor, date, start_time)
        if slot is None:
            return Response({"detail": "Slot not available"}, status=400)
        end_time = datetime.datetime.strptime(slot["end"], "%H:%M").time()
        try:
            appointment = Appointment.objects.create(
                patient=request.user,
                doctor=doctor,
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
            patient=request.user,
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
        _audit(request, "appointment.booked", appointment, decision="allow")
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
    allowed_roles = ["patient", "doctor"]
    ACTIONS = {"confirm", "cancel", "complete", "miss"}
    action = None

    def post(self, request, pk, action=None):
        action = action or self.action
        if action not in self.ACTIONS:
            return Response({"detail": "Unknown action"}, status=404)
        appointment = get_object_or_404(Appointment, pk=pk)
        is_doctor = appointment.doctor_id == request.user.id
        is_patient = appointment.patient_id == request.user.id
        reason = str(request.data.get("reason", "")).strip()

        if action == "confirm" and not is_doctor:
            return Response({"detail": "Only the doctor can confirm"}, status=403)
        if action == "cancel" and not (is_doctor or is_patient):
            return Response({"detail": "Only the patient or doctor involved can cancel"}, status=403)
        if action in {"complete", "miss"} and not is_doctor:
            return Response({"detail": f"Only the doctor can {action}"}, status=403)

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
            other = appointment.doctor if is_patient else appointment.patient
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
