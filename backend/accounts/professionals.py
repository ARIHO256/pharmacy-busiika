"""Shared professional profile helpers.

The project keeps legacy ``DoctorProfile`` and organization-invited ``StaffProfile``
records, but booking, verification and public-directory code should not need to
know which table stores a clinician's data.
"""
from django.utils import timezone

from .models import DoctorProfile, ProfileStatus, StaffProfile
from .roles import BOOKABLE_PROVIDER_ROLES, PROFESSIONAL_ROLES


def regulated_professional_profile(user):
    """Return the credential-bearing profile for any regulated professional.

    Doctors retain their legacy ``DoctorProfile`` while every other regulated
    cadre is represented by ``StaffProfile``.  Keeping this distinction in one
    helper prevents authorization code from silently treating nurses,
    pharmacists, radiology staff or allied-health practitioners as unverified.
    """
    if getattr(user, "role", None) == "doctor":
        return getattr(user, "doctor_profile", None)
    if getattr(user, "role", None) in PROFESSIONAL_ROLES:
        return getattr(user, "staff_profile", None)
    return None


def regulated_professional_is_verified(user):
    """Return whether a regulated professional is active and credential-valid."""
    if not user or not getattr(user, "is_active", False) or not getattr(user, "is_verified", False):
        return False
    if getattr(user, "role", None) not in PROFESSIONAL_ROLES:
        return False
    profile = regulated_professional_profile(user)
    if not profile or profile.status != ProfileStatus.VERIFIED:
        return False
    expiry = getattr(profile, "license_expires_on", None)
    return not expiry or expiry >= timezone.localdate()


def professional_profile(user):
    if getattr(user, "role", None) == "doctor":
        return getattr(user, "doctor_profile", None)
    if getattr(user, "role", None) in BOOKABLE_PROVIDER_ROLES:
        return getattr(user, "staff_profile", None)
    return None


def professional_is_verified(user, *, require_bookable=False):
    if getattr(user, "role", None) not in BOOKABLE_PROVIDER_ROLES:
        return False
    if not regulated_professional_is_verified(user):
        return False
    profile = professional_profile(user)
    if require_bookable and isinstance(profile, StaffProfile) and not profile.offers_appointments:
        return False
    return True


def public_professional_payload(user, *, detail=False):
    profile = professional_profile(user)
    if isinstance(profile, DoctorProfile):
        cadre = profile.get_cadre_display() or profile.cadre
        specialization = profile.specialization
        hospital = profile.hospital
        experience_years = profile.experience_years
        fees = profile.fees
        rating = profile.average_rating
    else:
        cadre = profile.cadre or user.get_role_display()
        specialization = profile.specialty
        hospital = profile.workplace
        experience_years = profile.experience_years
        fees = profile.consultation_fee
        rating = profile.average_rating
    data = {
        "id": user.id,
        "role": user.role,
        "role_label": user.get_role_display(),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "cadre": cadre,
        "specialization": specialization,
        "hospital": hospital,
        "experience_years": experience_years,
        "fees": fees,
        "bio": profile.bio,
        "average_rating": rating,
    }
    if detail:
        data["status"] = profile.status
    return data
