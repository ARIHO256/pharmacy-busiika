# Client Requirements Implementation Map

This document maps the WhatsApp requirements and supplied flow chart to the enhanced Django and React implementation. It is intended for client review, QA acceptance and future development planning.

## 1. Registration and account ownership

### Patient

Implemented registration fields:

- first and last name;
- email and password;
- phone/contact number;
- location or address.

The patient is activated immediately and can browse verified providers, book appointments, receive invoices, pay, print receipts, use consultations and view released clinical information. Date of birth, gender, blood group, allergies, medical history and emergency contact remain editable after registration.

### Doctor or clinician

Implemented mandatory registration fields:

- full name, email and phone;
- year of completion;
- university of completion;
- professional cadre;
- current workplace;
- practising licence number;
- licence image or PDF;
- consultation fee.

Speciality is optional. The doctor starts in `pending` status. Availability publishing, public listing and new bookings are blocked until an administrator verifies the credential. A later licence update resets verification to pending so an administrator must review the new evidence.

### Healthcare organization

Implemented organization account types:

- hospital or clinic;
- pharmacy;
- laboratory;
- insurance organization.

Mandatory registration data includes organization name, registered licence number, private licence image/PDF, district/location, physical address and services description. A canonical registry record is created and remains outside public listings until verified.

### Facility staff

Nurses, receptionists, records officers, cashiers, pharmacists, laboratory professionals, facility managers, insurance officers and storekeepers are not public marketplace providers. They join a verified facility through a secure invitation. The invitation assigns an organization, role and optional department. Regulated staff upload their own licence and remain professionally restricted until verification.

## 2. Exact role workspaces

### Patient portal — `/patient`

Pages and duties:

- dashboard: next appointment, alerts, invoices and quick actions;
- find doctors: verified professionals only;
- doctor details: cadre, speciality, workplace, fee, rating and availability;
- appointments: booking, status, cancellation, consultation access and follow-up;
- health record: timeline, allergies, conditions, observations, encounters and consent;
- prescriptions: issued medicines and pharmacy transfer;
- laboratory: test bookings, orders and released results;
- pharmacy: product browsing and orders;
- hospitals: service discovery and bookings;
- insurance: policies, eligibility and claims;
- invoices: itemized bills, balances and receipt printing;
- messages and notifications;
- profile and notification preferences.

### Doctor portal — `/doctor`

Pages and duties:

- dashboard: appointments, waiting patients, follow-ups, result alerts and earnings;
- profile and verification: qualifications, licence, expiry, workplace, fee and review status;
- availability: recurring schedules, slot duration, breaks and holidays;
- appointments: confirm, consult, complete, cancel or mark missed;
- clinical workspace: patient summary, allergies, conditions, observations and encounters;
- consultation room: secure chat/audio/video entry for confirmed appointments;
- prescriptions: issue and review prescriptions;
- laboratory referrals: order tests, record indication and provisional diagnosis;
- earnings: paid consultations, commission and payout requests.

The API, not only the interface, prevents an unverified doctor from publishing availability or receiving bookings.

### Nurse or midwife portal — `/nurse`

Pages and duties:

- nursing dashboard and assigned work queue;
- triage: chief complaint, urgency level, temperature, pulse, respiratory rate, blood pressure, oxygen saturation, weight, height, pain and allergies;
- nursing notes: assessment, progress, handover and discharge-related notes;
- medication administration: medication, dose, route, schedule, administration time and response;
- patient-flow visibility for assigned or organization-scoped visits.

Nurses cannot verify providers, alter prices, issue cashier receipts or perform doctor-only final diagnosis and prescribing actions.

### Reception and medical-records portal — `/reception`

Pages and duties:

- front-desk dashboard;
- patient search by name, email or contact;
- minimum-data patient registration for walk-ins;
- appointment or walk-in check-in;
- queue creation and queue-number assignment;
- provider/department routing;
- patient-flow board from registration through triage, consultation, billing and completion.

Receptionists do not receive access to detailed clinical notes. Records officers share identity and queue tools but are intended for patient identity correction, duplicate-resolution and authorized records handling rather than clinical authorship.

### Cashier and billing portal — `/cashier`

Pages and duties:

- billing dashboard with pending invoices, outstanding balances, daily collections and receipts;
- itemized invoice creation for consultation, tests, medicines and other services;
- tax and discount fields;
- partial or full payment collection;
- cash, mobile money, card, bank, wallet and insurance payment methods;
- payment reference capture;
- automatic receipt generation;
- printable receipt view;
- cashier shift opening float, expected cash, closing cash and variance;
- daily reconciliation summary.

A patient can view only their own bills. A cashier can work only inside an active organization membership.

### Pharmacist and storekeeper portal — `/pharmacist`

Pages and duties:

- pharmacy dashboard;
- prescription-order queue;
- medicine catalogue;
- inventory quantities;
- product and supplier management;
- order fulfilment;
- stock and procurement views.

The pharmacist role is a regulated role and requires credential verification. Storekeepers use inventory/procurement functions but do not gain pharmacist-only clinical authority.

### Laboratory professional portal — `/lab-staff`

Pages and duties:

- laboratory dashboard and incoming worklist;
- doctor/referrer details and clinical indication;
- test order lifecycle;
- specimen identifier, type, collection, receipt and rejection reason;
- result entry with value, unit, reference range and critical flag;
- preliminary, validation and release states;
- author, validator/releaser and timestamps;
- amendment reason and history;
- patient notification after release.

Patients cannot see preliminary or unvalidated results.

### Facility manager portal — `/facility`

Pages and duties:

- facility operations summary;
- departments and service units;
- secure staff invitations;
- role and department assignment;
- membership suspension/reactivation;
- verification-state visibility for regulated staff;
- organization-scoped operational and billing information.

