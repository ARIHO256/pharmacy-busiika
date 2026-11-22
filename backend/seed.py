"""Seed MyDoctor demo data. Run: python seed.py"""
import os
import sys
import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()
from accounts.models import DoctorProfile, PatientProfile, ProviderProfile, StaffProfile  # noqa: E402
from appointments.models import Availability  # noqa: E402
from registry.models import Organization, PractitionerCredential, PractitionerRole  # noqa: E402
from registry.services import sync_provider_organization  # noqa: E402
from interoperability.models import TerminologyConcept  # noqa: E402
from workforce.models import Department, StaffMembership  # noqa: E402
from services.models import (  # noqa: E402
    Bed,
    HospitalService,
    InsurancePolicy,
    LabTest,
    Medicine,
    Supplier,
)

PW = "pass123456"


def make_user(email, role, first, last, phone="+256700000000", verified=True):
    u, created = User.objects.get_or_create(
        email=email,
        defaults=dict(
            first_name=first, last_name=last, role=role, phone=phone, is_verified=verified
        ),
    )
    if created:
        u.set_password(PW)
        u.save()
    return u


# --- admin ---
if not User.objects.filter(email="admin@mydoctor.test").exists():
    User.objects.create_superuser(
        email="admin@mydoctor.test", password="admin12345",
        first_name="Platform", last_name="Admin",
    )
    print("admin created")

# --- patients ---
p1 = make_user("patient1@mydoctor.test", "patient", "Amina", "Nansubuga")
p2 = make_user("patient2@mydoctor.test", "patient", "Brian", "Okello")
for p in (p1, p2):
    PatientProfile.objects.get_or_create(
        user=p,
        defaults=dict(
            dob=datetime.date(1995, 4, 12), gender="female",
            blood_group="O+", allergies="None known",
            medical_history="No chronic conditions",
            emergency_contact="+256700111222", location="Kampala", address="Kampala, Uganda",
        ),
    )

# --- doctors ---
DOCTORS = [
    ("dr.nakato@mydoctor.test", "Sarah", "Nakato", "General Medicine", "Mulago Hospital", 8, 30000),
    ("dr.kato@mydoctor.test", "James", "Kato", "Pediatrics", "Nsambya Hospital", 12, 45000),
    ("dr.aina@mydoctor.test", "Grace", "Aina", "Dermatology", "Kampala Skin Clinic", 6, 50000),
]
doctor_users = []
for email, first, last, spec, hosp, years, fee in DOCTORS:
    d = make_user(email, "doctor", first, last)
    doctor_users.append((d, spec, hosp))
    DoctorProfile.objects.get_or_create(
        user=d,
        defaults=dict(
            year_of_completion=max(1990, datetime.date.today().year - years - 6),
            university="Makerere University College of Health Sciences",
            cadre="specialist" if spec != "General Medicine" else "medical_officer",
            specialization=spec, hospital=hosp, experience_years=years,
            fees=fee, bio=f"{spec} specialist with {years} years of experience at {hosp}.",
            license_number=f"DEMO-MDC-{d.id:04d}", license_issuer="MyDoctor Demo Medical Council",
            license_expires_on=datetime.date.today() + datetime.timedelta(days=365), status="verified",
        ),
    )
    for weekday in range(0, 5):  # Mon-Fri
        Availability.objects.get_or_create(
            doctor=d, weekday=weekday,
            defaults=dict(
                start_time=datetime.time(9, 0), end_time=datetime.time(16, 0),
                slot_minutes=30, breaks=[{"start": "13:00", "end": "14:00"}],
                holidays=[], is_active=True,
            ),
        )
print("doctors + availability seeded")

# --- providers ---
def provider(email, role, first, last, org, address, organization_type=None):
    u = make_user(email, role, first, last)
    type_map = {
        "hospital": "hospital",
        "pharmacy": "pharmacy",
        "lab": "laboratory",
        "insurance": "insurer",
    }
    profile, _ = ProviderProfile.objects.get_or_create(
        user=u, defaults=dict(organization_type=organization_type or type_map[role],
                              org_name=org, license_number="LIC-" + role.upper() + "-001",
                              district="Kampala", address=address,
                              services_description=f"Verified {role} services for local demonstration.",
                              status="verified")
    )
    sync_provider_organization(u, profile)
    return u

