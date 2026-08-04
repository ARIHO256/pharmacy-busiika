"""Idempotent enterprise seed covering every one of the 21 implementation areas."""
from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from appointments.models import Appointment
from interoperability.models import OutboxEvent
from operations.models import Admission, AmbulanceDispatch, ImagingOrder
from registry.models import Organization, OrganizationLocation, PractitionerCredential
from workforce.models import Department, StaffMembership

from .models import (
    ActiveRoleContext, AmbulanceTelemetry, AmbulanceVehicle, ClinicalCode,
    CommunicationConsent, ContentEntry, DuplicatePatientCandidate, EnterpriseRecord,
    EscalationPolicy, EscalationStep, EventDelivery, EventSchema, FeatureConfiguration,
    FHIRResource, FHIRSubscription, ImagingStudy, IntegrationEndpoint,
    MasterPatientIndex, MedicationInteraction, MedicationKnowledge, NotificationProvider,
    PACSNode, PartnerApplication, PayerContract, RecordsRequest, RegulatorConnector,
    ReportSchedule, RoleContext, SavedReport, SecurityOperation, TariffSchedule,
    VerificationAutomation, WorkflowTransition,
)
from .schemas import RECORD_SCHEMAS, WORKFLOWS

User = get_user_model()
NOW = timezone.now()
TODAY = timezone.localdate()

ROLE_EMAIL = {
    "admin": "admin@mydoctor.test", "patient": "patient1@mydoctor.test", "doctor": "dr.nakato@mydoctor.test",
    "clinical_officer": "clinical.officer@mydoctor.test", "dentist": "dentist@mydoctor.test",
    "medical_director": "medical.director@mydoctor.test", "nurse": "nurse@mydoctor.test",
    "midwife": "midwife@mydoctor.test", "theatre_nurse": "theatre.nurse@mydoctor.test",
    "anaesthetist": "anaesthetist@mydoctor.test", "radiologist": "radiologist@mydoctor.test",
    "radiographer": "radiographer@mydoctor.test", "physiotherapist": "physio@mydoctor.test",
    "nutritionist": "nutrition@mydoctor.test", "psychologist": "psychology@mydoctor.test",
    "paramedic": "paramedic@mydoctor.test", "ambulance_dispatcher": "dispatcher@mydoctor.test",
    "receptionist": "reception@mydoctor.test", "records_officer": "records@mydoctor.test",
    "cashier": "cashier@mydoctor.test", "accountant": "accountant@mydoctor.test",
    "finance_manager": "finance.manager@mydoctor.test", "facility_manager": "manager@mydoctor.test",
    "procurement_officer": "procurement@mydoctor.test", "storekeeper": "storekeeper@mydoctor.test",
    "quality_officer": "quality@mydoctor.test", "compliance_officer": "compliance@mydoctor.test",
    "hr_officer": "hr@mydoctor.test", "it_support": "it@mydoctor.test",
    "pharmacist": "pharmacist.staff@mydoctor.test", "lab_technician": "labtech@mydoctor.test",
    "insurance_officer": "insurance.officer@mydoctor.test", "claims_reviewer": "claims@mydoctor.test",
    "hospital": "hospital@mydoctor.test", "pharmacy": "pharmacy@mydoctor.test",
    "lab": "lab@mydoctor.test", "insurance": "insurance@mydoctor.test",
}


def user_for(role):
    return User.objects.filter(email=ROLE_EMAIL.get(role, ROLE_EMAIL["admin"])).first() or User.objects.filter(role=role).first()


