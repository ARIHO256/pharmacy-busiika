# Production Acceptance and Workflow Completion Release

## Purpose

This release continues from the deep-role experience build. It does not add route names merely to increase page coverage. It closes the highest-risk gaps identified in the source audit by connecting visible actions to persistent backend transactions, enforcing request-scoped role context, limiting administrative power, replacing fabricated operational values, and adding repeatable acceptance gates.

## Critical findings addressed

### 1. Page definitions versus complete workflows

The page catalogue remains useful for navigation and role discovery, but workflow-capable pages now use the `journeys` case API as their persistent transaction boundary. A page definition describes the page; it is not treated as proof that an operation happened. Mutable pages expose create, update, assignment, status transition, approval, rejection, comments, attachments, audit history, and domain-specific action adapters. Read-only pages are explicitly read-only and do not present a fake submit path.

The operational data layer now uses canonical domain records where those records exist. Workflow cases are retained for task orchestration and auditability rather than being presented as clinical truth.

### 2. Decorative controls

The acceptance audit rejects empty click handlers and known hard-coded demonstration controls. The following previously decorative areas now call real APIs:

- patient notification read and mark-all-read;
- invoice and receipt PDF download;
- secure conversation posting;
- imaging study access through authorized endpoints;
- administrative clinical-elevation requests and decisions;
- workflow case create, edit, assignment, comment and transition actions;
- theatre, maternity, emergency, laboratory, pharmacy and finance domain actions.

Controls that require an unavailable external provider are disabled with an explicit configuration message rather than simulating success.

### 3. Hard-coded operational values

Static verification confidence, service-health labels, default claim outcomes, fabricated bed data and simulated success indicators have been removed from acceptance-critical paths. Dashboards now derive values from domain APIs, workflow queues, readiness endpoints or provider state. Empty datasets render honest empty states.

### 4. Multi-role authorization

`accounts.User.role` is treated as a registration/default role only. Acting authorization resolves through:

1. active role context;
2. active organization;
3. active location or branch;
4. active department;
5. effective permissions and time-bound delegation.

The authorization audit fails request-time code that reintroduces unsafe direct role checks in protected application paths. Superusers do not silently inherit doctor, nurse, pharmacist or other clinical identities.

### 5. IT and compliance separation

The administrative capabilities are separated into four scopes:

- **Platform super administrator:** identity, platform configuration, organizations and integrations;
- **Operations administrator:** appointments, subscriptions, support and operational workflows;
- **Compliance administrator:** privacy, audit, access investigations and regulatory evidence;
- **Clinical safety administrator:** exceptional clinical governance and patient-specific safety review.

IT support can view system health and administer approved integrations. It does not receive broad clinical, financial or identity-management authority. Compliance officers can investigate controlled evidence but do not receive unrestricted platform configuration.

### 6. Controlled clinical access for administrators

Standing administrator access to patient clinical records is not accepted. The Controlled Clinical Access Centre requires:

- a named patient;
- a specific purpose and reason;
- selected scopes;
- MFA-enabled requester;
- independent approval;
- a time-limited expiry;
- read-only access by default;
- audit events for request, approval, use, review, revocation and expiry.

The requester cannot approve their own request. Signed clinical records, released laboratory results, prescriptions, financial history and audit records retain their normal immutability controls.

## Actor journey completion

### Patient

The patient journey is connected across appointment detail, rescheduling, cancellation, refund state, waiting position, consultation messages, prescriptions, refill and adherence, laboratory trends, imaging authorization, admission and discharge, insurance/preauthorization/claim details, mobile-money status, invoice/receipt downloads, consent, caregiver/dependent authority, complaints and notifications.

### Doctor and clinical professionals

Clinical work is patient-centred through care relationships, a persistent patient summary context, results and critical-results queues, order entry, medication renewal, admission/discharge actions, tasks, on-call and multidisciplinary workflows, verifiable generated documents and speciality-specific workflow definitions.

