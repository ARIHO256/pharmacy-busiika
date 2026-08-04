from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsRole, request_role
from accounts.roles import DOCTOR_ROLES
from enterprise.access import active_role

from .models import Prescription
from .serializers import (
    PrescriptionCreateSerializer,
    PrescriptionDetailSerializer,
    PrescriptionListSerializer,
)


def _safe_notify(user, title, body, kind):
    try:
        from communication.services import notify

        notify(user, title, body, kind)
    except Exception:
        return None


def _get_appointment(pk):
    from appointments.models import Appointment

    return Appointment.objects.filter(pk=pk).first()


def _audit(request, action, prescription, metadata=None):
    try:
        from governance.services import audit

        audit(
            actor=request.user,
            patient=prescription.patient,
            action=action,
            resource=prescription,
            purpose="treatment",
            metadata=metadata or {},
            request=request,
        )
    except Exception:
        return None


class AppointmentPrescriptionView(APIView):
    permission_classes = [IsRole]
    allowed_roles = sorted(DOCTOR_ROLES)

    @transaction.atomic
    def post(self, request, pk):
        appointment = _get_appointment(pk)
        if appointment is None:
            return Response({"detail": "appointment not found"}, status=404)
        if appointment.doctor_id != request.user.id:
            return Response({"detail": "not the prescribing clinician for this appointment"}, status=403)
        if appointment.status != "confirmed":
            return Response({"detail": "appointment must be confirmed"}, status=400)

        try:
            from clinical.services import can_access_patient

            allowed, _emergency, reason = can_access_patient(request.user, appointment.patient)
            if not allowed:
                return Response({"detail": reason}, status=403)
        except ImportError:
            pass

        serializer = PrescriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        encounter = None
        encounter_id = data.get("encounter_id")
        if encounter_id:
            try:
                from clinical.models import ClinicalEncounter

                encounter = ClinicalEncounter.objects.get(
                    pk=encounter_id,
                    appointment=appointment,
                    doctor=request.user,
                )
            except ClinicalEncounter.DoesNotExist:
                return Response({"detail": "encounter not found for this appointment"}, status=404)
        elif hasattr(appointment, "clinical_encounter"):
            encounter = appointment.clinical_encounter

        prescription = Prescription.objects.create(
            appointment=appointment,
            encounter=encounter,
            doctor=request.user,
            patient=appointment.patient,
            notes=data.get("notes", ""),
            status=Prescription.Status.ISSUED,
        )
        for item in data["items"]:
            prescription.items.create(**item)
        try:
            appointment.transition_to(
                appointment.Status.COMPLETED,
                actor=request.user,
                reason="Consultation completed with prescription",
                metadata={"prescription_id": prescription.id},
            )
        except DjangoValidationError as exc:
            transaction.set_rollback(True)
            return Response({"detail": "; ".join(exc.messages)}, status=409)

        _safe_notify(
            appointment.patient,
            "New prescription",
            f"Prescription {prescription.number} was issued by {request.user.display_name}.",
            "prescription",
        )
        _audit(request, "prescription.issued", prescription)
        try:
            from interoperability.services import emit_event

            emit_event(
                "prescription.issued",
                prescription,
                {
                    "number": prescription.number,
                    "appointment_id": appointment.id,
                    "doctor_id": request.user.id,
                    "patient_id": appointment.patient_id,
                    "item_count": prescription.items.count(),
                    "status": prescription.status,
                },
                actor=request.user,
                patient=appointment.patient,
                request=request,
            )
        except Exception:
            pass
        return Response(PrescriptionDetailSerializer(prescription).data, status=201)


class PrescriptionListView(generics.ListAPIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(DOCTOR_ROLES)]
    serializer_class = PrescriptionListSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Prescription.objects.select_related("doctor", "patient", "encounter").prefetch_related("items")
        return qs.filter(doctor=user) if active_role(user) in DOCTOR_ROLES else qs.filter(patient=user)


class PrescriptionDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PrescriptionDetailSerializer
    queryset = Prescription.objects.select_related("doctor", "patient", "encounter").prefetch_related("items")

    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.user.id not in (obj.patient_id, obj.doctor_id) and request_role(request) != "admin":
            return Response({"detail": "not allowed"}, status=403)
        _audit(request, "prescription.viewed", obj)
        return Response(self.get_serializer(obj).data)


class SendToPharmacyView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient"]

    def post(self, request, pk):
        try:
            prescription = Prescription.objects.get(pk=pk, patient=request.user)
        except Prescription.DoesNotExist:
            return Response({"detail": "prescription not found"}, status=404)
        if prescription.status not in [Prescription.Status.ISSUED, Prescription.Status.PARTIALLY_DISPENSED]:
            return Response({"detail": "Prescription cannot be sent in its current state."}, status=409)
        pharmacy_id = request.data.get("pharmacy_id")
        if not pharmacy_id:
            return Response({"detail": "pharmacy_id is required"}, status=400)
        try:
            from accounts.models import ProviderProfile, User
            from services.models import PharmacyOrder

            pharmacy = User.objects.filter(
                pk=pharmacy_id,
                role=User.Role.PHARMACY,
                provider_profile__status="verified",
            ).first()
            if not pharmacy:
                return Response({"detail": "verified pharmacy not found"}, status=404)
            order, created = PharmacyOrder.objects.get_or_create(
                pharmacy=pharmacy,
                prescription_id=prescription.id,
                patient=request.user,
                defaults={"status": "new"},
            )
        except Exception:
            return Response({"detail": "pharmacy service unavailable"}, status=503)
        _audit(
            request,
            "prescription.sent_to_pharmacy",
            prescription,
            {"pharmacy_id": int(pharmacy_id), "pharmacy_order_id": order.id},
        )
        try:
            from interoperability.services import emit_event

            emit_event(
                "prescription.sent_to_pharmacy",
                prescription,
                {
                    "prescription_number": prescription.number,
                    "pharmacy_id": int(pharmacy_id),
                    "pharmacy_order_id": order.id,
                },
                actor=request.user,
                patient=request.user,
                request=request,
            )
        except Exception:
            pass
        return Response(
            {"detail": "sent", "pharmacy_order_id": order.id, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
