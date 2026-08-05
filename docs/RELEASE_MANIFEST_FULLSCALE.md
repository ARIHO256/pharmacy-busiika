# HealthPilot Enterprise Full-Scale Release Manifest

## Release purpose

This release extends the supplied HealthPilot Django/React application in place. It preserves the original platform and adds production-oriented role separation, hospital operations, diagnostics, billing, notifications, insurance, fake data and deployment tooling.

## Repository inventory

- 224 backend Python source and migration files
- 45 database migrations
- 120 Django model classes
- 230 URL route declarations
- 135 frontend JavaScript/JSX source files
- 120 portal/page JSX files
- 85 backend test methods supplied in the repository
- Docker Compose services for PostgreSQL, Redis, backend, Celery worker, Celery beat and frontend

## Delivered functional areas

1. Identity, contact verification, password recovery, MFA, session revocation and account lockout.
2. Public patient/professional/organization registration and invitation-only facility workforce onboarding.
3. Professional/facility licence review, expiry, suspension, revocation and protected document access.
4. Granular facility roles, permissions, departments, staff membership, shifts and leave.
5. Patient/dependent/caregiver services and consent-aware access.
6. Verified multi-cadre provider directory, availability and appointment lifecycle.
7. Reception, walk-in registration, check-in, queues and triage.
8. Clinical encounters, observations, diagnoses, care plans, prescriptions and closed-loop referrals.
9. Nursing, wards, beds, admissions, transfers, tasks, rounds and discharge.
10. Emergency, ambulance, theatre, maternity and radiology workflows.
11. Laboratory panels, specimen tracking, result validation/release and critical-result acknowledgement.
12. Pharmacy dispensing, inventory batches, expiry, stock movement and procurement.
13. Invoices, partial payments, PDF invoices/receipts, cashier shifts, adjustments and refunds.
14. Flutterwave and Paystack hosted checkout, signed webhook verification and refund adapters.
15. Insurance policies, benefits, eligibility, preauthorization, claim line items, adjudication and remittance.
16. In-app/email/SMS/push/WhatsApp notifications, templates, callbacks, retries and broadcasts.
17. Subscriptions, support, announcements, quality incidents, privacy requests and enterprise analytics.
18. Transactional outbox, webhook publication, FHIR-aligned summary foundation and terminology catalogue.
19. Large idempotent demonstration data set with accounts for clinical, operational and administrative roles.
20. PostgreSQL/Redis/Celery/Gunicorn/Nginx/S3-compatible deployment configuration and CI gates.

## Key entry points

- React development/production port: `3000`
- Django API port: `4000`
- Public web app: `/`
- API: `/api/` and `/api/v1/`
- OpenAPI schema: `/api/schema/`
- Health checks: `/healthz` and `/readyz`

## Demo data

Run `python seed.py` after migrations. Credentials and the complete account list are in `docs/DEMO_DATA.md`. Demonstration data must never be loaded into a real patient database.

## Validation status

Static source, migration-dependency, backend route-import, frontend parser/import, JSON and shell checks passed. Full Django runtime tests, clean database migration execution, Vite build and Docker boot could not be performed in the packaging environment because required packages were unavailable from its mirrors and Docker was unavailable. The included CI workflow performs those runtime gates in a normal connected environment.

## Deployment-specific requirements

Live operation still requires credentials and contracts for email, SMS, WhatsApp, push, object storage, payments and any regulator/insurer/PACS/laboratory interfaces. A healthcare deployment also requires privacy, clinical-safety, security, backup/restore and regulatory acceptance before real patient use.