### Nursing and midwifery

Nursing workflows support patient charting, medication schedules, due and overdue doses, five-rights confirmation, omissions and escalation, fluid balance, wounds, fall and pressure-injury risk, isolation, transfusion observation, handover acknowledgement, discharge clearance and supply/equipment requests. Maternity adapters enforce labour and delivery chronology, APGAR ranges, birth measurements and linked stock/notification effects.

### Reception and records

Reception actions are connected to schedules, appointments, referral intake, eligibility and preauthorization checks, deposits, printing, admissions, discharge coordination, duplicate warnings, call-centre tasks and notification tracking. Records workflows cover duplicate comparison, controlled merge/unmerge cases, demographic corrections, classification, disclosure, legal holds, restrictions, retention, destruction approval, exports and custody history.

### Finance

Finance workflow adapters support payer allocation, multiple payment records, deposits, refunds and void controls, credit/debit adjustments, supplier invoices, expenses, balanced journals, reconciliation, receivables, payables, financial statements, periods, budgets and approval limits. Payment gateways remain disabled unless explicitly configured.

### Pharmacy and laboratory

Pharmacy and laboratory actions use domain models for dispensing, stock deduction, recalled/expired batch protection, stock counts and variance, recalls, quarantine, cold-chain escalation, specimen custody, result entry, validation/release, critical escalation, quality control and compatibility workflows.

### Emergency, theatre and maternity

Emergency routing includes recorded coordinates, distance and ETA calculation, status transitions and telemetry. Offline paramedic edits are stored locally as clearly labelled unsent drafts and never presented as submitted clinical records. Theatre actions enforce schedule conflict checks and safety/count/recovery requirements. Maternity actions enforce delivery prerequisites and APGAR validation.

### Administration

The Identity Command Centre supports global search, account history, session revocation, lock/unlock, MFA reset controls, role-context assignment/removal, organization/branch/department scope, context dates and ownership management. Separate consoles cover verification renewal, subscriptions, communication providers, payment configuration, settlement monitoring, CMS, event delivery, dead-letter replay, worker health, backups, localization and platform settings.

## Progressive web and offline behavior

A web manifest and service worker provide application-shell caching and an offline fallback. Network-failed workflow drafts are explicitly marked as local and unsent, can be retried or discarded, and are not counted as completed work. This is a safety fallback, not a replacement for a formally validated offline clinical application.

## Automated acceptance assets

- `scripts/validate-static.sh` — syntax, migration graph, URL imports, role/page/workflow coverage, imports, JSON/YAML, authorization and frontend acceptance.
- `scripts/authorization-audit.py` — rejects unsafe acting-role shortcuts and checks controlled clinical access.
- `scripts/frontend-acceptance.mjs` — rejects empty handlers, known hard-coded operational values and missing critical API wiring.
- `scripts/runtime-role-smoke.py` — signs in all 37 seeded roles and verifies context/dashboard access against a running API.
- `scripts/http-load-smoke.py` — dependency-free concurrent health/readiness smoke test.
- `scripts/release-gate.sh` — clean migration, seed verification, Django tests, role smoke, load smoke, frontend build and container manifest checks.

## External acceptance still required

No source archive can supply production credentials or regulatory approval. Before real patient data is processed, the deploying organization must complete:

- PostgreSQL migration and seeded demonstration verification in its environment;
- full backend and frontend test execution;
- container startup and backup/restore exercise;
- approved SMS, WhatsApp, push, mobile-money, payment, object-storage, Zoom, PACS, regulator and insurer sandbox testing;
- qualified clinical workflow review;
- privacy, security, legal and regulatory acceptance;
- performance, accessibility and penetration testing.

See `docs/VALIDATION_PRODUCTION_ACCEPTANCE.log` and `docs/RUNTIME_ACCEPTANCE_CHECKLIST.md`.
