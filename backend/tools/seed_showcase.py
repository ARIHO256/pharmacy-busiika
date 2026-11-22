"""Populate the local SQLite development database with linked fictional records."""
import os
import sys
from functools import cache
from getpass import getpass
from datetime import time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile, ProviderProfile, StaffProfile, User
from appointments.models import Appointment, Availability
from clinical.models import ClinicalEncounter
from communication.models import Conversation, Message, Notification
from governance.models import Consent
from reviews.models import Review
from operations.models import Admission, ImagingOrder, MedicineBatch, MedicationSchedule
from payments.models import Invoice, InvoiceItem
from payments.services import confirm_invoice_payment
from prescriptions.models import Prescription, PrescriptionItem
from registry.models import CareRelationship, Organization
from services.models import (
    Bed, HospitalBooking, HospitalService, InsuranceClaim, InsurancePolicy, LabOrder,
    LabResult, LabTest, Medicine, Order, OrderItem, PatientCoverage, PharmacyOrder, Supplier, SupplierProduct,
)
from workforce.models import Department, MedicationAdministration, NursingNote, PatientVisit, StaffMembership, TriageRecord

COUNT = 50
PREFIX = "SHOWCASE"
ROLES = {
    "admin": "admin", "patient": "patient", "doctor": "doctor", "nurse": "nurse",
    "receptionist": "receptionist", "records_officer": "records", "cashier": "cashier",
    "facility_manager": "manager", "pharmacist": "pharmacist", "storekeeper": "storekeeper",
    "lab_technician": "labtech", "insurance_officer": "insuranceofficer", "pharmacy": "pharmacy",
    "lab": "lab", "hospital": "hospital", "insurance": "insurance",
}
PROVIDERS = {
    "hospital": ("hospital", "Kampala Demonstration Hospital"),
    "lab": ("laboratory", "Kampala Demonstration Diagnostics"),
    "pharmacy": ("pharmacy", "Kampala Demonstration Pharmacy"),
    "insurance": ("insurer", "Kampala Demonstration Health Cover"),
}
FIRST = ["Amina", "Joan", "Moses", "Esther", "Peter", "Sarah", "Daniel", "Ruth", "David", "Lydia"]
LAST = ["Okello", "Nabirye", "Kato", "Adoch", "Ssemanda"]
MEDICINES = [
    ("Paracetamol 500 mg tablets", 2500), ("Ibuprofen 200 mg tablets", 3500),
    ("Cetirizine 10 mg tablets", 4500), ("Loratadine 10 mg tablets", 5000),
    ("Oral rehydration salts sachets", 2000), ("Vitamin C 500 mg tablets", 5500),
    ("Calcium carbonate antacid tablets", 6500), ("Folic acid 400 mcg tablets", 4000),
    ("Zinc sulfate 20 mg tablets", 4200), ("Cholecalciferol 1,000 IU capsules", 8000),
]
LABS = [
    ("Hemoglobin", "Blood", "g/dL", "13.2"),
    ("Platelet count", "Blood", "10^9/L", "240"),
    ("White blood cell count", "Blood", "10^9/L", "6.8"),
    ("Glucose", "Plasma", "mg/dL", "91"),
    ("Creatinine", "Serum", "mg/dL", "0.9"),
    ("Sodium", "Serum", "mmol/L", "139"),
    ("Potassium", "Serum", "mmol/L", "4.2"),
    ("Total cholesterol", "Serum", "mg/dL", "170"),
    ("Total bilirubin", "Serum", "mg/dL", "0.8"),
    ("Urine specific gravity", "Urine", "", "1.015"),
]
CLINICS = ["General consultation", "Follow-up clinic", "Health screening", "Nutrition review", "Outpatient assessment"]


@cache
def showcase_password():
    password = os.getenv("MYDOCTOR_SHOWCASE_PASSWORD") or getpass("Password for new showcase logins: ")
    if not password:
        raise ValueError("The showcase password cannot be empty.")
    return password


def account(role, local, first, last, login=True):
    email = f"{local}@gmail.com" if login else f"{local}@example.test"
    user, created = User.objects.get_or_create(email=email, defaults={
        "role": role, "first_name": first, "last_name": last,
        "is_verified": True, "is_staff": role == "admin", "is_superuser": role == "admin",
    })
    if not created and (user.role != role or not user.last_name.startswith(PREFIX)):
        raise RuntimeError(f"Refusing to modify an account outside the showcase: {email}")
    if created:
        if login:
            user.set_password(showcase_password())
        else:
            user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


