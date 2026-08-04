from django.db.models import Q
from django.utils import timezone

from accounts.models import PatientRelationship
from accounts.professionals import regulated_professional_is_verified
from accounts.roles import CLINICAL_ROLES
from enterprise.access import active_role, is_any_admin
from appointments.models import Appointment
from governance.models import AuditEvent, Consent
from governance.services import active_break_glass, active_privileged_access, audit, current_consent


def care_relationship(doctor, patient):
    try:
        from registry.models import CareRelationship

        if CareRelationship.objects.filter(
            practitioner=doctor,
            patient=patient,
            status=CareRelationship.Status.ACTIVE,
        ).exists():
            return True
    except Exception:
        pass
    # Compatibility fallback for data created before the registry was introduced.
    return Appointment.objects.filter(doctor=doctor, patient=patient).exclude(
        status=Appointment.Status.CANCELLED
    ).exists()


def can_access_patient(user, patient, *, required_scope="patient_summary", write=False):
    if not user or not user.is_authenticated:
        return False, False, "Unauthenticated"
    role = active_role(user)
    if is_any_admin(user):
        grant = active_privileged_access(user, patient, required_scope=required_scope, write=write)
        if grant:
            return True, False, f"Approved privileged access #{grant.id}"
        return False, False, "Administrator clinical access requires an approved, patient-specific elevation grant"
    if user.id == patient.id and role == "patient":
        return True, False, "Patient self-access"

    # A verified caregiver may access only the scopes explicitly granted by the
    # patient/administrator.  Adult relationships remain pending until reviewed.
    if role == "patient":
        relationship = PatientRelationship.objects.filter(
            caregiver=user,
            patient=patient,
            status=PatientRelationship.Status.ACTIVE,
            can_view_records=True,
        ).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())).first()
        if relationship:
            return True, False, f"Authorized {relationship.get_relationship_display()} access"
        return False, False, "No active record-access authority"

    if role not in CLINICAL_ROLES:
        return False, False, "Role not permitted"
    if not regulated_professional_is_verified(user):
        return False, False, "Professional credential is not active"
    emergency = active_break_glass(user, patient)
    if emergency:
        return True, True, "Active emergency access"
    if not care_relationship(user, patient):
        return False, False, "No care relationship"
    consent = current_consent(
        patient,
        [
            Consent.Type.TREATMENT,
            Consent.Type.TELEMEDICINE,
            Consent.Type.DATA_SHARING,
        ],
        recipient=user,
    )
    if consent:
        return True, False, "Active patient consent"
    # Legacy records and fixtures may pre-date executable consent. Preserve the
    # existing care workflow only when the patient has no consent records at all.
    # New bookings create named treatment consent automatically.
    if not Consent.objects.filter(patient=patient).exists():
        return True, False, "Legacy care relationship (consent migration required)"
    return False, False, "No active treatment consent"


def resolve_patient_access(request, patient, *, required_scope="patient_summary"):
    write = request.method not in {"GET", "HEAD", "OPTIONS"}
    allowed, emergency, reason = can_access_patient(
        request.user,
        patient,
        required_scope=required_scope,
        write=write,
    )
    audit(
        actor=request.user,
        patient=patient,
        action="clinical.record.access",
        resource_type="PatientRecord",
        resource_id=str(patient.id),
        purpose="emergency" if emergency else "treatment",
        decision=AuditEvent.Decision.ALLOW if allowed else AuditEvent.Decision.DENY,
        emergency_access=emergency,
        metadata={"reason": reason, "scope": required_scope, "write": write},
        request=request,
    )
    return allowed, emergency, reason
