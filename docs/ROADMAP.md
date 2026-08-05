# Health Super-App Roadmap

This roadmap prioritizes safety and durable records before feature volume.

## Phase 0 — Release hardening

- PostgreSQL production environment
- private object storage and malware scanning
- Redis/Celery for reminders, notifications and document work
- broker-backed outbox publisher with retries/dead letters
- signed payment webhooks and idempotent reconciliation
- MFA/passkeys for clinicians and administrators
- centralized logs, metrics, traces and alerting
- backup restoration and disaster-recovery exercise
- formal privacy impact assessment and clinical-safety review

**Exit condition:** the present MVP can operate reliably without mock infrastructure.

## Phase 1 — Identity and trust network

- separate person/account/patient/practitioner representations
- household, guardian, dependant and delegated-caregiver relationships
- enterprise master patient index
- deterministic/probabilistic duplicate matching
- governed merge and unmerge workflow
- national/facility identifier namespaces
- provider licence verification adapters
- organization onboarding and accreditation evidence
- segmented sensitive-record access policies

**Exit condition:** identities and access remain safe across several organizations.

## Phase 2 — Complete longitudinal care

- richer encounter types and clinical documents
- problem list and medication reconciliation
- structured vital-sign/device feeds
- clinical orders framework
- referral acceptance, scheduling and closure loop
- multidisciplinary care teams
- patient goals and care-plan activities
- immunization, maternal/child and chronic-care programmes
- clinical document signature and correction workflows

**Exit condition:** a patient's care journey is continuous rather than a collection of appointments.

## Phase 3 — Diagnostic and medication network

- specimen lifecycle and chain of custody
- laboratory instrument/LIS adapters
- critical-result escalation timers
- imaging order workflow
- PACS/VNA and DICOMweb viewer
- structured radiology/pathology reports
- medication catalogue and formulary
- allergy, duplication and interaction knowledge service
- pharmacy batch, expiry, recall and controlled-stock workflows
- pharmacovigilance reporting

**Exit condition:** diagnostic and medication information is structured, traceable and safely closed-loop.

## Phase 4 — Facility operating system

- outpatient queue and triage
- admission, transfer and discharge
- bed allocation and ward management
- nursing observations and task lists
- medication administration record
- theatre/procedure scheduling
- discharge summary and follow-up
- inventory and procurement integration
- facility edge/offline node with conflict review

**Exit condition:** selected facilities can operate essential clinical workflows on the platform.

## Phase 5 — Insurance and health finance

- eligibility and benefit rules
- preauthorization
- coded claim lines
- adjudication and appeals
- tariffs and contracts
- provider settlements and remittance advice
- fraud/waste/abuse monitoring
- sponsor/government subsidy programmes
- complete gateway and bank/mobile-money reconciliation

**Exit condition:** every financial outcome is explainable from service through ledger settlement.

## Phase 6 — Interoperability and digital public infrastructure

- approved implementation guide and conformance test suite
- standards-based patient, provider, facility and terminology services
- document exchange
- consent-aware HIE adapter
- national reporting interfaces
- partner sandbox and certification process
- API lifecycle/deprecation programme
- portable patient summary and verifiable credentials where supported

**Exit condition:** external systems integrate through governed contracts, not custom database access.

## Phase 7 — Public health, analytics and research

- governed operational warehouse
- de-identification/pseudonymization service
- cohort and quality-measure engine
- public-health reporting and surveillance
- small-cell suppression and export controls
- OMOP-compatible research model
- research consent and data-access committee workflow

**Exit condition:** secondary use cannot compromise treatment operations or patient rights.

## Phase 8 — Governed HealthPilot Copilot

Start only after clinical governance, terminology and data quality are mature.

Safe early uses:

- navigation and service discovery;
- administrative summarization;
- document classification;
- draft referral/visit summaries;
- coding suggestions;
- translation support;
- no-show and capacity forecasting.

Higher-risk clinical functions require model registration, intended-use definition, bias and safety evaluation, human approval, version pinning, monitoring and rollback. AI output must never silently become a signed clinical record.

## Permanent modernization cycle

Every year:

1. review data formats and cryptography;
2. test full export and restore;
3. rehearse vendor exit;
4. review terminologies and clinical content;
5. review access policies and patient rights;
6. review incident and near-miss trends;
7. deprecate obsolete APIs with a documented migration period;
8. update the architecture decision record.
