# Security, Privacy and Clinical-Safety Guide

## 1. Security model

MyDoctor uses layered decisions rather than trusting role alone:

```text
Authentication
  → account active/verified state
  → role permission
  → object ownership or organization context
  → care relationship
  → patient consent and permitted data category
  → emergency break-glass where applicable
  → append-only audit event
```

## 2. Controls already present

- Django password validators with a 10-character minimum for public registration
- JWT access token lifetime and rotating/blacklisted refresh tokens
- anonymous and authenticated throttling
- object-level clinical access resolver
- executable consent and revocation
- time-limited break-glass access
- append-only governance events
- private-resource intent in the data model
- upload-size limits
- environment-driven secrets, hosts, CORS and database settings
- production HTTPS/HSTS/cookie defaults
- denial of framing and MIME sniffing
- request correlation IDs
- database readiness probe

## 3. Required production controls

The repository does not replace an operational security programme. Before real clinical use, implement:

1. **Identity** — MFA/passkeys for clinicians and administrators, secure recovery, device/session inventory and step-up authentication.
2. **Secrets** — managed secret vault, rotation, least-privilege service identities and no secrets in source control.
3. **Files** — private object storage, malware scanning, content-type validation, quarantine, encryption and short-lived signed downloads.
4. **Infrastructure** — WAF, rate limits at the edge, network segmentation, hardened images, patch management and vulnerability scanning.
5. **Database** — PostgreSQL, encrypted storage, restricted administrative access, automated backup, point-in-time recovery and restoration tests.
6. **Monitoring** — centralized immutable audit retention, security alerts, anomaly detection and incident response on call.
7. **Integrations** — signed webhooks, replay prevention, idempotency, certificate/key rotation and partner allow-listing.
8. **Data lifecycle** — approved retention schedule, legal holds, archival, export, correction and deletion procedures.
9. **Suppliers** — privacy/security assessment and exit plan for every video, payment, cloud, messaging and AI provider.
10. **Testing** — SAST, dependency scanning, DAST, penetration testing and access-control regression tests.

## 4. Data classification

Recommended classes:

| Class | Examples | Minimum handling |
|---|---|---|
| Public | marketing pages, verified public provider directory | integrity and availability controls |
| Internal | operational dashboards without patient detail | authenticated access |
| Confidential | account and financial data | encryption and strict role/object access |
| Clinical restricted | encounters, diagnoses, prescriptions, results | consent/care-relationship decision plus audit |
| Highly restricted | selected mental, reproductive, genetic or safeguarding records | segmented policy and explicit authorization |
| Emergency only | minimum emergency summary | time-bound break-glass and review |

The current model provides a confidentiality foundation but does not yet implement a complete segmented-record policy engine.

## 5. Audit events

Security-relevant actions should include:

- actor and role;
- patient context;
- purpose of use;
- decision;
- resource type and identifier;
- request/correlation ID;
- source IP and user agent;
- emergency flag;
- timestamp and metadata.

Never write passwords, OTP values, access/refresh tokens, full card data, API secrets or unrestricted clinical note bodies into application logs.

## 6. Clinical-safety controls

Every clinical workflow should have an accountable clinical owner. Before release:

- define intended users and patient population;
- define exclusions and emergency escalation;
- approve data fields and terminology;
- test normal, boundary and hazardous scenarios;
- document override rules;
- monitor incidents and near misses;
- maintain version and withdrawal procedures.

AI-generated clinical text must remain a draft until a qualified clinician explicitly reviews and signs it.

## 7. Data-protection programme

Complete a formal data-flow inventory and impact assessment covering:

- registration and identity documents;
- appointment and clinical data;
- telemedicine;
- pharmacy, laboratory and insurance exchanges;
- payments;
- analytics;
- cross-border processors;
- retention and archival;
- support access;
- patient rights and complaint handling.

Consent does not replace every legal basis. Treatment, payment, statutory reporting, public health and research may require different policy and legal analysis.

## 8. Incident response

Maintain runbooks for:

- compromised account;
- lost device;
- inappropriate record access;
- incorrect patient merge;
- wrong prescription or critical-result delay;
- payment fraud;
- malware upload;
- ransomware;
- vendor outage;
- data exfiltration;
- integrity corruption.

Each runbook should state containment, clinical continuity, evidence preservation, notification, recovery and post-incident review.
