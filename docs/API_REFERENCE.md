# API Reference

All authenticated endpoints use a JWT bearer token unless marked public.

```http
Authorization: Bearer <access-token>
X-Request-ID: optional-client-correlation-id
```

The response includes `X-Request-ID`. New integrations should use `/api/v1`; the legacy React application continues to use `/api`.

## Authentication

```text
POST /api/v1/auth/register/
POST /api/v1/auth/token/
POST /api/v1/auth/token/refresh/
GET  /api/v1/auth/me/
PATCH /api/v1/auth/me/
GET  /api/v1/auth/me/profile/
PATCH /api/v1/auth/me/profile/
POST /api/v1/doctors/verify-upload/
```

Public registration uses one multipart endpoint with role-specific fields. For a hospital or clinic account, send `role=hospital` and distinguish the facility with `organization_type=hospital` or `organization_type=clinic`. Pharmacy, laboratory and insurance account types are inferred from their public role.

```json
{
  "email": "contact@hopeclinic.test",
  "password": "StrongPass123!",
  "first_name": "Hope",
  "last_name": "Administrator",
  "phone": "+256700000000",
  "role": "hospital",
  "organization_type": "clinic",
  "organization_name": "Hope Clinic",
  "license_number": "CLINIC-001",
  "district": "Kampala",
  "address": "Wandegeya",
  "services_description": "Outpatient and maternal care",
  "license_document": "<multipart file>"
}
```

## Doctor discovery and scheduling

```text
GET  /api/v1/doctors/
GET  /api/v1/doctors/{doctor_id}/
GET  /api/v1/doctors/{doctor_id}/slots/?date=YYYY-MM-DD
GET  /api/v1/availability/
POST /api/v1/availability/
DELETE /api/v1/availability/{id}/
```

## Appointments

```text
GET  /api/v1/appointments/
POST /api/v1/appointments/

Appointment creation requires explicit telemedicine/data-sharing acknowledgement in the request body:

```json
{
  "doctor": 42,
  "date": "2026-08-04",
  "start_time": "09:00:00",
  "end_time": "09:30:00",
  "type": "online",
  "reason": "Follow-up consultation",
  "consent_acknowledged": true
}
```

The booking, consent grant, care relationship, status history and interoperability event are committed atomically. A missing or false acknowledgement is rejected.
POST /api/v1/appointments/{id}/confirm/
POST /api/v1/appointments/{id}/cancel/
POST /api/v1/appointments/{id}/complete/
POST /api/v1/appointments/{id}/miss/
```

Appointment actions are validated against the allowed transition graph and create status-history records.

## Clinical record

```text
GET  /api/v1/clinical/summary/?patient_id={id}
GET  /api/v1/clinical/timeline/?patient_id={id}
GET/POST /api/v1/clinical/allergies/
PATCH /api/v1/clinical/allergies/{id}/
GET/POST /api/v1/clinical/conditions/
PATCH /api/v1/clinical/conditions/{id}/
GET/POST /api/v1/clinical/medications/
PATCH /api/v1/clinical/medications/{id}/
GET/POST /api/v1/clinical/observations/
GET/POST /api/v1/clinical/encounters/
PATCH /api/v1/clinical/encounters/{id}/
POST /api/v1/clinical/encounters/{id}/finalize/
POST /api/v1/clinical/encounters/{id}/amend/
GET/POST /api/v1/clinical/referrals/
GET/POST /api/v1/clinical/care-plans/
```

Doctors/admins specify `patient_id` where required. The API checks access rather than trusting the query parameter.

## Governance

```text
GET/POST /api/v1/governance/consents/
POST /api/v1/governance/consents/{id}/revoke/
GET /api/v1/governance/patients/{patient_id}/consents/
GET/POST /api/v1/governance/break-glass/
POST /api/v1/governance/break-glass/{id}/end/
POST /api/v1/governance/break-glass/{id}/review/
GET /api/v1/governance/compliance/overview/
GET /api/v1/governance/audit/
```

## Provider and practitioner registry

