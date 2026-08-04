from django.db.models import Q
from django.utils import timezone

from clinical.models import Allergy, CarePlan, ClinicalEncounter, Condition, MedicationStatement, Observation
from governance.models import Consent

FHIR_VERSION = "4.0.1"
FHIR_FORMAT = "MyDoctor FHIR R4-aligned draft export; not a certified national implementation guide"


def _reference(resource_type, object_id):
    return f"{resource_type}/{object_id}"


def _coding(system, code, display):
    coding = {"system": system, "code": code, "display": display}
    return {"coding": [coding], "text": display}


def _compact(value):
    """Remove null values from generated resources while preserving false/zero."""

    if isinstance(value, dict):
        return {key: _compact(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_compact(item) for item in value if item is not None]
    return value


def _entry(resource):
    resource = _compact(resource)
    return {
        "fullUrl": f"urn:uuid:mydoctor-{resource['resourceType'].lower()}-{resource['id']}",
        "resource": resource,
    }


def patient_resource(patient):
    profile = getattr(patient, "patient_profile", None)
    resource = {
        "resourceType": "Patient",
        "id": str(patient.id),
        "meta": {"tag": [{"system": "urn:mydoctor:export", "code": "r4-aligned-draft", "display": FHIR_FORMAT}]},
        "identifier": [{"system": "urn:mydoctor:patient-id", "value": str(patient.id)}],
        "active": patient.is_active,
        "name": [{"use": "official", "family": patient.last_name or "", "given": [patient.first_name] if patient.first_name else []}],
        "telecom": [item for item in [
            {"system": "phone", "value": patient.phone, "use": "mobile"} if patient.phone else None,
            {"system": "email", "value": patient.email, "use": "home"} if patient.email else None,
        ] if item],
    }
    if profile:
        if profile.gender:
            resource["gender"] = profile.gender
        if profile.dob:
            resource["birthDate"] = profile.dob.isoformat()
        if profile.address:
            resource["address"] = [{"text": profile.address}]
    return resource


def allergy_resource(obj):
    return {
        "resourceType": "AllergyIntolerance",
        "id": str(obj.id),
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active" if obj.status == obj.Status.ACTIVE else "inactive"}]},
        "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification", "code": {
            obj.Verification.CLINICIAN_VERIFIED: "confirmed",
            obj.Verification.REFUTED: "refuted",
        }.get(obj.verification, "unconfirmed")}]},
        "patient": {"reference": _reference("Patient", obj.patient_id)},
        "code": _coding("urn:mydoctor:local:allergy", str(obj.id), obj.substance),
        "reaction": [{"manifestation": [{"text": obj.reaction}], "severity": obj.severity if obj.severity in ["mild", "moderate", "severe"] else None}] if obj.reaction else [],
        "recordedDate": obj.created_at.isoformat(),
    }


def condition_resource(obj):
    return {
        "resourceType": "Condition",
        "id": str(obj.id),
        "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": obj.clinical_status}]},
        "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": {
            obj.Verification.PATIENT_REPORTED: "unconfirmed",
            obj.Verification.PROVISIONAL: "provisional",
            obj.Verification.CONFIRMED: "confirmed",
            obj.Verification.REFUTED: "refuted",
        }.get(obj.verification, "unconfirmed")}]},
        "subject": {"reference": _reference("Patient", obj.patient_id)},
        "code": _coding(obj.code_system or "urn:mydoctor:local:condition", obj.code or str(obj.id), obj.display),
        "onsetDateTime": obj.onset_date.isoformat() if obj.onset_date else None,
        "recordedDate": obj.created_at.isoformat(),
        "note": [{"text": obj.notes}] if obj.notes else [],
    }


def medication_resource(obj):
    return {
        "resourceType": "MedicationStatement",
        "id": str(obj.id),
        "status": obj.status,
        "subject": {"reference": _reference("Patient", obj.patient_id)},
        "medicationCodeableConcept": _coding("urn:mydoctor:local:medication", str(obj.id), obj.medication_name),
        "dosage": [{"text": " ".join(part for part in [obj.dose, obj.frequency, obj.route] if part)}],
        "dateAsserted": obj.created_at.isoformat(),
        "note": [{"text": obj.notes}] if obj.notes else [],
    }


