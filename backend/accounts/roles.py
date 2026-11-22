"""Role groups used by API permissions and workflow services.

The platform keeps a primary portal role on ``User`` for backwards
compatibility, while organization membership and department scope live in the
workforce application.  Use these groups instead of scattering role strings
through new code.
"""

PATIENT_ROLES = {"patient"}
DOCTOR_ROLES = {"doctor"}
NURSING_ROLES = {"nurse"}
CLINICAL_ROLES = {"doctor", "nurse"}
FRONT_DESK_ROLES = {"receptionist", "records_officer"}
BILLING_ROLES = {"cashier"}
PHARMACY_STAFF_ROLES = {"pharmacist"}
LAB_STAFF_ROLES = {"lab_technician"}
FACILITY_MANAGEMENT_ROLES = {"facility_manager"}
ORGANIZATION_ACCOUNT_ROLES = {"pharmacy", "lab", "hospital", "insurance"}
PLATFORM_ADMIN_ROLES = {"admin"}

PROFESSIONAL_ROLES = DOCTOR_ROLES | NURSING_ROLES | PHARMACY_STAFF_ROLES | LAB_STAFF_ROLES
STAFF_ROLES = (
    NURSING_ROLES
    | FRONT_DESK_ROLES
    | BILLING_ROLES
    | PHARMACY_STAFF_ROLES
    | LAB_STAFF_ROLES
    | FACILITY_MANAGEMENT_ROLES
    | {"insurance_officer", "storekeeper"}
)
FACILITY_OPERATIONS_ROLES = STAFF_ROLES | DOCTOR_ROLES | ORGANIZATION_ACCOUNT_ROLES

APPOINTMENT_VIEW_ROLES = PATIENT_ROLES | DOCTOR_ROLES | NURSING_ROLES | FRONT_DESK_ROLES | FACILITY_MANAGEMENT_ROLES
CARE_TEAM_ROLES = CLINICAL_ROLES | LAB_STAFF_ROLES | PHARMACY_STAFF_ROLES
NOTIFICATION_ROLES = (
    PATIENT_ROLES
    | DOCTOR_ROLES
    | STAFF_ROLES
    | ORGANIZATION_ACCOUNT_ROLES
    | PLATFORM_ADMIN_ROLES
)

PUBLIC_REGISTRATION_ROLES = {"patient", "doctor", "pharmacy", "lab", "hospital", "insurance"}

ROLE_PORTAL_PATHS = {
    "patient": "/patient",
    "doctor": "/doctor",
    "nurse": "/nurse",
    "receptionist": "/reception",
    "records_officer": "/reception",
    "cashier": "/cashier",
    "pharmacist": "/pharmacist",
    "storekeeper": "/pharmacist",
    "lab_technician": "/lab-staff",
    "facility_manager": "/facility",
    "insurance_officer": "/insurance",
    "pharmacy": "/pharmacy",
    "lab": "/lab",
    "hospital": "/facility",
    "insurance": "/insurance",
    "admin": "/admin",
}


def portal_path_for_role(role):
    """Return the React portal route for a primary account role."""
    return ROLE_PORTAL_PATHS.get(role, "/")

