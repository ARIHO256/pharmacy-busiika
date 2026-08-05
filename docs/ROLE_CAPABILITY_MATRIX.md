# Role Capability & Gap Matrix

Assessment date: 2026-08-04. Legend:
**Active** = the role can perform its core job end-to-end through real endpoints.
**Partial** = core actions exist, but some expected capabilities are missing or read-only.
**Ceremonial risk** = dashboards exist but little/no actionable work reaches the role.

This matrix was produced from the live codebase (portals, `allowed_roles` on
every API view, the visit engine in `workforce`, and the seeded demo data), and
from browser-level acceptance runs against the seeded stack.

## The headline finding

The backend engines for almost every workflow exist and are role-gated. The
historic problem was **data flow**: work rarely propagated between roles, so
most portals looked empty/ceremonial. Fixes landed in this release:

- Cross-party notifications: appointment→doctor, store order→pharmacy, lab
  order→lab, lab result→referring doctor, hospital booking→hospital, Rx→pharmacy.
- One inventory truth: store catalog and staff stock pages are synced both ways
  (`Medicine.inventory_item` + FEFO batch consumption + movement audit trail).
- The outpatient visit engine now auto-advances: lab order → `laboratory`,
  result released → `waiting_clinician`, prescription → `pharmacy`,
  dispensing → `billing`, invoice paid → `completed`
  (`workforce.services.advance_active_visit`).
- `seed_workflow.py` populates every visit stage so each role has live work.

## Clinical roles

| Role | Can do today | Gaps |
|---|---|---|
| doctor | Confirm/complete appointments, consult (chat+video), encounters/SOAP, prescribe, refer (closed-loop), order labs, availability, earnings, profile+photo | Visit queue is appointment-centric; walk-in clinic queue needs a dedicated doctor view (visits endpoint exists, portal surfaces it only via dashboards) |
| nurse | Triage with vitals (TriageRecord), drive visit stages, ward tasks, medication administration, notes | Medication administration is not yet linked back to the originating prescription item |
| midwife | Antenatal dashboards, partograph pages, maternity episodes (operations) | Maternity pages partly generic (visual partograph is a schema-driven board) |
| clinical_officer / dentist / physiotherapist / nutritionist / psychologist | Bookable provider flows (appointments, availability, consult) via shared doctor machinery | No specialty-specific charting; share generic deep pages |
| theatre_nurse / anaesthetist | Theatre cases, ward tasks (theatre mode), safety checklists | Anaesthesia chart is a generic fallback page, not a bespoke chart |
| paramedic / ambulance_dispatcher | Dispatch board, ambulance fleet/tracking (operations), offline-paramedic fallback page | Dispatch ↔ hospital handover not linked to visits |
| medical_director | Oversight dashboards, safety cases, quality | Read-heavy by design |

## Pharmacy & diagnostics

| Role | Can do today | Gaps |
|---|---|---|
| pharmacy (org) | Full medicine catalog CRUD, store orders, suppliers, rx orders, dispensing; stock now unified with operations inventory | Purchase orders not linked to catalog restocking (procurement module is hospital-side) |
| pharmacist | Verified dispensing with quantity guards, rx queue, stock pages fed by unified inventory | Controlled-drug register is schema-driven, not a bespoke register |
| lab (org) / lab_technician | Tests/panels catalog, orders lifecycle, specimen custody, result entry + release, critical acknowledgements; gets order notifications | Analyser integration is external by design |
| radiologist / radiographer | Imaging orders, reporting editor, PACS viewer page (Orthanc external) | PACS viewer uses placeholder references until Orthanc is configured |
| records_officer | MPI duplicate scanning, merge candidates, record release | Merge execution (actual record consolidation) not implemented |

## Finance & access

| Role | Can do today | Gaps |
|---|---|---|
| cashier | Invoices, cash/card/wallet payment recording, receipts + print, shifts open/close, float reconciliation | — |
| accountant / finance_manager | Ledger, journal posting, adjustments/refunds workflow, earnings/payouts | Financial reports are dashboard-level; no period close/lock |
| insurance (org) / insurance_officer / claims_reviewer | Policies, benefit rules, coverage enrolment, eligibility checks (audited), preauthorization, claims adjudication, remittances | Insurer interchange formats are connector-specific (external) |

## Administration & operations

| Role | Can do today | Gaps |
|---|---|---|
| admin | User verify/suspend/activate, role matrix, registry oversight, finance, operations, compliance/audit, CMS, release acceptance centre, backups | — (fullest portal) |
| hospital (org) / facility_manager | Services, beds/wards, bookings, staff, departments, multi-branch dashboards, admissions | — |
| receptionist | Patient directory, check-in (creates visit + queue number), queue board, appointment calendar | — |
| hr_officer | Staff invitations, memberships, departments, granular facility roles/permissions | Payroll out of scope |
| procurement_officer / storekeeper | Purchase orders, stock movements, inventory batches | Store PO receipt does not yet auto-create inventory batches |
| quality_officer / compliance_officer | Audit trails, consent oversight, security operations, quality registers | Reports are pull-based |
| it_support | Support tickets, security operations, notification console | — |

## Remaining systemic gaps (prioritized)

1. **Doctor walk-in queue view** — the visit engine feeds `waiting_clinician`
   but the doctor portal is appointment-centric; surface the clinic queue.
2. **165 of 382 deep pages** render through generic queue/record fallbacks
   rather than bespoke screens (anaesthesia chart, birth record, blood bank,
   partograph…). Prioritize high-acuity pages.
3. **Provider dashboards** (pharmacy/lab/hospital/insurance org accounts,
   insurance_officer, claims_reviewer) had rendering crashes in the last
   browser run — under investigation.
4. **E2E console-error policy**: pages whose APIs legitimately 403 for a role
   log browser errors; nav should hide unauthorized entries instead.
5. **External integrations** (payments, SMS, PACS, analysers) remain
   credential/configuration work, not code gaps.
