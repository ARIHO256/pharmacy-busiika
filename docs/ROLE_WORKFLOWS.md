# HealthPilot Role Workspaces and End-to-End Workflows

This document describes the enhanced role-based operating model now represented in the Django API and React application. It is the working guide for product, design, backend, frontend, QA and hospital stakeholders.

## 1. Identity model

HealthPilot separates four concepts that must never be confused:

1. **Account role** — the user's primary portal and default permission set.
2. **Professional verification** — whether a regulated health professional's practising credential is approved and current.
3. **Organization membership** — the hospital, clinic, pharmacy, laboratory or insurer where a staff member works.
4. **Department scope** — the branch or department in which a staff member may operate.

A role does not automatically grant access to every record. Access also depends on active organization membership, patient-care context, verification state and the requested operation.

### Public registration roles

- Patient
- Doctor
- Hospital or clinic organization
- Pharmacy organization
- Laboratory organization
- Insurance organization

### Invitation-only facility roles

- Nurse or midwife
- Receptionist
- Medical records officer
- Cashier or billing officer
- Pharmacist
- Laboratory professional
- Facility manager
- Insurance officer
- Storekeeper or procurement officer

Facility staff are invited by an organization owner or facility manager. Regulated staff submit credentials while accepting the invitation and remain unable to perform protected professional actions until verified.

---

## 2. Patient workspace

### Dashboard

The patient dashboard should answer four questions immediately:

- What is my next appointment?
- Is any action required from me?
- Are there new prescriptions, results or invoices?
- How do I get care now?

Recommended content:

- next appointment card with doctor, facility, time and consultation type;
- unread notification count;
- unpaid invoice and outstanding balance summary;
- recently released laboratory result;
- active prescription summary;
- quick actions for finding a doctor, booking, opening the consultation room and viewing records;
- health alerts such as allergies and overdue follow-up.

### Find care

Pages:

- verified doctor directory;
- verified hospital or clinic directory;
- laboratory directory;
- pharmacy directory;
- insurance provider directory;
- doctor profile;
- organization profile.

Doctor cards should show only verified professionals and include name, cadre, speciality, workplace, fee, languages, rating and availability. Licence images are never public.

### Appointment booking

The patient flow is:

1. Select a verified doctor or service.
2. Review provider profile, fee and consultation type.
3. Select an available date and time.
4. Confirm the reason for visit and required consent.
5. Create the booking.
6. Pay immediately or receive a pending invoice, depending on facility policy.
7. Receive in-app and configured email/SMS confirmation.
8. Receive reminders before the appointment.
9. Check in physically or enter the online consultation room.

Appointment pages should support pending, confirmed, checked-in, waiting, in-consultation, completed, cancelled, missed and rescheduled states.

### Health record

Patient-facing record pages include:

- summary;
- timeline;
- encounters;
- allergies;
- active and historical conditions;
- medicines;
- vital signs and observations;
- prescriptions;
- laboratory orders and released results;
- referrals;
- care plans;
- documents;
- consent and privacy controls.

Preliminary laboratory results must not be shown. Final or amended results become visible only after an authorized laboratory professional releases them.

### Billing and receipts

The patient should see:

- invoice number and facility;
- itemized services;
- subtotal, tax, discount and total;
- amount paid and balance;
- payment history;
- payment method and reference;
- downloadable or printable receipt;
- due date and payment status.

### Patient limitations

Patients cannot:

- verify providers;
- edit signed clinical notes;
- view another patient's record;
- see unreleased laboratory results;
- access private licence files;
- change prices or financial records.

---

## 3. Doctor workspace

A doctor account is a regulated professional account. Registration requires completion year, university, cadre, workplace, practising licence number, licence image and consultation fee. Speciality remains optional.

### Verification status page

The doctor should see:

- current verification state;
- licence number and issuer;
- expiry date;
- submitted document status;
- administrator request for more information;
- rejection, expiry, suspension or revocation reason;
- renewal action.

Until verified, the doctor may sign in and complete the profile but cannot publish availability or receive bookings.

