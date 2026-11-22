from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DoctorProfile, ProviderProfile, StaffProfile
from accounts.permissions import IsRole
from accounts.roles import PROFESSIONAL_ROLES, portal_path_for_role

from .models import AuditLog
from .serializers import AuditLogSerializer
from .services import log_action

User = get_user_model()

COMMISSION_RATE = getattr(settings, "COMMISSION_RATE", 0.10)


def _name(user):
    if user is None:
        return None
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.email


def _doctor_profile(user):
    try:
        from accounts.models import DoctorProfile

        return DoctorProfile.objects.filter(user=user).first()
    except Exception:
        return None


def _staff_profile(user):
    try:
        from accounts.models import StaffProfile

        return StaffProfile.objects.filter(user=user).first()
    except Exception:
        return None


def _provider_profile(user):
    try:
        from accounts.models import ProviderProfile

        return ProviderProfile.objects.filter(user=user).first()
    except Exception:
        return None


def _profile_for(user):
    if user.role == "doctor":
        return _doctor_profile(user)
    if user.role in ("pharmacy", "lab", "hospital", "insurance"):
        return _provider_profile(user)
    if user.role in ("nurse", "receptionist", "cashier", "pharmacist", "lab_technician", "facility_manager", "records_officer", "insurance_officer", "storekeeper"):
        return _staff_profile(user)
    return None


def _paid_revenue():
    try:
        from payments.models import Invoice

        return (
            Invoice.objects.filter(status="paid").aggregate(t=Sum("amount"))["t"] or 0
        )
    except Exception:
        return 0


class AdminOverviewView(APIView):
    """GET /api/admin/overview/"""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        users = {
            row["role"]: row["c"]
            for row in User.objects.values("role").annotate(c=Count("id"))
        }

        appointments = {}
        try:
            from appointments.models import Appointment

            appointments = {
                row["status"]: row["c"]
                for row in Appointment.objects.values("status").annotate(c=Count("id"))
            }
        except Exception:
            pass

        revenue = _paid_revenue()

        pending_verifications = 0
        try:
            from accounts.models import DoctorProfile, ProviderProfile, StaffProfile

            pending_verifications = (
                DoctorProfile.objects.filter(status="pending").count()
                + ProviderProfile.objects.filter(status="pending").count()
                + StaffProfile.objects.filter(status="pending").count()
            )
        except Exception:
            try:
                from accounts.models import DoctorProfile

                pending_verifications = DoctorProfile.objects.filter(
                    status="pending"
                ).count()
            except Exception:
                pass

        pending_payouts = 0
        try:
            from payments.models import Payout

            pending_payouts = Payout.objects.filter(status="pending").count()
        except Exception:
            pass

        organizations_by_type = {}
        organization_statuses = {}
        failed_notification_deliveries = 0
        try:
            from registry.models import Organization
            organizations_by_type = {
                row["organization_type"]: row["c"]
                for row in Organization.objects.values("organization_type").annotate(c=Count("id"))
            }
            organization_statuses = {
                row["status"]: row["c"]
                for row in Organization.objects.values("status").annotate(c=Count("id"))
            }
        except Exception:
            pass
        try:
            from communication.models import NotificationDelivery
            failed_notification_deliveries = NotificationDelivery.objects.filter(status="failed").count()
        except Exception:
            pass

        from governance.models import AuditEvent, Consent
        from interoperability.models import TerminologyConcept
        from payments.models import Invoice
        from services.models import InsuranceClaim, LabOrder, LabResult, Medicine, Order
        from workforce.models import NursingNote, PatientVisit

        operation_counts = {
            "visits": PatientVisit.objects.count(),
            "nursing_handovers": NursingNote.objects.filter(note_type=NursingNote.Type.HANDOVER).count(),
            "lab_orders": LabOrder.objects.count(),
            "released_lab_results": LabResult.objects.filter(released_at__isnull=False).count(),
            "medicines": Medicine.objects.count(),
            "medicine_register": TerminologyConcept.objects.filter(category="registered_medicine_reference", active=True).count(),
            "pharmacy_orders": Order.objects.count(),
            "invoices": Invoice.objects.count(),
            "insurance_claims": InsuranceClaim.objects.count(),
            "active_consents": Consent.objects.filter(status=Consent.Status.ACTIVE).count(),
            "audit_events": AuditEvent.objects.count() + AuditLog.objects.count(),
        }

        return Response(
            {
                "users": users,
                "operation_counts": operation_counts,
                "appointments": appointments,
                "revenue": revenue,
                "commissions": round(revenue * COMMISSION_RATE),
                "pending_verifications": pending_verifications,
                "pending_payouts": pending_payouts,
                "organizations_by_type": organizations_by_type,
                "organization_statuses": organization_statuses,
                "failed_notification_deliveries": failed_notification_deliveries,
                "verification_counts": {
                    "doctors_pending": DoctorProfile.objects.filter(status="pending").count(),
                    "doctors_verified": DoctorProfile.objects.filter(status="verified").count(),
                    "organizations_pending": ProviderProfile.objects.filter(status="pending").count(),
                    "organizations_verified": ProviderProfile.objects.filter(status="verified").count(),
                    "staff_pending": StaffProfile.objects.filter(status="pending").count(),
                },
            }
        )


