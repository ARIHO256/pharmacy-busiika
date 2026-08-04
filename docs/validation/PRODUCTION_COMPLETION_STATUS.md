# Production Completion Status

Release prepared: 2026-08-04

This status separates code-side completion from runtime, provider, and human acceptance. A gate is not marked passed unless evidence exists for this exact release.

## Code and static gates

| Gate | Status | Evidence |
|---|---|---|
| Every actionable deep page has an adapter | Passed | `scripts/workflow-completion-audit.py` reports 259 actionable pages and zero missing adapters. |
| Every non-actionable page is explicitly classified | Passed | 123 pages are classified as dashboards, details, references, record workspaces, or work queues. |
| Frontend API calls resolve to declared client methods | Passed | `scripts/frontend-api-contract-audit.mjs` checked 444 calls. |
| Explicit action buttons have a click, form, or disabled contract | Passed | The same audit checked 95 explicit `type="button"` controls. |
| Empty/decorative acceptance handlers are blocked | Passed | `scripts/frontend-acceptance.mjs`. |
| Active-role authorization source audit | Passed | `scripts/authorization-audit.py`. |
| Role, portal, workflow, and seeded account coverage | Passed | 37 roles, 81 workflow schemas, 382 pages, and 971 role-page links. |
| Python, migration, URL, JS/JSX, import, JSON, and YAML structure | Passed | `production-completion-static-final-2.log`. |

## Implemented acceptance infrastructure

- Clean isolated Docker Compose project for every release gate.
- PostgreSQL migration, drift, seed, and test stage.
- Full-stack service health verification.
- All 37 seeded role login and active-context smoke testing.
- Playwright critical journeys, navigation crawl, button-persistence checks, responsive viewports, accessibility basics, printing, and offline behavior.
- Organization-isolation and privileged-access backend tests.
- Multi-service soak workload with authenticated reads and persistent writes.
- Provider sandbox connectivity checker for mobile money, payment gateways, SMS, WhatsApp, push, Zoom, object storage, PACS, malware scanning, and event delivery.
- Backup creation and restore-verification commands.
- Release Acceptance Centre with evidence upload, SHA-256 evidence hashing, reviewer identity, signature time, expiry, and role-restricted approval.
- Production-readiness command that blocks promotion until every mandatory acceptance is current.

## Gates not executed in this delivery environment

| Gate | Status | Reason / evidence |
|---|---|---|
| Clean PostgreSQL migration and seed | Not executed here | Docker is unavailable. Run `scripts/production-acceptance-gate.sh`. |
| Complete Django runtime suite | Not executed here | The configured Python mirror could not provide Django. See `pip-install-attempt.log`. |
| Vite production build | Not executed here | The configured npm mirror returned 404 for `yaml-2.9.0.tgz`. See `npm-ci-production-completion-attempt.log`. |
| Docker full-stack startup | Not executed here | Docker CLI is unavailable. See `docker-production-completion-attempt.log`. |
| Playwright browser execution | Not executed here | The application stack could not be started. The test suite itself parses and exposes its CLI successfully. |
| Multi-hour soak | Not executed here | Requires the running full stack. |
| Real provider sandbox acceptance | Not executed here | Requires deployment-owned credentials, approved senders, and network access. |
| Qualified professional workflow acceptance | Pending external review | Must be signed by independent doctors, nurses/midwives, laboratory professionals, pharmacists, finance staff, records officers, and administrators. |
| Legal, privacy, clinical-safety, security, backup, and disaster-recovery approval | Pending external review | The application records evidence but cannot make or fabricate these decisions. |

## Authoritative promotion command

```bash
RELEASE_VERSION=2026.08.04 SOAK_HOURS=4 bash scripts/production-acceptance-gate.sh
```

A deployment is not approved for real patient information until that command succeeds and the Release Acceptance Centre reports all mandatory gates as accepted for the exact release and environment.
