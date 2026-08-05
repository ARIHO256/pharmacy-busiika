"""Controlled platform administration endpoints.

The platform super administrator can manage identities and role contexts, while
operations, compliance and clinical-safety administrators receive only their
narrowly defined read or decision surfaces. Clinical record access is deliberately
excluded and requires a patient-specific PrivilegedAccessGrant.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from accounts.models import SecurityEvent
from enterprise.access import (
    active_role,
    has_role_identity,
    registration_role,
    can_manage_operations,
    can_review_clinical_safety,
    can_review_compliance,
    can_view_system_health,
    is_any_admin,
    is_platform_super_admin,
)
from enterprise.models import ActiveRoleContext, RoleContext
from governance.models import AuditEvent, PrivilegedAccessGrant
from governance.services import audit
from accounts.roles import PROFESSIONAL_ROLES
from registry.models import Organization, PractitionerCredential

from .models import WorkflowActionEvent

User = get_user_model()


class AnyAdminPermission(BasePermission):
    def has_permission(self, request, view):
        return is_any_admin(request.user)


class PlatformIdentityAdminPermission(BasePermission):
    def has_permission(self, request, view):
        return is_platform_super_admin(request.user)


class SystemHealthPermission(BasePermission):
    def has_permission(self, request, view):
        return can_view_system_health(request.user)


def _user_summary(user):
    active_context = None
    try:
        active_context = user.active_role_context.context
    except Exception:
        pass
    return {
        "id": user.id,
        "email": user.email,
        "name": user.display_name,
        "phone": user.phone,
        "registration_role": registration_role(user),
        "active_role": active_context.role_code if active_context else active_role(user),
        "active_context_id": active_context.id if active_context else None,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "mfa_enabled": user.mfa_enabled,
        "email_verified": bool(user.email_verified_at),
        "phone_verified": bool(user.phone_verified_at),
        "locked_until": user.locked_until,
        "last_login": user.last_login,
        "date_joined": user.date_joined,
    }


def _context_payload(context):
    return {
        "id": context.id,
        "role_code": context.role_code,
        "title": context.title,
        "organization": context.organization_id,
        "organization_name": getattr(context.organization, "legal_name", None),
        "location": context.location_id,
        "location_name": getattr(context.location, "name", None),
        "department": context.department_id,
        "department_name": getattr(context.department, "name", None),
        "permissions": context.permissions,
        "is_primary": context.is_primary,
        "active": context.active,
        "starts_on": context.starts_on,
        "ends_on": context.ends_on,
        "is_current": context.is_current,
        "created_at": context.created_at,
        "updated_at": context.updated_at,
    }


class AdminGlobalSearchView(APIView):
    permission_classes = [PlatformIdentityAdminPermission]

    def get(self, request):
        query = str(request.query_params.get("q", "")).strip()
        kind = str(request.query_params.get("kind", "all")).strip()
        if len(query) < 2:
            return Response({"users": [], "organizations": [], "professionals": []})
        response = {"users": [], "organizations": [], "professionals": []}
        if kind in {"all", "user", "users"}:
            users = User.objects.filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(phone__icontains=query)
            ).order_by("email")[:30]
            response["users"] = [_user_summary(user) for user in users]
        if kind in {"all", "organization", "organizations"}:
            organizations = Organization.objects.filter(
                Q(legal_name__icontains=query)
                | Q(trading_name__icontains=query)
                | Q(license_number__icontains=query)
            ).order_by("legal_name")[:30]
            response["organizations"] = [
                {
                    "id": organization.id,
                    "name": organization.legal_name,
                    "trading_name": organization.trading_name,
                    "organization_type": organization.organization_type,
                    "status": organization.status,
                    "owner": organization.owner_id,
                    "licence_number": organization.license_number,
                }
                for organization in organizations
            ]
        if kind in {"all", "professional", "professionals"}:
            professionals = User.objects.filter(role__in=PROFESSIONAL_ROLES).filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(professional_credentials__identifier__icontains=query)
            ).distinct().order_by("email")[:30]
            response["professionals"] = []
            for professional in professionals:
                credential = professional.professional_credentials.order_by("-created_at").first()
                response["professionals"].append({
                    "id": professional.id,
                    "user": professional.id,
                    "name": professional.display_name,
                    "email": professional.email,
                    "cadre": professional.role,
                    "registration_number": getattr(credential, "identifier", ""),
                    "status": getattr(credential, "status", "unsubmitted"),
                })
        return Response(response)


class AdminUserDetailView(APIView):
    permission_classes = [PlatformIdentityAdminPermission]

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        contexts = user.role_contexts.select_related("organization", "location", "department").all()
        security_events = list(
            user.security_events.values("id", "event_type", "detail", "ip_address", "created_at")[:50]
        )
        audit_events = list(
            AuditEvent.objects.filter(Q(actor=user) | Q(patient=user)).values(
                "event_id", "action", "resource_type", "resource_id", "purpose", "decision", "created_at"
            )[:50]
        )
        grants = list(
            PrivilegedAccessGrant.objects.filter(Q(requester=user) | Q(patient=user)).values(
                "id", "requester_id", "patient_id", "purpose", "status", "read_only", "expires_at", "requested_at"
            )[:30]
        )
        session_count = OutstandingToken.objects.filter(user=user).exclude(blacklistedtoken__isnull=False).count()
        return Response(
            {
                "user": _user_summary(user),
                "contexts": [_context_payload(context) for context in contexts],
                "security_events": security_events,
                "audit_events": audit_events,
                "privileged_access": grants,
                "active_sessions": session_count,
            }
        )


class AdminUserActionView(APIView):
    permission_classes = [PlatformIdentityAdminPermission]

    @transaction.atomic
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        action_name = str(request.data.get("action", "")).strip()
        reason = str(request.data.get("reason", "")).strip()
        if user.pk == request.user.pk and action_name in {"lock", "deactivate"}:
            return Response({"detail": "Administrators cannot lock or deactivate their own account."}, status=409)
        if action_name == "lock":
            try:
                minutes = min(max(int(request.data.get("minutes", 60)), 5), 10080)
            except (TypeError, ValueError):
                return Response({"minutes": "Enter a whole number between 5 and 10080."}, status=400)
            user.locked_until = timezone.now() + timedelta(minutes=minutes)
            user.save(update_fields=["locked_until"])
        elif action_name == "unlock":
            user.locked_until = None
            user.failed_login_attempts = 0
            user.save(update_fields=["locked_until", "failed_login_attempts"])
        elif action_name == "deactivate":
            user.is_active = False
            user.save(update_fields=["is_active"])
        elif action_name == "activate":
            user.is_active = True
            user.save(update_fields=["is_active"])
        elif action_name == "reset_mfa":
            if len(reason) < 5:
                return Response({"reason": "A reason is required to reset MFA."}, status=400)
            user.mfa_enabled = False
            user.save(update_fields=["mfa_enabled"])
            user.one_time_tokens.filter(consumed_at__isnull=True).update(consumed_at=timezone.now())
        elif action_name == "revoke_sessions":
            tokens = OutstandingToken.objects.filter(user=user)
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)
        elif action_name == "verify":
            user.is_verified = True
            user.save(update_fields=["is_verified"])
        elif action_name == "unverify":
            if len(reason) < 5:
                return Response({"reason": "A reason is required to remove verification."}, status=400)
            user.is_verified = False
            user.save(update_fields=["is_verified"])
        else:
            return Response({"action": "Unsupported administrator action."}, status=400)
        security_event_types = {
            "lock": SecurityEvent.Type.ACCOUNT_LOCKED,
            "reset_mfa": SecurityEvent.Type.MFA_DISABLED,
            "revoke_sessions": SecurityEvent.Type.SESSION_REVOKED,
        }
        if action_name in security_event_types:
            SecurityEvent.objects.create(
                user=user,
                event_type=security_event_types[action_name],
                detail={"admin_action": action_name, "reason": reason, "actor": request.user.id},
            )
        audit(
            actor=request.user,
            patient=user if has_role_identity(user, "patient") else None,
            action=f"admin.user.{action_name}",
            resource=user,
            purpose="identity_administration",
            decision=AuditEvent.Decision.ALLOW,
            metadata={"reason": reason},
            request=request,
        )
        return Response(_user_summary(user))


class AdminRoleContextListCreateView(APIView):
    permission_classes = [PlatformIdentityAdminPermission]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        contexts = user.role_contexts.select_related("organization", "location", "department")
        return Response([_context_payload(context) for context in contexts])

    @transaction.atomic
    def post(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        role_code = str(request.data.get("role_code", "")).strip()
        if not role_code:
            return Response({"role_code": "This field is required."}, status=400)
        context = RoleContext(
            user=user,
            organization_id=request.data.get("organization") or None,
            location_id=request.data.get("location") or None,
            department_id=request.data.get("department") or None,
            role_code=role_code,
            title=request.data.get("title", ""),
            permissions=request.data.get("permissions") or [],
            is_primary=bool(request.data.get("is_primary", False)),
            active=bool(request.data.get("active", True)),
            starts_on=request.data.get("starts_on") or None,
            ends_on=request.data.get("ends_on") or None,
            created_by=request.user,
        )
        try:
            context.full_clean()
        except DjangoValidationError as exc:
            return Response(getattr(exc, "message_dict", {"detail": exc.messages}), status=400)
        context.save()
        if context.is_primary:
            user.role_contexts.exclude(pk=context.pk).update(is_primary=False)
        audit(actor=request.user, action="admin.role_context.created", resource=context, purpose="identity_administration", decision=AuditEvent.Decision.ALLOW, request=request)
        return Response(_context_payload(context), status=status.HTTP_201_CREATED)


class AdminRoleContextDetailView(APIView):
    permission_classes = [PlatformIdentityAdminPermission]

    @transaction.atomic
    def patch(self, request, pk):
        context = get_object_or_404(RoleContext, pk=pk)
        for field in ["role_code", "title", "permissions", "is_primary", "active", "starts_on", "ends_on"]:
            if field in request.data:
                setattr(context, field, request.data[field])
        for field in ["organization", "location", "department"]:
            if field in request.data:
                setattr(context, f"{field}_id", request.data[field] or None)
        try:
            context.full_clean()
        except DjangoValidationError as exc:
            return Response(getattr(exc, "message_dict", {"detail": exc.messages}), status=400)
        context.save()
        if context.is_primary:
            context.user.role_contexts.exclude(pk=context.pk).update(is_primary=False)
        if not context.active:
            ActiveRoleContext.objects.filter(context=context).delete()
        audit(actor=request.user, action="admin.role_context.updated", resource=context, purpose="identity_administration", decision=AuditEvent.Decision.ALLOW, request=request)
        return Response(_context_payload(context))

    def delete(self, request, pk):
        context = get_object_or_404(RoleContext, pk=pk)
        context.active = False
        context.save(update_fields=["active", "updated_at"])
        ActiveRoleContext.objects.filter(context=context).delete()
        audit(actor=request.user, action="admin.role_context.revoked", resource=context, purpose="identity_administration", decision=AuditEvent.Decision.ALLOW, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminOrganizationOwnershipView(APIView):
    permission_classes = [PlatformIdentityAdminPermission]

    def post(self, request, pk):
        organization = get_object_or_404(Organization, pk=pk)
        owner = get_object_or_404(User, pk=request.data.get("owner"))
        reason = str(request.data.get("reason", "")).strip()
        if len(reason) < 5:
            return Response({"reason": "A reason is required."}, status=400)
        previous_owner = organization.owner_id
        organization.owner = owner
        organization.save(update_fields=["owner", "updated_at"])
        audit(actor=request.user, action="admin.organization.owner_changed", resource=organization, purpose="organization_administration", decision=AuditEvent.Decision.ALLOW, metadata={"from": previous_owner, "to": owner.id, "reason": reason}, request=request)
        return Response({"id": organization.id, "owner": owner.id, "owner_name": owner.display_name})


class AdminSystemHealthView(APIView):
    permission_classes = [SystemHealthPermission]

    def get(self, request):
        checks = {}
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                checks["database"] = cursor.fetchone()[0] == 1
        except Exception as exc:
            checks["database"] = False
            checks["database_error"] = str(exc)
        try:
            marker = f"health-{timezone.now().timestamp()}"
            cache.set("healthpilot-admin-health", marker, 20)
            checks["cache"] = cache.get("healthpilot-admin-health") == marker
        except Exception as exc:
            checks["cache"] = False
            checks["cache_error"] = str(exc)
        checks["workflow_actions_24h"] = WorkflowActionEvent.objects.filter(created_at__gte=timezone.now() - timedelta(hours=24)).count()
        checks["failed_security_events_24h"] = AuditEvent.objects.filter(decision=AuditEvent.Decision.DENY, created_at__gte=timezone.now() - timedelta(hours=24)).count()
        checks["active_privileged_grants"] = PrivilegedAccessGrant.objects.filter(status=PrivilegedAccessGrant.Status.ACTIVE, expires_at__gt=timezone.now()).count()
        return Response({"ready": bool(checks.get("database") and checks.get("cache")), "checks": checks, "checked_at": timezone.now()})
