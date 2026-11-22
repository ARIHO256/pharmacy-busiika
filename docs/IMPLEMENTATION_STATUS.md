# Implementation Status

This document is the source of truth for what the repository actually implements. “Foundation” means the data model and core workflow exist but external production infrastructure or certification is still required.

The 4 November 2026 operational delivery is detailed in
[OPERATIONS_IMPLEMENTATION.md](OPERATIONS_IMPLEMENTATION.md), including exact API
contracts, new portal pages, external-service requirements and remaining clinical
validation limits. Payments were excluded from that delivery.

## Implemented and tested

| Area | Status | Notes |
|---|---|---|
| Authentication and role portals | Implemented | JWT access/refresh, rotated refresh tokens, password validation, role routing |
| Patient and provider profiles | Implemented | Provider profile synchronizes to canonical registry organization |
| Doctor discovery | Implemented | Verified doctors, search and fee filters |
| Availability and appointments | Implemented | slot generation, uniqueness constraints, lifecycle validation and history |
| Care relationship | Implemented | created from a booking and used during clinical access decisions |
| Chat and consultation room | Implemented MVP | persisted chat and Jitsi room integration; production video governance remains |
| Clinical encounters | Implemented | draft, final, amended and versioned revision snapshots |
| Allergies, conditions and medication statements | Implemented | patient-reported versus clinician-verified source is retained |
| Observations | Implemented | numeric/text values, units and interpretations |
| Patient summary and timeline | Implemented | consent-aware API and patient/doctor interfaces |
| Referrals and care plans | Implemented foundation | create/list and longitudinal display; receiving-facility workflow is future work |
| Consent | Implemented | grant, expiry, recipient, data categories and revocation |
| Break-glass access | Implemented | 30-minute access, reason, end and compliance review |
| Governance audit | Implemented | append-only audit events and admin monitoring |
| Organization registry | Implemented | organizations, locations, public verified directory and admin status controls |
| Practitioner credential registry | Implemented | submission and administrator verification/rejection/revocation |
| Practitioner roles | Implemented foundation | organization affiliation and specialty |
| Prescriptions | Implemented enhanced MVP | version, status, signature time, expiry, item instructions and pharmacy transfer |
| Pharmacy commerce and stock safety | Implemented operational workflows | medicines, cart, orders, suppliers, prescription orders, batch/expiry/FEFO stock, recall, cold-chain quarantine, witnessed controlled-stock register and prescription quantity checks |
| Laboratory | Implemented enhanced MVP | catalogue, bookings, structured results, critical flag and acknowledgement |
| Hospital | Implemented operational workflows | service catalogue, bookings, admissions, transfers, discharge, bed allocation, signed-prescription medication schedules and procedure booking conflicts |
| Insurance | Implemented operational workflows | policies, coverage, service benefits, preauthorization, annual-limit assessments, immutable decision snapshots and reconciliation totals |
| Payments | Implemented development flow | mock gateway plus invoice/receipt; production provider adapter required |
| Accounting ledger | Implemented foundation | immutable journal entries and balanced postings |
| Transactional outbox | Implemented worker and adapter | event persistence, Celery/Redis configuration, leased publication, signed idempotent webhooks, retries and dead letters; deployment required |
| Terminology catalogue | Implemented foundation | local concepts and mappings; no external terminology-server integration |
| FHIR export | Implemented draft | R4-aligned patient-summary collection; not certified or a complete FHIR server |
| Request tracing | Implemented | validated/generated `X-Request-ID` response header |
| Health probes | Implemented | `/healthz` and database-aware `/readyz` |
| API version alias | Implemented | `/api/v1/` mirrors legacy `/api/` |
| Responsive design system | Implemented | semantic health colours, accessibility focus and reduced-motion rules |