### Doctor dashboard

Recommended content:

- today's appointment count;
- patients waiting;
- consultations in progress;
- results awaiting review;
- follow-ups due;
- unsigned draft encounters;
- current verification and licence-expiry alert;
- earnings and unpaid payout summary;
- high-priority notifications.

### Availability

The doctor can configure:

- working days;
- start and end time;
- slot duration;
- breaks;
- holidays and exceptions;
- in-person, audio or video availability;
- facility or location;
- consultation fee where policy permits.

Verification is enforced by the backend, not only by hiding the frontend page.

### Appointment worklist

Each row should show:

- patient name and identifiers allowed for care;
- visit reason;
- appointment type;
- date and time;
- payment or coverage state;
- check-in and queue state;
- triage priority;
- actions to confirm, start, complete, cancel or mark missed.

### Patient chart

The doctor chart includes:

- identity banner;
- allergies and critical alerts;
- current medicines;
- recent conditions;
- vitals and triage;
- consultation history;
- laboratory and imaging history;
- prescriptions;
- referrals;
- care plans;
- consent state;
- access audit context.

### Consultation workspace

A clinical encounter should contain:

- chief complaint;
- history of presenting complaint;
- past, family and social history;
- review of systems;
- examination findings;
- assessment;
- diagnosis and differential diagnosis;
- treatment plan;
- patient instructions;
- follow-up date;
- linked prescriptions;
- laboratory orders;
- referrals;
- supporting files.

Drafts may be edited. Finalized notes become immutable. Corrections are appended as amendments that retain the prior version, author, reason and time.

### Laboratory referral page

The doctor can create a laboratory order with:

- patient;
- verified laboratory;
- test;
- clinical indication;
- provisional diagnosis;
- priority;
- specimen type;
- referring facility.

The doctor can follow the specimen and result lifecycle and is notified when a result is released or a critical value requires action.

### Prescription page

The doctor can:

- search or enter medicines;
- specify dose, route, frequency, duration and instructions;
- record diagnosis or indication;
- issue and electronically sign a prescription;
- send it to a pharmacy;
- discontinue or amend using governed status transitions.

### Referrals and follow-up

The doctor can create a referral with receiving provider or facility, urgency, reason, clinical summary and supporting results. Referral status and response should remain visible in the patient's timeline.

### Doctor limitations

Doctors cannot:

- approve their own licence;
- view patients outside a care relationship without authorized emergency access;
- silently edit finalized notes;
- release laboratory results unless separately assigned an authorized lab role;
- change cashier reconciliation or platform settings.

---

## 4. Nurse or midwife workspace

Nurses are regulated professionals and must have verified credentials before recording protected clinical work.

### Nursing dashboard

Recommended content:

- patients waiting for triage;
- assigned patients;
- emergency and urgent cases;
- medication tasks;
- pending nursing documentation;
- handovers;
- recent alerts;
- licence status.

### Triage queue

The nurse sees only visits within the active organization scope. The triage form records:

- chief complaint;
- triage level;
- temperature;
- pulse;
- respiratory rate;
- blood pressure;
- oxygen saturation;
- weight and height;
- pain score;
- allergies;
- notes.

A red triage level changes visit priority to emergency. Orange or yellow changes it to urgent. The visit then moves to the clinician queue.

### Nursing notes

The nurse can create:

- assessment notes;
- progress notes;
- handover notes;
- procedure notes;
- discharge notes.

Each note stores the visit, patient, nurse and time. The nurse cannot impersonate another author.

### Medication administration

The medication administration record includes:

- medication;
- dose;
- route;
- scheduled time;
- administered time;
- status: given, held, refused or missed;
- notes;
- nurse identity.

### Nurse limitations

A nurse cannot:

- approve licences;
- create facility prices;
- receive cashier payments;
- validate laboratory results without a lab role;
- dispense as a pharmacist;
- modify signed doctor documentation.

---

## 5. Receptionist workspace