ph = provider("pharmacy@mydoctor.test", "pharmacy", "Busiika", "Pharmacy", "Busiika Pharmacy", "Kampala Road")
lb = provider("lab@mydoctor.test", "lab", "City", "Diagnostics", "City Diagnostics Lab", "Nakasero")
ho = provider("hospital@mydoctor.test", "hospital", "Hope", "Clinic", "Hope Clinic", "Wandegeya", organization_type="clinic")
ins = provider("insurance@mydoctor.test", "insurance", "SafeHealth", "Cover", "SafeHealth Insurance", "Nakawa")

# --- durable provider/facility registry ---
provider_orgs = [
    (ph, "Busiika Pharmacy", "pharmacy", "LIC-PHARMACY-001", "Kampala Road"),
    (lb, "City Diagnostics Lab", "laboratory", "LIC-LAB-001", "Nakasero"),
    (ho, "Hope Clinic", "clinic", "LIC-HOSPITAL-001", "Wandegeya"),
    (ins, "SafeHealth Insurance", "insurer", "LIC-INSURANCE-001", "Nakawa"),
]
for owner, name, org_type, license_number, address in provider_orgs:
    Organization.objects.get_or_create(
        owner=owner, organization_type=org_type, legal_name=name,
        defaults=dict(
            trading_name=name, license_number=license_number,
            services_description=f"Verified {org_type} services for the MyDoctor demonstration.",
            status="verified", contact_email=owner.email, phone=owner.phone,
            address=address, district="Kampala",
        ),
    )

for doctor, specialty, facility_name in doctor_users:
    facility, _ = Organization.objects.get_or_create(
        legal_name=facility_name, organization_type="hospital",
        defaults=dict(trading_name=facility_name, status="verified", active=True),
    )
    PractitionerRole.objects.get_or_create(
        practitioner=doctor, organization=facility, role_name="Doctor", specialty=specialty,
        defaults={"active": True, "telemedicine_enabled": True},
    )
    PractitionerCredential.objects.get_or_create(
        practitioner=doctor, issuer="MyDoctor Demo Medical Council", identifier=f"DEMO-MDC-{doctor.id:04d}",
        defaults=dict(credential_type="license", title=f"License to practise — {specialty}", status="verified"),
    )

# --- facility departments and role-specific staff workspaces ---
hospital_org = Organization.objects.get(owner=ho)
pharmacy_org = Organization.objects.get(owner=ph)
lab_org = Organization.objects.get(owner=lb)

outpatient, _ = Department.objects.get_or_create(organization=hospital_org, name="Outpatient", defaults={"code": "OPD"})
nursing, _ = Department.objects.get_or_create(organization=hospital_org, name="Nursing", defaults={"code": "NUR"})
finance, _ = Department.objects.get_or_create(organization=hospital_org, name="Finance", defaults={"code": "FIN"})
pharmacy_dept, _ = Department.objects.get_or_create(organization=pharmacy_org, name="Dispensary", defaults={"code": "PHA"})
lab_dept, _ = Department.objects.get_or_create(organization=lab_org, name="Main Laboratory", defaults={"code": "LAB"})

STAFF = [
    ("nurse@mydoctor.test", "nurse", "Esther", "Nabirye", hospital_org, nursing, "Registered Nurse", True, "DEMO-NMC-1001"),
    ("reception@mydoctor.test", "receptionist", "Ruth", "Adoch", hospital_org, outpatient, "Receptionist", False, ""),
    ("records@mydoctor.test", "records_officer", "Moses", "Ssemanda", hospital_org, outpatient, "Medical Records Officer", False, ""),
    ("cashier@mydoctor.test", "cashier", "Diana", "Atwine", hospital_org, finance, "Cashier", False, ""),
    ("manager@mydoctor.test", "facility_manager", "Paul", "Kizito", hospital_org, outpatient, "Facility Manager", False, ""),
    ("pharmacist.staff@mydoctor.test", "pharmacist", "Irene", "Namuli", pharmacy_org, pharmacy_dept, "Pharmacist", True, "DEMO-PSU-2001"),
    ("storekeeper@mydoctor.test", "storekeeper", "John", "Wasswa", pharmacy_org, pharmacy_dept, "Storekeeper", False, ""),
    ("labtech@mydoctor.test", "lab_technician", "Kevin", "Otim", lab_org, lab_dept, "Laboratory Technologist", True, "DEMO-AHPC-3001"),
]
for email, role, first, last, organization, department, title, professional, registration_number in STAFF:
    staff_user = make_user(email, role, first, last, verified=True)
    profile, _ = StaffProfile.objects.get_or_create(
        user=staff_user,
        defaults={
            "employee_number": f"EMP-{staff_user.id:04d}",
            "cadre": title,
            "university": "MyDoctor Demo Health Institute" if professional else "",
            "year_of_completion": 2020 if professional else None,
            "qualification": title,
            "registration_number": registration_number,
            "license_issuer": "Uganda Demo Health Regulator" if professional else "",
            "license_expires_on": datetime.date.today() + datetime.timedelta(days=365) if professional else None,
            "status": "verified",
        },
    )
    StaffMembership.objects.get_or_create(
        user=staff_user,
        organization=organization,
        role=role,
        defaults={
            "department": department,
            "job_title": title,
            "employee_number": profile.employee_number,
            "status": "active",
            "is_primary": True,
            "created_by": ho,
        },
    )
    if professional:
        PractitionerCredential.objects.get_or_create(
            practitioner=staff_user,
            issuer="Uganda Demo Health Regulator",
            identifier=registration_number,
            defaults={
                "credential_type": "license",
                "title": f"{title} practising licence",
                "expires_on": datetime.date.today() + datetime.timedelta(days=365),
                "status": "verified",
            },
        )
