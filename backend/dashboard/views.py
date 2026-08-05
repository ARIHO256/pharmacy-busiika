from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DoctorProfile, ProviderProfile, StaffProfile
from accounts.permissions import IsRole
from accounts.roles import PROFESSIONAL_ROLES, portal_path_for_role
from enterprise.access import active_role

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


def _roles_for_user(user):
    roles = {getattr(user, "role", "")}
    try:
        roles |= set(user.role_contexts.filter(active=True).values_list("role_code", flat=True))
    except Exception:
        pass
    return {role for role in roles if role}


def _profile_for(user):
    roles = _roles_for_user(user)
    if roles & PROFESSIONAL_ROLES:
        return _doctor_profile(user) or _staff_profile(user)
    if roles & {"pharmacy", "lab", "hospital", "insurance"}:
        return _provider_profile(user)
    if roles - {"patient", "admin", "platform_super_admin"}:
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

        return Response(
            {
                "users": users,
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
        target_is_admin = User.objects.filter(pk=user.pk, role=User.Role.ADMIN).exists()
        if (
            action == "suspend"
            and target_is_admin
            and not User.objects.filter(role=User.Role.ADMIN, is_active=True)
            .exclude(pk=user.pk)
            .exists()
        ):
            return Response(
                {"detail": "Cannot deactivate the last remaining platform administrator."},
                status=400,
            )

        credential = None
        if _roles_for_user(user) & PROFESSIONAL_ROLES:
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

        if _roles_for_user(user) & {"pharmacy", "lab", "hospital", "insurance"} and action == "verify":
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
            user.save(update_fields=["is_active"])
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

        if _roles_for_user(user) & {"pharmacy", "lab", "hospital", "insurance"} and profile is not None:
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
                or f"Your HealthPilot account status was changed by an administrator: {action}.",
                kind="verification" if action in {"verify", "reject"} else "account",
                priority="high",
                action_url=portal_path_for_role(active_role(user)),
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


class AdminReviewActionView(APIView):
    """POST /api/admin/reviews/<pk>/action/ — flag, hide, or restore a review.

    Hidden/flagged reviews leave the public listing and stop counting toward
    the doctor's average rating until unhidden.
    """

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def post(self, request, pk):
        from reviews.models import Review
        from reviews.serializers import ReviewAdminSerializer
        from reviews.views import _recompute_average_rating

        action = request.data.get("action")
        if action not in ("flag", "hide", "unhide"):
            return Response(
                {"detail": "action must be flag|hide|unhide"}, status=400
            )
        review = Review.objects.select_related("doctor").filter(pk=pk).first()
        if review is None:
            return Response({"detail": "review not found"}, status=404)

        review.status = {
            "flag": Review.Status.FLAGGED,
            "hide": Review.Status.HIDDEN,
            "unhide": Review.Status.VISIBLE,
        }[action]
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.moderation_note = str(request.data.get("note", "")).strip()
        review.save(
            update_fields=["status", "moderated_by", "moderated_at", "moderation_note"]
        )
        _recompute_average_rating(review.doctor)
        log_action(
            request.user,
            f"review.{action}",
            {"review_id": review.id, "note": review.moderation_note},
        )
        return Response(ReviewAdminSerializer(review).data)


class AdminAuditView(APIView):
    """GET /api/admin/audit/ — newest first."""

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        qs = AuditLog.objects.select_related("user").order_by("-created_at")
        return Response(AuditLogSerializer(qs, many=True).data)


class AdminAppointmentAnalyticsView(APIView):
    """GET /api/admin/analytics/appointments/?from=&to= (YYYY-MM-DD).

    Defaults to the last 30 days when no range is supplied.
    """

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def get(self, request):
        from appointments.models import Appointment

        today = timezone.localdate()
        try:
            date_to = (
                date.fromisoformat(request.query_params["to"])
                if request.query_params.get("to")
                else today
            )
            date_from = (
                date.fromisoformat(request.query_params["from"])
                if request.query_params.get("from")
                else date_to - timedelta(days=29)
            )
        except ValueError:
            return Response(
                {"detail": "from/to must be YYYY-MM-DD dates"}, status=400
            )
        if date_from > date_to:
            return Response({"detail": "from must not be after to"}, status=400)

        qs = Appointment.objects.filter(date__gte=date_from, date__lte=date_to)

        totals_by_status = {
            row["status"]: row["c"]
            for row in qs.values("status").annotate(c=Count("id"))
        }
        total = sum(totals_by_status.values())
        missed = totals_by_status.get("missed", 0)

        per_day_map = {}
        for row in qs.values("date", "status").annotate(c=Count("id")):
            entry = per_day_map.setdefault(
                row["date"], {"date": row["date"], "total": 0, "by_status": {}}
            )
            entry["by_status"][row["status"]] = row["c"]
            entry["total"] += row["c"]
        per_day = [per_day_map[day] for day in sorted(per_day_map)]

        doctor_rows = list(
            qs.values("doctor")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                missed=Count("id", filter=Q(status="missed")),
            )
            .order_by("-total")[:20]
        )
        doctor_names = {
            user.id: _name(user)
            for user in User.objects.filter(
                pk__in=[row["doctor"] for row in doctor_rows]
            )
        }
        doctors = [
            {
                "doctor": row["doctor"],
                "doctor_name": doctor_names.get(row["doctor"]),
                "total": row["total"],
                "completed": row["completed"],
                "missed": row["missed"],
            }
            for row in doctor_rows
        ]

        revenue = 0
        try:
            from payments.models import Invoice

            revenue = (
                Invoice.objects.filter(
                    status="paid",
                    appointment__date__gte=date_from,
                    appointment__date__lte=date_to,
                ).aggregate(t=Sum("amount"))["t"]
                or 0
            )
        except Exception:
            pass

        return Response(
            {
                "from": date_from,
                "to": date_to,
                "total": total,
                "totals_by_status": totals_by_status,
                "missed_rate": round(missed * 100 / total, 2) if total else 0,
                "per_day": per_day,
                "doctors": doctors,
                "revenue": revenue,
            }
        )


class AdminUserSetRoleView(APIView):
    """POST /api/admin/users/<pk>/set-role/ — platform super admin only.

    The last remaining platform administrator cannot be demoted.
    """

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    @transaction.atomic
    def post(self, request, pk):
        role = str(request.data.get("role", "")).strip()
        if role not in User.Role.values:
            return Response(
                {"detail": "invalid role", "valid_roles": sorted(User.Role.values)},
                status=400,
            )
        try:
            user = User.objects.select_for_update().get(pk=pk)
        except User.DoesNotExist:
            return Response({"detail": "user not found"}, status=404)

        previous = user.role
        if role == previous:
            return Response({"id": user.id, "email": user.email, "role": user.role})
        if (
            previous == User.Role.ADMIN
            and not User.objects.filter(role=User.Role.ADMIN, is_active=True)
            .exclude(pk=user.pk)
            .exists()
        ):
            return Response(
                {"detail": "Cannot demote the last remaining platform administrator."},
                status=400,
            )

        user.role = role
        user.save(update_fields=["role"])
        log_action(
            request.user,
            "user.set_role",
            {
                "target_user_id": user.id,
                "target_email": user.email,
                "from_role": previous,
                "to_role": role,
            },
        )
        return Response({"id": user.id, "email": user.email, "role": user.role})


class AdminBroadcastView(APIView):
    """POST /api/admin/notifications/broadcast/ — {title, message, roles[], channels[]}.

    Fans out through communication.services.notify, which applies each
    recipient's notification channel preferences.
    """

    permission_classes = [IsRole]
    allowed_roles = ["admin"]

    def post(self, request):
        title = str(request.data.get("title", "")).strip()
        message = str(request.data.get("message", "")).strip()
        if not title or not message:
            return Response(
                {"detail": "title and message are required"}, status=400
            )

        roles = request.data.get("roles") or []
        if not isinstance(roles, list) or any(
            role not in User.Role.values for role in roles
        ):
            return Response(
                {"detail": "roles must be a list of valid role codes"}, status=400
            )

        channels = request.data.get("channels") or None
        if channels is not None:
            from communication.models import NotificationDelivery

            if not isinstance(channels, list) or any(
                channel not in NotificationDelivery.Channel.values
                for channel in channels
            ):
                return Response(
                    {"detail": "channels must be a list of valid channel codes"},
                    status=400,
                )

        recipients = User.objects.filter(is_active=True)
        if roles:
            recipients = recipients.filter(role__in=roles)

        from communication.services import notify

        count = 0
        for user in recipients:
            try:
                notify(user, title, message, kind="general", channels=channels)
                count += 1
            except Exception:
                pass

        log_action(
            request.user,
            "notifications.broadcast",
            {
                "title": title,
                "roles": roles,
                "channels": channels or [],
                "recipients": count,
            },
        )
        return Response({"recipients": count})