Receptionists are non-clinical facility staff. They are invited by a verified organization and require active membership but not professional licence verification.

### Front-desk dashboard

Recommended content:

- today's appointments;
- arrivals awaiting check-in;
- patients awaiting triage;
- clinician queue;
- completed visits;
- no-shows;
- quick patient search;
- provider availability.

### Patient search and registration

The receptionist can search by name, email or phone before creating a new patient. This reduces duplicate records.

For a new walk-in patient, capture only the minimum operational information:

- full name;
- email where available;
- phone;
- location;
- address;
- temporary or permanent account state according to facility policy.

The receptionist must not enter diagnoses or clinical history as if they were a clinician.

### Check-in

The receptionist can:

- select an existing appointment or create a walk-in visit;
- choose visit type;
- record visit reason;
- set routine, urgent or emergency priority only according to approved desk policy;
- route the patient to triage;
- print a visit or queue slip.

### Queue management

The queue shows visit number, queue number, patient, priority, arrival time, assigned clinician and status. Allowed actions include moving the patient to waiting for triage, waiting for clinician, billing, completed or cancelled, depending on policy.

### Receptionist limitations

Receptionists can see demographics, bookings and queue information, but cannot read detailed clinical notes, diagnoses, psychotherapy notes or unrelated laboratory results.

---

## 6. Medical records officer workspace

The current records officer shares the front-desk route foundation and should evolve with dedicated pages for:

- duplicate patient review;
- demographic correction requests;
- document scanning;
- authorized record exports;
- patient privacy requests;
- record retention;
- release-of-information tracking;
- merge and unmerge review.

A records officer may manage record structure and authorized disclosure but must not rewrite signed clinical findings.

---

## 7. Cashier and billing workspace

### Cashier dashboard

Recommended content:

- open shift state;
- opening float;
- pending invoices;
- today's payments;
- cash expected;
- payment-method totals;
- unpaid balances;
- recent receipts;
- shift variance alert.

### Cashier shift

The cashier opens a shift with an opening float. All cash payments received by that cashier contribute to expected cash. At close, the cashier enters closing cash and notes. The system calculates variance.

### Invoice creation

The cashier selects a patient and optional appointment, then creates one or more itemized lines:

- code;
- description;
- quantity;
- unit price;
- line discount;
- service type;
- source reference.

The invoice also supports tax, invoice discount, notes, due date and currency.

### Payment collection

The cashier can record:

- cash;
- mobile money;
- card;
- bank transfer;
- wallet;
- insurance.

Payments may be partial. The invoice becomes partially paid until the full balance is confirmed.

### Receipt

Every confirmed payment generates a unique receipt containing:

- receipt number;
- invoice number;
- patient;
- facility;
- itemized invoice lines;
- amount received;
- payment method;
- transaction reference;
- balance after payment;
- cashier;
- date and time.

The receipt page is designed for browser printing and should be suitable for A4 or compact receipt printers after production print-CSS tuning.

### Cashier limitations

The cashier sees the financial service description necessary to collect payment, but not detailed clinical notes. Cashiers cannot alter verification, laboratory results or prescriptions.

---

## 8. Pharmacist and storekeeper workspaces

### Pharmacist dashboard

Recommended content:

- new prescriptions;
- prescriptions requiring clarification;
- prepared and dispensed orders;
- low stock;
- near-expiry batches;
- controlled medicine alerts;
- pending supplier deliveries.

A pharmacist must be professionally verified before protected dispensing operations.

### Prescription fulfilment

The pharmacist should:

1. open a valid prescription;
2. confirm prescriber and patient;
3. review allergies and medication-relevant alerts;
4. verify medicine, dose and instructions;
5. request clarification where needed;
6. prepare or partially dispense;
7. record batch and quantity;
8. counsel the patient;
9. complete the dispensing record;
10. create or update the invoice.

### Inventory

The existing catalog supports medicines, stock, price, pharmacy orders and suppliers. The next production layer should add batch, expiry, storage location, recall, adjustment approval and controlled-medicine registers.

### Storekeeper

