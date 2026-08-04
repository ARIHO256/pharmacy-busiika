# Deep Role Experiences and Page Implementation

This release converts the broad 21-section foundation into a much deeper role-oriented user experience. It does not remove the existing patient, clinician, hospital, pharmacy, laboratory, insurance, finance, governance, interoperability or security modules. The work extends them with dedicated page centres, tailored dashboards, searchable entity selection, specialist visualisations and richer seeded operational data.

## Coverage summary

- 37 account and staff roles have an explicit home route.
- 382 unique deep pages are represented in the page catalogue.
- 971 role-to-page links are available after shared clinical and operational responsibilities are included.
- 16 static portals expose a complete role page centre.
- All enterprise specialist-role portals expose their own page centre under the same role route.
- 81 structured enterprise workflow schemas remain connected to frontend workspaces.

Run the dependency-free coverage audit with:

```bash
node scripts/audit-deep-pages.mjs
```

## Dashboard redesign

The former common enterprise dashboard has been replaced with role-sensitive blueprints and data returned by `GET /api/v1/enterprise/dashboard/role/`. Dashboard metrics, queues, control lists, priority work and shortcuts now change for the active role and organization context.

Tailored blueprints include medical director, clinical officer, dentist, physiotherapist, nutritionist, psychologist, midwife, records officer, accountant, finance manager, procurement officer, quality officer, compliance officer, HR officer, IT support, claims reviewer, anaesthetist, ambulance dispatcher, paramedic, radiographer, storekeeper and insurance officer.

The pharmacist, laboratory professional, radiology, emergency/ambulance and theatre/anaesthesia portals now also have dedicated operational dashboards instead of reusing organization dashboards or worklist pages.

## Role page centres

Each supported portal now includes a **Complete page centre**. It groups pages by actual professional responsibility rather than displaying a flat list of generic records.

Examples include:

- Patient: appointment details, waiting room, result trends, admission, insurance, privacy, documents, caregivers and dependent dashboards.
- Doctor and allied clinicians: patient chart, result inbox, order entry, certificates, rounds, handover, templates and professional governance.
- Nursing: assigned patients, eMAR, due and overdue medicines, fluid balance, early warning, transfusion, handover and discharge.
- Reception: scheduling calendar, provider capacity, arrival board, referrals, admission registration, printing and call-centre work.
- Records: master patient index, duplicate comparison, merge/unmerge, correction, release, legal hold, archival and export.
- Finance: split payments, reconciliation, accounts receivable/payable, journals, general ledger, statements, budgets and forecasting.
- Pharmacy: clinical dispensing, labels, controlled medicines, recalls, transfers, counts, cold chain, quarantine and valuation.
- Laboratory: collection, accessioning, barcode, aliquot, storage, results, validation, microbiology, blood bank, calibration and QC.
- Radiology: scheduling, modality worklist, PACS viewer, reporting, verification, critical results, dose and exports.
- Emergency: call intake, dispatch map, telemetry, trauma, resuscitation, observation, transfer, mass casualty and offline paramedic work.
- Theatre: schedule, preparation, consent, anaesthesia, intraoperative charting, counts, implants, recovery, sterilisation and utilisation.
- Maternity: antenatal care, high-risk pregnancy, partograph, delivery, newborn, postnatal, immunisation, growth and family planning.
- Facility: branches, licences, departments, rooms, bed map, discharge clearance, workforce, equipment, quality and regulatory reporting.
- Insurance: members, plans, network, contracts, tariffs, eligibility, preauthorisation, claim adjudication, appeals, fraud and settlement.
- Administration: user and organization detail, verification, reconciliation, delivery monitoring, CMS, dead letters, audit, security, backup and configuration.

## Searchable entity selection

Clinical and operational forms no longer depend on staff manually entering internal database identifiers. The `EnterpriseEntityLookupView` provides scoped patient, staff, admission and appointment lookups.

The frontend `EntitySearchSelect` adds debounced search and descriptive results showing patient identity, staff role and department, admission ward and appointment context.

## Purpose-built clinical and operational visualisations

The deep workspaces include dedicated views rather than rendering every workflow as an ordinary text form:

- visual partograph;
- anaesthesia and intraoperative trends;
- fluid-balance comparison;
- electronic medication-administration board;
- observations and early-warning score;
- growth chart;
- laboratory quality-control trend;
- cold-chain monitoring;
- radiation-dose dashboard;
- live ambulance/incident map;
- surgical count controls;
- SBAR handover board;
- patient-context clinical board;
- specimen pipeline;
- theatre stage board;
- maternity safety board;
- insurance adjudication board;
- facility operations board.

## Management console improvements

The shared management console now supports create, edit, view, activate/deactivate, controlled delete, pagination, search, saved query, column selection, multi-selection, CSV export, print, action reasons and activity/configuration tabs.

The record workspace supports draft autosave, unsaved-change warning, entity search, attachment upload, status transitions, workflow audit, print, CSV export, pagination and visual clinical summaries.

## Public and system pages

The React application now includes public routes for About, Contact, Help, FAQs, Pricing, directories, public provider profiles, Privacy, Terms, Medical Disclaimer, Cookie Notice, Accessibility, Data Processing, Browser Compatibility and platform status. Dedicated 403, 404, 500, maintenance and offline pages are also present.

The authenticated top bar now checks the readiness endpoint and displays Operational, Degraded, Offline or Checking rather than using a static connected label.

## Demonstration data

The enterprise seed still creates a record for every workflow schema and all demonstration role contexts. It now additionally creates time-series records for partograph, anaesthesia, observations, fluid balance, growth, laboratory QC, cold chain, radiation dose, ambulance telemetry, medication administration, handover and surgical counts. This makes dashboards and charts populated immediately after seeding.

## Validation

Run:

```bash
bash scripts/validate-static.sh
```

This validates Python parsing, migration dependencies, URL imports, JavaScript/JSX syntax, model-to-migration sync, role routing, workflow coverage, deep-page coverage, frontend relative imports, JSON and deployment YAML.

Runtime release gates still require installed dependencies:

```bash
bash scripts/release-gate.sh
```

Real external services require deployment credentials and approved endpoints. These include payment gateways, mobile money, SMS, WhatsApp, push notifications, Zoom, regulator lookups, PACS/DICOM equipment, insurer interchange, object storage and production monitoring destinations.
