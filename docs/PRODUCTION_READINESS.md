# Production Readiness and Deployment Gate

The repository contains production-oriented infrastructure, but deployment is not achieved merely by setting `DJANGO_DEBUG=false`. Complete every gate below for the target country, facility and hosting environment.

## Required secrets and integrations

Configure outside source control:

- Django secret key and allowed hosts.
- PostgreSQL credentials and TLS mode.
- Redis/Celery endpoints.
- SMTP credentials.
- SMS, push and WhatsApp provider credentials.
- Flutterwave or Paystack credentials and signed webhook secrets.
- Private S3-compatible storage credentials and encryption settings.
- Outbox destination, bearer token and HMAC key.
- Error monitoring, metrics and log shipping.

## Mandatory operational controls

- HTTPS at the load balancer and secure cookies.
- Private database and Redis networks.
- Least-privilege object-storage policy.
- Malware scanning for uploaded documents and clinical attachments.
- Encrypted, versioned backups.
- Documented restore test.
- Database point-in-time recovery where available.
- Credential rotation procedure.
- Incident response and breach workflow.
- Audit retention and review schedule.
- Disaster recovery objectives.
- Staff onboarding/offboarding process.
- Support escalation and clinical-safety incident ownership.

## Release validation

Run in an environment with package and container access:

```bash
make backend-install
make check
make test
make frontend-install
make frontend-build
cp .env.production.example .env.production
# edit secrets and provider settings
docker compose config
docker compose up --build
```

Then validate:

- Every demo role can sign in and reaches only its portal.
- Restricted APIs reject unauthorized roles.
- A doctor cannot publish availability before verification.
- An expired/suspended licence blocks restricted actions.
- A receptionist cannot read clinical notes.
- A cashier cannot change clinical data.
- A storekeeper cannot clinically dispense medicine.
- Result entry, validation and release are separate actions.
- A patient cannot view an unreleased result.
- Signed encounters require an amendment instead of silent editing.
- Break-glass access is time-bound and audited.
- Payment webhooks are signed and idempotent.
- PDFs and emailed invoices contain correct totals.
- Celery retries notifications and outbox events.
- S3 objects are private and signed URLs expire.
- Backup restoration works.
- Load tests cover login, provider search, slot booking, queue, records and notifications.
- Accessibility and browser tests pass.

## External or site-specific integrations

These cannot be activated generically without the chosen supplier and credentials:

- National professional-regulator lookups.
- AI/OCR licence screening provider.
- PACS/DICOM archive.
- Laboratory analyser interfaces.
- National health-information exchange.
- Insurer-specific claims interchange.
- Fiscal/e-invoicing authority integration.
- Mobile-money merchant configuration.

The data model, protected documents, outbox and connector boundaries are prepared for these integrations. They must be implemented and certified against the selected external systems before use.

## Clinical and legal acceptance

Before real use, qualified representatives must approve:

- Registration and credentialing policy.
- Emergency access.
- Consent and guardian authority.
- Nursing, medication, laboratory, radiology, theatre, maternity and discharge forms.
- Prescription and controlled-medicine procedures.
- Result-release and critical-result communication.
- Record retention, correction, export and deletion policies.
- Patient-facing wording and clinical disclaimers.
- Applicable privacy, telemedicine, pharmacy, laboratory and professional-practice requirements.
