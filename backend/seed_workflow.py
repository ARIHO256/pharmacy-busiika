"""Seed a live outpatient workflow so every facility role has real work.

Creates PatientVisits at every stage of the care flow at Hope Medical Centre,
with triage records, assignments and queue numbers. Idempotent per patient.

Run from backend/:
    .venv/bin/python seed_workflow.py
"""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

from registry.models import Organization  # noqa: E402
from workforce.models import PatientVisit, TriageRecord  # noqa: E402
from workforce.services import assign_queue_number  # noqa: E402

User = get_user_model()

# (patient email, stage, triage level or None, complaint)
FLOW = [
    ("patient2@healthpilot.test", PatientVisit.Status.WAITING_TRIAGE, None, "Fever and chills since yesterday"),
    ("patient3@healthpilot.test", PatientVisit.Status.WAITING_TRIAGE, None, "Persistent cough for one week"),
    ("patient5@healthpilot.test", PatientVisit.Status.WAITING_CLINICIAN, TriageRecord.Level.YELLOW, "High fever, suspected malaria"),
    ("patient8@healthpilot.test", PatientVisit.Status.WAITING_CLINICIAN, TriageRecord.Level.GREEN, "Lower back pain after lifting"),
    ("patient12@healthpilot.test", PatientVisit.Status.LABORATORY, TriageRecord.Level.ORANGE, "Severe abdominal pain — awaiting CBC and malaria smear"),
    ("patient15@healthpilot.test", PatientVisit.Status.PHARMACY, TriageRecord.Level.GREEN, "Hypertension review — prescription issued"),
    ("patient20@healthpilot.test", PatientVisit.Status.BILLING, TriageRecord.Level.GREEN, "Dispensed medicines, awaiting payment"),
    ("patient22@healthpilot.test", PatientVisit.Status.COMPLETED, TriageRecord.Level.BLUE, "Routine wellness check"),
]

VITALS = {
    TriageRecord.Level.ORANGE: dict(temperature_c=38.9, pulse_bpm=112, respiratory_rate=22, systolic_bp=140, diastolic_bp=90, oxygen_saturation=95),
    TriageRecord.Level.YELLOW: dict(temperature_c=38.2, pulse_bpm=98, respiratory_rate=19, systolic_bp=130, diastolic_bp=85, oxygen_saturation=97),
    TriageRecord.Level.GREEN: dict(temperature_c=36.8, pulse_bpm=76, respiratory_rate=16, systolic_bp=124, diastolic_bp=80, oxygen_saturation=98),
    TriageRecord.Level.BLUE: dict(temperature_c=36.5, pulse_bpm=70, respiratory_rate=14, systolic_bp=118, diastolic_bp=76, oxygen_saturation=99),
}


def main():
    organization = Organization.objects.filter(organization_type="hospital", status="verified").first()
    receptionist = User.objects.get(email="reception@healthpilot.test")
    nurse = User.objects.get(email="nurse@healthpilot.test")
    doctor = User.objects.get(email="dr.nakato@healthpilot.test")

    created = 0
    for email, stage, level, complaint in FLOW:
        patient = User.objects.get(email=email)
        visit, was_created = PatientVisit.objects.get_or_create(
            organization=organization,
            patient=patient,
            defaults={
                "visit_type": PatientVisit.Type.WALK_IN,
                "status": stage,
                "registered_by": receptionist,
                "assigned_nurse": nurse if stage != PatientVisit.Status.WAITING_TRIAGE else None,
                "assigned_doctor": doctor if stage in {
                    PatientVisit.Status.WAITING_CLINICIAN,
                    PatientVisit.Status.IN_CONSULTATION,
                    PatientVisit.Status.LABORATORY,
                    PatientVisit.Status.PHARMACY,
                    PatientVisit.Status.BILLING,
                    PatientVisit.Status.COMPLETED,
                } else None,
                "reason": complaint,
            },
        )
        if was_created:
            visit.status = stage
            visit.save(update_fields=["status"])
            assign_queue_number(visit)
            created += 1
        if level is not None:
            TriageRecord.objects.update_or_create(
                visit=visit,
                defaults={
                    "nurse": nurse,
                    "level": level,
                    "chief_complaint": complaint,
                    "weight_kg": 68.0,
                    **VITALS.get(level, {}),
                },
            )
    print(f"Workflow seed complete: {created} visits created across {len(FLOW)} stages at {organization.legal_name}")


if __name__ == "__main__":
    main()
