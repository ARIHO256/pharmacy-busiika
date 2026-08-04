"""Registry synchronization services.

The legacy provider profile remains the lightweight portal profile.  The
registry organization is the canonical organization identity used by clinical,
compliance and interoperability workflows.  Keeping synchronization in one
service prevents account views from duplicating registry rules.
"""

from django.db import IntegrityError, transaction

from accounts.models import ProfileStatus, User
from enterprise.access import registration_role

from .models import Organization


ROLE_TO_ORGANIZATION_TYPE = {
    User.Role.PHARMACY: Organization.Type.PHARMACY,
    User.Role.LAB: Organization.Type.LABORATORY,
    User.Role.HOSPITAL: Organization.Type.HOSPITAL,
    User.Role.INSURANCE: Organization.Type.INSURER,
}

ROLE_TO_ALLOWED_ORGANIZATION_TYPES = {
    User.Role.HOSPITAL: {Organization.Type.HOSPITAL, Organization.Type.CLINIC},
    User.Role.PHARMACY: {Organization.Type.PHARMACY},
    User.Role.LAB: {Organization.Type.LABORATORY},
    User.Role.INSURANCE: {Organization.Type.INSURER},
}

PROFILE_TO_ORGANIZATION_STATUS = {
    ProfileStatus.PENDING: Organization.Status.PENDING,
    ProfileStatus.VERIFIED: Organization.Status.VERIFIED,
    ProfileStatus.SUSPENDED: Organization.Status.SUSPENDED,
    ProfileStatus.REJECTED: Organization.Status.REJECTED,
    ProfileStatus.EXPIRED: Organization.Status.INACTIVE,
    ProfileStatus.REVOKED: Organization.Status.INACTIVE,
}


def organization_type_for_role(role):
    return ROLE_TO_ORGANIZATION_TYPE.get(role)


def organization_type_for_profile(user, profile=None):
    """Resolve a provider profile to a canonical registry organization type."""
    role_code = registration_role(user)
    default_type = organization_type_for_role(role_code)
    candidate = getattr(profile, "organization_type", None) if profile is not None else None
    allowed = ROLE_TO_ALLOWED_ORGANIZATION_TYPES.get(role_code, set())
    return candidate if candidate in allowed else default_type


def _default_organization_name(user):
    full_name = user.get_full_name().strip()
    if full_name:
        return full_name
    local_part = (user.email or "Healthcare provider").split("@", 1)[0]
    readable = local_part.replace(".", " ").replace("_", " ").replace("-", " ").strip()
    return readable.title() or "Healthcare provider"


@transaction.atomic
def sync_provider_organization(user, profile, *, authoritative_status=False):
    """Create or update the canonical registry organization for a provider.

    The function is idempotent. Ordinary profile edits do not promote or demote
    administrator-controlled verification. Administrative workflows may pass
    ``authoritative_status=True`` to synchronize a reviewed status decision.
    """

    organization_type = organization_type_for_profile(user, profile)
    if not organization_type:
        return None

    organization = (
        Organization.objects.select_for_update()
        .filter(owner=user)
        .order_by("id")
        .first()
    )

    legal_name = (profile.org_name or "").strip() or _default_organization_name(user)
    requested_status = PROFILE_TO_ORGANIZATION_STATUS.get(
        profile.status, Organization.Status.PENDING
    )

    defaults = {
        "legal_name": legal_name,
        "trading_name": (profile.org_name or "").strip(),
        "license_number": (profile.license_number or "").strip(),
        "issuing_authority": getattr(profile, "license_issuer", "") or "",
        "license_issued_on": getattr(profile, "license_issued_on", None),
        "license_expires_on": getattr(profile, "license_expires_on", None),
        "contact_email": user.email,
        "phone": user.phone or "",
        "address": profile.address or "",
        "district": getattr(profile, "district", "") or "",
        "license_document": getattr(profile, "license_document", None),
        "services_description": getattr(profile, "services_description", "") or "",
        "active": requested_status != Organization.Status.SUSPENDED,
    }

    if organization is None:
        try:
            return Organization.objects.create(
                owner=user,
                organization_type=organization_type,
                status=requested_status,
                **defaults,
            )
        except IntegrityError as exc:
            # Give callers a domain-friendly error instead of leaking a raw
            # unique-constraint failure for a duplicate provider licence.
            if defaults["license_number"]:
                raise ValueError(
                    "This licence number is already registered for another organization."
                ) from exc
            raise

    organization.organization_type = organization_type
    organization.legal_name = defaults["legal_name"]
    organization.trading_name = defaults["trading_name"]
    organization.contact_email = defaults["contact_email"]
    organization.phone = defaults["phone"]
    organization.address = defaults["address"]
    organization.district = defaults["district"]
    organization.license_document = defaults["license_document"]
    organization.services_description = defaults["services_description"]
    organization.issuing_authority = defaults["issuing_authority"]
    organization.license_issued_on = defaults["license_issued_on"]
    organization.license_expires_on = defaults["license_expires_on"]

    if defaults["license_number"]:
        duplicate = (
            Organization.objects.filter(
                organization_type=organization_type,
                license_number=defaults["license_number"],
            )
            .exclude(pk=organization.pk)
            .exists()
        )
        if duplicate:
            raise ValueError(
                "This licence number is already registered for another organization."
            )
        organization.license_number = defaults["license_number"]

    # Suspension is safety-sensitive and must propagate immediately. Other
    # status changes require an explicitly authoritative administrative flow.
    if authoritative_status:
        organization.status = requested_status
        organization.active = requested_status not in {
            Organization.Status.SUSPENDED,
            Organization.Status.INACTIVE,
        }
    elif requested_status == Organization.Status.SUSPENDED:
        organization.status = Organization.Status.SUSPENDED
        organization.active = False
    elif organization.status == Organization.Status.PENDING:
        organization.active = True

    organization.save()
    return organization
