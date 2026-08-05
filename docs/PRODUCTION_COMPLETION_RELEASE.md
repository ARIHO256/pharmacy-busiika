# HealthPilot Production Completion Release

This release closes the code-side gates identified during the source audit. It does not fabricate external provider results, clinical approval, legal advice, or disaster-recovery evidence. Promotion is blocked until every automated and human gate has passed for the exact release version.

## Code-side completion

- Every actionable deep page has a canonical adapter. Pages that are intentionally queues, dashboards, reference views, or details are labelled accordingly.
- Cross-domain actions persist an `OperationalAction` in addition to their collaboration `WorkflowCase`.
- Front-desk, facility, insurance, radiology, clinical, finance, pharmacy, laboratory, emergency, theatre, maternity, and administration actions apply bounded domain effects where a canonical model exists.
- Page data no longer silently falls back to an unconfigured generic feed.
- Active role, organization, branch, department, effective permission, and delegation context are the authorization basis. `User.role` is retained only as the registration/default identity.
- Platform, operations, compliance, clinical-safety, and IT authorities are separated.
- Patient clinical access by administrators requires a patient-specific, independently approved, time-limited privileged-access grant.
- Formal release acceptances are stored with reviewer identity, evidence upload, SHA-256 evidence hash, signature time, expiry, and immutable audit history.
- The administrator Release Acceptance Centre displays all mandatory gates and blocks promotion until every gate is current.
- The frontend API/action contract audit validates declared API methods and explicit action-button contracts.
- The final static release audit covers 279 Python files, 52 migrations, 206 backend URL symbols, 166 frontend source files, 37 roles, 81 workflows, 382 pages, 971 role-page links, 444 API calls, and 95 explicit action buttons.

## Automated production gate

Run the full gate on a connected Ubuntu host with Docker, Playwright, and approved sandbox credentials:

```bash
RELEASE_VERSION=2026.08.04 SOAK_HOURS=4 bash scripts/production-acceptance-gate.sh
```

The gate performs source audits, image builds, PostgreSQL migration and seed, backend tests, full-stack startup, 37-role smoke testing, browser testing, provider sandbox checks, backup/restore verification, a multi-service soak, and formal release-readiness verification.

## What cannot be auto-approved

The following require independent qualified people and real evidence:

- Doctor, nursing/midwifery, laboratory, pharmacy, finance, records, and administrator workflow acceptance.
- Privacy and legal approval.
- Clinical-safety approval.
- Security approval.
- Backup/restore exercise evidence.
- Disaster-recovery exercise approval.

Use `/admin/release-acceptance` to upload evidence for the exact release. The application must never create fake acceptance evidence.
