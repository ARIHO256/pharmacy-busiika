"""Central request-scoped role, organization and permission resolution.

Every authorization decision for the acting user should pass through this module.
``accounts.User.role`` is retained as a registration/default role only.  The active
``RoleContext`` is authoritative for multi-role and multi-organization sessions.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import BasePermission

from accounts.roles import PROFESSIONAL_ROLES

PLATFORM_SUPER_ADMIN_ROLES = {"admin", "platform_super_admin"}
OPERATIONS_ADMIN_ROLES = {"operations_admin"}
COMPLIANCE_ADMIN_ROLES = {"compliance_admin"}
CLINICAL_SAFETY_ADMIN_ROLES = {"clinical_safety_admin"}
ADMIN_ROLE_CODES = (
    PLATFORM_SUPER_ADMIN_ROLES
    | OPERATIONS_ADMIN_ROLES
    | COMPLIANCE_ADMIN_ROLES
    | CLINICAL_SAFETY_ADMIN_ROLES
)

ORG_MANAGEMENT_ROLES = {
    "facility_manager",
    "medical_director",
    "finance_manager",
    "quality_officer",
    "compliance_officer",
    "hr_officer",
    "hospital",
    "pharmacy",
    "lab",
    "insurance",
}


def active_context_for(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    try:
        active = user.active_role_context
        if active.context.is_current:
            return active.context
    except Exception:
        pass
    try:
        return (
            user.role_contexts.filter(active=True)
            .filter(Q(starts_on__isnull=True) | Q(starts_on__lte=timezone.localdate()))
            .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=timezone.localdate()))
            .order_by("-is_primary", "id")
            .first()
        )
    except Exception:
        return None


def registration_role(user):
    """Return the immutable/default registration identity, never for authorization."""
    return getattr(user, "role", "") if user else ""


def active_role(user):
    context = active_context_for(user)
    return context.role_code if context else registration_role(user)


def has_role_identity(user, role_code):
    """Check whether an account owns a role identity independent of active context.

    Use this for profile selection, notification routing and subject validation.
    Authorization must still use ``active_role`` and the active organization scope.
    """
    if not user:
        return False
    if registration_role(user) == role_code:
        return True
    try:
        return user.role_contexts.filter(role_code=role_code, active=True).exists()
    except Exception:
        return False


def active_organization(user):
    context = active_context_for(user)
    if context and context.organization_id:
        return context.organization
    try:
        from workforce.access import organization_for_user

        return organization_for_user(user)
    except Exception:
        return None


def active_location(user):
    context = active_context_for(user)
    return context.location if context and context.location_id else None


def active_department(user):
    context = active_context_for(user)
    return context.department if context and context.department_id else None


def is_platform_super_admin(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (getattr(user, "is_superuser", False) or active_role(user) in PLATFORM_SUPER_ADMIN_ROLES)
    )


def is_operations_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and active_role(user) in OPERATIONS_ADMIN_ROLES)


def is_compliance_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and active_role(user) in COMPLIANCE_ADMIN_ROLES)


def is_clinical_safety_admin(user):
    return bool(user and getattr(user, "is_authenticated", False) and active_role(user) in CLINICAL_SAFETY_ADMIN_ROLES)


def is_any_admin(user):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (getattr(user, "is_superuser", False) or active_role(user) in ADMIN_ROLE_CODES)
    )


def effective_permissions(user):
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    if is_platform_super_admin(user):
        return {"*"}
    context = active_context_for(user)
    permissions = set(context.permissions or []) if context else set()
    try:
        from workforce.access_control import permissions_for_user

        permissions |= set(permissions_for_user(user, context.organization if context else None))
    except Exception:
        pass
    if context:
        now = timezone.now()
        delegations = context.delegations_received.filter(
            revoked_at__isnull=True, starts_at__lte=now, ends_at__gte=now
        )
        for delegation in delegations:
            permissions |= set(delegation.permissions or [])
    return permissions


def has_permission(user, permission):
    permissions = effective_permissions(user)
    return "*" in permissions or permission in permissions


def can_manage_platform(user):
    """Full platform configuration and identity administration.

    IT support and compliance roles are intentionally excluded.  They receive only
    the narrowly-scoped capabilities exposed by the functions below.
    """

    return is_platform_super_admin(user)


def can_manage_operations(user):
    return is_platform_super_admin(user) or is_operations_admin(user)


def can_manage_integrations(user):
    role = active_role(user)
    return is_platform_super_admin(user) or role in {"it_support"} or has_permission(user, "platform.integrations.manage")


def can_view_system_health(user):
    role = active_role(user)
    return is_platform_super_admin(user) or role in {"it_support", "operations_admin"} or has_permission(user, "platform.health.view")


def can_review_compliance(user):
    role = active_role(user)
    return is_platform_super_admin(user) or is_compliance_admin(user) or role == "compliance_officer" or has_permission(user, "compliance.review")


def can_review_clinical_safety(user):
    role = active_role(user)
    return is_platform_super_admin(user) or is_clinical_safety_admin(user) or role == "medical_director" or has_permission(user, "clinical_safety.review")


def can_manage_org(user, organization):
    if not organization:
        return can_manage_platform(user)
    if is_platform_super_admin(user):
        return True
    context = active_context_for(user)
    if not context or context.organization_id != organization.id:
        return False
    return active_role(user) in ORG_MANAGEMENT_ROLES or has_permission(user, "organization.manage")


def scope_queryset(user, queryset, *, organization_field="organization", location_field="location", department_field="department"):
    """Apply active organization, branch and department scope when those fields exist."""

    if is_platform_super_admin(user):
        return queryset
    context = active_context_for(user)
    if not context:
        return queryset.none()
    filters = Q()
    model_fields = {field.name for field in queryset.model._meta.get_fields()}
    if context.organization_id and organization_field in model_fields:
        filters &= Q(**{f"{organization_field}_id": context.organization_id})
    if context.location_id and location_field in model_fields:
        filters &= Q(**{f"{location_field}_id": context.location_id})
    if context.department_id and department_field in model_fields:
        filters &= Q(**{f"{department_field}_id": context.department_id})
    return queryset.filter(filters) if filters.children else queryset


def record_queryset_for(user, queryset):
    if is_platform_super_admin(user):
        return queryset
    role = active_role(user)
    org = active_organization(user)
    location = active_location(user)
    department = active_department(user)
    if role == "patient":
        return queryset.filter(Q(patient=user) | Q(owner=user) | Q(assigned_to=user)).distinct()
    filters = Q(owner=user) | Q(assigned_to=user) | Q(created_by=user)
    if org:
        filters |= Q(organization=org)
    if location:
        filters &= Q(location__isnull=True) | Q(location=location)
    if department:
        filters &= Q(department__isnull=True) | Q(department=department)
    if role in PROFESSIONAL_ROLES:
        filters |= Q(
            patient__care_relationships__practitioner=user,
            patient__care_relationships__status="active",
        )
    return queryset.filter(filters).distinct()


class EnterpriseAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class PlatformAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return can_manage_platform(request.user)


class OperationsAdminOnly(BasePermission):
    def has_permission(self, request, view):
        return can_manage_operations(request.user)


class ComplianceAccessOnly(BasePermission):
    def has_permission(self, request, view):
        return can_review_compliance(request.user)


class ClinicalSafetyAccessOnly(BasePermission):
    def has_permission(self, request, view):
        return can_review_clinical_safety(request.user)


class EnterpriseResourcePermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if is_platform_super_admin(request.user):
            return True
        role = active_role(request.user)
        roles = set(getattr(view, "resource_roles", []) or [])
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            read_roles = set(getattr(view, "read_roles", []) or roles)
            return not read_roles or role in read_roles
        return not roles or role in roles
