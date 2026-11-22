# MyDoctor HealthOS

MyDoctor is a multi-role telehealth and connected-care platform built with **Django REST Framework** and **React + Vite**. This enhanced edition keeps the original appointments, chat, prescriptions, pharmacy, laboratory, hospital, insurance, payment and administration flows, while adding the safety and governance foundations required for a serious health platform.

> This repository is a strong engineering foundation, not a claim of regulatory certification or a complete hospital information system. The implementation-status document clearly separates working code from planned platform capabilities.

## What is now implemented

- One role-aware registration flow for patients, doctors and healthcare organizations
- Mandatory doctor and organization licence evidence with pending-verification gating
- Invitation-only facility workforce with organization and department scope
- Dedicated nurse, reception, cashier, pharmacist, laboratory-staff and facility-manager workspaces
- Triage, nursing notes and medication-administration workflows
- Walk-in registration, check-in and queue management
- Itemized invoices, partial payments, cashier shifts and printable receipts
- Multi-channel notification records, preferences and delivery tracking
- Protected, audited licence-document endpoints
- Expanded laboratory referral, specimen, validation and result-release workflow
- Longitudinal patient summary and timeline
- Structured allergies, conditions, medications and observations
- Versioned clinical encounters with finalisation and amendment history
- Referrals and care plans
- Executable consent and revocation
- Time-bound emergency break-glass access with compliance review
- Append-only governance audit events
- Provider/facility registry, practitioner credentials and practitioner roles
- Appointment status history, validated transitions and slot-conflict protection
- Care relationships created from appointments
- Structured laboratory results and critical-result acknowledgement
- Safer electronic prescriptions with signing/status/version fields
- Immutable double-entry accounting foundation
- Transactional event outbox
- Draft FHIR R4-aligned patient-summary export
- Terminology catalogue foundation
- Request correlation IDs and liveness/readiness probes
- Versioned `/api/v1/` route alias while preserving `/api/`
- Expanded patient, doctor and administrator interfaces

## Architecture at a glance

```text
React/Vite role portals
        │
Django REST API + JWT
        │
┌─────────────────────────────────────────────────────────┐
│ Care delivery: appointments, consultations, referrals  │
│ Clinical: encounters, allergies, conditions, medicines │
│ Connected services: pharmacy, lab, hospital, insurance │
│ Trust: consent, break-glass, audit, registry            │
│ Finance: invoices, ledger, earnings, payouts            │
│ Integration: FHIR draft, terminology, event outbox      │
└─────────────────────────────────────────────────────────┘
        │
PostgreSQL in production / SQLite for local demo
Private object storage in production
```

Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md) before adding new modules.

## Operational workflow expansion

The operational extension adds admission/transfer/discharge, scheduled medication
administration, theatre booking, batch stock and recall, insurance benefit and
preauthorization assessment, reversible patient identity links, receiving referrals,
imaging orders, encrypted offline capture/review, private scanned documents,
WebSocket chat and governed research/administrative-draft workflows.

Approved new pages are available under facility/doctor/nurse/lab-staff operations,
pharmacy/pharmacist stock control, insurance benefits and administrator operations.
Existing portal presentation is preserved. Payments were excluded from this work.

See [docs/OPERATIONS_IMPLEMENTATION.md](docs/OPERATIONS_IMPLEMENTATION.md) for API
contracts, deployment commands, validation and explicit limits. Provider adapters
need real services and credentials; licensed clinical content, diagnostic image
viewing, full research warehousing and clinical/regulatory validation are not
implied by adding the application workflows.

## Public landing page

The root route (`/`) now provides a responsive, healthcare-focused marketing website inspired by the supplied premium marketplace reference. It includes:

- a dark connected-health hero with original local artwork;
- patient and provider calls to action;
- floating appointment, consultation, record and privacy cards;
- healthcare service, care journey, network and provider sections;
- mobile navigation and accessible interaction states;
- no external image dependency for the main hero.

Authenticated users can enter their role dashboard from `/dashboard` or the landing-page dashboard button.

## Roles and portals

| Role | Portal | Main capabilities |
|---|---|---|
| Patient | `/patient` | discovery, bookings, consultation, records, prescriptions, labs, billing and receipts |
| Doctor | `/doctor` | verification, availability, appointments, clinical records, laboratory referrals, prescriptions and earnings |
| Nurse / Midwife | `/nurse` | triage, vitals, nursing documentation and medication administration |
| Reception / Records | `/reception` | patient search, walk-in registration, check-in and queue management |
| Cashier / Billing | `/cashier` | itemized invoices, partial payments, printable receipts and cashier shifts |
| Pharmacist / Storekeeper | `/pharmacist` | medicines, prescription fulfilment, orders, inventory and suppliers |
| Laboratory professional | `/lab-staff` | specimen workflow, structured results, validation and release |
| Facility manager | `/facility` | departments, staff invitations, memberships, operations and billing oversight |
| Pharmacy organization | `/pharmacy` | organization inventory, commerce and prescription orders |
| Laboratory organization | `/lab` | test catalogue and laboratory operations |
| Clinic / Hospital organization | `/facility` | shared bookings, patient flow, billing and staff administration, with inpatient tools for hospitals |
| Insurance organization / officer | `/insurance` | plans, coverage and claims |
| Platform administrator | `/admin` | users, verification, protected evidence, appointments, finance, compliance and audit |