```text
GET/POST /api/v1/registry/organizations/
GET /api/v1/registry/organizations/mine/
GET/PATCH /api/v1/registry/organizations/{public_id}/
GET/POST /api/v1/registry/organizations/{public_id}/locations/
POST /api/v1/registry/organizations/{public_id}/status/
GET/POST /api/v1/registry/credentials/
POST /api/v1/registry/credentials/{id}/verify/
GET/POST /api/v1/registry/practitioner-roles/
GET /api/v1/registry/care-relationships/
```

Only verified active organizations are returned by the public organization list.

## Prescriptions

```text
POST /api/v1/appointments/{appointment_id}/prescription/
GET  /api/v1/prescriptions/
GET  /api/v1/prescriptions/{id}/
POST /api/v1/prescriptions/{id}/send-to-pharmacy/
```

## Laboratory and connected services

Services are mounted under `/api/v1/services/`. Major groups include:

```text
medicines
cart
orders
pharmacy-orders
suppliers
lab-tests
lab-orders
lab-results
hospital-services
hospital-bookings
beds
policies
coverage
claims
```

Structured lab results are available through:

```text
GET/POST /api/v1/services/lab-orders/{order_id}/results/
POST /api/v1/services/lab-results/{result_id}/acknowledge/
```

## Payments

```text
POST /api/v1/payments/initiate/
GET  /api/v1/payments/invoices/
GET  /api/v1/payments/invoices/{id}/receipt/
GET  /api/v1/payments/earnings/
POST /api/v1/payments/withdraw/
```

Mock payment completion is development-only and must be disabled in production.

## Interoperability

```text
GET /api/v1/interoperability/fhir/metadata/
GET /api/v1/interoperability/fhir/patients/{patient_id}/summary/
GET /api/v1/interoperability/terminology/concepts/
POST/PATCH /api/v1/interoperability/terminology/concepts/manage/
GET /api/v1/interoperability/outbox/
```

The FHIR endpoints are explicitly labelled an **R4-aligned draft**. They are not a certified national profile and do not implement complete FHIR search, validation, persistence or conformance.

## Health and operations

```text
GET /healthz   # process liveness
GET /readyz    # database readiness
```

## Error shape

Most validation errors follow DRF field-error structures. Registration additionally returns a human-readable summary:

```json
{
  "detail": "Human-readable first error",
  "errors": {
    "field": ["Detailed validation message"]
  }
}
```

## Role, workforce, billing and notification enhancements

### Workforce

```text
GET|POST /api/workforce/departments/
GET|POST /api/workforce/staff/
POST     /api/workforce/staff/{membership_id}/status/
GET|POST /api/workforce/invitations/{token}/
GET|POST /api/workforce/patients/
GET|POST /api/workforce/visits/
POST     /api/workforce/visits/{visit_id}/action/
GET|POST /api/workforce/triage/
GET|POST /api/workforce/nursing-notes/
GET|POST /api/workforce/medication-administrations/
GET      /api/workforce/summary/
```

### Billing and receipts

```text
GET|POST /api/billing/invoices/
POST     /api/billing/invoices/{invoice_id}/payments/
GET|POST /api/billing/shifts/
POST     /api/billing/shifts/{shift_id}/close/
GET      /api/billing/summary/
GET      /api/payments/receipts/{receipt_id}/
```

### Notifications

```text
GET   /api/notifications/
POST  /api/notifications/{notification_id}/read/
POST  /api/notifications/read-all/
GET   /api/notifications/preferences/
PATCH /api/notifications/preferences/
```

### Protected verification documents

```text
GET /api/registry/organizations/{public_id}/license-document/
GET /api/registry/credentials/{credential_id}/document/
```

The protected document routes require an authenticated owner/practitioner or platform administrator and create audit events.

## Operational notification commands

```bash
python manage.py send_appointment_reminders --hours 24
python manage.py notify_expiring_credentials
python manage.py dispatch_notifications --limit 200 --max-attempts 3
```

The first two commands create deduplicated notification jobs. The dispatcher respects non-critical quiet hours and retries failed email deliveries up to the configured attempt limit. SMS and push remain queued/skipped until production provider adapters are configured.