def observation_resource(obj):
    resource = {
        "resourceType": "Observation",
        "id": str(obj.id),
        "status": "final",
        "category": [{"text": obj.category}],
        "code": _coding(obj.code_system or "urn:mydoctor:local:observation", obj.code or str(obj.id), obj.display),
        "subject": {"reference": _reference("Patient", obj.patient_id)},
        "effectiveDateTime": obj.observed_at.isoformat(),
        "issued": obj.created_at.isoformat(),
        "interpretation": [{"text": obj.interpretation}] if obj.interpretation else [],
    }
    if obj.value_numeric is not None:
        resource["valueQuantity"] = {"value": float(obj.value_numeric), "unit": obj.unit or ""}
    else:
        resource["valueString"] = obj.value_text
    return resource


def encounter_resource(obj):
    return {
        "resourceType": "Encounter",
        "id": str(obj.id),
        "status": "finished" if obj.status in [obj.Status.FINAL, obj.Status.AMENDED] else "in-progress",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "VR" if obj.appointment.type == "online" else "AMB"},
        "subject": {"reference": _reference("Patient", obj.patient_id)},
        "participant": [{"individual": {"reference": _reference("Practitioner", obj.doctor_id)}}],
        "appointment": [{"reference": _reference("Appointment", obj.appointment_id)}],
        "period": {"start": obj.created_at.isoformat(), "end": obj.signed_at.isoformat() if obj.signed_at else None},
        "reasonCode": [{"text": obj.chief_complaint}] if obj.chief_complaint else [],
        "note": [{"text": text} for text in [obj.assessment, obj.treatment_plan, obj.safety_net_advice] if text],
    }


def care_plan_resource(obj):
    return {
        "resourceType": "CarePlan",
        "id": str(obj.id),
        "status": "on-hold" if obj.status == obj.Status.ON_HOLD else obj.status,
        "intent": "plan",
        "title": obj.title,
        "description": obj.description,
        "subject": {"reference": _reference("Patient", obj.patient_id)},
        "author": {"reference": _reference("Practitioner", obj.author_id)} if obj.author_id else None,
        "period": {
            "start": obj.starts_on.isoformat() if obj.starts_on else None,
            "end": obj.ends_on.isoformat() if obj.ends_on else None,
        },
        "goal": [{"description": {"text": goal if isinstance(goal, str) else str(goal)}} for goal in obj.goals],
    }


def consent_resource(obj):
    return {
        "resourceType": "Consent",
        "id": str(obj.id),
        "status": "active" if obj.is_current else "inactive",
        "scope": {"text": obj.consent_type},
        "category": [{"text": obj.purpose}],
        "patient": {"reference": _reference("Patient", obj.patient_id)},
        "dateTime": obj.granted_at.isoformat(),
        "provision": {
            "type": "permit",
            "period": {
                "start": obj.valid_from.isoformat(),
                "end": obj.valid_until.isoformat() if obj.valid_until else None,
            },
            "purpose": [{"system": "urn:mydoctor:purpose", "code": obj.purpose}],
            "data": [{"meaning": "instance", "reference": {"display": category}} for category in obj.data_categories],
        },
    }


def patient_summary_bundle(patient, viewer=None):
    entries = [_entry(patient_resource(patient))]
    entries.extend(_entry(allergy_resource(obj)) for obj in Allergy.objects.filter(patient=patient))
    entries.extend(_entry(condition_resource(obj)) for obj in Condition.objects.filter(patient=patient))
    entries.extend(_entry(medication_resource(obj)) for obj in MedicationStatement.objects.filter(patient=patient))
    entries.extend(_entry(observation_resource(obj)) for obj in Observation.objects.filter(patient=patient))
    entries.extend(
        _entry(encounter_resource(obj))
        for obj in ClinicalEncounter.objects.filter(patient=patient).exclude(status=ClinicalEncounter.Status.DRAFT).select_related("appointment")
    )
    entries.extend(_entry(care_plan_resource(obj)) for obj in CarePlan.objects.filter(patient=patient))

    consent_qs = Consent.objects.filter(patient=patient)
    if viewer is not None:
        try:
            from enterprise.access import active_role
            viewer_role = active_role(viewer)
        except Exception:
            viewer_role = getattr(viewer, "role", None)
        if viewer_role in {"doctor", "clinical_officer", "dentist", "physiotherapist", "nutritionist", "psychologist", "medical_director"}:
            consent_qs = consent_qs.filter(Q(granted_to=viewer) | Q(granted_to__isnull=True))
    entries.extend(_entry(consent_resource(obj)) for obj in consent_qs)
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": timezone.now().isoformat(),
        "meta": {"tag": [{"system": "urn:mydoctor:export", "code": "r4-aligned-draft", "display": FHIR_FORMAT}]},
        "total": len(entries),
        "entry": entries,
    }
