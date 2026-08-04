# Clinical Governance and Safety Case Template

## 1. Governance bodies

Before production clinical use, appoint accountable groups for:

- clinical safety and care pathways;
- privacy and security;
- data and terminology governance;
- architecture and integration;
- patient/public representation;
- AI/model governance when applicable.

## 2. Workflow safety case

Every clinical workflow should document:

```text
Workflow name
Clinical owner
Intended users
Intended patient population
Care setting
Clinical objective
Inputs and data quality assumptions
Decision or action produced
Known limitations
Exclusion and emergency criteria
Hazards and mitigations
Test cases
Training requirements
Monitoring indicators
Version and effective date
Withdrawal/rollback procedure
```

## 3. High-priority workflows

Complete safety cases first for:

- emergency symptom routing;
- remote-consultation suitability;
- patient identity matching;
- allergy and medication display;
- prescription issuance and pharmacy transfer;
- critical laboratory result escalation;
- referral handover;
- break-glass record access;
- record correction/amendment;
- payment failure that could interrupt care.

## 4. Incident model

Recommended severity levels:

```text
Near miss
No harm
Low harm
Moderate harm
Severe harm
Death
```

Record occurrence time, discovery time, patient/encounter, immediate action, investigation, root cause, corrective action, owner and closure evidence.

## 5. Clinical content lifecycle

Clinical forms, value sets, order sets and rules require:

```text
Draft → multidisciplinary review → test → approval → controlled release
      → monitoring → scheduled review → update or withdrawal
```

Do not embed high-risk clinical rules only inside frontend components. Keep versioned knowledge artefacts with test fixtures and approval metadata.
