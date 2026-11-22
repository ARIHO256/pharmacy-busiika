"""Organization and patient access boundaries shared by operational APIs."""
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from registry.models import Organization, PractitionerRole
from workforce.models import StaffMembership


def organizations(user):
    if not user.is_authenticated or not user.is_active:
        return Organization.objects.none()
    if user.role == "admin":
        return Organization.objects.all()
    today = timezone.localdate()
    memberships = StaffMembership.objects.filter(user=user, status="active").filter(
        Q(starts_on__isnull=True) | Q(starts_on__lte=today)
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today)).values("organization_id")
    roles = PractitionerRole.objects.filter(practitioner=user, active=True).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=today)
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).values("organization_id")
    verified = Organization.objects.filter(active=True, status="verified")
    scope = verified.filter(Q(owner=user) | Q(pk__in=memberships) | Q(pk__in=roles))
    if user.role == "pharmacist" and user.is_verified:
        from services.views import provider_account_for

        pharmacy = provider_account_for(user, "pharmacy")
        if pharmacy:
            scope = scope | verified.filter(owner=pharmacy, organization_type="pharmacy")
    return scope.distinct()


def require_role(user, roles):
    if user.role not in set(roles) | {"admin"}:
        raise PermissionDenied("Role not permitted for this action.")
    if user.role in {"doctor", "nurse", "pharmacist", "lab_technician"} and not user.is_verified:
        raise PermissionDenied("Professional verification is required.")


def require_organization(user, organization_id, roles=None):
    if roles:
        require_role(user, roles)
    try:
        organization = organizations(user).filter(pk=organization_id).first()
    except (ValueError, TypeError):
        raise ValidationError({"organization": "A valid organization ID is required."})
    if organization is None:
        raise PermissionDenied("No active membership in this verified organization.")
    return organization


def patient_is_valid(patient):
    if patient.role != "patient" or not patient.is_active:
        raise ValidationError({"patient": "An active patient account is required."})


def clinician_at(user, organization):
    require_role(user, {"doctor", "nurse"})
    require_organization(user, organization.pk)


def require_patient_access(user, patient):
    from clinical.services import can_access_patient
    allowed, _, reason = can_access_patient(user, patient)
    if not allowed:
        raise PermissionDenied(reason)