The storekeeper shares inventory pages but should not perform pharmacist-only clinical validation. The role focuses on receiving, stock counts, transfers, suppliers and procurement.

---

## 9. Laboratory professional workspace

A laboratory professional must be verified before protected result operations.

### Laboratory dashboard

Recommended content:

- new orders;
- ready for collection;
- collected specimens;
- specimens received;
- tests in progress;
- preliminary results;
- awaiting validation;
- critical results;
- released and amended reports.

### Laboratory order lifecycle

The implemented statuses are:

1. ordered;
2. awaiting payment;
3. ready for collection;
4. sample collected;
5. sample received;
6. in progress;
7. preliminary;
8. awaiting validation;
9. validated;
10. released;
11. amended;
12. cancelled;
13. rejected specimen.

### Specimen handling

The worklist records:

- patient;
- referring doctor;
- referring facility;
- clinical indication;
- provisional diagnosis;
- priority;
- test;
- specimen type;
- specimen identifier;
- collection notes;
- collector and time;
- receipt time;
- rejection reason.

### Result entry and release

Each structured result supports:

- code and coding system;
- test name;
- numeric or text value;
- unit;
- reference range;
- interpretation;
- result status;
- person entering the result;
- validator;
- release actor and time;
- amendment reason.

The patient and referring doctor are notified only after release. Critical results create high-priority notification and acknowledgement workflows.

### Laboratory limitations

Laboratory staff cannot edit doctor diagnoses, collect unrelated payments unless separately assigned a cashier role, or access patients with no valid order or organization context.

---

## 10. Facility manager workspace

### Operations dashboard

The facility manager sees non-clinical operational summaries:

- today's visits;
- waiting for triage;
- waiting for clinician;
- in consultation;
- at billing;
- completed;
- active staff by role;
- department load;
- billing and cashier summaries.

### Staff administration

The manager can:

- invite staff;
- choose role and department;
- issue an employee number;
- review pending invitations;
- suspend or reactivate organization membership;
- view professional verification state;
- track licence expiry.

The manager cannot approve professional licences; that remains a platform verification function.

### Department administration

The manager can create and maintain departments, codes and descriptions. Membership and workflow data are scoped to the organization.

### Facility manager limitations

Manager access does not automatically allow routine reading of detailed patient notes. Clinical data should be available only for authorized quality, treatment or emergency purposes with auditing.

---

## 11. Organization-owner portals

Hospital, clinic, pharmacy, laboratory and insurance accounts represent organization operators. Registration requires organization name, registered licence number, licence image, location and services description.

Before approval:

- the owner may sign in and complete organization setup;
- the organization remains hidden from public listings;
- public bookings and provider discovery do not expose it.

After approval, organization pages may manage their service catalog, staff invitations, branches, departments and operational settings according to organization type.

---

## 12. Platform administrator workspace

### Command centre

The admin dashboard should show:

- total patients;
- doctors by pending and verified state;
- regulated staff pending verification;
- organizations pending and verified;
- counts by organization type;
- appointments by status;
- revenue and pending payouts;
- expiring credentials;
- suspended accounts;
- failed notification deliveries;
- failed integration outbox events.

### Users and roles

The admin can filter all supported roles and statuses, then verify, reject, suspend or reactivate accounts. Destructive or adverse actions require a reason and are audited.

### Provider registry

The admin can:

- inspect organization details and services;
- open a protected licence document;
- verify or suspend an organization;
- return an organization to review;
- inspect professional credential details;
- open a protected credential file;
- verify, reject, expire or revoke a credential;
- record a decision reason;
- review integration events.

Licence files are retrieved through authenticated endpoints and access is audited.

### Appointment operations

The admin monitors appointment states, missed appointments and exceptions without becoming the treating clinician.

### Financial management

The admin reviews invoices, revenue, commissions and payouts. Cashier-specific receipt and shift workflows remain facility-scoped.

### Compliance and audit

The admin or compliance team reviews:

