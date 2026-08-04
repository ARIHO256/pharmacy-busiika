"""Canonical role groups, portal routing and facility permission defaults."""

PATIENT_ROLES = {"patient"}
DOCTOR_ROLES = {"doctor", "clinical_officer", "dentist", "medical_director"}
NURSING_ROLES = {"nurse", "midwife", "theatre_nurse"}
DIAGNOSTIC_ROLES = {"lab_technician", "radiologist", "radiographer"}
ALLIED_HEALTH_ROLES = {"physiotherapist", "nutritionist", "psychologist"}
BOOKABLE_PROVIDER_ROLES = DOCTOR_ROLES | ALLIED_HEALTH_ROLES
THEATRE_ROLES = {"anaesthetist", "theatre_nurse"}
CLINICAL_ROLES = DOCTOR_ROLES | NURSING_ROLES | DIAGNOSTIC_ROLES | ALLIED_HEALTH_ROLES | {"anaesthetist", "paramedic"}
FRONT_DESK_ROLES = {"receptionist", "records_officer"}
BILLING_ROLES = {"cashier", "accountant", "finance_manager"}
PHARMACY_STAFF_ROLES = {"pharmacist"}
LAB_STAFF_ROLES = {"lab_technician"}
RADIOLOGY_STAFF_ROLES = {"radiologist", "radiographer"}
FACILITY_MANAGEMENT_ROLES = {
    "facility_manager", "medical_director", "quality_officer", "compliance_officer",
    "hr_officer", "it_support", "finance_manager",
}
SUPPLY_CHAIN_ROLES = {"storekeeper", "procurement_officer"}
INSURANCE_STAFF_ROLES = {"insurance_officer", "claims_reviewer"}
EMERGENCY_ROLES = {"ambulance_dispatcher", "paramedic"}
ORGANIZATION_ACCOUNT_ROLES = {"pharmacy", "lab", "hospital", "insurance"}
PLATFORM_ADMIN_ROLES = {"admin"}

PROFESSIONAL_ROLES = CLINICAL_ROLES | PHARMACY_STAFF_ROLES
STAFF_ROLES = (
    CLINICAL_ROLES | FRONT_DESK_ROLES | BILLING_ROLES | PHARMACY_STAFF_ROLES |
    FACILITY_MANAGEMENT_ROLES | SUPPLY_CHAIN_ROLES | INSURANCE_STAFF_ROLES | EMERGENCY_ROLES
)
FACILITY_OPERATIONS_ROLES = STAFF_ROLES | ORGANIZATION_ACCOUNT_ROLES
APPOINTMENT_VIEW_ROLES = PATIENT_ROLES | DOCTOR_ROLES | NURSING_ROLES | FRONT_DESK_ROLES | FACILITY_MANAGEMENT_ROLES
CARE_TEAM_ROLES = CLINICAL_ROLES | PHARMACY_STAFF_ROLES
NOTIFICATION_ROLES = PATIENT_ROLES | STAFF_ROLES | ORGANIZATION_ACCOUNT_ROLES | PLATFORM_ADMIN_ROLES

PUBLIC_REGISTRATION_ROLES = {"patient", "doctor", "pharmacy", "lab", "hospital", "insurance"}

ROLE_PORTAL_PATHS = {
    "patient": "/patient",
    "doctor": "/doctor", "clinical_officer": "/clinical-officer", "dentist": "/dentist", "medical_director": "/medical-director",
    "nurse": "/nurse", "midwife": "/midwife", "theatre_nurse": "/theatre-nurse",
    "receptionist": "/reception", "records_officer": "/records",
    "cashier": "/cashier", "accountant": "/accounting", "finance_manager": "/finance",
    "pharmacist": "/pharmacist", "storekeeper": "/storekeeping", "procurement_officer": "/procurement",
    "lab_technician": "/lab-staff",
    "radiologist": "/radiology", "radiographer": "/radiography",
    "physiotherapist": "/physiotherapy", "nutritionist": "/nutrition", "psychologist": "/psychology",
    "anaesthetist": "/anaesthesia", "paramedic": "/paramedic", "ambulance_dispatcher": "/dispatch",
    "facility_manager": "/facility", "quality_officer": "/quality", "compliance_officer": "/compliance",
    "hr_officer": "/hr", "it_support": "/it-operations",
    "insurance_officer": "/insurance-officer", "claims_reviewer": "/claims-review",
    "pharmacy": "/pharmacy", "lab": "/lab", "hospital": "/hospital", "insurance": "/insurance",
    "admin": "/admin",
}


def portal_path_for_role(role):
    return ROLE_PORTAL_PATHS.get(role, "/")