def demo_value(name, spec, index=1):
    kind = spec.get("kind", "text")
    if kind == "number":
        values = {
            "temperature_c": 36.8, "pulse_bpm": 82, "respiratory_rate": 18,
            "systolic": 118, "diastolic": 76, "spo2": 98, "pain_score": 3,
            "fetal_heart_rate": 142, "gestation_weeks": 34, "birth_weight_kg": 3.2,
            "apgar_1": 8, "apgar_5": 9, "score": 2, "latitude": 0.3476,
            "longitude": 32.5825, "amount": 125000,
        }
        return values.get(name, index)
    if kind == "boolean": return True
    if kind == "list": return [f"Demonstration {spec['label'].lower()}"]
    if kind == "json": return {"demo": True, "note": f"Structured {spec['label'].lower()} data"}
    if kind == "date": return (TODAY + timedelta(days=index)).isoformat()
    if kind == "datetime": return (NOW + timedelta(hours=index)).isoformat()
    if kind == "select": return (spec.get("options") or ["routine"])[0]
    if name.endswith("_id"): return 1
    if "reference" in name: return f"DEMO-{index:04d}"
    if "number" in name: return f"NUM-{index:04d}"
    if "status" in name: return "stable"
    if "email" in name: return "demo@mydoctor.test"
    if "phone" in name: return "+256700000001"
    return f"Demonstration {spec['label'].lower()}"


def starting_status(record_type):
    states = list(WORKFLOWS.get(record_type, WORKFLOWS["generic"]).keys())
    return "draft" if "draft" in states else states[0]


