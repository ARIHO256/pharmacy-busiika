# HealthPilot HealthOS

HealthPilot is a multi-role telehealth and connected-care platform built with **Django REST Framework** and **React + Vite**. This enhanced edition keeps the original appointments, chat, prescriptions, pharmacy, laboratory, hospital, insurance, payment and administration flows, while adding the safety and governance foundations required for a serious health platform.

> This repository is a production-oriented healthcare application baseline with complete role portals, database migrations, sample data, API workflows and deployment infrastructure. It is not a claim of regulatory certification; each deployment still requires local legal review, clinical validation, provider credentials and operational acceptance testing.

## Production acceptance workflow release

This edition includes the workflow-completion and authorization-hardening release. It connects acceptance-critical controls to persistent APIs, standardizes acting authorization on active role and organization context, separates platform/operations/compliance/clinical-safety administration, adds MFA-backed patient-specific administrator elevation, removes known hard-coded operational indicators, and adds role/runtime acceptance scripts.

Read [docs/PRODUCTION_ACCEPTANCE_WORKFLOW_RELEASE.md](docs/PRODUCTION_ACCEPTANCE_WORKFLOW_RELEASE.md) for the implementation map and [docs/VALIDATION_PRODUCTION_ACCEPTANCE.log](docs/VALIDATION_PRODUCTION_ACCEPTANCE.log) for the exact validation status. Static acceptance passed in the delivery environment; runtime dependency installation, migrations, tests, frontend build and Docker startup must be completed with `bash scripts/release-gate.sh` in a connected environment.

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
- Emergency/casualty cases, ambulance dispatch and escalation tracking
- Theatre scheduling, surgical safety checklist and peri-operative workflow
- Maternity episodes, labour/delivery status and postnatal tracking
- Inpatient admissions, bed allocation, transfers, ward tasks, rounds and discharge summaries
- Radiology worklists, imaging performance, reporting, verification and release
- Laboratory panels, specimen barcodes/custody events, structured results and critical-result acknowledgement
- Clinical pharmacy dispensing with partial fills, prescription quantities, counselling and stock deduction
- Inventory batches, expiries, stock movements, procurement and purchase-order receiving
- Organization workforce, departments, shifts, leave, granular roles and permissions
- Patient dependents, caregiver authority and booking/billing delegation
- Closed-loop specialist referrals with acceptance, treatment, feedback and acknowledgement
- Support tickets, announcements, notification templates, device registrations and broadcasts
- Subscription plans, account limits, renewals, refund controls and enterprise analytics
- Insurance benefit rules, eligibility calculations, preauthorizations, line-item adjudication and remittances
- Verified multi-cadre public provider directory with role-correct booking and clinical access

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

The complete audit-to-implementation map is in [docs/IMPLEMENTATION_STATUS_21_SECTIONS.md](docs/IMPLEMENTATION_STATUS_21_SECTIONS.md), and deployment acceptance is in [docs/RUNTIME_ACCEPTANCE_CHECKLIST.md](docs/RUNTIME_ACCEPTANCE_CHECKLIST.md).

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
| Hospital / Clinic organization | `/hospital` | services, bookings and bed management |
| Insurance organization / officer | `/insurance` | policies, benefit rules, eligibility, preauthorization, claims adjudication and remittances |
| Platform administrator | `/admin` | users, verification, protected evidence, appointments, finance, compliance and audit |

See [docs/ROLE_WORKFLOWS.md](docs/ROLE_WORKFLOWS.md) for page-by-page responsibilities and end-to-end care workflows. The direct client-to-implementation mapping is in [docs/CLIENT_REQUIREMENTS_IMPLEMENTATION.md](docs/CLIENT_REQUIREMENTS_IMPLEMENTATION.md). A concise implementation report for this enhancement is available at [docs/WORKFORCE_BILLING_ENHANCEMENT_REPORT.md](docs/WORKFORCE_BILLING_ENHANCEMENT_REPORT.md).

## Full-stack Docker demonstration

The archive includes a development-only `.env.compose`, so the complete local platform can be started without first creating an environment file:

```bash
docker compose up --build
```

This starts PostgreSQL, Redis, private MinIO storage, ClamAV, Orthanc, Redpanda/Kafka, RabbitMQ, Mailpit, Django/Channels, Celery worker and scheduler, Flower, the React frontend, Prometheus and Grafana. Demonstration data is loaded idempotently. Replace every development credential before a shared or production deployment.

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
python manage.py runserver 4000
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


### Notification delivery worker

For development, process pending email/SMS/push delivery records with:

```bash
cd backend
python manage.py send_appointment_reminders --hours 24
python manage.py notify_expiring_credentials
python manage.py dispatch_notifications --limit 200 --max-attempts 3
```

The Docker stack already runs Celery worker and beat processes. Email uses the configured Django email backend; SMS, WhatsApp and push become live after provider credentials and approved senders are configured.

## Demo accounts

After `python seed.py`:

| Role | Email | Password |
|---|---|---|
| Admin | `admin@healthpilot.test` | `AdminPass!2026` |
| Patient | `patient1@healthpilot.test` | `DemoPass!2026` |
| Doctor | `dr.nakato@healthpilot.test` | `DemoPass!2026` |
| Nurse | `nurse@healthpilot.test` | `DemoPass!2026` |
| Receptionist | `reception@healthpilot.test` | `DemoPass!2026` |
| Records officer | `records@healthpilot.test` | `DemoPass!2026` |
| Cashier | `cashier@healthpilot.test` | `DemoPass!2026` |
| Facility manager | `manager@healthpilot.test` | `DemoPass!2026` |
| Pharmacist | `pharmacist.staff@healthpilot.test` | `DemoPass!2026` |
| Storekeeper | `storekeeper@healthpilot.test` | `DemoPass!2026` |
| Laboratory professional | `labtech@healthpilot.test` | `DemoPass!2026` |
| Pharmacy organization | `pharmacy@healthpilot.test` | `DemoPass!2026` |
| Laboratory organization | `lab@healthpilot.test` | `DemoPass!2026` |
| Hospital organization | `hospital@healthpilot.test` | `DemoPass!2026` |
| Insurance organization | `insurance@healthpilot.test` | `DemoPass!2026` |

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

## Production completion gate

Static checks and the local SQLite developer gate do not certify a hospital deployment. The authoritative promotion command is:

```bash
RELEASE_VERSION=2026.08.04 SOAK_HOURS=4 bash scripts/production-acceptance-gate.sh
```

It runs a clean PostgreSQL deployment, seed verification, backend tests, 37-role smoke testing, Playwright browser journeys, provider sandbox checks, backup/restore, soak testing, and formal release acceptance. Human evidence is uploaded through `/admin/release-acceptance`; the system never auto-approves clinical, legal, privacy, security, or disaster-recovery gates.

Read `docs/PRODUCTION_COMPLETION_RELEASE.md` and `docs/acceptance/` before promotion.
