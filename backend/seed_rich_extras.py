"""Fill the remaining user-visible empty sections after seed_rich_data.py.

Run from backend/:
    .venv/bin/python seed_rich_extras.py
"""
import datetime as dt
import os
import sys
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

User = get_user_model()
NOW = timezone.now()
TODAY = timezone.localdate()


def main():
    from registry.models import Organization

    hospital = Organization.objects.filter(organization_type="hospital", status="verified").first()
    doctors = list(User.objects.filter(role="doctor", is_active=True))
    patients = list(User.objects.filter(role="patient", is_active=True))
    nurse = User.objects.get(email="nurse@healthpilot.test")
    cashier = User.objects.get(email="cashier@healthpilot.test")
    admin = User.objects.filter(role="admin").first()

    # A discharged admission with a full discharge summary and a ward transfer.
    from operations.models import Admission, AdmissionTransfer, DischargeSummary, Ward

    wards = list(Ward.objects.filter(organization=hospital)[:2])
    discharged = Admission.objects.filter(status="discharged").first()
    if discharged is None:
        discharged = Admission.objects.create(
            admission_number="ADM-DEMO-9001", organization=hospital, patient=patients[8],
            ward=wards[0], reason="Community-acquired pneumonia", attending_clinician=doctors[1],
            status="discharged", admitted_at=NOW - dt.timedelta(days=5), discharged_at=NOW - dt.timedelta(days=1),
            discharge_disposition="home",
        )
    if len(wards) > 1 and not AdmissionTransfer.objects.exists():
        AdmissionTransfer.objects.create(admission=discharged, from_ward=wards[0], to_ward=wards[1], reason="Step-down from high dependency", requested_by=doctors[1])
    if not DischargeSummary.objects.exists():
        DischargeSummary.objects.create(
            admission=discharged, clinician=doctors[1],
            final_diagnosis="Community-acquired pneumonia, resolved",
            treatment_summary="Five days of IV antibiotics with supportive care; full recovery.",
            discharge_medications="Amoxicillin 500 mg three times daily for 5 more days.",
            follow_up_plan="Review at outpatient clinic in one week with chest X-ray.",
            patient_instructions="Complete the antibiotic course; return if fever recurs.",
            finalized_at=NOW - dt.timedelta(days=1),
        )

    # Finance extras: adjustment, reconciliation run, supplier invoice.
    from payments.models import Invoice, InvoiceAdjustment, ReconciliationRun, SupplierInvoice

    invoice = Invoice.objects.filter(status="pending").first()
    if invoice and not InvoiceAdjustment.objects.exists():
        InvoiceAdjustment.objects.create(
            number="ADJ-DEMO-0001", invoice=invoice, adjustment_type="discount", amount=5000,
            reason="Goodwill discount for long wait.", status="approved", requested_by=cashier, approved_by=admin,
        )
    if not ReconciliationRun.objects.exists():
        ReconciliationRun.objects.create(
            number="REC-DEMO-0001", organization=hospital, kind="daily_cash",
            period_start=TODAY, period_end=TODAY, expected_amount=145000, actual_amount=145000,
            variance=0, status="completed", created_by=cashier, completed_by=cashier, completed_at=NOW,
        )
    if not SupplierInvoice.objects.exists():
        SupplierInvoice.objects.create(
            invoice_number="SUP-DEMO-0001", organization=hospital, supplier_name="MedSupply Uganda Ltd",
            amount=1250000, status="approved", invoice_date=TODAY - dt.timedelta(days=3), due_date=TODAY + dt.timedelta(days=27),
            created_by=cashier,
        )

    # A telemedicine session with participants (created on video-room use in production).
    from appointments.models import Appointment
    from enterprise.models import TelemedicineParticipant, TelemedicineSession

    online_appt = Appointment.objects.filter(type="online", status="confirmed").first()
    if online_appt and not TelemedicineSession.objects.exists():
        session = TelemedicineSession.objects.create(
            appointment=online_appt, provider="jitsi", external_id=f"healthpilot-demo-{online_appt.id}",
            join_url="https://meet.jit.si/healthpilot-demo", host_url="https://meet.jit.si/healthpilot-demo#config.prejoinPageEnabled=false",
            scheduled_start=NOW + dt.timedelta(days=1),
        )
        TelemedicineParticipant.objects.create(session=session, user=online_appt.patient, role="patient")
        TelemedicineParticipant.objects.create(session=session, user=online_appt.doctor, role="clinician")

    # Encounter revision history (created when a signed encounter is amended).
    from clinical.models import ClinicalEncounter, EncounterRevision

    encounter = ClinicalEncounter.objects.first()
    if encounter and not EncounterRevision.objects.exists():
        EncounterRevision.objects.create(
            encounter=encounter, version=encounter.version, author=encounter.doctor,
            snapshot={"assessment": encounter.assessment, "treatment_plan": encounter.treatment_plan},
            reason="Clarified treatment plan wording after review.",
        )

    # Workflow case collaboration comments.
    from journeys.models import WorkflowCase, WorkflowComment

    case = WorkflowCase.objects.first()
    if case and not WorkflowComment.objects.exists():
        WorkflowComment.objects.create(case=case, author=nurse, body="Patient contacted and briefed about the plan.")
        WorkflowComment.objects.create(case=case, author=doctors[0], body="Agreed with the proposed management. Proceed.")

    # Terminology concept mappings for the interoperability page.
    from interoperability.models import ConceptMapping, TerminologyConcept

    concept = TerminologyConcept.objects.first()
    if concept and not ConceptMapping.objects.exists():
        loinc, _ = TerminologyConcept.objects.get_or_create(system="http://loinc.org", code="8480-6", defaults={"display": "Systolic blood pressure", "category": "vital_sign"})
        snomed, _ = TerminologyConcept.objects.get_or_create(system="http://snomed.info/sct", code="271649006", defaults={"display": "Systolic blood pressure (observable entity)", "category": "vital_sign"})
        ConceptMapping.objects.create(source=concept, target=loinc, relationship="equivalent", confidence=Decimal("0.98"))
        ConceptMapping.objects.create(source=concept, target=snomed, relationship="equivalent", confidence=Decimal("0.97"))

    print("Extras complete.")


if __name__ == "__main__":
    main()