@transaction.atomic
def seed_enterprise_demo():
    admin = user_for("admin")
    patient = user_for("patient")
    hospital = Organization.objects.filter(owner__email=ROLE_EMAIL["hospital"]).first() or Organization.objects.filter(organization_type="hospital").first()
    pharmacy = Organization.objects.filter(owner__email=ROLE_EMAIL["pharmacy"]).first()
    lab = Organization.objects.filter(owner__email=ROLE_EMAIL["lab"]).first()
    insurer = Organization.objects.filter(owner__email=ROLE_EMAIL["insurance"]).first()
    location = OrganizationLocation.objects.filter(organization=hospital).first() if hospital else None
    admission = Admission.objects.filter(organization=hospital).first() if hospital else None
    appointment = Appointment.objects.filter(patient=patient).first() if patient else None

    # 1-2. Multi-role contexts and dedicated workspaces.
    for user in User.objects.filter(email__endswith="@mydoctor.test"):
        membership = StaffMembership.objects.filter(user=user, status="active").select_related("organization", "department").first()
        org = membership.organization if membership else ({"hospital": hospital, "pharmacy": pharmacy, "lab": lab, "insurance": insurer}.get(user.role))
        department = membership.department if membership else None
        branch = OrganizationLocation.objects.filter(organization=org).first() if org else None
        context, _ = RoleContext.objects.update_or_create(
            user=user, organization=org, location=branch, department=department, role_code=user.role,
            defaults={"title": membership.job_title if membership else user.get_role_display(), "is_primary": True, "active": True, "created_by": admin},
        )
        ActiveRoleContext.objects.update_or_create(user=user, defaults={"context": context})

    # Deliberate multi-role examples used by the context switcher.
    examples = [
        (user_for("doctor"), "medical_director", "Acting Medical Director", hospital),
        (user_for("nurse"), "midwife", "Maternity Relief Midwife", hospital),
        (user_for("facility_manager"), "finance_manager", "Finance Oversight", hospital),
        (user_for("pharmacist"), "storekeeper", "Pharmacy Stock Controller", pharmacy),
        (user_for("insurance_officer"), "claims_reviewer", "Senior Claims Reviewer", insurer),
    ]
    for user, role, title, org in examples:
        if not user or not org: continue
        RoleContext.objects.update_or_create(
            user=user, organization=org, location=OrganizationLocation.objects.filter(organization=org).first(), department=None, role_code=role,
            defaults={"title": title, "is_primary": False, "active": True, "created_by": admin},
        )

    # 3-19. At least one fully structured, audited workflow record for every schema.
    for index, (record_type, schema) in enumerate(RECORD_SCHEMAS.items(), start=1):
        role = next((role for role in schema["roles"] if user_for(role)), "admin")
        owner = user_for(role) or admin
        target_org = insurer if schema["domain"] == "insurance" else pharmacy if schema["domain"] == "pharmacy" else lab if schema["domain"] == "laboratory" else hospital
        payload = {name: demo_value(name, spec, index) for name, spec in schema["fields"].items() if spec.get("required") or index % 3 != 0}
        record, created = EnterpriseRecord.objects.update_or_create(
            reference=f"ENT-DEMO-{index:04d}",
            defaults={
                "domain": schema["domain"], "record_type": record_type, "organization": target_org,
                "location": OrganizationLocation.objects.filter(organization=target_org).first() if target_org else None,
                "patient": patient if schema["domain"] not in {"finance", "security", "verification", "reporting"} else None,
                "admission": admission if schema["domain"] == "inpatient" else None,
                "appointment": appointment if schema["domain"] in {"specialist", "radiology", "laboratory"} else None,
                "owner": owner, "assigned_to": owner, "status": starting_status(record_type),
                "priority": "critical" if record_type in {"resuscitation_event", "critical_imaging_alert", "security_alert"} else "routine",
                "title": f"Demo {schema['label']}", "summary": f"Production-style demonstration record for {schema['label']}.",
                "payload": payload, "created_by": owner, "updated_by": owner,
                "occurred_at": NOW - timedelta(minutes=index * 7), "due_at": NOW + timedelta(hours=(index % 24) + 1),
            },
        )
        if created:
            WorkflowTransition.objects.create(record=record, action="create", to_status=record.status, actor=owner)

    # Rich time-series demonstrations used by the purpose-built clinical charts.
    series_specs = {
        "partograph_observation": [
            {"cervical_dilation_cm": 2 + index, "fetal_heart_rate": 138 + (index % 4) * 2, "contractions_per_10_min": 2 + index // 3}
            for index in range(8)
        ],
        "anaesthesia_chart": [
            {"heart_rate": 78 + ((index % 5) - 2) * 3, "spo2": 99 - (index % 3), "airway_plan": "Endotracheal tube", "asa_class": "II", "anaesthesia_technique": "General", "recovery_score": min(10, 6 + index // 2)}
            for index in range(10)
        ],
        "observation_chart": [
            {"temperature_c": 36.6 + (index % 4) * 0.2, "respiratory_rate": 17 + index % 5, "early_warning_score": 1 if index < 6 else 4}
            for index in range(10)
        ],
        "fluid_balance": [
            {"intake_ml": 250 + (index % 3) * 100, "output_ml": 180 + (index % 4) * 60, "route": "oral" if index % 2 else "intravenous"}
            for index in range(8)
        ],
        "growth_measurement": [
            {"weight_kg": 8.4 + index * 0.55, "height_cm": 71 + index * 2.1, "muac_cm": 14.2 + index * 0.1}
            for index in range(8)
        ],
        "quality_control": [
            {"observed_value": 99.2 + ((index % 6) - 3) * 0.35, "control_level": "normal", "run_number": f"QC-{index + 1:03d}"}
            for index in range(16)
        ],
        "cold_chain": [
            {"temperature_c": 4.1 + ((index % 7) - 3) * 0.35, "device": "PHARM-COLD-01", "location": "Main pharmacy refrigerator"}
            for index in range(18)
        ],
        "radiation_dose": [
            {"dose_mgy": 8 + index * 4.5, "modality": "CT" if index % 2 else "XR", "study_reference": f"IMG-{index + 1:04d}"}
            for index in range(8)
        ],
        "ambulance_telemetry": [
            {"latitude": 0.315 + index * 0.004, "longitude": 32.56 + index * 0.003, "speed_kph": 36 + index * 3, "heading": 45 + index * 8, "pickup_location": "Kampala emergency zone", "destination": "MyDoctor General Hospital"}
            for index in range(10)
        ],
        "medication_dose": [
            {"medication": ["Paracetamol", "Ceftriaxone", "Normal saline"][index % 3], "dose": ["1 g", "2 g", "500 mL"][index % 3], "route": ["oral", "intravenous", "intravenous"][index % 3], "frequency": "8 hourly", "scheduled_at": (NOW + timedelta(hours=index)).isoformat()}
            for index in range(9)
        ],
        "handover": [
            {"situation": "Patient requires continued observation", "background": "Admitted after acute presentation", "assessment": f"Stable with observation score {index % 4}", "recommendation": "Continue monitoring and escalate deterioration"}
            for index in range(6)
        ],
        "surgical_count": [
            {"expected_count": 20 + index, "final_count": 20 + index, "count_type": ["swab", "instrument", "needle"][index % 3], "discrepancy": False}
            for index in range(6)
        ],
    }
    for record_type, samples in series_specs.items():
        schema = RECORD_SCHEMAS.get(record_type)
        if not schema:
            continue
        role = next((candidate for candidate in schema["roles"] if user_for(candidate)), "admin")
        owner = user_for(role) or admin
        target_org = pharmacy if schema["domain"] == "pharmacy" else lab if schema["domain"] == "laboratory" else hospital
        for position, sample in enumerate(samples, start=1):
            reference = f"SER-{record_type[:12].upper()}-{position:03d}"
            EnterpriseRecord.objects.update_or_create(
                reference=reference,
                defaults={
                    "domain": schema["domain"], "record_type": record_type, "organization": target_org,
                    "location": OrganizationLocation.objects.filter(organization=target_org).first() if target_org else None,
                    "patient": patient, "admission": admission if schema["domain"] == "inpatient" else None,
                    "appointment": appointment if schema["domain"] in {"specialist", "radiology", "laboratory"} else None,
                    "owner": owner, "assigned_to": owner, "status": "completed" if position % 5 == 0 else starting_status(record_type),
                    "priority": "critical" if position == len(samples) and record_type in {"observation_chart", "radiation_dose"} else "routine",
                    "title": f"{schema['label']} observation {position}",
                    "summary": f"Time-series demonstration entry {position} for {schema['label']}.",
                    "payload": sample, "created_by": owner, "updated_by": owner,
                    "occurred_at": NOW - timedelta(minutes=(len(samples) - position) * 30),
                    "due_at": NOW + timedelta(hours=position),
                },
            )

    # 7 & 17. Coding and interoperability foundations.
    clinical_codes = [
        ("ICD-10", "E11.9", "Type 2 diabetes mellitus without complications", "diagnosis"),
        ("ICD-10", "I10", "Essential hypertension", "diagnosis"),
        ("LOINC", "718-7", "Haemoglobin [Mass/volume] in Blood", "laboratory"),
        ("SNOMED-CT", "386661006", "Fever", "finding"),
    ]
    for system, code, display, category in clinical_codes:
        ClinicalCode.objects.update_or_create(system=system, version="demo-2026", code=code, defaults={"display": display, "category": category, "active": True})

    paracetamol, _ = MedicationKnowledge.objects.update_or_create(generic_name="Paracetamol", defaults={"brand_names": ["Panadol"], "atc_code": "N02BE01", "strengths": ["500 mg"], "dosage_forms": ["tablet"], "contraindications": ["Severe hepatic impairment"], "pregnancy_category": "Generally compatible", "renal_guidance": "Use normal dose unless severe impairment.", "hepatic_guidance": "Reduce maximum daily dose in hepatic impairment.", "max_dose_guidance": {"adult_mg_per_day": 4000}, "active": True})
    warfarin, _ = MedicationKnowledge.objects.update_or_create(generic_name="Warfarin", defaults={"brand_names": [], "atc_code": "B01AA03", "strengths": ["1 mg", "3 mg", "5 mg"], "dosage_forms": ["tablet"], "contraindications": ["Active bleeding", "Pregnancy"], "pregnancy_category": "Contraindicated", "renal_guidance": "Monitor INR.", "hepatic_guidance": "Use caution.", "active": True})
    metronidazole, _ = MedicationKnowledge.objects.update_or_create(generic_name="Metronidazole", defaults={"brand_names": ["Flagyl"], "atc_code": "J01XD01", "strengths": ["400 mg"], "dosage_forms": ["tablet", "infusion"], "contraindications": [], "active": True})
    MedicationInteraction.objects.update_or_create(medicine_a=warfarin, medicine_b=metronidazole, defaults={"severity": "major", "mechanism": "Reduced warfarin metabolism", "clinical_effect": "Increased anticoagulant effect and bleeding risk", "management": "Avoid or monitor INR closely and adjust dose.", "evidence": "Established", "active": True})

    if insurer and hospital:
        tariff, _ = TariffSchedule.objects.update_or_create(payer=insurer, provider=hospital, name="2026 Corporate Tariff", defaults={"currency": "UGX", "valid_from": TODAY, "valid_to": TODAY + timedelta(days=365), "items": [{"code": "CONS-GP", "description": "General consultation", "amount": 45000}, {"code": "LAB-FBC", "description": "Full blood count", "amount": 35000}], "active": True})
        PayerContract.objects.update_or_create(payer=insurer, provider=hospital, contract_number="CNT-DEMO-2026-001", defaults={"status": "active", "starts_on": TODAY, "ends_on": TODAY + timedelta(days=365), "tariff": tariff, "terms": {"payment_days": 30, "preauthorization_threshold": 500000}})

    # 8. PACS/DICOM and imaging study data.
    if hospital and patient:
        pacs, _ = PACSNode.objects.update_or_create(organization=hospital, ae_title="MYDOCTORPACS", defaults={"name": "MyDoctor Demo PACS", "host": "orthanc", "port": 4242, "dicomweb_base_url": "http://orthanc:8042/dicom-web", "tls_enabled": False, "active": True, "configuration": {"viewer": "ohif"}})
        imaging_order = ImagingOrder.objects.filter(patient=patient).first() or ImagingOrder.objects.first()
        ImagingStudy.objects.update_or_create(study_instance_uid="1.2.826.0.1.3680043.10.2026.1", defaults={"organization": hospital, "patient": patient, "imaging_order": imaging_order, "pacs_node": pacs, "accession_number": "ACC-DEMO-0001", "modality": "DX", "description": "Demo chest radiograph", "study_date": NOW - timedelta(hours=2), "series_count": 1, "instance_count": 2, "viewer_url": "http://localhost:3000/viewer/1.2.826.0.1.3680043.10.2026.1", "metadata": {"bodyPartExamined": "CHEST"}})

    # 6. Ambulance fleet and telemetry.
    dispatch = AmbulanceDispatch.objects.first()
    if hospital:
        vehicle, _ = AmbulanceVehicle.objects.update_or_create(organization=hospital, registration_number="UAM 021M", defaults={"call_sign": "AMB-021", "vehicle_type": "advanced_life_support", "status": "responding", "equipment": ["oxygen", "defibrillator", "suction", "trauma kit"], "last_service_on": TODAY - timedelta(days=14), "active": True})
        if user_for("paramedic"): vehicle.crew.add(user_for("paramedic"))
        AmbulanceTelemetry.objects.update_or_create(vehicle=vehicle, recorded_at=NOW.replace(microsecond=0), defaults={"dispatch": dispatch, "latitude": Decimal("0.347600"), "longitude": Decimal("32.582500"), "speed_kph": Decimal("42.50"), "heading": 120, "accuracy_m": Decimal("5.00")})

    # 13. Provider routing, consent and escalation.
    for channel, name, ptype, priority in [("email", "SMTP Primary", "webhook", 10), ("sms", "Africa's Talking Primary", "africastalking", 10), ("sms", "SMS Failover Webhook", "webhook", 20), ("whatsapp", "Meta WhatsApp", "meta", 10), ("push", "Firebase Cloud Messaging", "fcm", 10)]:
        NotificationProvider.objects.update_or_create(channel=channel, name=name, defaults={"provider_type": ptype, "priority": priority, "active": False, "credentials_reference": f"DEMO_{channel.upper()}_TOKEN", "configuration": {"url": "https://example.invalid/notifications", "sender": "MyDoctor"}, "cost_per_message": Decimal("50.0000") if channel == "sms" else Decimal("0.0000"), "currency": "UGX", "health_status": "not_configured"})
    if patient:
        for channel in ["email", "sms", "whatsapp", "push"]:
            CommunicationConsent.objects.update_or_create(user=patient, channel=channel, purpose="care_delivery", defaults={"granted": True, "source": "demo_registration", "evidence": {"seed": True}})
    if hospital:
        policy, _ = EscalationPolicy.objects.update_or_create(organization=hospital, name="Critical result escalation", defaults={"event_type": "critical_result", "conditions": {"priority": "critical"}, "active": True})
        EscalationStep.objects.update_or_create(policy=policy, order=1, defaults={"delay_minutes": 0, "channel": "push", "target_type": "assigned_user", "template_code": "critical_result"})
        EscalationStep.objects.update_or_create(policy=policy, order=2, defaults={"delay_minutes": 5, "channel": "sms", "target_type": "medical_director", "template_code": "critical_result_escalation"})

    # 14. Versioned event schema, endpoint and delivery/dead-letter operations.
    event_schema, _ = EventSchema.objects.update_or_create(name="patient.record.updated", version=1, defaults={"subject": "patient.record.updated", "json_schema": {"type": "object", "required": ["patient_id", "record_type"]}, "compatibility": "backward", "active": True})
    endpoint, _ = IntegrationEndpoint.objects.update_or_create(name="Demo Integration Webhook", defaults={"endpoint_type": "webhook", "base_url": "https://example.invalid/events", "topic": "patient.records", "credentials_reference": "DEMO_EVENT_WEBHOOK_SECRET", "configuration": {"timeout_seconds": 10}, "active": False, "health_status": "not_configured"})
    event, _ = OutboxEvent.objects.get_or_create(event_type="patient.record.updated", aggregate_type="Patient", aggregate_id=str(patient.id if patient else 0), defaults={"event_version": 1, "actor": admin, "patient": patient, "payload": {"patient_id": patient.id if patient else None, "record_type": "Patient", "seed": True}})
    EventDelivery.objects.update_or_create(event=event, endpoint=endpoint, defaults={"schema": event_schema, "status": "pending", "next_attempt_at": NOW, "idempotency_key": f"demo:{event.event_id}:{endpoint.id}"})

    # 15. Content management and feature flags.
    content_rows = [
        ("banner", "connected-care-hero", "Connected care for every stage of life", "Book verified professionals, receive results and manage care in one secure platform.", "home.hero"),
        ("promotion", "family-health-check", "Family health check package", "A coordinated consultation, laboratory screening and follow-up package.", "home.promotion"),
        ("faq", "how-verification-works", "How are professionals verified?", "Professional credentials are reviewed by administrators and may be pre-screened by automated verification tools.", "support.faq"),
        ("legal", "privacy-notice", "MyDoctor privacy notice", "Demonstration privacy content. Replace with jurisdiction-approved legal content before production use.", "legal"),
    ]
    for ctype, slug, title, body, placement in content_rows:
        ContentEntry.objects.update_or_create(content_type=ctype, slug=slug, locale="en-UG", version=1, defaults={"title": title, "summary": body[:120], "body": body, "target_url": "/register" if ctype in {"banner", "promotion"} else "", "audience": ["all"], "placement": placement, "status": "published", "published_at": NOW, "created_by": admin, "metadata": {"seed": True}})
    for key, value in {
        "platform.maintenance_mode": {"enabled": False, "message": ""},
        "platform.minimum_frontend_version": {"version": "1.0.0"},
        "country.UG": {"currency": "UGX", "timezone": "Africa/Kampala", "phone_prefix": "+256"},
        "clinical.break_glass_minutes": {"value": 30},
        "telemedicine.providers": {"default": "jitsi", "enabled": ["jitsi", "zoom"]},
    }.items():
        FeatureConfiguration.objects.update_or_create(key=key, defaults={"scope_type": "platform", "value": value, "enabled": True, "updated_by": admin})

    # 16. Master patient index, duplicates and records requests.
    mpi_rows = []
    for index, p in enumerate(User.objects.filter(role="patient").order_by("id")[:5], start=1):
        profile = getattr(p, "patient_profile", None)
        mpi, _ = MasterPatientIndex.objects.update_or_create(patient=p, defaults={"national_identifier": f"DEMO-NIN-{index:04d}", "identifiers": [{"system": "urn:mydoctor:demo:nin", "value": f"DEMO-NIN-{index:04d}"}], "normalized_name": p.display_name.lower(), "normalized_phone": p.phone.replace(" ", ""), "date_of_birth": getattr(profile, "dob", None), "sex": getattr(profile, "gender", ""), "status": "active", "confidence_score": Decimal("100.00")})
        mpi_rows.append(mpi)
    if len(mpi_rows) > 1:
        DuplicatePatientCandidate.objects.update_or_create(patient_a=mpi_rows[0], patient_b=mpi_rows[1], defaults={"score": Decimal("62.50"), "matching_fields": ["similar_name", "shared_phone_prefix"], "status": "pending", "notes": "Demonstration candidate for records-officer review."})
    if patient:
        RecordsRequest.objects.update_or_create(request_type="export", patient=patient, reason="Patient requested a machine-readable health record export.", defaults={"organization": hospital, "status": "submitted", "details": {"format": "FHIR Bundle", "date_range": "all"}, "due_at": NOW + timedelta(days=14), "requested_by": patient, "assigned_to": user_for("records_officer")})

    # 17. FHIR resources, partner app and subscription.
    if patient:
        fhir_patient, _ = FHIRResource.objects.update_or_create(resource_type="Patient", logical_id=uuid.uuid5(uuid.NAMESPACE_URL, f"mydoctor-patient-{patient.id}"), version_id=1, defaults={"patient": patient, "organization": hospital, "source_model": "accounts.User", "source_id": str(patient.id), "data": {"resourceType": "Patient", "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"mydoctor-patient-{patient.id}")), "identifier": [{"system": "urn:mydoctor:patient", "value": str(patient.id)}], "name": [{"use": "official", "text": patient.display_name}], "telecom": [{"system": "phone", "value": patient.phone}, {"system": "email", "value": patient.email}]}, "status": "active"})
        FHIRResource.objects.update_or_create(resource_type="Observation", logical_id=uuid.uuid5(uuid.NAMESPACE_URL, f"mydoctor-observation-{patient.id}"), version_id=1, defaults={"patient": patient, "organization": hospital, "source_model": "enterprise.EnterpriseRecord", "source_id": "demo", "data": {"resourceType": "Observation", "status": "final", "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}]}, "subject": {"reference": f"Patient/{fhir_patient.logical_id}"}, "valueQuantity": {"value": 36.8, "unit": "Cel"}}, "status": "active"})
    partner, _ = PartnerApplication.objects.update_or_create(name="Demo National HIE Adapter", defaults={"organization": hospital, "redirect_uris": ["https://example.invalid/oauth/callback"], "scopes": ["patient/*.read", "Observation.read", "DiagnosticReport.read"], "jwks_uri": "", "active": False})
    FHIRSubscription.objects.update_or_create(application=partner, criteria="Observation?status=final", endpoint="https://example.invalid/fhir-events", defaults={"payload_type": "application/fhir+json", "secret_reference": "DEMO_FHIR_SUBSCRIPTION_SECRET", "status": "off"})

    # 18. Regulator/AI verification configuration and sample scan.
    RegulatorConnector.objects.update_or_create(profession="doctor", authority="Uganda Medical and Dental Practitioners Council", defaults={"country_code": "UG", "base_url": "", "credentials_reference": "UMDPC_API_TOKEN", "lookup_template": {"license_number": "{identifier}"}, "active": False})
    credential = PractitionerCredential.objects.filter(practitioner=user_for("doctor")).first()
    if credential:
        VerificationAutomation.objects.update_or_create(credential=credential, organization=None, model_name="document-screening-v1", model_version="1.0", defaults={"status": "completed", "extracted_fields": {"name": credential.practitioner.display_name, "license_number": credential.identifier, "demo": True}, "document_quality_score": Decimal("92.00"), "match_score": Decimal("100.00"), "fraud_score": Decimal("0.00"), "flags": [], "regulator_response": {"status": "demo_verified"}, "recommendation": "manual_review", "human_decision": "approved", "reviewed_by": admin, "reviewed_at": NOW, "completed_at": NOW})

    # 19. Security, privacy, resilience and clinical-safety operations.
    security_rows = [
        ("vulnerability_scan", "completed", "medium", "Weekly container vulnerability scan", [{"severity": "medium", "package": "demo", "status": "remediated"}]),
        ("backup", "completed", "low", "Encrypted PostgreSQL backup", []),
        ("restore_test", "completed", "low", "Quarterly restore test", []),
        ("dpia", "approved", "medium", "Telemedicine data protection impact assessment", [{"risk": "recording disclosure", "control": "explicit consent and encrypted storage"}]),
        ("clinical_safety", "approved", "medium", "Medication administration clinical safety case", [{"hazard": "wrong dose", "control": "five-rights check and audit trail"}]),
        ("pen_test", "planned", "high", "Independent penetration test", []),
    ]
    for op_type, status, severity, title, findings in security_rows:
        SecurityOperation.objects.update_or_create(title=title, defaults={"operation_type": op_type, "status": status, "severity": severity, "description": f"Demonstration {title.lower()} evidence.", "scope": {"environment": "demo"}, "findings": findings, "evidence": {"seed": True}, "started_at": NOW - timedelta(days=2), "completed_at": NOW - timedelta(days=1) if status == "completed" else None, "next_due_at": NOW + timedelta(days=90), "owner": user_for("it_support") or admin, "approved_by": user_for("compliance_officer") or admin})

    # 20. Saved reports and schedules.
    if hospital:
        report_specs = [
            ("Clinical workload", "inpatient", {"domain": "inpatient"}),
            ("Maternity activity", "maternity", {"domain": "maternity"}),
            ("Finance controls", "finance", {"domain": "finance"}),
            ("Patient safety", "security", {"domain": "security"}),
        ]
        for index, (name, domain, definition) in enumerate(report_specs, start=1):
            report, _ = SavedReport.objects.update_or_create(organization=hospital, name=name, defaults={"domain": domain, "definition": definition, "visibility": "organization", "created_by": admin})
            ReportSchedule.objects.update_or_create(report=report, cron_expression="0 7 * * 1", defaults={"recipients": ["manager@mydoctor.test"], "formats": ["csv", "pdf"], "active": True, "next_run_at": NOW + timedelta(days=7), "created_by": admin})

    return {
        "role_contexts": RoleContext.objects.count(),
        "enterprise_records": EnterpriseRecord.objects.count(),
        "content_entries": ContentEntry.objects.count(),
        "fhir_resources": FHIRResource.objects.count(),
        "security_operations": SecurityOperation.objects.count(),
    }