class AdminUsersView(APIView):
    """GET /api/admin/users/?role=&status="""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        qs = User.objects.all().order_by("-date_joined")
        role = request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        status_filter = request.query_params.get("status")

        data = []
        for user in qs:
            profile = _profile_for(user)
            profile_status = getattr(profile, "status", None)
            if status_filter and profile_status != status_filter:
                continue
            data.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "name": _name(user),
                    "role": user.role,
                    "is_verified": user.is_verified,
                    "is_active": user.is_active,
                    "date_joined": user.date_joined,
                    "status": profile_status,
                }
            )
        return Response(data)


class AdminUserSetStatusView(APIView):
    """Review, suspend, reject, or reactivate a platform account."""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    @transaction.atomic
    def post(self, request, pk):
        action = request.data.get("action")
        if action not in ("verify", "reject", "suspend", "activate", "reactivate"):
            return Response(
                {"detail": "action must be verify|reject|suspend|activate|reactivate"},
                status=400,
            )
        try:
            user = User.objects.select_for_update().get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "user not found"}, status=404)

        profile = _profile_for(user)
        reason = str(request.data.get("reason", "")).strip()
        if action in {"reject", "suspend"} and not reason:
            return Response(
                {"detail": "A reason is required for this account action."}, status=400
            )

        credential = None
        if user.role in PROFESSIONAL_ROLES:
            from registry.models import PractitionerCredential

            credential = (
                PractitionerCredential.objects.select_for_update()
                .filter(
                    practitioner=user,
                    credential_type=PractitionerCredential.Type.LICENSE,
                )
                .order_by("-created_at")
                .first()
            )
            if action == "verify":
                if credential is None:
                    return Response(
                        {"detail": "A professional licence must be submitted before verification."},
                        status=400,
                    )
                if not credential.identifier or not credential.document:
                    return Response(
                        {"detail": "The licence number and protected licence document are required."},
                        status=400,
                    )
                if credential.expires_on and credential.expires_on <= date.today():
                    return Response(
                        {"detail": "The submitted professional licence has expired."},
                        status=400,
                    )

        if user.role in ("pharmacy", "lab", "hospital", "insurance") and action == "verify":
            required = {
                "org_name": "Organization name",
                "license_number": "Registered licence number",
                "license_document": "Protected licence document",
                "district": "District or location",
                "address": "Physical address",
                "services_description": "Services description",
            }
            missing = [
                label
                for field, label in required.items()
                if profile is None or not getattr(profile, field, None)
            ]
            if missing:
                return Response(
                    {"detail": "Complete the organization profile before verification.", "missing": missing},
                    status=400,
                )

        if action == "verify":
            if credential is not None:
                credential.status = credential.Status.VERIFIED
                credential.verified_by = request.user
                credential.verified_at = timezone.now()
                credential.save(update_fields=["status", "verified_by", "verified_at"])
            user.is_verified = True
            user.is_active = True
            user.save(update_fields=["is_verified", "is_active"])
            if profile is not None:
                profile.status = "verified"
                if hasattr(profile, "verification_notes"):
                    profile.verification_notes = reason
                    profile.save(update_fields=["status", "verification_notes"])
                else:
                    profile.save(update_fields=["status"])
        elif action == "reject":
            if credential is not None:
                credential.status = credential.Status.REJECTED
                credential.verified_by = request.user
                credential.verified_at = timezone.now()
                credential.save(update_fields=["status", "verified_by", "verified_at"])
            user.is_verified = False
            user.save(update_fields=["is_verified"])
            if profile is not None:
                profile.status = "rejected"
                if hasattr(profile, "verification_notes"):
                    profile.verification_notes = reason
                    profile.save(update_fields=["status", "verification_notes"])
                else:
                    profile.save(update_fields=["status"])
        elif action == "suspend":
            user.is_active = False
            user.is_verified = False
            user.save(update_fields=["is_active", "is_verified"])
            if profile is not None:
                profile.status = "suspended"
                if hasattr(profile, "verification_notes"):
                    profile.verification_notes = reason
                    profile.save(update_fields=["status", "verification_notes"])
                else:
                    profile.save(update_fields=["status"])
        else:  # activate/reactivate
            user.is_active = True
            user.save(update_fields=["is_active"])
            if profile is not None and getattr(profile, "status", None) == "suspended":
                profile.status = "verified" if user.is_verified else "pending"
                profile.save(update_fields=["status"])

        if user.role in ("pharmacy", "lab", "hospital", "insurance") and profile is not None:
            from registry.services import sync_provider_organization

            try:
                sync_provider_organization(user, profile, authoritative_status=True)
            except ValueError as exc:
                raise ValidationError({"detail": str(exc)}) from exc

        log_action(
            request.user,
            f"user.{action}",
            {
                "target_user_id": user.id,
                "target_email": user.email,
                "reason": reason,
                "credential_id": getattr(credential, "id", None),
            },
        )
        try:
            from communication.services import notify

            notify(
                user,
                f"Account status: {action}",
                reason
                or f"Your MyDoctor account status was changed by an administrator: {action}.",
                kind="verification" if action in {"verify", "reject"} else "account",
                priority="high",
                action_url=portal_path_for_role(user.role),
            )
        except Exception:
            pass
        return Response(
            {
                "id": user.id,
                "email": user.email,
                "is_verified": user.is_verified,
                "is_active": user.is_active,
                "status": getattr(profile, "status", None),
                "credential_status": getattr(credential, "status", None),
            }
        )


