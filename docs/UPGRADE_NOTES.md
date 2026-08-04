# Upgrade Notes for the Enhanced HealthOS Edition

## 1. Preserve the original database

Before migrating an existing installation:

```bash
cp backend/db.sqlite3 backend/db.sqlite3.pre-healthos
```

For production PostgreSQL, use a database-native consistent backup and verify that it can be restored.

## 2. Environment

```bash
cd backend
cp .env.example .env
```

Review secret, host, CORS, database, JWT and payment settings. `MOCK_PAYMENTS` must be false in production.

## 3. Dependencies and migrations

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py check
python manage.py migrate
python manage.py sync_provider_registry
```

New migrations introduce:

- appointment status history and slot constraints;
- governance records;
- longitudinal clinical records;
- registry organizations, roles, credentials and care relationships;
- ledger/journal/posting records;
- prescription version/signature fields and public numbers;
- structured laboratory results and critical acknowledgements;
- terminology, mappings and outbox events.

Data migrations backfill appointment status history, provider organizations and existing identifiers where applicable.

## 4. Seed/demo synchronization

For a local demo:

```bash
python seed.py
```

The seed is idempotent for the included demo data. It is not a production data migration tool.

## 5. API compatibility

Existing `/api/` routes remain available. Use `/api/v1/` for new integrations.

## 6. Frontend

```bash
cd frontend
cp .env.example .env
npm ci
npm run build
```

The frontend adds:

- Patient Health Record, consent and FHIR draft export
- Doctor Clinical Workspace and credential registry
- Administrator Compliance and Provider Registry pages
- Structured laboratory-result interfaces
- expanded semantic design tokens

## 7. Verification

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Then smoke-test each role and confirm:

- provider organization synchronization;
- doctor credential submission and administrator verification;
- appointment booking and duplicate-slot protection;
- encounter finalization and amendment;
- patient consent/revocation;
- emergency access review;
- lab critical-result acknowledgement;
- invoice posting and receipt;
- FHIR draft export;
- health probes and `X-Request-ID`.
