# HealthPilot HealthOS Architecture

## 1. Architecture objective

HealthPilot is structured as a connected-care platform rather than a single booking application. The codebase deliberately separates replaceable user experiences from durable clinical, governance, registry and financial records.

The present implementation uses a **modular Django monolith**. This is intentional: transactional consistency, simpler deployment and clear domain boundaries are more valuable at this stage than premature microservices. Modules may later be extracted only when scale, security boundaries, independent deployment or team ownership justify it.

## 2. Logical planes

```text
┌────────────────────────────────────────────────────────────┐
│ Experience plane                                           │
│ Patient • Doctor • Pharmacy • Lab • Hospital • Insurance  │
│ Administrator • Responsive web/PWA-ready React shell       │
└────────────────────────────────────────────────────────────┘
                           │
┌────────────────────────────────────────────────────────────┐
│ API and access plane                                       │
│ JWT • role checks • object checks • care relationships     │
│ consent decisions • break-glass • throttling • request ID  │
└────────────────────────────────────────────────────────────┘
                           │
┌────────────────────────────────────────────────────────────┐
│ Domain plane                                               │
│ Accounts • Appointments • Communication • Clinical         │
│ Prescriptions • Laboratory • Pharmacy • Hospital           │
│ Insurance • Payments • Reviews                             │
└────────────────────────────────────────────────────────────┘
                           │
┌────────────────────────────────────────────────────────────┐
│ Trust and platform plane                                   │
│ Governance • Registry • Terminology • Audit • Outbox       │
│ Ledger • File metadata • Health probes                     │
└────────────────────────────────────────────────────────────┘
                           │
┌────────────────────────────────────────────────────────────┐
│ Data and integration plane                                 │
│ PostgreSQL • private object storage • FHIR adapter          │
│ event broker (planned) • national/partner adapters         │
└────────────────────────────────────────────────────────────┘
```

## 3. Backend bounded contexts

### Accounts

Authentication accounts and role-specific portal profiles. The canonical facility identity is no longer only a provider profile; provider profiles synchronize into the registry.

Current limitation: `User` still carries a single primary role. A future identity programme should separate `Person`, `Account`, `Patient`, `Practitioner`, `RelatedPerson` and organization membership without breaking existing identifiers.

### Registry

Durable master records for:

- organizations and locations;
- practitioner credentials;
- practitioner affiliations/roles;
- patient-practitioner care relationships.

Provider registration creates a pending canonical organization. Provider profile updates synchronize organization name, licence and contact information. Verification status remains administrator controlled.

### Appointments

Responsible for availability, slot generation, booking and lifecycle transitions. It enforces database-level slot constraints, keeps status history and creates treatment access evidence.

### Clinical

The longitudinal clinical context includes:

- `ClinicalEncounter` and immutable `EncounterRevision` snapshots;
- allergies;
- conditions;
- medication statements;
- observations;
- referrals;
- care plans;
- patient summary and timeline selectors.

A final encounter is not silently edited. Amendments create a new revision and retain the signed history.

### Governance

Executable consent, emergency break-glass and append-only access/audit events. Clinical reads use role, patient identity, care relationship, consent and emergency context rather than role alone.

### Finance

Operational invoices and provider earnings are supported by an immutable accounting foundation:

```text
LedgerAccount → JournalEntry → Posting
```

Corrections should use reversing entries; posted financial history must not be rewritten.

### Interoperability

The implementation contains:

- a terminology concept catalogue;
- concept-mapping storage;
- a transactional outbox;
- an R4-aligned draft patient-summary bundle;
- a draft CapabilityStatement.

This is an adapter foundation, not a certified FHIR server or national implementation guide.

## 4. Data ownership rules

| Data | System of record |
|---|---|
| Login and portal identity | Accounts |
| Facility/provider identity | Registry |
| Slot and appointment lifecycle | Appointments |
| Clinical facts and encounter revisions | Clinical |
| Patient access permission | Governance |
| Prescription intent | Prescriptions |
| Laboratory order/result | Services laboratory domain |
| Money movements | Ledger/Payments |
| External event delivery state | Interoperability outbox |

A module may reference another module's identifier, but it should not duplicate or directly mutate the other module's authoritative state.

## 5. Clinical record invariants

1. Clinical facts identify the patient, author, source, clinical time and recorded time.
2. Patient-reported information remains distinguishable from clinician-verified information.
3. Final notes are amended, not overwritten.
4. A status transition has an actor and timestamp.
5. Sensitive reads create an audit event.
6. Emergency access is time-bound and reviewable.
7. FHIR export is generated from authoritative operational/clinical models; FHIR JSON is not the only database model.

## 6. Event architecture

Critical changes create an `OutboxEvent` inside the same database transaction as the business record. The included management command demonstrates safe publication state changes:

```bash
python manage.py publish_outbox
```

A production deployment must replace the demonstration publisher with a durable broker adapter, retry policy, dead-letter handling, metrics and idempotent consumers.

Typical events include:

- appointment booked/confirmed/cancelled;
- consent granted/revoked;
- encounter finalised/amended;
- prescription issued/sent;
- laboratory result published/acknowledged;
- payment posted.

## 7. API compatibility

`/api/` remains available for the original React application. The same route table is mounted at `/api/v1/` for new integrations. Breaking changes should be delivered through a new major API prefix and a documented deprecation window.

## 8. Production topology

```text
CDN/WAF
   │
Load balancer / Nginx
   ├── React static assets
   ├── Django API instances
   └── future WebSocket/video gateway
          │
          ├── PostgreSQL primary + backups
          ├── Redis/job queue
          ├── object storage
          ├── event broker
          ├── email/SMS/push adapters
          ├── payment adapters
          └── observability platform
```

SQLite, local media and synchronous notification behaviour are development conveniences, not the production target.

## 9. Extraction criteria

Do not split a module merely because microservices sound modern. Extract only when at least one condition is true:

- independent scaling is measurably required;
- the module needs a stronger security or compliance boundary;
- independent release cadence provides clear operational value;
- another team owns the entire domain;
- heavy workloads threaten the operational API;
- external standards require a dedicated conformance boundary.

Likely later candidates are notifications, video, payment orchestration, integration/FHIR, search, analytics and imaging.