| Role-based registration and verification | Implemented | Patients activate immediately; doctors and organizations require mandatory licence evidence and administrator approval |
| Facility workforce | Implemented enhanced foundation | invitation acceptance, departments, memberships, role routing and suspension/reactivation |
| Nursing | Implemented outpatient foundation | triage, vitals, nursing notes and medication administration with verification gates |
| Reception and queue | Implemented | patient search/registration, walk-in check-in, queue states and organization scope |
| Billing and cashier | Implemented enhanced foundation | itemized invoices, partial payments, receipts, shifts and reconciliation fields |
| Notification pipeline | Implemented enhanced foundation | role-correct action links, preferences, quiet hours, transactional default channels, delivery jobs, bounded email retries, appointment reminders and credential-expiry reminders; production SMS/push providers remain |
| Secure verification files | Implemented application control | owner/admin protected endpoints and access audit; production private object storage remains required |
| Laboratory operations | Implemented enhanced foundation | referrals, specimen lifecycle, result author/validator/release data and patient-release gating |
| Patient master identity | Implemented controlled linking | person/account links, identifier namespaces, demographic candidates, audited merge/unmerge without rewriting clinical record ownership |
| Receiving referrals | Implemented | receiving organization, acceptance/decline, assignment, scheduling, versioned transitions and completion outcome |
| Imaging operations | Implemented integration workflow | orders, scheduling, study UID, clinician reports and DICOMweb metadata adapter; external archive/viewer required |
| Real-time chat | Implemented | authenticated origin-checked WebSocket refresh, HTTP fallback, incremental synchronization, receipts and idempotent text-message retries |
| Private documents | Implemented fail-closed workflow | malware scanning, private local/S3 storage, authenticated downloads and 60-second signed access links; scanner/storage provisioning required |
| Offline capture | Implemented limited facility workflow | encrypted SQLite capture tool and server inbox, idempotent submission, clinician preview/review and application of observations/nursing notes |
| Research aggregates | Implemented limited analytics | independently approved monthly aggregates of consenting patients, distinct-patient thresholds and small-cell suppression |
| Administrative copilot governance | Implemented opt-in workflow | evaluated model registry, independently approved allowlisted adapter, administrative drafting and human review; no clinical AI activation by default |

## Deliberately not claimed as complete

| Area | Current gap |
|---|---|
| National health information exchange | consent-gated summary-delivery adapter exists; national profiles, trust agreement, credentials, conformance tests and certification remain external |
| Enterprise master patient index | controlled identity links and reversible merges exist; validated probabilistic matching, authoritative identity sources and national ID policies remain |
| Full hospital EHR | inpatient/procedure workflows now exist; complete ward/anesthesia documentation, clinical protocol validation and a fully validated eMAR remain |
| Medical imaging | imaging workflow and DICOMweb connector exist; PACS archive, acquisition hardware and diagnostic viewer are not bundled |
| Production telemedicine | JWT/private-room, recording-consent and quality-event controls exist; private Jitsi service, provider recording enforcement, QoS monitoring and SLA remain |
| Production payments | no live mobile-money/card credentials, signed webhooks, settlement files or gateway reconciliation |
| Background jobs | worker/scheduler and Compose definitions exist; broker/workers/monitoring have not been provisioned |
| Real-time messaging | authenticated service, receipts and incremental sync exist; production Redis/ASGI deployment and legacy-attachment storage migration remain |
| Pharmacy supply chain | batch, expiry, recall, cold-chain and controlled-stock workflows exist; procurement, maintained formulary, physical reconciliation and professional validation remain |
| Insurance adjudication | benefit/preauthorization/assessment workflows exist; contracted benefit data, enrollment validation, appeals and settlement integrations remain |
| Offline-first facility node | encrypted append-only capture/review exists; full offline portal replicas, broader synchronization and deployment validation remain |
| Clinical terminology server | lookup/expansion adapters exist; maintained terminology services and licensed ICD/SNOMED/LOINC content remain external |
| Clinical decision support | reviewed versioned rule evaluation exists; a licensed interaction knowledge base, full guideline engine and clinical validation are not included |
| AI clinical copilot | administrative provider/model governance and draft review exist; diagnostic/treatment AI requires separate clinical safety approval and is not enabled |
| Research warehouse | consented aggregate snapshots exist; full patient-level de-identification, OMOP warehouse and formal disclosure review remain |
| Regulatory certification | not certified as medical-device software, HIE participant or production clinical system |

## Validation evidence in this delivery

- All backend Python source and migration files pass `python3 -m compileall` syntax compilation.
- Frontend source is parsed with the locally available TypeScript parser during packaging.
- A full Django system check, migration execution and automated test suite require installing the Python dependencies from `backend/requirements.txt`.
- A full Vite build requires successful npm dependency installation. The isolated build environment used for this upgrade could not download one npm tarball from its package mirror, so the final build must be run in the target development environment.

## Appointments and scheduling

- Explicit consent acknowledgement at appointment booking; the UI and API reject booking until it is accepted.
- Atomic creation of the appointment, consent grant, care relationship, status history and outbox event.
