"""Seed an expanded community of patients, doctors and pharmacists.

Run from backend/ after seed.py:
    .venv/bin/python seed_community.py
"""
import datetime as dt
import os
import sys
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from accounts.models import DoctorProfile, ProfileStatus  # noqa: E402
from appointments.models import Appointment, Availability  # noqa: E402
from registry.models import Organization, PractitionerCredential  # noqa: E402
from seed import add_staff, make_user, upsert_patient, upsert_professional_profile  # noqa: E402
from workforce.models import Department  # noqa: E402

TODAY = timezone.localdate()
NOW = timezone.now()
LICENCE_EXPIRY = TODAY + dt.timedelta(days=540)

PATIENTS = [
    ("patient2@healthpilot.test", "Brian", "Ssekandi", "1990-03-14", "male", "O+"),
    ("patient3@healthpilot.test", "Catherine", "Nalwoga", "1985-07-02", "female", "A+"),
    ("patient4@healthpilot.test", "David", "Mugisha", "1978-11-25", "male", "B+"),
    ("patient5@healthpilot.test", "Esther", "Akello", "1993-05-19", "female", "AB+"),
    ("patient6@healthpilot.test", "Francis", "Okumu", "1982-09-08", "male", "O-"),
    ("patient7@healthpilot.test", "Gloria", "Nantume", "1996-01-30", "female", "A-"),
    ("patient8@healthpilot.test", "Henry", "Kibirige", "1970-12-12", "male", "B-"),
    ("patient9@healthpilot.test", "Irene", "Namono", "1988-06-21", "female", "O+"),
    ("patient10@healthpilot.test", "Joseph", "Lwanga", "1995-04-05", "male", "A+"),
    ("patient11@healthpilot.test", "Kevin", "Turyakira", "1991-08-16", "male", "AB-"),
    ("patient12@healthpilot.test", "Lillian", "Achan", "1987-02-27", "female", "O+"),
    ("patient13@healthpilot.test", "Moses", "Wekesa", "1983-10-09", "male", "B+"),
    ("patient14@healthpilot.test", "Naomi", "Kembabazi", "1998-03-23", "female", "A+"),
    ("patient15@healthpilot.test", "Oscar", "Sempala", "1975-06-11", "male", "O+"),
    ("patient16@healthpilot.test", "Patience", "Nabirye", "1992-09-14", "female", "B-"),
    ("patient17@healthpilot.test", "Ronald", "Kigozi", "1989-12-01", "male", "A-"),
    ("patient18@healthpilot.test", "Sandra", "Mirembe", "1994-07-28", "female", "AB+"),
    ("patient19@healthpilot.test", "Timothy", "Onyango", "1980-05-07", "male", "O+"),
    ("patient20@healthpilot.test", "Ursula", "Nakigudde", "1986-11-19", "female", "A+"),
    ("patient21@healthpilot.test", "Victor", "Muwonge", "1979-01-24", "male", "B+"),
    ("patient22@healthpilot.test", "Winnie", "Atim", "1997-08-31", "female", "O-"),
    ("patient23@healthpilot.test", "Xavier", "Lubega", "1990-04-17", "male", "AB-"),
    ("patient24@healthpilot.test", "Yvonne", "Najjuma", "1993-10-03", "female", "A+"),
    ("patient25@healthpilot.test", "Zachary", "Odongo", "1984-02-13", "male", "O+"),
]

DOCTORS = [
    ("dr.mugerwa@healthpilot.test", "Peter", "Mugerwa", "Internal Medicine", "consultant", 80000),
    ("dr.nambi@healthpilot.test", "Florence", "Nambi", "Obstetrics & Gynaecology", "specialist", 60000),
    ("dr.ssemakula@healthpilot.test", "Andrew", "Ssemakula", "General Surgery", "specialist", 70000),
    ("dr.acheng@healthpilot.test", "Beatrice", "Acheng", "Paediatrics", "specialist", 45000),
    ("dr.tumusiime@healthpilot.test", "Gerald", "Tumusiime", "Cardiology", "consultant", 90000),
    ("dr.nakafeero@healthpilot.test", "Miriam", "Nakafeero", "Family Medicine", "medical_officer", 30000),
    ("dr.ochan@healthpilot.test", "Samuel", "Ochan", "Orthopaedics", "specialist", 65000),
    ("dr.kyarisiima@healthpilot.test", "Doreen", "Kyarisiima", "Dermatology", "specialist", 50000),
    ("dr.bwire@healthpilot.test", "Collins", "Bwire", "ENT Surgery", "specialist", 55000),
    ("dr.nansamba@healthpilot.test", "Ritah", "Nansamba", "Psychiatry", "specialist", 60000),
    ("dr.kizito@healthpilot.test", "Allan", "Kizito", "Ophthalmology", "specialist", 55000),
    ("dr.akankwasa@healthpilot.test", "Belinda", "Akankwasa", "General Medicine", "medical_officer", 30000),
]

