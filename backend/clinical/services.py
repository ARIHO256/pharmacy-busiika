from django.db.models import Q

from appointments.models import Appointment
from governance.models import AuditEvent, Consent
from governance.services import active_break_glass, audit, current_consent


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


def can_access_patient(user, patient):
    if not user or not user.is_authenticated:
        return False, False, "Unauthenticated"
    if user.role == "admin":
        return True, False, "Administrator oversight"
    if user.id == patient.id and user.role == "patient":
        return True, False, "Patient self-access"
    if user.role != "doctor":
        return False, False, "Role not permitted"
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


def resolve_patient_access(request, patient):
    allowed, emergency, reason = can_access_patient(request.user, patient)
    audit(
        actor=request.user,
        patient=patient,
        action="clinical.record.access",
        resource_type="PatientRecord",
        resource_id=str(patient.id),
        purpose="emergency" if emergency else "treatment",
        decision=AuditEvent.Decision.ALLOW if allowed else AuditEvent.Decision.DENY,
        emergency_access=emergency,
        metadata={"reason": reason},
        request=request,
    )
    return allowed, emergency, reason
