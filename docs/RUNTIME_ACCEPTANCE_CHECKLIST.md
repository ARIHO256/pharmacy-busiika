# Runtime Acceptance Checklist

This checklist is the final gate between source delivery and a deployment that may handle real health information.

## 1. Local full-stack demonstration

```bash
cp .env.compose .env.compose.local
# Optional: edit .env.compose and docker-compose.yml values for your machine.
docker compose up --build
```

The bundled `.env.compose` is development-only and automatically loads demonstration data. Expected services:

- Web application: `http://localhost:3000`
- API: `http://localhost:4000`
- Mailpit: `http://localhost:8025`
- Orthanc: `http://localhost:8042`
- RabbitMQ management: `http://localhost:15672`
- Flower: `http://localhost:5555`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3001`

Run:

```bash
curl -f http://localhost:4000/healthz
curl -f http://localhost:4000/readyz
docker compose exec backend python manage.py verify_demo_data
```

## 2. Source and runtime gate

```bash
bash scripts/validate-static.sh
bash scripts/release-gate.sh
```

The full release gate must pass in a network-connected environment before release.

## 3. Role acceptance

For each account in `docs/DEMO_DATA.md`:

- Log in successfully.
- Confirm the expected role dashboard opens.
- Activate another valid role context where supplied.
- Confirm unrelated modules are hidden.
- Attempt at least one forbidden API and confirm HTTP 403.
- Create, update and transition at least one assigned workflow record.
- Confirm organization/branch/department isolation.

## 4. Clinical acceptance

Qualified clinicians must test:

- Outpatient consultation and amendment.
- Nursing and medication-administration workflow.
- Inpatient admission, transfer, observation, handover and discharge.
- Antenatal, partograph, delivery, newborn and immunization records.
- Theatre, anaesthesia, checklist, operation and recovery records.
- Emergency, ambulance and pre-hospital care.
- Laboratory order-to-release and critical-result escalation.
- Radiology order-to-report and critical-result escalation.
- Prescription safety, dispensing, inventory deduction and recall.

## 5. Financial acceptance

- Validate invoice totals, taxes, discounts, deposits and partial payments.
- Test mobile-money/card sandbox callbacks and duplicate webhook delivery.
- Reconcile gateway, cashier and ledger totals.
- Test refund, credit/debit adjustment and period close.
- Verify PDFs and thermal-print layouts.
- Test insurance eligibility, preauthorization, claim, query, resubmission and remittance.

## 6. Integration acceptance

- Publish a versioned event to Kafka and RabbitMQ.
- Force delivery failure, confirm dead-letter state, then replay.
- Create/read/update/version a FHIR resource with scoped credentials.
- Connect a test PACS/modality and open a study in the configured viewer.
- Verify SMS, email, WhatsApp and push delivery callbacks.
- Verify regulator/OCR integration against approved non-production records.

## 7. Security and privacy acceptance

- Run dependency, container and infrastructure scans.
- Upload clean, invalid and known test-malware files; verify quarantine/fail-closed behavior.
- Test MFA, lockout, reset, session revocation and break-glass review.
- Validate audit immutability and least privilege.
- Complete DPIA, threat model, penetration test and clinical-safety case.
- Verify encryption, secret rotation, retention and deletion.

## 8. Reliability and recovery

- Load-test the API, WebSocket, Celery and database tiers.
- Test worker loss, broker loss, storage loss and provider failover.
- Execute backup and restore into an isolated environment.
- Measure RPO/RTO and record evidence.
- Configure alert destinations and on-call escalation.

## 9. Production approval

Production approval requires signatures from:

- Product owner
- Medical director / clinical-safety owner
- Data-protection or compliance officer
- Security lead
- Infrastructure lead
- Finance/payment owner
- Facility operations representative

Do not process real patient data until all applicable checks pass.

## Production acceptance workflow release additions

- [ ] Run `python scripts/authorization-audit.py` and resolve every unsafe direct acting-role check.
- [ ] Run `node scripts/frontend-acceptance.mjs` and resolve empty handlers or hard-coded acceptance values.
- [ ] Seed all 37 role identities, then run `python scripts/runtime-role-smoke.py --base http://127.0.0.1:4000/api`.
- [ ] Verify a platform/operations administrator cannot self-approve clinical elevation.
- [ ] Verify compliance and clinical-safety reviewers can approve only independently requested grants.
- [ ] Verify IT support cannot read patient charts, manage identities or view unrestricted finance data.
- [ ] Verify expired/revoked grants stop clinical access immediately.
- [ ] Verify active role, organization, branch and department changes affect both navigation and API authorization.
- [ ] Test unsent offline drafts: they must remain visibly unsent, must not create server records, and must support retry/discard.
- [ ] Confirm live notification, payment, storage, PACS and regulator adapters never fall back to mock success in production.
