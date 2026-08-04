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
| Platform admin | `admin@mydoctor.test` |
| Patient / parent | `patient1@mydoctor.test` |
| Doctor | `dr.nakato@mydoctor.test` |
| Second doctor | `dr.kato@mydoctor.test` |
| Medical director | `medical.director@mydoctor.test` |
| Clinical officer | `clinical.officer@mydoctor.test` |
| Dentist | `dentist@mydoctor.test` |
| Nurse | `nurse@mydoctor.test` |
| Midwife | `midwife@mydoctor.test` |
| Theatre nurse | `theatre.nurse@mydoctor.test` |
| Anaesthetist | `anaesthetist@mydoctor.test` |
| Receptionist | `reception@mydoctor.test` |
| Records officer | `records@mydoctor.test` |
| Cashier | `cashier@mydoctor.test` |
| Accountant | `accountant@mydoctor.test` |
| Facility manager | `manager@mydoctor.test` |
| Finance manager | `finance.manager@mydoctor.test` |
| Pharmacist | `pharmacist.staff@mydoctor.test` |
| Storekeeper | `storekeeper@mydoctor.test` |
| Procurement officer | `procurement@mydoctor.test` |
| Laboratory professional | `labtech@mydoctor.test` |
| Radiologist | `radiologist@mydoctor.test` |
| Radiographer | `radiographer@mydoctor.test` |
| Physiotherapist | `physio@mydoctor.test` |
| Nutritionist / dietitian | `nutrition@mydoctor.test` |
| Psychologist / counsellor | `psychology@mydoctor.test` |
| Paramedic | `paramedic@mydoctor.test` |
| Ambulance dispatcher | `dispatcher@mydoctor.test` |
| Quality officer | `quality@mydoctor.test` |
| Compliance officer | `compliance@mydoctor.test` |
| HR officer | `hr@mydoctor.test` |
| IT support | `it@mydoctor.test` |
| Insurance officer | `insurance.officer@mydoctor.test` |
| Claims reviewer | `claims@mydoctor.test` |
| Hospital organization | `hospital@mydoctor.test` |
| Pharmacy organization | `pharmacy@mydoctor.test` |
| Laboratory organization | `lab@mydoctor.test` |
| Insurance organization | `insurance@mydoctor.test` |

## Automated seed verification

After seeding, verify complete coverage with:

```bash
python manage.py verify_demo_data
```

The command checks all 37 role identities, active role contexts, all 81 enterprise workflow record types and the required organization categories.

Never load demonstration data into a database containing real patient information.