print("facility departments and staff workspaces seeded")

# --- starter terminology (local codes, safe to map to national standards later) ---
for code, display, category, aliases in [
    ("blood-pressure", "Blood pressure", "vital_sign", ["BP"]),
    ("heart-rate", "Heart rate", "vital_sign", ["Pulse"]),
    ("body-temperature", "Body temperature", "vital_sign", ["Temperature"]),
    ("oxygen-saturation", "Oxygen saturation", "vital_sign", ["SpO2"]),
    ("weight", "Body weight", "vital_sign", ["Weight"]),
]:
    TerminologyConcept.objects.get_or_create(
        system="urn:mydoctor:local:observation", version="1", code=code,
        defaults=dict(display=display, category=category, aliases=aliases),
    )

# --- pharmacy catalog ---
MEDS = [
    ("Paracetamol 500mg (20 tabs)", "Pain and fever relief", 3000, 120),
    ("Amoxicillin 250mg (10 caps)", "Broad-spectrum antibiotic", 8500, 60),
    ("Metformin 500mg (30 tabs)", "Type 2 diabetes management", 12000, 80),
    ("Cetirizine 10mg (10 tabs)", "Allergy relief", 4500, 100),
    ("Omeprazole 20mg (14 caps)", "Acid reflux treatment", 9800, 45),
    ("ORS Sachets (5 pack)", "Oral rehydration salts", 2500, 150),
]
for name, desc, price, stock in MEDS:
    Medicine.objects.get_or_create(pharmacy=ph, name=name, defaults=dict(description=desc, price=price, stock=stock))
Supplier.objects.get_or_create(
    pharmacy=ph, suppliername="MediSource Uganda",
    defaults=dict(contact="0700222333", email="sales@medisource.ug", address="Industrial Area, Kampala"),
)

# --- lab catalog ---
TESTS = [
    ("Complete Blood Count (CBC)", "Full blood picture", 20000, "Blood"),
    ("Malaria Rapid Test", "Malaria parasite screening", 8000, "Blood"),
    ("Urinalysis", "Urine composition analysis", 12000, "Urine"),
    ("Blood Sugar (Fasting)", "Glucose level test", 10000, "Blood"),
]
for name, desc, price, sample in TESTS:
    LabTest.objects.get_or_create(lab=lb, name=name, defaults=dict(description=desc, price=price, sample_type=sample))

# --- hospital catalog ---
SERVICES = [("General OPD Consultation", 15000), ("Antenatal Visit", 25000), ("Minor Surgery", 150000)]
for name, price in SERVICES:
    HospitalService.objects.get_or_create(hospital=ho, name=name, defaults=dict(price=price))
for ward, labels in [("General", ["G-01", "G-02", "G-03"]), ("Maternity", ["M-01", "M-02"])]:
    for label in labels:
        Bed.objects.get_or_create(hospital=ho, ward=ward, label=label)

# --- insurance catalog ---
POLICIES = [
    ("SafeHealth Basic", 60, 50000, "Covers consultations and basic lab tests"),
    ("SafeHealth Premium", 85, 120000, "Covers consultations, labs, pharmacy and admissions"),
]
for name, cov, prem, desc in POLICIES:
    InsurancePolicy.objects.get_or_create(provider=ins, name=name, defaults=dict(coverage_percent=cov, premium=prem, description=desc))

print("Seed complete. Demo credentials in README.md")