See [docs/ROLE_WORKFLOWS.md](docs/ROLE_WORKFLOWS.md) for page-by-page responsibilities and end-to-end care workflows. The direct client-to-implementation mapping is in [docs/CLIENT_REQUIREMENTS_IMPLEMENTATION.md](docs/CLIENT_REQUIREMENTS_IMPLEMENTATION.md). A concise implementation report for this enhancement is available at [docs/WORKFORCE_BILLING_ENHANCEMENT_REPORT.md](docs/WORKFORCE_BILLING_ENHANCEMENT_REPORT.md).

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python seed.py
python manage.py runserver
```

The backend is configured to start at `http://localhost:4000` when no explicit port is supplied.

Health probes:

```text
GET http://localhost:4000/healthz
GET http://localhost:4000/readyz
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open `http://localhost:3000`. The public landing page is available at `/`, while authentication and role portals remain available through the same React application.

After installing both dependency sets, you may also start both servers from the project root with:

```bash
./start-dev.sh
```


### Clinic and hospital workspace

The main frontend at `http://localhost:3000` is MyDoctor Facility. Public
registration creates a patient account. A clinic or hospital owner can apply
through **Register a clinic or hospital** and invite their team from **Staff &
Access** once verified. Both organization types use `/facility`. Admissions,
wards, beds and theatre are available for hospitals. Existing `/hospital`
bookmarks redirect to the corresponding Facility page.

### Standalone Pharmacy frontend

Start Django as above, then run `npm run dev:pharmacy` from `frontend` and open
`http://localhost:3001`. Pharmacy owners register here, and pharmacists and
storekeepers sign in with their existing MyDoctor accounts or accept a staff
invitation. The full MyDoctor frontend still runs on port 3000.

Run `npm run build:pharmacy` from `frontend` to build the separately deployable
app into `frontend/dist-pharmacy`. Serve that directory from the Pharmacy
hostname, serve `index.html` for client-side routes, and forward `/api/` and
`/media/` to the shared Django service. Set `VITE_PLATFORM_URL` at build time
to give accounts from other workspaces a link to the full MyDoctor frontend.

For the first branch, use **Staff & Access** to invite individual staff accounts.
Create medicines in **Medicine Inventory**, then enter physical quantities
under **Batch Stock & Safety → Add batch** with the batch number and expiry.
Open **Cash Shifts** with the starting float, complete a sample OTC transaction
in **New Sale**, and print its receipt on the branch printer. At close, record
the counted cash in **Cash Shifts** and use **Stocktake** for physical batch
reconciliation. Review paid sales under **Orders & Receipts**.

### Notification delivery worker

For development, process pending email/SMS/push delivery records with:

```bash
cd backend
python manage.py send_appointment_reminders --hours 24
python manage.py notify_expiring_credentials
python manage.py dispatch_notifications --limit 200 --max-attempts 3
```

Connect these commands to Celery, RQ, a systemd timer or a managed queue before production use. Email uses the configured Django email backend; SMS and push require provider adapters.

## Demo accounts

After `python seed.py`:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@mydoctor.test` | `admin12345` |
| Patient | `patient1@mydoctor.test` | `pass123456` |
| Doctor | `dr.nakato@mydoctor.test` | `pass123456` |
| Nurse | `nurse@mydoctor.test` | `pass123456` |
| Receptionist | `reception@mydoctor.test` | `pass123456` |
| Records officer | `records@mydoctor.test` | `pass123456` |
| Cashier | `cashier@mydoctor.test` | `pass123456` |
| Facility manager | `manager@mydoctor.test` | `pass123456` |
| Pharmacist | `pharmacist.staff@mydoctor.test` | `pass123456` |
| Storekeeper | `storekeeper@mydoctor.test` | `pass123456` |
| Laboratory professional | `labtech@mydoctor.test` | `pass123456` |
| Pharmacy organization | `pharmacy@mydoctor.test` | `pass123456` |
| Laboratory organization | `lab@mydoctor.test` | `pass123456` |
| Hospital organization | `hospital@mydoctor.test` | `pass123456` |
| Insurance organization | `insurance@mydoctor.test` | `pass123456` |

These credentials are for local demonstration only.

## API paths

The original routes remain under `/api/`. New integrations should use the versioned alias:

```text
/api/v1/auth/
/api/v1/clinical/
/api/v1/governance/
/api/v1/registry/
/api/v1/interoperability/
```

See [docs/API_REFERENCE.md](docs/API_REFERENCE.md).

## Tests

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Frontend production build:

```bash
cd frontend
npm ci
npm run build
```

## Production warnings

Before handling real patient data:

- replace SQLite with PostgreSQL;
- use private object storage with malware scanning and short-lived access URLs;
- disable mock payments;
- configure HTTPS, secure secrets, backups and tested recovery;
- deploy a real background-job/event-delivery system;
- complete legal, privacy, clinical-safety and regulatory review;
- validate every clinical workflow with qualified professionals;
- complete interoperability conformance testing before claiming FHIR or national-HIE compliance.

The production checklist is in [docs/SECURITY_PRIVACY.md](docs/SECURITY_PRIVACY.md).
