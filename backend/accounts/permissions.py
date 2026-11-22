from rest_framework.permissions import BasePermission


class IsRole(BasePermission):
    """Usage: permission_classes=[IsRole]; set allowed_roles on the view."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        roles = getattr(view, "allowed_roles", None)
        if not roles:
            return True
        return request.user.role in roles


class IsOwnerOrAdmin(BasePermission):
    """For objects exposing `user`/`patient` FK or being the user itself."""

    def has_object_permission(self, request, view, obj):
        if request.user.role == "admin":
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "patient", None) or obj
        return owner == request.user
