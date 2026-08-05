from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import HttpResponse
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
        try:
            from workforce.services import advance_active_visit

            advance_active_visit(
                appointment.patient,
                "pharmacy",
                actor=request.user,
                reason=f"Prescription {prescription.number} issued",
            )
        except Exception:
            pass
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


def _prescription_pdf(prescription):
    """Generate a server-side PDF of the prescription for printing and pharmacy use."""
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    def safe(value):
        return escape(str(value or ""))

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=prescription.number,
        author="HealthPilot Platform",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="RightSmall", parent=styles["BodyText"], alignment=TA_RIGHT, fontSize=8, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle(name="DocTitle", parent=styles["Title"], fontSize=22, leading=26, textColor=colors.HexColor("#123b72"), spaceAfter=4))
    story = []
    story.append(Table([
        [Paragraph('<b>HealthPilot Platform</b><br/><font size="9">Connected healthcare services</font>', styles["BodyText"]), Paragraph(f"<b>PRESCRIPTION</b><br/>{safe(prescription.number)}", styles["RightSmall"])],
    ], colWidths=[120 * mm, 42 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#dbeafe")), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]))
    story.append(Spacer(1, 8 * mm))
    doctor = prescription.doctor
    profile = getattr(doctor, "doctor_profile", None)
    cadre = profile.get_cadre_display() if profile and profile.cadre else ""
    license_number = profile.license_number if profile else ""
    signed = prescription.signed_at.astimezone().strftime("%d %b %Y %H:%M") if prescription.signed_at else ""
    expires = prescription.expires_at.astimezone().strftime("%d %b %Y") if prescription.expires_at else ""
    details = [
        [Paragraph("<b>Prescriber</b>", styles["BodyText"]), Paragraph("<b>Patient</b>", styles["BodyText"])],
        [
            Paragraph(f"{safe(doctor.display_name)}<br/>{safe(cadre)}<br/>License: {safe(license_number or '-')}", styles["BodyText"]),
            Paragraph(f"{safe(prescription.patient.display_name)}<br/>{safe(prescription.patient.email)}<br/>Signed: {safe(signed)}<br/>Expires: {safe(expires)}", styles["BodyText"]),
        ],
    ]
    story.append(Table(details, colWidths=[88 * mm, 74 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eff6ff")), ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#cbd5e1")), ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#e2e8f0")), ("PADDING", (0, 0), (-1, -1), 7)]))
    story.append(Spacer(1, 6 * mm))
    item_rows = [["Medicine", "Dosage", "Frequency", "Route", "Duration", "Qty", "Instructions"]]
    for item in prescription.items.all():
        medicine = safe(item.medicine_name)
        if item.generic_name:
            medicine += f'<br/><font size="8">{safe(item.generic_name)}</font>'
        item_rows.append([
            Paragraph(medicine, styles["BodyText"]),
            safe(item.dosage),
            safe(item.frequency),
            safe(item.route),
            safe(item.duration),
            str(item.quantity),
            Paragraph(safe(item.instructions), styles["BodyText"]),
        ])
    items_table = Table(item_rows, colWidths=[34 * mm, 20 * mm, 22 * mm, 16 * mm, 20 * mm, 12 * mm, 38 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b72")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#cbd5e1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(items_table)
    if prescription.notes:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(f"<b>Notes</b><br/>{safe(prescription.notes)}", styles["BodyText"]))
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("Generated securely by HealthPilot. Dispense only against a verified prescription number. Verification and audit references are retained by the issuing clinician.", styles["RightSmall"]))
    doc.build(story)
    return buffer.getvalue()


class PrescriptionPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        prescription = (
            Prescription.objects.select_related("doctor", "patient")
            .prefetch_related("items")
            .filter(pk=pk)
            .first()
        )
        if prescription is None:
            return Response({"detail": "prescription not found"}, status=404)
        if request.user.id not in (prescription.patient_id, prescription.doctor_id) and request_role(request) != "admin":
            return Response({"detail": "not allowed"}, status=403)
        try:
            payload = _prescription_pdf(prescription)
        except ImportError:
            return Response({"detail": "PDF generation dependency is unavailable."}, status=503)
        _audit(request, "prescription.pdf.generated", prescription)
        response = HttpResponse(payload, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{prescription.number}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response


class SendToPharmacyView(APIView):
    permission_classes = [IsRole]
    allowed_roles = ["patient", *sorted(DOCTOR_ROLES)]

    def post(self, request, pk):
        prescription = Prescription.objects.filter(pk=pk).first()
        if prescription is None or request.user.id not in (prescription.patient_id, prescription.doctor_id):
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
                patient=prescription.patient,
                defaults={"status": "new"},
            )
            if created:
                _safe_notify(
                    pharmacy,
                    "New prescription order",
                    f"Prescription {prescription.number} for {prescription.patient.display_name} was sent to your pharmacy.",
                    "pharmacy",
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
                patient=prescription.patient,
                request=request,
            )
        except Exception:
            pass
        return Response(
            {"detail": "sent", "pharmacy_order_id": order.id, "created": created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