@transaction.atomic
def seed():
    roles = {role: account(role, local, "Amina" if role == "patient" else local.replace("_", " ").title(),
                           f"{PREFIX} Demo") for role, local in ROLES.items()}
    orgs = {}
    for role, (kind, name) in PROVIDERS.items():
        owner = roles[role]
        orgs[role], _ = Organization.objects.get_or_create(owner=owner, legal_name=name, defaults={
            "organization_type": kind, "status": "verified", "district": "Kampala",
            "license_number": f"{PREFIX}-{role.upper()}",
        })
        ProviderProfile.objects.get_or_create(user=owner, defaults={
            "organization_type": kind, "org_name": name, "district": "Kampala",
            "status": "verified", "license_number": f"{PREFIX}-{role.upper()}",
            "services_description": "Fictional demonstration provider.",
        })

    teams = {
        "hospital": ["doctor", "nurse", "receptionist", "records_officer", "cashier", "facility_manager"],
        "lab": ["lab_technician"], "pharmacy": ["pharmacist", "storekeeper"],
        "insurance": ["insurance_officer"],
    }
    for site, members in teams.items():
        department, _ = Department.objects.get_or_create(organization=orgs[site], name="Demonstration services")
        for role in members:
            StaffMembership.objects.get_or_create(organization=orgs[site], user=roles[role], role=role,
                                                 defaults={"department": department, "is_primary": True})
            if role != "doctor":
                StaffProfile.objects.get_or_create(user=roles[role], defaults={
                    "employee_number": f"{PREFIX}-{role}", "cadre": role.replace("_", " ").title(), "status": "verified",
                })

    doctor, nurse, cashier = (roles[role] for role in ("doctor", "nurse", "cashier"))
    DoctorProfile.objects.get_or_create(user=doctor, defaults={
        "specialization": "General practice", "hospital": orgs["hospital"].legal_name, "fees": 35000, "status": "verified",
    })
    for day in range(7):
        Availability.objects.get_or_create(doctor=doctor, weekday=day, start_time=time(8), end_time=time(17))

    now = timezone.now()
    today = timezone.localdate()
    for number in range(1, COUNT + 1):
        marker = f"{PREFIX}-{number:03}"
        offset = number - 1
        patient = roles["patient"] if number == 1 else account(
            "patient", f"showcase-patient-{number:03}", FIRST[offset % len(FIRST)],
            f"{PREFIX} {LAST[offset // len(FIRST)]} {number:02}", login=False,
        )
        PatientProfile.objects.get_or_create(user=patient, defaults={"location": "Kampala"})
        drug, base_price = MEDICINES[offset % len(MEDICINES)]
        pack = offset // len(MEDICINES) + 1
        medicine, _ = Medicine.objects.get_or_create(pharmacy=roles["pharmacy"], name=f"{drug} · Pack option {pack}", defaults={
            "price": base_price * pack, "stock": 35 + offset * 2,
            "description": "Fictional stock and price for the demonstration pharmacy. Price is per pack.",
        })
        MedicineBatch.objects.get_or_create(medicine=medicine, batch_number=marker, defaults={
            "organization": orgs["pharmacy"], "created_by": roles["pharmacist"],
            "quantity": medicine.stock, "expires_on": today + timedelta(days=180 + offset),
        })
        supplier, _ = Supplier.objects.get_or_create(pharmacy=roles["pharmacy"], suppliername=f"Demo supplier {number:02}",
                                                     defaults={"address": "Kampala"})
        SupplierProduct.objects.get_or_create(supplier=supplier, name=medicine.name,
                                              defaults={"price": base_price, "qty": 100 + offset})
        lab_name, sample, unit, value = LABS[offset % len(LABS)]
        description = f"This laboratory test measures {lab_name.lower()} in a {sample.lower()} sample."
        test, _ = LabTest.objects.get_or_create(lab=roles["lab"], name=f"{lab_name} · {['Routine', 'Priority', 'Follow-up', 'Screening', 'Outpatient'][pack-1]}",
                                                defaults={"sample_type": sample, "price": 9000 + offset * 350, "description": description})
        if not test.description.strip():
            test.description = description
            test.save(update_fields=["description"])
        service, _ = HospitalService.objects.get_or_create(
            hospital=roles["hospital"], name=f"{CLINICS[offset % len(CLINICS)]} · Clinic {offset // len(CLINICS) + 1}",
            defaults={"price": 25000 + offset * 750},
        )
        bed, _ = Bed.objects.get_or_create(hospital=roles["hospital"], ward=["General", "Observation", "Short stay"][offset % 3],
                                           label=f"Demo {number:02}", defaults={"is_occupied": number % 5 == 0})
        policy, _ = InsurancePolicy.objects.get_or_create(provider=roles["insurance"], name=f"Demo health plan {number:02}",
                                                          defaults={"coverage_percent": 50 + offset % 5 * 10, "premium": 75000 + offset * 2500})
        PatientCoverage.objects.get_or_create(provider=roles["insurance"], member_id=marker,
                                               defaults={"patient": patient, "policy": policy})
        appointment, _ = Appointment.objects.get_or_create(patient=patient, doctor=doctor, reason=marker, defaults={
            "date": today + timedelta(days=offset - 35), "start_time": time(9), "end_time": time(9, 30),
            "status": "completed" if number <= 35 else "confirmed", "notes": "Fictional outpatient follow-up.",
        })
        CareRelationship.objects.get_or_create(patient=patient, practitioner=doctor)
        Consent.objects.get_or_create(
            patient=patient, granted_to=doctor, consent_type=Consent.Type.TREATMENT,
            purpose="showcase_treatment", defaults={"data_categories": ["clinical"]},
        )
        if appointment.status == Appointment.Status.COMPLETED:
            Review.objects.get_or_create(appointment=appointment, defaults={
                "patient": patient, "doctor": doctor, "rating": 3 + offset % 3,
                "comment": ["Clear follow-up instructions.", "Helpful explanation during the visit.",
                            "The care team explained the next steps."][offset % 3] + " Fictional showcase review.",
            })
        visit, _ = PatientVisit.objects.get_or_create(visit_number=f"VIS-{marker}", defaults={
            "patient": patient, "organization": orgs["hospital"], "appointment": appointment,
            "registered_by": roles["receptionist"], "assigned_doctor": doctor, "assigned_nurse": nurse,
            "queue_number": number, "status": ["laboratory", "completed", "billing", "waiting_clinician", "waiting_triage"][offset % 5],
            "reason": ["Routine review", "Follow-up assessment", "Outpatient screening"][offset % 3],
        })
        TriageRecord.objects.get_or_create(visit=visit, defaults={
            "nurse": nurse, "chief_complaint": "Fictional outpatient review", "level": "green",
            "systolic_bp": 108 + offset % 23, "diastolic_bp": 66 + offset % 16,
        })
        NursingNote.objects.get_or_create(visit=visit, note_type="handover", defaults={
            "nurse": nurse, "note": "Awaiting the next scheduled review.",
            "handover": {"situation": "Awaiting scheduled review", "assessment": "Demo observations recorded",
                         "next_actions": "Assigned nurse to confirm follow-up with the care team"},
        })
        MedicationAdministration.objects.get_or_create(visit=visit, medication=medicine.name, defaults={
            "nurse": nurse, "dose": "Demo unit", "route": "oral", "status": ["given", "held", "refused", "missed"][offset % 4],
            "notes": "Fictional medication administration entry.",
        })
        conversation, _ = Conversation.objects.get_or_create(patient=patient, doctor=doctor, defaults={"appointment": appointment})
        Message.objects.get_or_create(conversation=conversation, sender=doctor,
                                      text="Your demonstration visit summary is ready for review.")
        Notification.objects.get_or_create(user=patient, title=f"Visit update · {marker}", defaults={
            "body": "A fictional visit update is available in MyDoctor.",
            "kind": "visit", "action_url": "/patient/health-record",
        })
        encounter, _ = ClinicalEncounter.objects.get_or_create(appointment=appointment, defaults={
            "patient": patient, "doctor": doctor, "chief_complaint": visit.reason,
            "assessment": "Fictional encounter record for workflow demonstration.",
            "status": "final" if appointment.status == "completed" else "draft",
            "signed_at": now if appointment.status == "completed" else None,
        })
        rx, rx_created = Prescription.objects.get_or_create(appointment=appointment, notes=marker, defaults={
            "encounter": encounter, "doctor": doctor, "patient": patient,
        })
        if rx_created:
            PrescriptionItem.objects.create(prescription=rx, medicine_name=medicine.name, dosage="Demo directions", quantity=1)
        PharmacyOrder.objects.get_or_create(patient=patient, pharmacy=roles["pharmacy"], prescription_id=rx.pk,
                                            defaults={"status": ["new", "prepared", "rejected"][offset % 3]})
        lab_order, _ = LabOrder.objects.get_or_create(visit=visit, lab=roles["lab"], test=test, defaults={
            "patient": patient, "referring_doctor": doctor, "referring_facility": orgs["hospital"].legal_name,
            "specimen_id": f"SP-{marker}", "specimen_type": sample, "arrived_at": now,
            "clinical_indication": "Fictional screening sample",
            "status": "completed" if number <= 40 else "processing",
            "result_released": number <= 40, "released_at": now if number <= 40 else None,
        })
        LabResult.objects.get_or_create(order=lab_order, name=lab_name, code=marker, defaults={
            "value_numeric": value, "unit": unit, "interpretation": "normal", "entered_by": roles["lab_technician"],
            "status": "final" if number <= 40 else "preliminary",
            "released_at": now if number <= 40 else None,
        })
        order, created = Order.objects.get_or_create(patient=patient, pharmacy=roles["pharmacy"], address=marker, defaults={
            "total": medicine.price, "status": ["pending", "confirmed", "delivered", "cancelled"][offset % 4],
        })
        if created:
            OrderItem.objects.create(order=order, medicine=medicine, name=medicine.name, price=medicine.price, qty=1)
        HospitalBooking.objects.get_or_create(patient=patient, hospital=roles["hospital"], service=service,
                                               defaults={"date": appointment.date, "status": appointment.status})
        admission, _ = Admission.objects.get_or_create(patient=patient, organization=orgs["hospital"], reason=marker, defaults={
            "created_by": nurse, "attending_doctor": doctor, "bed": bed,
            "status": "admitted" if bed.is_occupied else "discharged",
            "discharged_at": None if bed.is_occupied else now,
        })
        MedicationSchedule.objects.get_or_create(admission=admission, prescription=rx, medication_name=medicine.name, defaults={
            "organization": orgs["hospital"], "created_by": doctor, "dose": "Demo unit", "route": "oral",
            "due_at": now + timedelta(hours=offset % 12) if admission.status == "admitted" else admission.admitted_at,
            "status": "scheduled" if admission.status == "admitted" else "given",
            "administered_by": None if admission.status == "admitted" else nurse,
            "administered_at": None if admission.status == "admitted" else admission.discharged_at,
        })
        ImagingOrder.objects.get_or_create(
            patient=patient, organization=orgs["lab"], indication=f"Fictional imaging request {marker}", defaults={
                "created_by": doctor, "referring_doctor": doctor,
                "modality": ["US", "DX", "MR", "CT"][offset % 4],
                "body_site": ["Abdomen", "Chest", "Knee", "Head"][offset % 4],
                "status": ["ordered", "scheduled", "reported"][offset % 3],
                "scheduled_at": now + timedelta(days=1) if offset % 3 == 1 else None,
                "report": "Fictional imaging report for demonstration." if offset % 3 == 2 else "",
                "reported_by": doctor if offset % 3 == 2 else None,
                "reported_at": now if offset % 3 == 2 else None,
            },
        )
        invoice, new_invoice = Invoice.objects.get_or_create(number=f"INV-{marker}", defaults={
            "patient": patient, "appointment": appointment, "organization": orgs["hospital"], "issued_by": cashier,
            "amount": service.price, "status": "pending", "notes": "Fictional demonstration invoice.",
        })
        if new_invoice:
            InvoiceItem.objects.create(invoice=invoice, description=service.name, quantity=1, unit_price=service.price)
            if number % 3 == 0:
                confirm_invoice_payment(invoice=invoice, amount=service.price, method="cash", received_by=cashier, reference=marker)
        InsuranceClaim.objects.get_or_create(provider=roles["insurance"], patient=patient, invoice_id=invoice.pk, defaults={
            "policy": policy, "amount": service.price, "status": ["submitted", "approved", "rejected"][offset % 3],
        })

    Appointment.objects.get_or_create(patient=roles["patient"], doctor=doctor, reason=f"{PREFIX} upcoming follow-up", defaults={
        "date": today + timedelta(days=2), "start_time": time(10), "end_time": time(10, 30), "status": "confirmed",
    })
    print(f"Seeded {len(roles)} role logins and {COUNT} linked scenarios in {settings.DATABASES['default']['NAME']}.")


if __name__ == "__main__":
    database = settings.DATABASES["default"]
    expected = Path(__file__).resolve().parents[1] / "db.sqlite3"
    if not settings.DEBUG or database["ENGINE"] != "django.db.backends.sqlite3" or Path(database["NAME"]).resolve() != expected:
        raise SystemExit("This seed is restricted to the local development SQLite database.")
    seed()