class AdminAppointmentsView(APIView):
    """GET /api/admin/appointments/?status="""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        try:
            from appointments.models import Appointment
        except Exception:
            return Response([])

        qs = Appointment.objects.select_related("patient", "doctor").order_by(
            "-date", "-start_time"
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        data = [
            {
                "id": a.id,
                "patient": a.patient_id,
                "patient_name": _name(a.patient),
                "doctor": a.doctor_id,
                "doctor_name": _name(a.doctor),
                "date": a.date,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "type": a.type,
                "status": a.status,
            }
            for a in qs
        ]
        return Response(data)


class AdminFinanceView(APIView):
    """GET /api/admin/finance/"""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        invoices = []
        payouts = []
        try:
            from payments.models import Invoice, Payout

            for inv in Invoice.objects.select_related(
                "patient", "appointment", "appointment__doctor"
            ).order_by("-created_at"):
                doctor = None
                if inv.appointment_id and inv.appointment:
                    doctor = _name(inv.appointment.doctor)
                invoices.append(
                    {
                        "id": inv.id,
                        "number": inv.number,
                        "patient": _name(inv.patient),
                        "doctor": doctor,
                        "amount": inv.amount,
                        "status": inv.status,
                        "paid_at": inv.paid_at,
                    }
                )
            payouts = [
                {
                    "id": p.id,
                    "doctor": _name(p.doctor),
                    "amount": p.amount,
                    "status": p.status,
                    "created_at": p.created_at,
                }
                for p in Payout.objects.select_related("doctor").order_by(
                    "-created_at"
                )
            ]
        except Exception:
            pass

        revenue = _paid_revenue()
        return Response(
            {
                "invoices": invoices,
                "commissions_total": round(revenue * COMMISSION_RATE),
                "payouts": payouts,
                "revenue": revenue,
            }
        )


class AdminReviewsView(APIView):
    """GET /api/admin/reviews/"""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        from reviews.models import Review
        from reviews.serializers import ReviewAdminSerializer

        qs = Review.objects.select_related("patient", "doctor").order_by("-created_at")
        return Response(ReviewAdminSerializer(qs, many=True).data)


class AdminAuditView(APIView):
    """GET /api/admin/audit/ — newest first."""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        qs = AuditLog.objects.select_related("user").order_by("-created_at")
        return Response(AuditLogSerializer(qs, many=True).data)
