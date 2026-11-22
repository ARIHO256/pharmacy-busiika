from registry.models import Organization, PractitionerRole

from .models import StaffMembership


def organization_for_user(user, organization_id=None):
    """Resolve the organization currently in scope for an authenticated user."""
    if not user or not user.is_authenticated:
        return None
    if user.role == "admin":
        if organization_id:
            return Organization.objects.filter(pk=organization_id).first()
        return None
    owned = Organization.objects.filter(owner=user, active=True)
    if organization_id:
        owned = owned.filter(pk=organization_id)
    organization = owned.first()
    if organization:
        return organization
    memberships = StaffMembership.objects.filter(
        user=user, status=StaffMembership.Status.ACTIVE, organization__active=True
    ).select_related("organization")
    if organization_id:
        memberships = memberships.filter(organization_id=organization_id)
    membership = memberships.order_by("-is_primary", "id").first()
    if membership:
        return membership.organization
    roles = PractitionerRole.objects.filter(
        practitioner=user, active=True, organization__active=True
    ).select_related("organization")
    if organization_id:
        roles = roles.filter(organization_id=organization_id)
    role = roles.first()
    return role.organization if role else None


def membership_for_user(user, organization=None):
    qs = StaffMembership.objects.filter(user=user, status=StaffMembership.Status.ACTIVE)
    if organization is not None:
        qs = qs.filter(organization=organization)
    return qs.select_related("organization", "department").order_by("-is_primary", "id").first()


def user_can_manage_organization(user, organization):
    if user.role == "admin":
        return True
    if organization.owner_id == user.id:
        return True
    return StaffMembership.objects.filter(
        user=user,
        organization=organization,
        status=StaffMembership.Status.ACTIVE,
        role="facility_manager",
    ).exists()