PHARMACISTS = [
    ("pharmacist2@healthpilot.test", "Dennis", "Wanyama"),
    ("pharmacist3@healthpilot.test", "Sharon", "Tendo"),
    ("pharmacist4@healthpilot.test", "Marvin", "Ouma"),
    ("pharmacist5@healthpilot.test", "Lydia", "Nabunya"),
    ("pharmacist6@healthpilot.test", "Emmanuel", "Sseruyange"),
    ("pharmacist7@healthpilot.test", "Priscilla", "Ahebwa"),
]


def main():
    hospital_org = Organization.objects.filter(organization_type="hospital", status="verified").first()
    pharmacy_org = Organization.objects.filter(organization_type="pharmacy", status="verified").first()
    opd = Department.objects.filter(organization=hospital_org, code="OPD").first()
    pha = Department.objects.filter(organization=pharmacy_org, code="PHA").first()

    for email, first, last, dob, gender, blood in PATIENTS:
        user = make_user(email, "patient", first, last, f"+256 70{abs(hash(email)) % 9000000 + 1000000}")
        upsert_patient(user, dob, gender, blood, "Busiika, Wakiso")
    print(f"patients seeded: {len(PATIENTS)}")

    doctors = []
    for index, (email, first, last, specialty, cadre, fee) in enumerate(DOCTORS, start=4):
        doctor = make_user(email, "doctor", first, last, f"+256 70{abs(hash(email)) % 9000000 + 1000000}")
        licence = f"MDC-DEMO-{index:04d}"
        DoctorProfile.objects.update_or_create(
            user=doctor,
            defaults={
                "year_of_completion": 2012,
                "university": "Makerere University College of Health Sciences",
                "cadre": cadre,
                "specialization": specialty,
                "hospital": hospital_org.legal_name if hospital_org else "",
                "experience_years": 12,
                "fees": fee,
                "bio": f"Verified {specialty} specialist offering in-person and online consultations.",
                "license_number": licence,
                "license_issuer": "Uganda Demo Medical Council",
                "license_issued_on": TODAY - dt.timedelta(days=200),
                "license_expires_on": LICENCE_EXPIRY,
                "status": ProfileStatus.VERIFIED,
                "verification_notes": "Verified demonstration professional.",
                "average_rating": Decimal("4.70"),
            },
        )
        PractitionerCredential.objects.update_or_create(
            practitioner=doctor,
            issuer="Uganda Demo Medical Council",
            identifier=licence,
            defaults={
                "credential_type": PractitionerCredential.Type.LICENSE,
                "title": f"Licence to practise — {specialty}",
                "issued_on": TODAY - dt.timedelta(days=200),
                "expires_on": LICENCE_EXPIRY,
                "status": PractitionerCredential.Status.VERIFIED,
            },
        )
        if hospital_org:
            add_staff(doctor, hospital_org, opd, f"{specialty} Doctor", True)
        for weekday in range(6):
            Availability.objects.update_or_create(
                doctor=doctor, weekday=weekday, start_time=dt.time(8, 0), end_time=dt.time(17, 0),
                defaults={"slot_minutes": 30, "breaks": [{"start": "13:00", "end": "14:00"}], "holidays": [], "is_active": True},
            )
        doctors.append(doctor)
    print(f"doctors seeded: {len(DOCTORS)}")

    for email, first, last in PHARMACISTS:
        user = make_user(email, "pharmacist", first, last, f"+256 70{abs(hash(email)) % 9000000 + 1000000}")
        registration = f"PHA-DEMO-{abs(hash(email)) % 9000 + 1000}"
        upsert_professional_profile(user, "Pharmacist", registration, True)
        if pharmacy_org:
            add_staff(user, pharmacy_org, pha, "Pharmacist", True)
    print(f"pharmacists seeded: {len(PHARMACISTS)}")

    # A spread of upcoming appointments so dashboards are alive.
    from django.contrib.auth import get_user_model

    User = get_user_model()
    patients = list(User.objects.filter(email__in=[p[0] for p in PATIENTS[:12]]))
    for index, patient in enumerate(patients):
        doctor = doctors[index % len(doctors)]
        day = TODAY + dt.timedelta(days=index % 7 + 1)
        Appointment.objects.get_or_create(
            patient=patient,
            doctor=doctor,
            date=day,
            start_time=dt.time(9 + index % 6, 0),
            defaults={
                "end_time": dt.time(9 + index % 6, 30),
                "type": "online" if index % 2 else "in_person",
                "status": "confirmed",
                "reason": "Routine consultation",
            },
        )
    print(f"appointments seeded: {len(patients)}")


if __name__ == "__main__":
    main()
