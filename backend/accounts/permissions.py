from rest_framework.permissions import BasePermission


def request_role(request):
    """Resolve the active enterprise role for the acting request principal."""
    try:
        from enterprise.access import active_role

        return active_role(request.user)
    except Exception:
        return getattr(request.user, "role", "")


def request_context(request):
    try:
        from enterprise.access import active_context_for

        return active_context_for(request.user)
    except Exception:
        return None


def role_allowed(role, allowed_roles, user=None):
    allowed = set(allowed_roles or [])
    if not allowed:
        return True
    # A Django superuser remains a platform super administrator, but never
    # silently inherits a clinician, cashier, records or facility role. Clinical
    # access is granted separately through the privileged-access workflow.
    # A platform super administrator may perform platform administration but does
    # not silently inherit clinical roles.  Clinical access uses an elevation grant.
    if role in {"admin", "platform_super_admin"}:
        return bool(allowed & {"admin", "platform_super_admin"})
    if role == "operations_admin":
        return "operations_admin" in allowed
    if role == "compliance_admin":
        return bool(allowed & {"compliance_admin", "compliance_officer"})
    if role == "clinical_safety_admin":
        return bool(allowed & {"clinical_safety_admin", "medical_director"})
    return role in allowed


class IsRole(BasePermission):
    """Authorize using the active role context rather than the registration role."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return role_allowed(request_role(request), getattr(view, "allowed_roles", None), request.user)


class IsOwnerOrAdmin(BasePermission):
    """For objects exposing ``user``/``patient`` FK or being the user itself."""

    def has_object_permission(self, request, view, obj):
        if request_role(request) in {"admin", "platform_super_admin"}:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "patient", None) or obj
        return owner == request.user