- account and role changes;
- verification decisions;
- protected document access;
- clinical record access;
- break-glass events;
- consent changes;
- prescriptions and result release;
- payments, refunds and receipt activity;
- event delivery failures.

---

## 13. Notification pipeline

The notification system uses three layers:

1. **Notification record** — title, body, kind, priority, action URL, metadata and expiry.
2. **User preferences** — channel and event-category choices.
3. **Delivery records** — one tracked job per in-app, email, SMS or push channel.

### Important events

Notifications should be created for:

- registration and welcome;
- verification approval, rejection, suspension, expiry and reactivation;
- staff invitation and acceptance;
- booking confirmation, reminder, cancellation and rescheduling;
- patient check-in and queue updates where useful;
- released laboratory result and critical-result escalation;
- prescription issue and pharmacy fulfilment;
- invoice issue, partial payment, full payment and receipt;
- referral status;
- licence-expiry reminders;
- security changes.

### Delivery worker

The management command below processes pending delivery jobs:

```bash
python manage.py dispatch_notifications
```

In production, schedule it with a worker system such as Celery, RQ or a managed queue. SMS and push remain provider adapters; the model and retry state are present, but credentials and vendor integration are deployment responsibilities.

---

## 14. Data communication pipeline

Every important business action follows this pattern:

1. Validate identity, role, verification, organization and resource scope.
2. Run the database mutation inside a transaction where consistency matters.
3. Write an audit event with actor, action, patient or resource and reason.
4. Write a transactional outbox event for downstream integrations.
5. Create user notifications and channel-delivery records.
6. Return a stable API response to the React portal.
7. Deliver email/SMS/push asynchronously.
8. Mark outbox and delivery attempts as sent, failed or retryable.

This reduces hidden coupling. Appointment, clinical, laboratory, billing and notification modules communicate using durable identifiers and events rather than directly changing unrelated UI state.

---

## 15. Billing workflow example

A common outpatient workflow is:

1. Reception checks in the patient.
2. Nurse records triage.
3. Doctor consults and orders a laboratory test.
4. Billing creates consultation and test invoice lines.
5. Cashier receives a partial or full payment.
6. The system creates a payment transaction and receipt.
7. Patient and cashier can print the receipt.
8. Laboratory receives the paid order according to facility policy.
9. Laboratory releases the result.
10. Doctor reviews the result and completes the plan.
11. Pharmacy receives the prescription and creates medicine charges.
12. Remaining invoice balance is collected and the visit is completed.

Every stage has an actor, status, timestamp, audit event and notification where appropriate.

---

## 16. Core authorization rules

- Patients book immediately and require no professional verification.
- Doctors cannot publish availability or receive bookings until verified.
- Nurses, pharmacists and laboratory staff cannot perform protected professional actions until verified.
- Organizations are absent from public listings until verified.
- Receptionists and cashiers are invited, not publicly self-registered.
- Staff access is restricted to active organization membership.
- Receptionists see demographic and queue data, not detailed clinical notes.
- Cashiers see invoices and service descriptions, not detailed clinical notes.
- Patients see laboratory results only after release.
- Licence documents are limited to the owner or practitioner and authorized administrator.
- Finalized clinical notes are amended, not overwritten.
- Every verification and status action is audited.
- Frontend route checks improve usability; backend permissions are authoritative.

---

## 17. Recommended next modules

The current enhancement concentrates on registration, verification, staff roles, outpatient patient flow, nursing, laboratory workflow, billing, receipts and notification foundations. A later phase should add:

- inpatient admission, ward and bed allocation;
- full medication administration scheduling;
- radiology and DICOM/PACS integration;
- theatre and anaesthesia;
- maternity and newborn records;
- configurable insurance preauthorization and claims adjudication;
- pharmacy batches, expiry, recalls and controlled medicines;
- enterprise patient duplicate merge/unmerge;
- branch-aware price lists;
- live mobile-money/card reconciliation;
- production worker queue and delivery providers;
- licence-expiry scheduled jobs;
- AI-assisted OCR pre-screening with mandatory human decision.
