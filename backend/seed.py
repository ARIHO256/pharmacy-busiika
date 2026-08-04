"""Create a broad, idempotent MyDoctor demonstration dataset.

Run after migrations:
    python seed.py

All demonstration accounts use ``DemoPass!2026`` except the platform admin,
which uses ``AdminPass!2026``.  Never enable demo data in a real production
instance containing live patient information.
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
from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import (  # noqa: E402
    DoctorProfile,
    PatientProfile,
    PatientRelationship,
    ProfileStatus,
    ProviderProfile,
    StaffProfile,
)
from accounts.roles import BOOKABLE_PROVIDER_ROLES  # noqa: E402
from appointments.models import Appointment, AppointmentStatusHistory, Availability  # noqa: E402
from clinical.models import Referral, ReferralStatusHistory  # noqa: E402
from communication.models import (  # noqa: E402
    Conversation,
    Message,
    Notification,
    NotificationPreference,
    NotificationTemplate,
)
from interoperability.models import TerminologyConcept  # noqa: E402
from operations.models import (  # noqa: E402
    AccountSubscription,
    Admission,
    AmbulanceDispatch,
    Announcement,
    BedAllocation,
    ClinicalRound,
    EmergencyCase,
    FacilityBed,
    ImagingOrder,
    ImagingReport,
    InventoryBatch,
    InventoryItem,
    LeaveRequest,
    MaternityEpisode,
    PrivacyRequest,
    PurchaseOrder,
    PurchaseOrderItem,
    QualityIncident,
    StaffShift,
    StockMovement,
    SubscriptionPlan,
    SupportTicket,
    SurgicalCase,
    SurgicalChecklist,
    Ward,
    WardTask,
)
from payments.models import CashierShift, Invoice, InvoiceItem, PaymentTransaction  # noqa: E402
from payments.services import confirm_invoice_payment  # noqa: E402
from prescriptions.models import Prescription, PrescriptionItem  # noqa: E402
from registry.models import (  # noqa: E402
    Organization,
    OrganizationLocation,
    PractitionerCredential,
    PractitionerRole,
)
from registry.services import sync_provider_organization  # noqa: E402
from services.models import (  # noqa: E402
    Bed,
    CriticalResultAcknowledgement,
    DispensingItem,
    DispensingRecord,
    HospitalBooking,
    HospitalService,
    InsuranceBenefitRule,
    InsuranceClaim,
    InsuranceClaimItem,
    InsuranceEligibilityCheck,
    InsurancePreauthorization,
    InsuranceRemittance,
    InsurancePolicy,
    LabOrder,
    LabTestPanel,
    LabTestPanelItem,
    LabResult,
    LabTest,
    Medicine,
    Order,
    OrderItem,
    PatientCoverage,
    PharmacyOrder,
    Supplier,
    SupplierProduct,
    SpecimenEvent,
)
from workforce.access_control import DEFAULT_ROLE_PERMISSIONS  # noqa: E402
from workforce.models import (  # noqa: E402
    Department,
    FacilityRole,
    FacilityRolePermission,
    MembershipRoleAssignment,
    NursingNote,
    PatientVisit,
    PermissionDefinition,
    StaffMembership,
    TriageRecord,
)

User = get_user_model()
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoPass!2026")
ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "AdminPass!2026")
TODAY = timezone.localdate()
NOW = timezone.now()
LICENCE_EXPIRY = TODAY + dt.timedelta(days=420)

# One deterministic account for every platform role.  The seed performs a final
# database assertion against this catalogue so role/portal demos cannot silently
# drift apart.
DEMO_ROLE_ACCOUNTS = {
    "patient": "patient1@mydoctor.test",
    "doctor": "dr.nakato@mydoctor.test",
    "nurse": "nurse@mydoctor.test",
    "receptionist": "reception@mydoctor.test",
    "cashier": "cashier@mydoctor.test",
    "pharmacist": "pharmacist.staff@mydoctor.test",
    "lab_technician": "labtech@mydoctor.test",
    "facility_manager": "manager@mydoctor.test",
    "records_officer": "records@mydoctor.test",
    "insurance_officer": "insurance.officer@mydoctor.test",
    "storekeeper": "storekeeper@mydoctor.test",
    "midwife": "midwife@mydoctor.test",
    "clinical_officer": "clinical.officer@mydoctor.test",
    "dentist": "dentist@mydoctor.test",
    "radiologist": "radiologist@mydoctor.test",
    "radiographer": "radiographer@mydoctor.test",
    "physiotherapist": "physio@mydoctor.test",
    "nutritionist": "nutrition@mydoctor.test",
    "psychologist": "psychology@mydoctor.test",
    "anaesthetist": "anaesthetist@mydoctor.test",
    "theatre_nurse": "theatre.nurse@mydoctor.test",
    "medical_director": "medical.director@mydoctor.test",
    "accountant": "accountant@mydoctor.test",
    "finance_manager": "finance.manager@mydoctor.test",
    "procurement_officer": "procurement@mydoctor.test",
    "quality_officer": "quality@mydoctor.test",
    "compliance_officer": "compliance@mydoctor.test",
    "hr_officer": "hr@mydoctor.test",
    "it_support": "it@mydoctor.test",
    "claims_reviewer": "claims@mydoctor.test",
    "ambulance_dispatcher": "dispatcher@mydoctor.test",
    "paramedic": "paramedic@mydoctor.test",
    "pharmacy": "pharmacy@mydoctor.test",
    "lab": "lab@mydoctor.test",
    "hospital": "hospital@mydoctor.test",
    "insurance": "insurance@mydoctor.test",
    "admin": "admin@mydoctor.test",
}


def log(message):
    print(f"[seed] {message}")


def make_user(email, role, first, last, phone, *, verified=True, staff=False, superuser=False):
    user, _ = User.objects.get_or_create(email=email)
    user.role = role
    user.first_name = first
    user.last_name = last
    user.phone = phone
    user.is_active = True
    user.is_verified = verified
    user.email_verified_at = user.email_verified_at or NOW
    user.phone_verified_at = user.phone_verified_at or NOW
    user.is_staff = staff or superuser
    user.is_superuser = superuser
    user.failed_login_attempts = 0
    user.locked_until = None
    user.set_password(ADMIN_PASSWORD if superuser else DEMO_PASSWORD)
    user.save()
    NotificationPreference.objects.get_or_create(
        user=user,
        defaults={
            "in_app_enabled": True,
            "email_enabled": True,
            "sms_enabled": False,
            "appointment_reminders": True,
            "clinical_updates": True,
            "payment_updates": True,
        },
    )
    return user


def upsert_patient(user, dob, gender, blood_group, location, history="No chronic condition documented"):
    PatientProfile.objects.update_or_create(
        user=user,
        defaults={
            "dob": dob,
            "gender": gender,
            "blood_group": blood_group,
            "allergies": "Penicillin" if user.email.startswith("patient2") else "None known",
            "medical_history": history,
            "emergency_contact": "+256 700 555 900",
            "location": location,
            "address": f"{location}, Uganda",
        },
    )


def upsert_provider(email, role, first, last, phone, name, org_type, licence, address):
    user = make_user(email, role, first, last, phone)
    profile, _ = ProviderProfile.objects.update_or_create(
        user=user,
        defaults={
            "organization_type": org_type,
            "org_name": name,
            "license_number": licence,
            "license_issuer": "Uganda Demo Health Facilities Authority",
            "license_issued_on": TODAY - dt.timedelta(days=120),
            "license_expires_on": LICENCE_EXPIRY,
            "district": "Kampala",
            "address": address,
            "services_description": f"Verified {org_type.replace('_', ' ')} services, appointments, billing and digital records.",
            "status": ProfileStatus.VERIFIED,
            "verification_notes": "Verified demonstration organization.",
        },
    )
    sync_provider_organization(user, profile)
    organization, _ = Organization.objects.update_or_create(
        owner=user,
        organization_type=org_type,
        defaults={
            "legal_name": name,
            "trading_name": name,
            "license_number": licence,
            "license_issued_on": TODAY - dt.timedelta(days=120),
            "license_expires_on": LICENCE_EXPIRY,
            "services_description": profile.services_description,
            "issuing_authority": profile.license_issuer,
            "status": Organization.Status.VERIFIED,
            "contact_email": user.email,
            "phone": user.phone,
            "address": address,
            "district": "Kampala",
            "country_code": "UG",
            "active": True,
        },
    )
    OrganizationLocation.objects.update_or_create(
        organization=organization,
        name="Main Branch",
        defaults={
            "address": address,
            "district": "Kampala",
            "timezone": "Africa/Kampala",
            "phone": phone,
            "active": True,
        },
    )
    return user, organization


def upsert_professional_profile(user, title, registration_number, professional=True):
    StaffProfile.objects.update_or_create(
        user=user,
        defaults={
            "employee_number": f"EMP-{user.id:05d}",
            "cadre": title,
            "university": "Makerere University Health Sciences" if professional else "",
            "year_of_completion": 2020 if professional else None,
            "qualification": title,
            "specialty": title if user.role in BOOKABLE_PROVIDER_ROLES else "",
            "workplace": "MyDoctor Demonstration Facility" if user.role in BOOKABLE_PROVIDER_ROLES else "",
            "experience_years": 6 if user.role in BOOKABLE_PROVIDER_ROLES else 0,
            "consultation_fee": 45000 if user.role in BOOKABLE_PROVIDER_ROLES else 0,
            "offers_appointments": user.role in BOOKABLE_PROVIDER_ROLES,
            "registration_number": registration_number if professional else "",
            "license_issuer": "Uganda Demo Professional Council" if professional else "",
            "license_expires_on": LICENCE_EXPIRY if professional else None,
            "bio": f"Demonstration {title.lower()} account for workflow testing.",
            "status": ProfileStatus.VERIFIED,
        },
    )
    if professional:
        PractitionerCredential.objects.update_or_create(
            practitioner=user,
            issuer="Uganda Demo Professional Council",
            identifier=registration_number,
            defaults={
                "credential_type": PractitionerCredential.Type.LICENSE,
                "title": f"{title} practising licence",
                "issued_on": TODAY - dt.timedelta(days=120),
                "expires_on": LICENCE_EXPIRY,
                "status": PractitionerCredential.Status.VERIFIED,
                "verified_at": NOW,
            },
        )


def add_staff(user, organization, department, title, professional=False):
    profile = getattr(user, "staff_profile", None)
    membership, _ = StaffMembership.objects.update_or_create(
        user=user,
        organization=organization,
        role=user.role,
        defaults={
            "department": department,
            "job_title": title,
            "employee_number": getattr(profile, "employee_number", f"EMP-{user.id:05d}"),
            "status": StaffMembership.Status.ACTIVE,
            "is_primary": True,
            "starts_on": TODAY - dt.timedelta(days=180),
            "created_by": organization.owner,
        },
    )
    if professional:
        PractitionerRole.objects.update_or_create(
            practitioner=user,
            organization=organization,
            role_name=title,
            specialty="",
            defaults={
                "active": True,
                "telemedicine_enabled": user.role in {
                    "doctor", "clinical_officer", "psychologist", "nutritionist"
                },
            },
        )
    return membership


def seed_permissions(organizations, memberships):
    all_codes = sorted({code for codes in DEFAULT_ROLE_PERMISSIONS.values() for code in codes})
    definitions = {}
    for code in all_codes:
        module = code.split(".", 1)[0]
        definition, _ = PermissionDefinition.objects.update_or_create(
            code=code,
            defaults={
                "name": code.replace(".", " ").replace("_", " ").title(),
                "module": module,
                "description": f"Allows authorized users to perform {code.replace('.', ' ')} operations.",
                "sensitive": module in {"clinical", "privacy", "security", "refunds", "records"},
                "active": True,
            },
        )
        definitions[code] = definition
    membership_by_org_role = {(m.organization_id, m.role): m for m in memberships}
    for organization in organizations:
        roles_in_org = sorted({m.role for m in memberships if m.organization_id == organization.id})
        for role_code in roles_in_org:
            role, _ = FacilityRole.objects.update_or_create(
                organization=organization,
                code=role_code.replace("_", "-"),
                defaults={
                    "name": role_code.replace("_", " ").title(),
                    "description": "System role seeded from the MyDoctor least-privilege catalogue.",
                    "active": True,
                    "is_system": True,
                    "created_by": organization.owner,
                },
            )
            wanted = DEFAULT_ROLE_PERMISSIONS.get(role_code, set())
            FacilityRolePermission.objects.filter(role=role).exclude(permission__code__in=wanted).delete()
            for code in wanted:
                FacilityRolePermission.objects.get_or_create(
                    role=role,
                    permission=definitions[code],
                    defaults={"granted_by": organization.owner},
                )
            membership = membership_by_org_role.get((organization.id, role_code))
            if membership:
                MembershipRoleAssignment.objects.update_or_create(
                    membership=membership,
                    role=role,
                    defaults={"assigned_by": organization.owner, "active": True},
                )


@transaction.atomic
def run():
    admin = make_user(
        "admin@mydoctor.test", "admin", "Platform", "Administrator",
        "+256 700 000 001", staff=True, superuser=True,
    )

    patient_specs = [
        ("patient1@mydoctor.test", "Amina", "Nansubuga", "+256 700 101 001", dt.date(1995, 4, 12), "female", "O+", "Kampala"),
        ("patient2@mydoctor.test", "Brian", "Okello", "+256 700 101 002", dt.date(1988, 9, 3), "male", "A+", "Wakiso"),
        ("patient3@mydoctor.test", "Mariam", "Achen", "+256 700 101 003", dt.date(2000, 1, 17), "female", "B+", "Mukono"),
        ("patient4@mydoctor.test", "Samuel", "Kato", "+256 700 101 004", dt.date(1974, 6, 22), "male", "O-", "Kampala"),
        ("patient5@mydoctor.test", "Joan", "Atim", "+256 700 101 005", dt.date(1992, 11, 8), "female", "AB+", "Entebbe"),
    ]
    patients = []
    for email, first, last, phone, dob, gender, blood, location in patient_specs:
        patient = make_user(email, "patient", first, last, phone)
        upsert_patient(patient, dob, gender, blood, location)
        patients.append(patient)
    p1, p2, p3, p4, p5 = patients

    dependent = make_user(
        "dependent.joy@patients.mydoctor.local", "patient", "Joy", "Nansubuga", ""
    )
    dependent.set_unusable_password()
    dependent.save(update_fields=["password"])
    upsert_patient(dependent, dt.date(2017, 8, 19), "female", "O+", "Kampala")
    PatientRelationship.objects.update_or_create(
        caregiver=p1, patient=dependent,
        defaults={
            "relationship": PatientRelationship.Relationship.PARENT,
            "status": PatientRelationship.Status.ACTIVE,
            "can_book": True, "can_view_records": True,
            "can_manage_billing": True, "can_receive_notifications": True,
            "verified_by": admin, "verified_at": NOW,
            "notes": "Demonstration child profile managed by the parent account.",
        },
    )

    hospital_owner, hospital_org = upsert_provider(
        "hospital@mydoctor.test", "hospital", "Hope", "Medical Centre", "+256 700 200 001",
        "Hope Medical Centre", Organization.Type.HOSPITAL, "HFA-DEMO-1001", "Wandegeya, Kampala",
    )
    pharmacy_owner, pharmacy_org = upsert_provider(
        "pharmacy@mydoctor.test", "pharmacy", "Busiika", "Pharmacy", "+256 700 200 002",
        "Busiika Pharmacy", Organization.Type.PHARMACY, "NDA-DEMO-2001", "Kampala Road",
    )
    lab_owner, lab_org = upsert_provider(
        "lab@mydoctor.test", "lab", "City", "Diagnostics", "+256 700 200 003",
        "City Diagnostics Laboratory", Organization.Type.LABORATORY, "AHPC-DEMO-3001", "Nakasero, Kampala",
    )
    insurer_owner, insurer_org = upsert_provider(
        "insurance@mydoctor.test", "insurance", "SafeHealth", "Insurance", "+256 700 200 004",
        "SafeHealth Insurance", Organization.Type.INSURER, "IRA-DEMO-4001", "Nakawa, Kampala",
    )

    # Departments and branches drive organization-scoped access.
    department_specs = [
        (hospital_org, "Outpatient Department", "OPD"),
        (hospital_org, "Emergency & Ambulance", "ED"),
        (hospital_org, "Nursing Services", "NUR"),
        (hospital_org, "Maternity", "MAT"),
        (hospital_org, "Theatre & Recovery", "THR"),
        (hospital_org, "Radiology", "RAD"),
        (hospital_org, "Physiotherapy", "PHY"),
        (hospital_org, "Nutrition", "NUT"),
        (hospital_org, "Mental Health", "PSY"),
        (hospital_org, "Medical Records", "REC"),
        (hospital_org, "Finance & Billing", "FIN"),
        (hospital_org, "Procurement & Stores", "PRO"),
        (hospital_org, "Quality & Compliance", "QAC"),
        (hospital_org, "Human Resources", "HR"),
        (hospital_org, "Information Technology", "IT"),
        (pharmacy_org, "Dispensary", "PHA"),
        (pharmacy_org, "Pharmacy Stores", "PST"),
        (lab_org, "Sample Collection", "COL"),
        (lab_org, "Main Laboratory", "LAB"),
        (insurer_org, "Membership & Eligibility", "ELG"),
        (insurer_org, "Claims", "CLM"),
    ]
    departments = {}
    for organization, name, code in department_specs:
        department, _ = Department.objects.update_or_create(
            organization=organization,
            name=name,
            defaults={"code": code, "description": f"{name} operational unit", "active": True},
        )
        departments[(organization.id, code)] = department

    # Doctors use the doctor profile and can be directly listed after verification.
    doctors = []
    doctor_specs = [
        ("dr.nakato@mydoctor.test", "Sarah", "Nakato", "+256 700 300 001", "General Medicine", "medical_officer", 30000, "MDC-DEMO-0001"),
        ("dr.kato@mydoctor.test", "James", "Kato", "+256 700 300 002", "Paediatrics", "specialist", 45000, "MDC-DEMO-0002"),
        ("dr.aina@mydoctor.test", "Grace", "Aina", "+256 700 300 003", "Dermatology", "specialist", 50000, "MDC-DEMO-0003"),
    ]
    memberships = []
    for email, first, last, phone, specialty, cadre, fee, licence in doctor_specs:
        doctor = make_user(email, "doctor", first, last, phone)
        DoctorProfile.objects.update_or_create(
            user=doctor,
            defaults={
                "year_of_completion": 2014,
                "university": "Makerere University College of Health Sciences",
                "cadre": cadre,
                "specialization": specialty,
                "hospital": hospital_org.legal_name,
                "experience_years": 10,
                "fees": fee,
                "bio": f"Verified {specialty} professional providing in-person and online care.",
                "license_number": licence,
                "license_issuer": "Uganda Demo Medical Council",
                "license_issued_on": TODAY - dt.timedelta(days=120),
                "license_expires_on": LICENCE_EXPIRY,
                "status": ProfileStatus.VERIFIED,
                "verification_notes": "Verified demonstration professional.",
                "average_rating": Decimal("4.80"),
            },
        )
        PractitionerCredential.objects.update_or_create(
            practitioner=doctor,
            issuer="Uganda Demo Medical Council",
            identifier=licence,
            defaults={
                "credential_type": PractitionerCredential.Type.LICENSE,
                "title": f"Licence to practise — {specialty}",
                "issued_on": TODAY - dt.timedelta(days=120),
                "expires_on": LICENCE_EXPIRY,
                "status": PractitionerCredential.Status.VERIFIED,
                "verified_by": admin,
                "verified_at": NOW,
            },
        )
        PractitionerRole.objects.update_or_create(
            practitioner=doctor,
            organization=hospital_org,
            role_name="Doctor",
            specialty=specialty,
            defaults={"active": True, "telemedicine_enabled": True},
        )
        membership, _ = StaffMembership.objects.update_or_create(
            user=doctor,
            organization=hospital_org,
            role="doctor",
            defaults={
                "department": departments[(hospital_org.id, "OPD")],
                "job_title": specialty,
                "employee_number": f"DOC-{doctor.id:05d}",
                "status": StaffMembership.Status.ACTIVE,
                "is_primary": True,
                "starts_on": TODAY - dt.timedelta(days=365),
                "created_by": hospital_owner,
            },
        )
        memberships.append(membership)
        for weekday in range(5):
            Availability.objects.update_or_create(
                doctor=doctor,
                weekday=weekday,
                start_time=dt.time(9, 0),
                end_time=dt.time(16, 0),
                defaults={
                    "slot_minutes": 30,
                    "breaks": [{"start": "13:00", "end": "14:00"}],
                    "holidays": [],
                    "is_active": True,
                },
            )
        doctors.append(doctor)
    dr_sarah, dr_james, dr_grace = doctors

    staff_specs = [
        # email, role, names, phone, org, dept code, title, regulated
        ("clinical.officer@mydoctor.test", "clinical_officer", "Daniel", "Mugisha", "+256 701 400 001", hospital_org, "OPD", "Senior Clinical Officer", True),
        ("dentist@mydoctor.test", "dentist", "Lydia", "Nabwire", "+256 701 400 002", hospital_org, "OPD", "Dental Surgeon", True),
        ("medical.director@mydoctor.test", "medical_director", "Peter", "Ouma", "+256 701 400 003", hospital_org, "OPD", "Medical Director", True),
        ("nurse@mydoctor.test", "nurse", "Esther", "Nabirye", "+256 701 400 004", hospital_org, "NUR", "Registered Nurse", True),
        ("midwife@mydoctor.test", "midwife", "Rebecca", "Nalukenge", "+256 701 400 005", hospital_org, "MAT", "Registered Midwife", True),
        ("theatre.nurse@mydoctor.test", "theatre_nurse", "Martha", "Akello", "+256 701 400 006", hospital_org, "THR", "Theatre Nurse", True),
        ("anaesthetist@mydoctor.test", "anaesthetist", "Michael", "Obote", "+256 701 400 007", hospital_org, "THR", "Anaesthetist", True),
        ("radiologist@mydoctor.test", "radiologist", "Christine", "Namara", "+256 701 400 008", hospital_org, "RAD", "Consultant Radiologist", True),
        ("radiographer@mydoctor.test", "radiographer", "Alex", "Tumwine", "+256 701 400 009", hospital_org, "RAD", "Radiographer", True),
        ("physio@mydoctor.test", "physiotherapist", "Anita", "Kiconco", "+256 701 400 010", hospital_org, "PHY", "Physiotherapist", True),
        ("nutrition@mydoctor.test", "nutritionist", "Brenda", "Auma", "+256 701 400 011", hospital_org, "NUT", "Clinical Nutritionist", True),
        ("psychology@mydoctor.test", "psychologist", "David", "Ssemakula", "+256 701 400 012", hospital_org, "PSY", "Clinical Psychologist", True),
        ("paramedic@mydoctor.test", "paramedic", "Ivan", "Ocen", "+256 701 400 013", hospital_org, "ED", "Paramedic", True),
        ("dispatcher@mydoctor.test", "ambulance_dispatcher", "Rose", "Namutebi", "+256 701 400 014", hospital_org, "ED", "Ambulance Dispatcher", False),
        ("reception@mydoctor.test", "receptionist", "Ruth", "Adoch", "+256 701 400 015", hospital_org, "OPD", "Receptionist", False),
        ("records@mydoctor.test", "records_officer", "Moses", "Ssemanda", "+256 701 400 016", hospital_org, "REC", "Medical Records Officer", False),
        ("cashier@mydoctor.test", "cashier", "Diana", "Atwine", "+256 701 400 017", hospital_org, "FIN", "Cashier", False),
        ("accountant@mydoctor.test", "accountant", "Geoffrey", "Byaruhanga", "+256 701 400 018", hospital_org, "FIN", "Accountant", False),
        ("finance.manager@mydoctor.test", "finance_manager", "Patricia", "Nankya", "+256 701 400 019", hospital_org, "FIN", "Finance Manager", False),
        ("manager@mydoctor.test", "facility_manager", "Paul", "Kizito", "+256 701 400 020", hospital_org, "OPD", "Facility Manager", False),
        ("procurement@mydoctor.test", "procurement_officer", "Stephen", "Muwanga", "+256 701 400 021", hospital_org, "PRO", "Procurement Officer", False),
        ("storekeeper@mydoctor.test", "storekeeper", "John", "Wasswa", "+256 701 400 022", hospital_org, "PRO", "Hospital Storekeeper", False),
        ("quality@mydoctor.test", "quality_officer", "Agnes", "Nabukenya", "+256 701 400 023", hospital_org, "QAC", "Quality Assurance Officer", False),
        ("compliance@mydoctor.test", "compliance_officer", "Martin", "Kakooza", "+256 701 400 024", hospital_org, "QAC", "Data Protection Officer", False),
        ("hr@mydoctor.test", "hr_officer", "Sharon", "Nabasa", "+256 701 400 025", hospital_org, "HR", "Human Resources Officer", False),
        ("it@mydoctor.test", "it_support", "Ronald", "Mwesigwa", "+256 701 400 026", hospital_org, "IT", "IT Support Officer", False),
        ("pharmacist.staff@mydoctor.test", "pharmacist", "Irene", "Namuli", "+256 701 500 001", pharmacy_org, "PHA", "Pharmacist", True),
        ("pharmacy.store@mydoctor.test", "storekeeper", "Isaac", "Kintu", "+256 701 500 002", pharmacy_org, "PST", "Pharmacy Storekeeper", False),
        ("pharmacy.procurement@mydoctor.test", "procurement_officer", "Mercy", "Atukunda", "+256 701 500 003", pharmacy_org, "PST", "Pharmacy Procurement Officer", False),
        ("labtech@mydoctor.test", "lab_technician", "Kevin", "Otim", "+256 701 600 001", lab_org, "LAB", "Laboratory Technologist", True),
        ("phlebotomist@mydoctor.test", "lab_technician", "Mercy", "Aciro", "+256 701 600 002", lab_org, "COL", "Phlebotomist", True),
        ("insurance.officer@mydoctor.test", "insurance_officer", "Hellen", "Nakirya", "+256 701 700 001", insurer_org, "ELG", "Insurance Officer", False),
        ("claims@mydoctor.test", "claims_reviewer", "Andrew", "Kasaija", "+256 701 700 002", insurer_org, "CLM", "Claims Reviewer", False),
    ]
    staff_users = {}
    for index, (email, role, first, last, phone, organization, dept_code, title, professional) in enumerate(staff_specs, start=1):
        user = make_user(email, role, first, last, phone)
        registration = f"REG-DEMO-{index:04d}"
        upsert_professional_profile(user, title, registration, professional)
        membership = add_staff(user, organization, departments[(organization.id, dept_code)], title, professional)
        memberships.append(membership)
        if role in BOOKABLE_PROVIDER_ROLES:
            for weekday in range(5):
                Availability.objects.update_or_create(
                    doctor=user, weekday=weekday, start_time=dt.time(10, 0), end_time=dt.time(15, 0),
                    defaults={"slot_minutes": 30, "breaks": [{"start": "12:30", "end": "13:00"}], "holidays": [], "is_active": True},
                )
        staff_users[role] = user
        staff_users[email] = user

    seed_permissions([hospital_org, pharmacy_org, lab_org, insurer_org], memberships)

    # Terminology and message templates.
    for code, display, category, aliases in [
        ("blood-pressure", "Blood pressure", "vital_sign", ["BP"]),
        ("heart-rate", "Heart rate", "vital_sign", ["Pulse"]),
        ("body-temperature", "Body temperature", "vital_sign", ["Temperature"]),
        ("oxygen-saturation", "Oxygen saturation", "vital_sign", ["SpO2"]),
        ("weight", "Body weight", "vital_sign", ["Weight"]),
        ("cbc", "Complete blood count", "laboratory", ["FBC", "CBC"]),
    ]:
        TerminologyConcept.objects.update_or_create(
            system="urn:mydoctor:local:observation",
            version="1",
            code=code,
            defaults={"display": display, "category": category, "aliases": aliases, "active": True},
        )
    for code, title, body, kind, channels in [
        ("appointment.confirmed", "Appointment confirmed", "Your appointment with {provider} is confirmed for {date} at {time}.", "appointment", ["in_app", "email", "sms"]),
        ("payment.received", "Payment received", "Payment for invoice {invoice} was received. Receipt {receipt} is available.", "payment", ["in_app", "email"]),
        ("result.released", "Result released", "A verified result for {test} is now available in your patient portal.", "clinical", ["in_app", "email"]),
        ("licence.expiry", "Licence expiry reminder", "Your licence expires on {expiry}. Upload a renewal before the deadline.", "credential_expiry", ["in_app", "email", "sms"]),
    ]:
        NotificationTemplate.objects.update_or_create(
            code=code,
            defaults={"title_template": title, "body_template": body, "kind": kind, "default_channels": channels, "active": True},
        )

    # Catalogues.
    medicines = []
    for name, desc, price, stock in [
        ("Paracetamol 500 mg (20 tablets)", "Pain and fever relief", 3000, 120),
        ("Amoxicillin 250 mg (10 capsules)", "Prescription antibiotic", 8500, 60),
        ("Metformin 500 mg (30 tablets)", "Type 2 diabetes management", 12000, 80),
        ("Cetirizine 10 mg (10 tablets)", "Allergy relief", 4500, 100),
        ("Omeprazole 20 mg (14 capsules)", "Acid reflux treatment", 9800, 45),
        ("ORS sachets (5 pack)", "Oral rehydration salts", 2500, 150),
    ]:
        medicine, _ = Medicine.objects.update_or_create(
            pharmacy=pharmacy_owner, name=name,
            defaults={"description": desc, "price": price, "stock": stock},
        )
        medicines.append(medicine)
    supplier, _ = Supplier.objects.update_or_create(
        pharmacy=pharmacy_owner,
        suppliername="MediSource Uganda",
        defaults={"contact": "0700222333", "email": "sales@medisource.example", "address": "Industrial Area, Kampala"},
    )
    for medicine in medicines[:3]:
        SupplierProduct.objects.update_or_create(
            supplier=supplier, name=medicine.name,
            defaults={"qty": 100, "price": max(medicine.price - 500, 1)},
        )

    lab_tests = []
    for name, desc, price, sample in [
        ("Complete Blood Count (CBC)", "Full blood picture", 20000, "EDTA blood"),
        ("Malaria Rapid Test", "Malaria parasite screening", 8000, "Capillary blood"),
        ("Urinalysis", "Urine composition analysis", 12000, "Urine"),
        ("Fasting Blood Glucose", "Glucose measurement", 10000, "Fluoride blood"),
    ]:
        test, _ = LabTest.objects.update_or_create(
            lab=lab_owner, name=name,
            defaults={"description": desc, "price": price, "sample_type": sample},
        )
        lab_tests.append(test)

    hospital_services = []
    for name, price in [
        ("General OPD Consultation", 30000),
        ("Antenatal Visit", 25000),
        ("Emergency Assessment", 45000),
        ("Minor Surgery", 150000),
        ("Ultrasound", 80000),
    ]:
        service, _ = HospitalService.objects.update_or_create(
            hospital=hospital_owner, name=name, defaults={"price": price}
        )
        hospital_services.append(service)
    for ward_name, labels in [("General", ["G-01", "G-02", "G-03"]), ("Maternity", ["M-01", "M-02"]), ("Emergency", ["ED-01", "ED-02"])]:
        for label in labels:
            Bed.objects.update_or_create(hospital=hospital_owner, ward=ward_name, label=label, defaults={"is_occupied": False})

    # Reusable laboratory panels preserve individual tests and structured results.
    wellness_panel, _ = LabTestPanel.objects.update_or_create(
        lab=lab_owner, code="WELLNESS-BASIC",
        defaults={
            "name": "Basic Wellness Panel",
            "description": "CBC, fasting glucose and renal function screening.",
            "price": 75000,
            "active": True,
        },
    )
    for sequence, test in enumerate(lab_tests[:3], start=1):
        LabTestPanelItem.objects.update_or_create(
            panel=wellness_panel, test=test,
            defaults={"sequence": sequence, "required": True},
        )

    policies = []
    for name, coverage, premium, description in [
        ("SafeHealth Basic", 60, 50000, "Consultations and selected laboratory tests"),
        ("SafeHealth Premium", 85, 120000, "Consultations, diagnostics, pharmacy and admissions"),
    ]:
        policy, _ = InsurancePolicy.objects.update_or_create(
            provider=insurer_owner, name=name,
            defaults={
                "coverage_percent": coverage,
                "premium": premium,
                "description": description,
                "annual_limit": 2500000 if coverage < 80 else 10000000,
                "deductible": 10000 if coverage < 80 else 5000,
                "copay_percent": 10 if coverage < 80 else 5,
                "waiting_period_days": 14 if coverage < 80 else 0,
                "requires_preauthorization": coverage >= 80,
                "network_only": True,
                "active": True,
                "exclusions": "Cosmetic procedures and services without medical necessity.",
            },
        )
        policies.append(policy)
    for policy in policies:
        for service_code, category, pct, limit, preauth in [
            ("CONSULT", "consultation", policy.coverage_percent, 150000, False),
            ("LAB", "laboratory", min(policy.coverage_percent + 5, 100), 500000, False),
            ("IMAGING", "radiology", policy.coverage_percent, 1500000, True),
            ("ADMISSION", "inpatient", policy.coverage_percent, 5000000, True),
            ("PHARMACY", "pharmacy", max(policy.coverage_percent - 10, 0), 1000000, False),
        ]:
            InsuranceBenefitRule.objects.update_or_create(
                policy=policy,
                service_code=service_code,
                service_category=category,
                defaults={
                    "description": f"{category.title()} benefit for {policy.name}",
                    "coverage_percent": pct,
                    "annual_limit": limit,
                    "per_visit_limit": max(limit // 4, 1),
                    "requires_preauthorization": preauth,
                    "active": True,
                },
            )
    coverage, _ = PatientCoverage.objects.update_or_create(
        patient=p1, provider=insurer_owner, policy=policies[1],
        defaults={
            "member_id": "SH-0001026",
            "active": True,
            "effective_from": TODAY - dt.timedelta(days=120),
            "expires_on": TODAY + dt.timedelta(days=245),
            "employer_or_group": "MyDoctor Demonstration Group",
            "verified_at": NOW - dt.timedelta(days=3),
        },
    )

    # Appointments, a front-desk visit and clinical communication.
    tomorrow = TODAY + dt.timedelta(days=1)
    appointment, _ = Appointment.objects.update_or_create(
        patient=p1,
        doctor=dr_sarah,
        date=tomorrow,
        start_time=dt.time(10, 0),
        defaults={
            "end_time": dt.time(10, 30),
            "type": Appointment.Type.OFFLINE,
            "status": Appointment.Status.CONFIRMED,
            "reason": "Recurring headaches and fatigue",
            "notes": "Bring previous medication list.",
            "booked_by": p1,
        },
    )
    AppointmentStatusHistory.objects.get_or_create(
        appointment=appointment,
        from_status=Appointment.Status.PENDING,
        to_status=Appointment.Status.CONFIRMED,
        defaults={"actor": staff_users["receptionist"], "reason": "Demonstration booking confirmed"},
    )
    online_appointment, _ = Appointment.objects.update_or_create(
        patient=dependent,
        doctor=dr_james,
        date=TODAY + dt.timedelta(days=2),
        start_time=dt.time(14, 0),
        defaults={
            "end_time": dt.time(14, 30),
            "type": Appointment.Type.ONLINE,
            "status": Appointment.Status.PENDING,
            "reason": "Paediatric follow-up for dependent",
            "booked_by": p1,
        },
    )
    specialist_referral, _ = Referral.objects.update_or_create(
        patient=p1,
        referring_provider=dr_sarah,
        target_provider=dr_james,
        target_specialty="Internal Medicine",
        defaults={
            "target_facility": hospital_org.legal_name,
            "target_organization": hospital_org,
            "reason": "Persistent headaches requiring specialist medical review",
            "clinical_summary": "Stable observations; recurrent symptoms despite first-line management.",
            "priority": Referral.Priority.URGENT,
            "status": Referral.Status.ACCEPTED,
            "accepted_by": dr_james,
            "accepted_at": NOW - dt.timedelta(hours=2),
        },
    )
    ReferralStatusHistory.objects.get_or_create(
        referral=specialist_referral, to_status=Referral.Status.SENT,
        defaults={"actor": dr_sarah, "from_status": "", "reason": "Referral issued"},
    )
    ReferralStatusHistory.objects.get_or_create(
        referral=specialist_referral, to_status=Referral.Status.ACCEPTED,
        defaults={"actor": dr_james, "from_status": Referral.Status.SENT, "reason": "Referral accepted"},
    )

    visit, _ = PatientVisit.objects.update_or_create(
        appointment=appointment,
        defaults={
            "organization": hospital_org,
            "patient": p1,
            "registered_by": staff_users["receptionist"],
            "assigned_doctor": dr_sarah,
            "assigned_nurse": staff_users["nurse"],
            "queue_number": 12,
            "visit_type": PatientVisit.Type.APPOINTMENT,
            "status": PatientVisit.Status.WAITING_CLINICIAN,
            "priority": PatientVisit.Priority.ROUTINE,
            "reason": appointment.reason,
        },
    )
    TriageRecord.objects.update_or_create(
        visit=visit,
        defaults={
            "nurse": staff_users["nurse"],
            "level": TriageRecord.Level.GREEN,
            "chief_complaint": appointment.reason,
            "temperature_c": Decimal("36.8"),
            "pulse_bpm": 78,
            "respiratory_rate": 18,
            "systolic_bp": 118,
            "diastolic_bp": 76,
            "oxygen_saturation": 98,
            "weight_kg": Decimal("64.50"),
            "pain_score": 3,
            "allergies": "None known",
            "notes": "Stable at triage.",
        },
    )
    NursingNote.objects.get_or_create(
        visit=visit,
        nurse=staff_users["nurse"],
        note_type=NursingNote.Type.ASSESSMENT,
        defaults={"note": "Patient alert, ambulant and awaiting clinician review."},
    )
    conversation, _ = Conversation.objects.get_or_create(patient=p1, doctor=dr_sarah, defaults={"appointment": appointment})
    Message.objects.get_or_create(
        conversation=conversation,
        sender=p1,
        text="Hello Doctor, I have uploaded my medication history and will attend tomorrow.",
    )
    Message.objects.get_or_create(
        conversation=conversation,
        sender=dr_sarah,
        text="Thank you. Please arrive 15 minutes early for triage.",
    )

    # Inpatient, emergency, imaging, theatre and maternity operations.
    general_ward, _ = Ward.objects.update_or_create(
        organization=hospital_org,
        code="GEN",
        defaults={"name": "General Medical Ward", "ward_type": Ward.Type.GENERAL, "floor": "First floor", "nurse_station": "Station A", "active": True},
    )
    maternity_ward, _ = Ward.objects.update_or_create(
        organization=hospital_org,
        code="MAT",
        defaults={"name": "Maternity Ward", "ward_type": Ward.Type.MATERNITY, "floor": "Ground floor", "nurse_station": "Maternity desk", "active": True},
    )
    emergency_ward, _ = Ward.objects.update_or_create(
        organization=hospital_org,
        code="EDO",
        defaults={"name": "Emergency Observation", "ward_type": Ward.Type.EMERGENCY, "floor": "Ground floor", "nurse_station": "ED station", "active": True},
    )
    beds = []
    for ward, labels in [(general_ward, ["G-01", "G-02", "G-03"]), (maternity_ward, ["M-01", "M-02"]), (emergency_ward, ["ED-01", "ED-02"])]:
        for label in labels:
            bed, _ = FacilityBed.objects.update_or_create(
                ward=ward, label=label,
                defaults={"bed_type": "standard", "daily_rate": 35000, "active": True},
            )
            beds.append(bed)
    admission, _ = Admission.objects.get_or_create(
        organization=hospital_org,
        patient=p4,
        ward=general_ward,
        status=Admission.Status.ADMITTED,
        defaults={
            "admitting_clinician": dr_sarah,
            "attending_clinician": dr_sarah,
            "reason": "Observation after acute dehydration",
            "provisional_diagnosis": "Acute gastroenteritis with dehydration",
            "admitted_at": NOW - dt.timedelta(hours=18),
            "expected_discharge_at": NOW + dt.timedelta(days=1),
            "created_by": staff_users["receptionist"],
        },
    )
    active_allocation = BedAllocation.objects.filter(admission=admission, released_at__isnull=True).first()
    if not active_allocation:
        bed = beds[0]
        bed.status = FacilityBed.Status.OCCUPIED
        bed.save(update_fields=["status"])
        BedAllocation.objects.create(admission=admission, bed=bed, assigned_by=staff_users["nurse"])
    WardTask.objects.get_or_create(
        admission=admission,
        title="Record observations every four hours",
        defaults={
            "category": WardTask.Category.OBSERVATION,
            "instructions": "Escalate systolic BP below 90 or oxygen saturation below 94%.",
            "priority": "urgent",
            "assigned_to": staff_users["nurse"],
            "due_at": NOW + dt.timedelta(hours=2),
            "status": WardTask.Status.OPEN,
            "created_by": dr_sarah,
        },
    )
    ClinicalRound.objects.get_or_create(
        admission=admission,
        clinician=dr_sarah,
        assessment="Improving hydration status; haemodynamically stable.",
        defaults={
            "subjective": "Nausea reduced; tolerating oral fluids.",
            "objective": "BP 112/72, pulse 82, temperature 36.9 C.",
            "plan": "Continue fluids, repeat electrolytes and review for discharge tomorrow.",
            "discharge_readiness": "planning",
        },
    )
    imaging_order, _ = ImagingOrder.objects.update_or_create(
        organization=hospital_org,
        patient=p2,
        study_name="Chest radiograph",
        defaults={
            "ordering_clinician": dr_sarah,
            "modality": ImagingOrder.Modality.XRAY,
            "clinical_indication": "Persistent cough and pleuritic pain",
            "provisional_diagnosis": "Lower respiratory infection",
            "priority": "urgent",
            "status": ImagingOrder.Status.REPORTING,
            "scheduled_at": NOW + dt.timedelta(hours=1),
            "performed_at": NOW - dt.timedelta(minutes=30),
            "radiographer": staff_users["radiographer"],
            "radiologist": staff_users["radiologist"],
            "image_reference": "PACS-DEMO-STUDY-1001",
        },
    )
    ImagingReport.objects.update_or_create(
        order=imaging_order,
        defaults={
            "findings": "Mild right basal patchy air-space opacity. No pleural effusion.",
            "impression": "Right basal infective change.",
            "recommendations": "Clinical correlation and follow-up imaging if symptoms persist.",
            "critical": False,
            "status": ImagingReport.Status.PRELIMINARY,
            "created_by": staff_users["radiologist"],
        },
    )
    emergency_case, _ = EmergencyCase.objects.get_or_create(
        organization=hospital_org,
        patient=p2,
        chief_complaint="Severe abdominal pain and vomiting",
        status=EmergencyCase.Status.IN_TREATMENT,
        defaults={
            "arrival_mode": "walk_in",
            "acuity": EmergencyCase.Acuity.EMERGENT,
            "triage_notes": "Pain 8/10, IV access established.",
            "assigned_clinician": staff_users["clinical_officer"],
            "arrival_at": NOW - dt.timedelta(minutes=35),
            "treatment_started_at": NOW - dt.timedelta(minutes=20),
            "created_by": staff_users["receptionist"],
        },
    )
    AmbulanceDispatch.objects.get_or_create(
        organization=hospital_org,
        caller_phone="+256 700 888 111",
        pickup_location="Ntinda, Kampala",
        status=AmbulanceDispatch.Status.EN_ROUTE,
        defaults={
            "patient": p3,
            "caller_name": "Family member",
            "destination": hospital_org.legal_name,
            "priority": "critical",
            "dispatcher": staff_users["ambulance_dispatcher"],
            "paramedic": staff_users["paramedic"],
            "ambulance_identifier": "AMB-UG-021",
            "pickup_coordinates": {"lat": 0.354, "lng": 32.612},
            "destination_coordinates": {"lat": 0.329, "lng": 32.573},
            "clinical_notes": "Suspected respiratory distress; oxygen prepared.",
            "requested_at": NOW - dt.timedelta(minutes=12),
            "dispatched_at": NOW - dt.timedelta(minutes=10),
        },
    )
    surgical_case, _ = SurgicalCase.objects.get_or_create(
        organization=hospital_org,
        patient=p4,
        procedure_name="Laparoscopic appendicectomy",
        status=SurgicalCase.Status.PRE_OP,
        defaults={
            "admission": admission,
            "preoperative_diagnosis": "Acute appendicitis",
            "surgeon": dr_sarah,
            "anaesthetist": staff_users["anaesthetist"],
            "theatre_nurse": staff_users["theatre_nurse"],
            "theatre_name": "Main Theatre 1",
            "urgency": "urgent",
            "consent_obtained": True,
            "scheduled_start": NOW + dt.timedelta(hours=3),
            "scheduled_end": NOW + dt.timedelta(hours=5),
            "created_by": dr_sarah,
        },
    )
    SurgicalChecklist.objects.update_or_create(
        surgical_case=surgical_case,
        defaults={
            "patient_identity_confirmed": True,
            "procedure_confirmed": True,
            "site_marked": True,
            "consent_confirmed": True,
            "allergies_reviewed": True,
            "anaesthesia_safety_check": True,
            "antibiotic_prophylaxis": True,
            "team_introduction_complete": False,
            "instrument_count_complete": False,
            "specimen_labelled": False,
            "recovery_plan_confirmed": True,
            "notes": "Time-out to be completed immediately before incision.",
            "completed_by": staff_users["theatre_nurse"],
        },
    )
    MaternityEpisode.objects.get_or_create(
        organization=hospital_org,
        patient=p3,
        status=MaternityEpisode.Status.ANTENATAL,
        defaults={
            "gravida": 2,
            "para": 1,
            "expected_delivery_date": TODAY + dt.timedelta(days=45),
            "gestational_age_weeks": 33,
            "risk_level": "moderate",
            "risk_notes": "Previous caesarean birth; consultant review planned.",
            "assigned_midwife": staff_users["midwife"],
            "assigned_clinician": dr_sarah,
            "created_by": staff_users["midwife"],
        },
    )

    # Inventory, procurement and stock accountability.
    inventory_specs = [
        ("Paracetamol 500 mg tablets", "MED-PARA-500", "Medicine", 100, False, False, "BATCH-PARA-26", 500, 470, 80, 250),
        ("Amoxicillin 250 mg capsules", "MED-AMOX-250", "Medicine", 50, False, False, "BATCH-AMOX-26", 200, 140, 420, 850),
        ("Insulin 100 IU/ml", "MED-INS-100", "Medicine", 20, True, True, "BATCH-INS-26", 60, 35, 22000, 28000),
        ("Nitrile examination gloves", "SUP-GLOVE-M", "Consumable", 200, False, False, "BATCH-GLV-26", 1000, 760, 180, 300),
    ]
    inventory_items = []
    for name, sku, category, reorder, controlled, cold, batch_no, received, available, cost, sell in inventory_specs:
        item, _ = InventoryItem.objects.update_or_create(
            organization=hospital_org,
            sku=sku,
            defaults={
                "name": name,
                "category": category,
                "unit": "unit",
                "reorder_level": reorder,
                "controlled": controlled,
                "requires_cold_chain": cold,
                "active": True,
            },
        )
        batch, _ = InventoryBatch.objects.update_or_create(
            item=item,
            batch_number=batch_no,
            defaults={
                "expiry_date": TODAY + dt.timedelta(days=240),
                "quantity_received": received,
                "quantity_available": available,
                "unit_cost": cost,
                "selling_price": sell,
                "storage_location": "Main medical store",
                "supplier_name": "MediSource Uganda",
            },
        )
        StockMovement.objects.get_or_create(
            batch=batch,
            movement_type=StockMovement.Type.RECEIPT,
            reference=f"GRN-{batch_no}",
            defaults={
                "quantity": received,
                "balance_after": available,
                "reason": "Initial demonstration goods received note",
                "created_by": staff_users["storekeeper@mydoctor.test"],
            },
        )
        inventory_items.append(item)
    purchase_order, _ = PurchaseOrder.objects.get_or_create(
        organization=hospital_org,
        supplier_name="MediSource Uganda",
        status=PurchaseOrder.Status.SUBMITTED,
        defaults={
            "supplier_contact": "+256 700 222 333",
            "expected_on": TODAY + dt.timedelta(days=4),
            "notes": "Routine replenishment of essential medicines and consumables.",
            "created_by": staff_users["procurement@mydoctor.test"],
        },
    )
    for item, quantity in [(inventory_items[0], 500), (inventory_items[3], 1000)]:
        PurchaseOrderItem.objects.update_or_create(
            purchase_order=purchase_order,
            description=item.name,
            defaults={"inventory_item": item, "quantity": quantity, "unit_cost": 200, "quantity_received": 0},
        )

    # Laboratory processing and released result.
    lab_order, _ = LabOrder.objects.update_or_create(
        patient=p1,
        lab=lab_owner,
        test=lab_tests[0],
        defaults={
            "referring_doctor": dr_sarah,
            "referring_facility": hospital_org.legal_name,
            "clinical_indication": "Fatigue and headache",
            "provisional_diagnosis": "Rule out anaemia",
            "priority": LabOrder.Priority.ROUTINE,
            "specimen_id": "SPM-DEMO-0001",
            "specimen_type": "EDTA blood",
            "collection_notes": "Specimen intact and correctly labelled.",
            "collected_by": staff_users["labtech@mydoctor.test"],
            "collected_at": NOW - dt.timedelta(hours=3),
            "received_at": NOW - dt.timedelta(hours=2, minutes=45),
            "released_at": NOW - dt.timedelta(minutes=30),
            "result_released": True,
            "status": LabOrder.Status.COMPLETED,
            "result_notes": "Verified CBC results.",
        },
    )
    haemoglobin, _ = LabResult.objects.update_or_create(
        order=lab_order,
        code="HB",
        name="Haemoglobin",
        defaults={
            "code_system": "urn:mydoctor:local:lab",
            "value_numeric": Decimal("12.4000"),
            "unit": "g/dL",
            "reference_low": Decimal("12.0000"),
            "reference_high": Decimal("16.0000"),
            "interpretation": LabResult.Interpretation.NORMAL,
            "status": LabResult.Status.FINAL,
            "entered_by": staff_users["labtech@mydoctor.test"],
            "verified_by": staff_users["labtech@mydoctor.test"],
            "verified_at": NOW - dt.timedelta(minutes=45),
            "released_by": staff_users["labtech@mydoctor.test"],
            "released_at": NOW - dt.timedelta(minutes=30),
        },
    )
    critical_order, _ = LabOrder.objects.update_or_create(
        patient=p4,
        lab=lab_owner,
        test=lab_tests[3],
        defaults={
            "referring_doctor": dr_sarah,
            "referring_facility": hospital_org.legal_name,
            "clinical_indication": "Altered level of consciousness",
            "priority": LabOrder.Priority.STAT,
            "specimen_id": "SPM-DEMO-0002",
            "specimen_type": "Fluoride blood",
            "collected_by": staff_users["labtech@mydoctor.test"],
            "collected_at": NOW - dt.timedelta(hours=1),
            "received_at": NOW - dt.timedelta(minutes=50),
            "result_released": True,
            "released_at": NOW - dt.timedelta(minutes=10),
            "status": LabOrder.Status.COMPLETED,
        },
    )
    critical_result, _ = LabResult.objects.update_or_create(
        order=critical_order,
        code="GLU",
        name="Blood glucose",
        defaults={
            "value_numeric": Decimal("2.1000"),
            "unit": "mmol/L",
            "reference_low": Decimal("3.9000"),
            "reference_high": Decimal("6.1000"),
            "interpretation": LabResult.Interpretation.CRITICAL,
            "status": LabResult.Status.FINAL,
            "entered_by": staff_users["labtech@mydoctor.test"],
            "verified_by": staff_users["labtech@mydoctor.test"],
            "verified_at": NOW - dt.timedelta(minutes=15),
            "released_by": staff_users["labtech@mydoctor.test"],
            "released_at": NOW - dt.timedelta(minutes=10),
        },
    )
    CriticalResultAcknowledgement.objects.get_or_create(
        result=critical_result,
        defaults={"acknowledged_by": dr_sarah, "notes": "Hypoglycaemia protocol started."},
    )
    for order, barcode in [(lab_order, "LAB-DEMO-0001"), (critical_order, "LAB-DEMO-0002")]:
        order.specimen_id = barcode
        order.save(update_fields=["specimen_id", "updated_at"])
        for event_type, offset, location in [
            (SpecimenEvent.Type.LABELLED, 190, "Sample collection desk"),
            (SpecimenEvent.Type.COLLECTED, 180, "Phlebotomy room"),
            (SpecimenEvent.Type.RECEIVED, 165, "Accession desk"),
            (SpecimenEvent.Type.PROCESSING, 120, "Main analyser bay"),
        ]:
            SpecimenEvent.objects.get_or_create(
                order=order, event_type=event_type, barcode=barcode,
                defaults={
                    "location": location,
                    "notes": f"Demonstration specimen {event_type} event.",
                    "performed_by": staff_users["labtech@mydoctor.test"],
                    "occurred_at": NOW - dt.timedelta(minutes=offset),
                },
            )

    # Pharmacy sales and prescription work queue.
    prescription, _ = Prescription.objects.update_or_create(
        appointment=appointment,
        doctor=dr_sarah,
        patient=p1,
        defaults={
            "notes": "Take after food and return if symptoms persist.",
            "status": Prescription.Status.PARTIALLY_DISPENSED,
            "signed_at": NOW - dt.timedelta(hours=4),
            "expires_at": NOW + dt.timedelta(days=21),
        },
    )
    paracetamol_item, _ = PrescriptionItem.objects.update_or_create(
        prescription=prescription, medicine_name="Paracetamol 500 mg",
        defaults={
            "generic_name": "Paracetamol", "dosage": "1 tablet",
            "frequency": "Three times daily", "route": "oral",
            "duration": "5 days", "quantity": 15, "dispensed_quantity": 10,
            "instructions": "Take after meals.",
        },
    )
    PrescriptionItem.objects.update_or_create(
        prescription=prescription, medicine_name="Oral Rehydration Salts",
        defaults={
            "generic_name": "ORS", "dosage": "1 sachet in 1 litre",
            "frequency": "After each loose stool", "route": "oral",
            "duration": "3 days", "quantity": 6, "dispensed_quantity": 6,
            "instructions": "Use clean drinking water and discard after 24 hours.",
        },
    )
    pharmacy_order, _ = PharmacyOrder.objects.update_or_create(
        pharmacy=pharmacy_owner, patient=p1, prescription_id=prescription.id,
        defaults={"status": PharmacyOrder.Status.PREPARED},
    )
    dispensing, _ = DispensingRecord.objects.get_or_create(
        pharmacy_order=pharmacy_order,
        pharmacist=staff_users["pharmacist"],
        status=DispensingRecord.Status.PARTIAL,
        defaults={
            "counselling_notes": "Explained dose timing, hydration and red-flag symptoms.",
            "dispensed_at": NOW - dt.timedelta(hours=2),
        },
    )
    DispensingItem.objects.update_or_create(
        record=dispensing, prescription_item_id=paracetamol_item.id, medicine_name=paracetamol_item.medicine_name,
        defaults={
            "prescribed_quantity": paracetamol_item.quantity,
            "dispensed_quantity": 10,
            "batch_number": "PCM-DEMO-2401",
            "expiry_date": TODAY + dt.timedelta(days=300),
            "label_instructions": "Take one tablet three times daily after meals.",
        },
    )
    sale_order, _ = Order.objects.get_or_create(
        patient=p2,
        pharmacy=pharmacy_owner,
        status=Order.Status.CONFIRMED,
        defaults={"total": medicines[0].price * 2, "delivery": True, "address": "Ntinda, Kampala"},
    )
    OrderItem.objects.update_or_create(
        order=sale_order,
        name=medicines[0].name,
        defaults={"medicine": medicines[0], "price": medicines[0].price, "qty": 2},
    )

    # Billing, receipt, cashier shift, insurance claim.
    invoice, _ = Invoice.objects.update_or_create(
        patient=p1,
        organization=hospital_org,
        appointment=appointment,
        defaults={
            "issued_by": staff_users["cashier"],
            "amount": 0,
            "discount_amount": 5000,
            "tax_amount": 0,
            "status": Invoice.Status.PENDING,
            "gateway": Invoice.Gateway.CASH,
            "notes": "Consultation and laboratory services.",
            "due_at": NOW + dt.timedelta(days=7),
        },
    )
    for code, description, qty, price, service_type in [
        ("CONSULT", "General medical consultation", Decimal("1"), 30000, "consultation"),
        ("LAB-CBC", "Complete blood count", Decimal("1"), 20000, "laboratory"),
    ]:
        InvoiceItem.objects.update_or_create(
            invoice=invoice,
            code=code,
            defaults={"description": description, "quantity": qty, "unit_price": price, "service_type": service_type},
        )
    invoice.recalculate_amount()
    if not invoice.payments.filter(status=PaymentTransaction.Status.CONFIRMED).exists():
        confirm_invoice_payment(
            invoice=invoice,
            amount=invoice.amount,
            method=PaymentTransaction.Method.CASH,
            received_by=staff_users["cashier"],
            reference="CASH-DEMO-0001",
            notes="Demonstration payment received at main cashier.",
        )
    CashierShift.objects.update_or_create(
        cashier=staff_users["cashier"],
        organization=hospital_org,
        status=CashierShift.Status.OPEN,
        defaults={"opening_float": 100000, "expected_cash": invoice.amount, "notes": "Demonstration morning shift"},
    )
    preauthorization, _ = InsurancePreauthorization.objects.update_or_create(
        patient=p1,
        provider=insurer_owner,
        policy=policies[1],
        coverage=coverage,
        service_code="IMAGING",
        service_name="Diagnostic imaging package",
        defaults={
            "requesting_facility": hospital_owner,
            "clinical_indication": "Persistent symptoms requiring radiology evaluation.",
            "diagnosis_code": "R51.9",
            "requested_amount": 180000,
            "approved_amount": 150000,
            "status": InsurancePreauthorization.Status.APPROVED,
            "decision_reason": "Approved within policy imaging benefit.",
            "reviewed_by": staff_users["insurance_officer"],
            "reviewed_at": NOW - dt.timedelta(days=2),
            "valid_until": TODAY + dt.timedelta(days=28),
        },
    )
    InsuranceEligibilityCheck.objects.get_or_create(
        coverage=coverage,
        service_code="CONSULT",
        checked_at__date=TODAY,
        defaults={
            "patient": p1,
            "provider": insurer_owner,
            "member_id": coverage.member_id,
            "service_category": "consultation",
            "estimated_amount": invoice.amount,
            "result": InsuranceEligibilityCheck.Result.ELIGIBLE,
            "coverage_percent": policies[1].coverage_percent,
            "covered_amount": int(invoice.amount * Decimal("0.80")),
            "patient_responsibility": int(invoice.amount * Decimal("0.20")),
            "requires_preauthorization": False,
            "reason": "Active demonstration coverage.",
            "response_snapshot": {"source": "seed", "policy": policies[1].name},
            "requested_by": staff_users["cashier"],
        },
    )
    claim, _ = InsuranceClaim.objects.update_or_create(
        patient=p1,
        provider=insurer_owner,
        policy=policies[1],
        invoice_id=invoice.id,
        defaults={
            "coverage": coverage,
            "preauthorization": preauthorization,
            "status": InsuranceClaim.Status.PARTIALLY_APPROVED,
            "amount": invoice.amount,
            "approved_amount": int(invoice.amount * Decimal("0.80")),
            "patient_responsibility": int(invoice.amount * Decimal("0.20")),
            "diagnosis_code": "R51.9",
            "clinical_summary": "Outpatient consultation and diagnostic workup.",
            "decision_reason": "Approved according to consultation and laboratory benefits.",
            "requested_by": staff_users["cashier"],
            "reviewed_by": staff_users["insurance_officer"],
            "submitted_at": NOW - dt.timedelta(days=2),
            "reviewed_at": NOW - dt.timedelta(days=1),
        },
    )
    for item in invoice.items.all():
        approved = int(item.line_total * Decimal("0.80"))
        InsuranceClaimItem.objects.update_or_create(
            claim=claim,
            invoice_item_id=item.id,
            defaults={
                "service_code": item.code,
                "description": item.description,
                "quantity": max(int(item.quantity), 1),
                "unit_price": item.unit_price,
                "requested_amount": item.line_total,
                "approved_amount": approved,
                "status": InsuranceClaimItem.Status.PARTIALLY_APPROVED,
                "reason": "Member copay applies.",
            },
        )
    InsuranceRemittance.objects.update_or_create(
        claim=claim,
        remittance_number="REM-DEMO-0001",
        defaults={
            "provider": insurer_owner,
            "paid_amount": max(claim.approved_amount // 2, 1),
            "payment_reference": "BANK-DEMO-INS-1001",
            "paid_on": TODAY,
            "notes": "Partial demonstration remittance.",
            "created_by": staff_users["insurance_officer"],
        },
    )

    # Subscriptions, support, announcements, schedules, compliance and privacy.
    plans = {}
    for code, name, audience, price, cycle, features, limits in [
        ("patient-plus", "Patient Plus", SubscriptionPlan.Audience.PATIENT, 15000, "monthly", ["Priority support", "Family health timeline", "Discounted consultations"], {"dependents": 5}),
        ("professional-pro", "Professional Pro", SubscriptionPlan.Audience.PROFESSIONAL, 45000, "monthly", ["Online availability", "E-prescriptions", "Earnings analytics"], {"locations": 3}),
        ("organization-enterprise", "Organization Enterprise", SubscriptionPlan.Audience.ORGANIZATION, 750000, "monthly", ["Unlimited staff", "Advanced operations", "Audit and analytics"], {"branches": 20}),
    ]:
        plan, _ = SubscriptionPlan.objects.update_or_create(
            code=code,
            defaults={"name": name, "audience": audience, "price": price, "currency": "UGX", "billing_cycle": cycle, "features": features, "limits": limits, "active": True},
        )
        plans[code] = plan
    AccountSubscription.objects.update_or_create(
        user=p1,
        plan=plans["patient-plus"],
        defaults={"status": AccountSubscription.Status.ACTIVE, "starts_at": NOW - dt.timedelta(days=5), "ends_at": NOW + dt.timedelta(days=25), "auto_renew": True, "provider_reference": "SUB-DEMO-PATIENT"},
    )
    AccountSubscription.objects.update_or_create(
        user=dr_sarah,
        plan=plans["professional-pro"],
        defaults={"status": AccountSubscription.Status.ACTIVE, "starts_at": NOW - dt.timedelta(days=10), "ends_at": NOW + dt.timedelta(days=20), "auto_renew": True, "provider_reference": "SUB-DEMO-DOCTOR"},
    )
    AccountSubscription.objects.update_or_create(
        organization=hospital_org,
        plan=plans["organization-enterprise"],
        defaults={"status": AccountSubscription.Status.ACTIVE, "starts_at": NOW - dt.timedelta(days=15), "ends_at": NOW + dt.timedelta(days=15), "auto_renew": True, "provider_reference": "SUB-DEMO-ORG"},
    )
    SupportTicket.objects.update_or_create(
        requester=p1,
        subject="Unable to update emergency contact",
        defaults={
            "organization": hospital_org,
            "category": "account",
            "priority": "normal",
            "description": "The patient needs assistance updating an emergency contact.",
            "status": SupportTicket.Status.IN_PROGRESS,
            "assigned_to": staff_users["it_support"],
        },
    )
    Announcement.objects.update_or_create(
        organization=hospital_org,
        title="Weekend outpatient clinic hours",
        defaults={
            "audience": Announcement.Audience.ALL,
            "body": "The outpatient department will operate from 8:00 AM to 2:00 PM this weekend.",
            "severity": "info",
            "starts_at": NOW - dt.timedelta(hours=1),
            "ends_at": NOW + dt.timedelta(days=4),
            "active": True,
            "created_by": hospital_owner,
        },
    )
    for index, (role, dept_code, start_hour, shift_type) in enumerate([
        ("nurse", "NUR", 7, "day"),
        ("midwife", "MAT", 7, "day"),
        ("receptionist", "OPD", 8, "day"),
        ("cashier", "FIN", 8, "day"),
        ("lab_technician", "LAB", 8, "day"),
        ("theatre_nurse", "THR", 13, "evening"),
        ("paramedic", "ED", 19, "night"),
    ]):
        user = staff_users[role]
        starts = timezone.make_aware(dt.datetime.combine(TODAY + dt.timedelta(days=index % 2), dt.time(start_hour, 0)))
        StaffShift.objects.update_or_create(
            organization=hospital_org if role != "lab_technician" else lab_org,
            staff=user,
            starts_at=starts,
            defaults={
                "department": departments[((hospital_org if role != "lab_technician" else lab_org).id, dept_code)],
                "shift_type": shift_type,
                "ends_at": starts + dt.timedelta(hours=12 if shift_type == "night" else 8),
                "status": StaffShift.Status.CONFIRMED,
                "location": "Main Branch",
                "notes": "Demonstration duty roster entry.",
                "created_by": hospital_owner if role != "lab_technician" else lab_owner,
            },
        )
    LeaveRequest.objects.update_or_create(
        organization=hospital_org,
        staff=staff_users["nurse"],
        starts_on=TODAY + dt.timedelta(days=20),
        ends_on=TODAY + dt.timedelta(days=24),
        defaults={"leave_type": "annual", "reason": "Planned annual leave", "status": LeaveRequest.Status.PENDING},
    )
    QualityIncident.objects.update_or_create(
        organization=hospital_org,
        title="Delayed morning medication round",
        defaults={
            "patient": p4,
            "category": "medication",
            "severity": "moderate",
            "description": "A scheduled oral medicine was administered 35 minutes late during a busy handover.",
            "immediate_actions": "Medicine administered; patient assessed with no harm identified.",
            "status": QualityIncident.Status.INVESTIGATING,
            "occurred_at": NOW - dt.timedelta(days=1),
            "reported_by": staff_users["nurse"],
            "assigned_to": staff_users["quality_officer"],
        },
    )
    PrivacyRequest.objects.update_or_create(
        requester=p2,
        request_type=PrivacyRequest.Type.EXPORT,
        defaults={
            "organization": hospital_org,
            "requester_email": p2.email,
            "details": "Please provide a machine-readable export of my consultation and laboratory records.",
            "status": PrivacyRequest.Status.VERIFYING,
            "identity_verified": False,
            "assigned_to": staff_users["compliance_officer"],
            "due_at": NOW + dt.timedelta(days=14),
        },
    )

    # Patient-facing notifications and hospital booking.
    HospitalBooking.objects.update_or_create(
        patient=p3,
        hospital=hospital_owner,
        service=hospital_services[1],
        date=TODAY + dt.timedelta(days=5),
        defaults={"status": HospitalBooking.Status.CONFIRMED},
    )
    Notification.objects.get_or_create(
        user=p1,
        title="Welcome to your complete MyDoctor demo",
        defaults={
            "body": "Your dashboard contains a confirmed appointment, paid invoice, receipt, released laboratory result and subscription.",
            "kind": "general",
            "priority": Notification.Priority.NORMAL,
            "action_url": "/patient",
            "channels": ["in_app"],
            "metadata": {"seed": True},
        },
    )
    Notification.objects.get_or_create(
        user=staff_users["quality_officer"],
        title="Quality incident requires review",
        defaults={
            "body": "A medication-timing incident has been assigned for investigation.",
            "kind": "operations",
            "priority": Notification.Priority.HIGH,
            "action_url": "/facility/quality",
            "channels": ["in_app", "email"],
            "metadata": {"seed": True},
        },
    )

    missing_demo_accounts = [
        f"{role} ({email})"
        for role, email in DEMO_ROLE_ACCOUNTS.items()
        if not User.objects.filter(email=email, role=role, is_active=True).exists()
    ]
    if missing_demo_accounts:
        raise RuntimeError("Seed did not create active accounts for: " + ", ".join(missing_demo_accounts))

    log(f"created/updated {User.objects.filter(email__endswith='@mydoctor.test').count()} demo users")
    log("demo workflows include appointments, triage, admission, emergency, ambulance, imaging, theatre, maternity, lab, pharmacy, billing, insurance, stock, subscriptions, workforce and compliance")
    log(f"standard password: {DEMO_PASSWORD}; admin password: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    run()
    from enterprise.demo_seed import seed_enterprise_demo
    enterprise_counts = seed_enterprise_demo()
    print(f"Enterprise seed complete: {enterprise_counts}")
    print("Seed complete. See docs/DEMO_DATA.md for accounts and walkthroughs.")
