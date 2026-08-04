# Testing Strategy

## Current automated checks

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

The backend suite covers account/profile flows, provider registry, appointments, care relationships, consent, break-glass, clinical access, encounter revisions, prescriptions, payments, laboratory results and interoperability exports.

## Required release test layers

### Unit and domain tests

- transition guards;
- consent dates and recipient rules;
- ledger balance invariants;
- clinical revision immutability;
- terminology validation;
- identity/registry uniqueness.

### API authorization tests

For each sensitive endpoint, test:

- unauthenticated request;
- wrong role;
- correct role but wrong patient/organization;
- revoked or expired consent;
- care relationship present/absent;
- valid and invalid break-glass access;
- administrator access and audit event.

### End-to-end journeys

1. register patient;
2. register and verify provider;
3. create availability;
4. book and pay;
5. conduct consultation;
6. finalize and amend encounter;
7. issue prescription;
8. publish and acknowledge critical result;
9. export patient summary;
10. verify ledger and audits.

### Non-functional tests

- concurrency for slot booking and idempotent payments;
- load and latency;
- object-storage failure;
- payment/video/SMS provider outage;
- backup restoration;
- security scanning and penetration test;
- accessibility and keyboard navigation;
- low-bandwidth behaviour;
- privacy and clinical-safety scenario review.