Facility ownership or management does not automatically grant unrestricted access to every clinical record.

### Organization portals

- `/hospital`: services, bookings and bed foundation;
- `/pharmacy`: medicines, inventory, suppliers, commerce and prescription orders;
- `/lab`: test catalogue and laboratory operations;
- `/insurance`: policies, coverage and claims.

Only verified active organizations appear publicly.

### Platform administrator portal — `/admin`

Pages and duties:

- global dashboard with patient, professional, organization and pending-verification counts;
- users: filter by role/status, verify, reject, suspend and reactivate;
- provider registry: inspect doctor/staff credentials and organization licence evidence;
- protected document viewing through authenticated audited endpoints;
- appointment monitoring;
- finance and payout overview;
- reviews and complaints;
- compliance dashboard;
- immutable audit-event viewer;
- event-outbox monitoring for integration/data-pipeline failures.

Adverse actions require a reason and are written to the audit trail.

Hospital and clinic registrations are stored as distinct organization types, so administrator counts and public filtering do not combine clinics into the hospital category.

## 3. Verification workflow

1. Doctor or organization submits mandatory profile and licence evidence.
2. Account/profile is marked `pending`.
3. Public listing and regulated operations remain disabled.
4. Administrator opens the registry queue and reviews protected evidence.
5. Administrator verifies, rejects, suspends, revokes or reactivates with an audited reason.
6. User receives in-app and configured external-channel notifications.
7. Verified professionals can work within their role and organization scope.
8. Updating licence data resets the professional to pending review.
9. Scheduled credential checks send expiry reminders and disable expired credentials.

Private licence files are blocked from generic development media URLs and are exposed only through authenticated owner/practitioner/admin endpoints. Production still requires private object storage and short-lived signed access.

## 4. End-to-end outpatient workflow

1. **Registration or search** — reception locates the patient or creates a minimum patient record.
2. **Booking/check-in** — patient books online or reception creates a walk-in visit and assigns a queue number.
3. **Triage** — verified nurse records complaint, urgency, vitals, pain and allergies.
4. **Clinician queue** — patient moves to waiting-for-clinician and is assigned to a verified doctor.
5. **Consultation** — doctor reviews triage/history, documents an encounter, diagnosis, plan, prescriptions, tests and referrals.
6. **Laboratory** — order moves through payment, collection, receipt, processing, validation and release. Critical results are flagged.
7. **Pharmacy** — prescription is transferred, reviewed and fulfilled; inventory/order records are updated.
8. **Billing** — cashier issues an itemized invoice containing all billable services.
9. **Payment** — one or more payments are recorded until the balance is zero; each transaction receives its own receipt.
10. **Completion/follow-up** — visit is completed, notifications are sent and a follow-up appointment can be booked.

Every important transition writes an audit event and/or transactional outbox event so integrations do not have to run inside the clinical transaction.

## 5. Notification workflow

Notification records support:

- priorities: low, normal, high and critical;
- channels: in-app, email, SMS and push;
- user preferences and quiet hours;
- action links to the correct role portal;
- per-channel delivery records, attempts, status and error details;
- bounded email retries;
- appointment reminder scheduling;
- credential-expiry reminders;
- payment, receipt, result, verification and account alerts.

Commands:

```bash
python manage.py send_appointment_reminders --hours 24
python manage.py notify_expiring_credentials
python manage.py dispatch_notifications --limit 200 --max-attempts 3
```

Run these from Celery/RQ, cron, a systemd timer or a managed job platform in production. The repository queues SMS/push delivery records but intentionally does not claim a live provider integration; provider credentials/adapters must be configured before those channels are enabled.

## 6. Coordinated data pipeline

The project uses a transactional outbox pattern:

```text
React role page
  -> authenticated Django endpoint
  -> role + organization + verification checks
  -> atomic database transaction
  -> audit event
  -> outbox event
  -> background publisher/integration adapter
  -> notification delivery jobs
  -> recipient portal/email/SMS/push
```

Each outbox event carries event type, aggregate, actor, patient context, payload, correlation ID, causation ID, status and retry data. This allows future Kafka, RabbitMQ, FHIR, payment, Zoom, SMS and partner integrations without making the clinical request depend on an external service being online.

## 7. Acceptance checks implemented

- Patient registration is immediate and does not require professional verification.
- Doctor/organization licence number and document are stored separately.
- Doctor and organization profiles remain pending until reviewed.
- Unverified doctors cannot publish availability or receive bookings.
- Regulated invited staff remain restricted until credential approval.
- Only verified doctors and active verified organizations appear publicly.
- Private licence documents are owner/admin restricted and audited.
- Admin can manage users and verification states.
- Admin can see role/status counts and organization breakdowns.
- Reception can register/check in patients but cannot triage.
- Nurse can triage but cannot perform cashier operations.
- Cashier can invoice, accept partial payments and print receipts but cannot read detailed clinical notes.
- Laboratory personnel can enter and release results; patients see only released results.
- Organization membership suspension is scoped to that organization rather than silently disabling unrelated memberships.
- Every sensitive administrative, clinical, laboratory and financial action is auditable.

## 8. Production items that remain external configuration

The codebase provides the application foundation, but production deployment still requires:

- PostgreSQL and migration execution;
- private S3-compatible object storage and malware scanning;
- real mobile-money/card gateway credentials and signed webhooks;
- an SMS provider and push-notification provider;
- background worker/scheduler deployment;
- production telemedicine provider configuration;
- backups, disaster recovery, monitoring and alerting;
- legal/privacy/clinical-safety review and regulator-specific verification integrations;
- future AI-assisted licence pre-screening with mandatory human decision-making.
