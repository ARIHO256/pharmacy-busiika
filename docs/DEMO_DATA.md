# Demonstration Data

Run:

```bash
cd backend
python manage.py migrate
python seed.py
```

The seed is idempotent and may be run again in a clean development database. It creates patients, a managed child profile, verified professionals, multiple facility staff roles, organizations, credentials, departments, permissions, appointments, triage, conversations, referrals, admissions, emergency cases, ambulance dispatch, theatre cases, maternity care, imaging, laboratory panels and specimens, prescriptions and dispensing, stock, procurement, invoices, payments, insurance, subscriptions, support, announcements, shifts, leave, quality incidents, privacy requests and notifications.

## Passwords

- Platform admin: `AdminPass!2026`
- All login-capable demonstration users: `DemoPass!2026`
- The child dependent has an unusable password and is managed through the parent account.

## Primary accounts

| Workspace | Email |
|---|---|
| Platform admin | `admin@healthpilot.test` |
| Patient / parent | `patient1@healthpilot.test` |
| Doctor | `dr.nakato@healthpilot.test` |
| Second doctor | `dr.kato@healthpilot.test` |
| Medical director | `medical.director@healthpilot.test` |
| Clinical officer | `clinical.officer@healthpilot.test` |
| Dentist | `dentist@healthpilot.test` |
| Nurse | `nurse@healthpilot.test` |
| Midwife | `midwife@healthpilot.test` |
| Theatre nurse | `theatre.nurse@healthpilot.test` |
| Anaesthetist | `anaesthetist@healthpilot.test` |
| Receptionist | `reception@healthpilot.test` |
| Records officer | `records@healthpilot.test` |
| Cashier | `cashier@healthpilot.test` |
| Accountant | `accountant@healthpilot.test` |
| Facility manager | `manager@healthpilot.test` |
| Finance manager | `finance.manager@healthpilot.test` |
| Pharmacist | `pharmacist.staff@healthpilot.test` |
| Storekeeper | `storekeeper@healthpilot.test` |
| Procurement officer | `procurement@healthpilot.test` |
| Laboratory professional | `labtech@healthpilot.test` |
| Radiologist | `radiologist@healthpilot.test` |
| Radiographer | `radiographer@healthpilot.test` |
| Physiotherapist | `physio@healthpilot.test` |
| Nutritionist / dietitian | `nutrition@healthpilot.test` |
| Psychologist / counsellor | `psychology@healthpilot.test` |
| Paramedic | `paramedic@healthpilot.test` |
| Ambulance dispatcher | `dispatcher@healthpilot.test` |
| Quality officer | `quality@healthpilot.test` |
| Compliance officer | `compliance@healthpilot.test` |
| HR officer | `hr@healthpilot.test` |
| IT support | `it@healthpilot.test` |
| Insurance officer | `insurance.officer@healthpilot.test` |
| Claims reviewer | `claims@healthpilot.test` |
| Hospital organization | `hospital@healthpilot.test` |
| Pharmacy organization | `pharmacy@healthpilot.test` |
| Laboratory organization | `lab@healthpilot.test` |
| Insurance organization | `insurance@healthpilot.test` |

## Automated seed verification

After seeding, verify complete coverage with:

```bash
python manage.py verify_demo_data
```

The command checks all 37 role identities, active role contexts, all 81 enterprise workflow record types and the required organization categories.

Never load demonstration data into a database containing real patient information.
