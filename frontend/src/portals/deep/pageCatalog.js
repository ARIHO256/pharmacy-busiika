const page = (slug, label, group, icon, description, source = 'enterprise', recordTypes = [], variant = 'queue') => ({ slug, label, group, icon, description, source, recordTypes, variant })
const make = (group, icon, source, variant, rows) => rows.map(([slug, label, description, recordTypes = []]) => page(slug, label, group, icon, description, source, recordTypes, variant))

const patient = [
  ...make('Appointments & access','calendar','appointments','timeline',[
    ['appointment-detail','Appointment details','Review appointment status, clinician, instructions and the complete event timeline.'],
    ['reschedule-appointment','Reschedule appointment','Choose another verified slot while preserving payment and referral context.'],
    ['cancel-refund','Cancellation & refund','Cancel safely, see refund eligibility and track the financial reversal.'],
    ['virtual-waiting-room','Virtual waiting room','Complete readiness checks, see queue position and join the care session.'],
  ]),
  ...make('Consultation & communication','message','conversations','conversation',[
    ['consultation-detail','Consultation details','Review consultation notes, care instructions, attachments and follow-up actions.'],
    ['secure-conversation','Secure conversation','Open a protected patient–care-team conversation with delivery and read status.'],
  ]),
  ...make('Medicines','pill','prescriptions','medication',[
    ['prescription-detail','Prescription details','Review medicine, dosage, duration, dispensing status and prescriber instructions.'],
    ['refill-request','Refill request','Request a clinically reviewed repeat supply without creating an unsafe duplicate.'],
    ['medication-adherence','Medication adherence','Track doses, reminders, missed medicines and adherence progress.'],
    ['allergy-medication-card','Allergy & medication card','Maintain a portable medication and allergy safety summary.'],
  ]),
  ...make('Diagnostics','flask','enterprise','clinical',[
    ['laboratory-order-detail','Laboratory order','See requested tests, collection instructions, specimen progress and billing.', ['analyzer_result']],
    ['laboratory-result-trends','Laboratory result trends','Compare released results across time with reference-range context.', ['analyzer_result','reference_range']],
    ['imaging-order-detail','Imaging order','Review preparation, acquisition status, report release and critical alerts.', ['modality_worklist','structured_report']],
    ['diagnostic-viewer','Diagnostic image viewer','Open authorised DICOM/PACS studies and compare prior imaging.', ['structured_report','radiation_dose']],
  ]),
  ...make('Hospital care','hospital','admissions','care',[
    ['admission-detail','Admission details','See ward, bed, attending team, active tasks and discharge plan.'],
    ['ward-care-team','Ward & care team','Know the current ward, responsible staff and planned care.'],
    ['discharge-summary','Discharge summary','View signed diagnosis, procedures, medicines, advice and follow-up.'],
    ['referral-detail','Referral details','Track referral acceptance, booking, specialist feedback and closure.'],
  ]),
  ...make('Insurance & finance','insurance','claims','finance',[
    ['insurance-policy-detail','Insurance policy','Review benefits, exclusions, limits, deductible and copayment.'],
    ['preauthorization-detail','Preauthorization','Track requested service, evidence, payer questions and decision.'],
    ['claim-detail','Claim details','Follow line items, decisions, patient responsibility and remittance.'],
    ['payment-methods','Payment methods','Manage approved payment methods and mobile-money preferences.'],
    ['mobile-money-status','Mobile money status','Track collection request, confirmation, timeout or reversal.'],
    ['receipt-detail','Receipt details','Review, download, print and verify an issued receipt.'],
  ]),
  ...make('Records, privacy & family','shield','enterprise','records',[
    ['medical-documents','Medical documents centre','Securely view, classify and download authorised clinical documents.', ['scanned_document']],
    ['consent-centre','Consent centre','Grant, review and revoke care, sharing and communication consent.'],
    ['privacy-requests','Privacy requests','Request access, correction, restriction, portability or deletion review.', ['release_information','record_correction']],
    ['emergency-medical-card','Emergency medical card','Share a minimal emergency summary with allergies, conditions and contacts.'],
    ['notification-inbox','Notification inbox','Read care, billing, security and appointment notifications.'],
    ['family-access','Family access permissions','Control which caregivers can access each dependent and action.'],
    ['caregiver-invitation','Caregiver invitation','Invite a trusted caregiver with time-bound, revocable permissions.'],
    ['dependent-dashboard','Dependent dashboard','Open a separate care view for each authorised dependent.'],
    ['feedback-complaint','Feedback & complaint','Submit, track and respond to a service-quality case.'],
  ]),
]

const doctor = [
  ...make('Patient care','doctor','appointments','clinical',[
    ['my-patients','My patients','Search active care relationships, recent encounters and follow-up needs.'],
    ['patient-detail','Patient chart','Use a persistent patient summary header across all clinical actions.'],
    ['daily-inpatients','Daily inpatient list','Review admitted patients, current ward, severity and discharge readiness.'],
    ['consultation-history','Consultation history','Review prior encounters, amendments and signed clinical notes.'],
  ]),
  ...make('Clinical inbox','clipboard','enterprise','queue',[
    ['results-inbox','Results inbox','Review new laboratory and imaging results requiring clinical action.', ['analyzer_result','structured_report']],
    ['critical-results','Critical results','Acknowledge and act on urgent laboratory and imaging findings.', ['critical_imaging_alert','blood_bank']],
    ['clinical-task-inbox','Clinical task inbox','Prioritise assigned clinical, inpatient and follow-up work.', ['care_plan','handover']],
    ['medication-renewals','Medication renewal requests','Review repeat requests against diagnosis, adherence and safety.', ['medication_safety_check']],
  ]),
  ...make('Orders & documentation','file','enterprise','form',[
    ['order-entry','Order entry centre','Place laboratory, imaging, medicine, procedure and referral orders from one page.', ['care_plan']],
    ['admission-orders','Admission orders','Create admission, treatment, observation and nursing instructions.', ['care_plan','medication_schedule']],
    ['procedure-documentation','Procedure documentation','Record indication, consent, team, findings, complications and aftercare.', ['care_plan']],
    ['discharge-summary-builder','Discharge summary builder','Draft and sign structured inpatient discharge documentation.', ['handover','care_plan']],
    ['medical-documents','Document & certificate centre','Generate signed clinical documents with QR verification.'],
    ['medical-certificates','Medical certificate generator','Issue structured, signed and verifiable medical certificates.'],
    ['sick-notes','Sick-note generator','Create time-bound work or school absence recommendations.'],
    ['referral-letters','Referral-letter generator','Create a complete clinical referral package and feedback request.'],
  ]),
  ...make('Coordination','users','enterprise','coordination',[
    ['patient-handover','Patient handover','Create and acknowledge structured SBAR handovers.', ['handover']],
    ['on-call-schedule','On-call schedule','View on-call commitments, swaps and escalation coverage.'],
    ['multidisciplinary-team','Multidisciplinary team','Coordinate case conferences, decisions and action ownership.'],
    ['virtual-waiting-room','Virtual waiting room','Call patients, review readiness and launch secure teleconsultations.'],
    ['secure-message-inbox','Secure message inbox','Triage clinical conversations and attach them to the patient record.'],
    ['follow-up-recall-list','Follow-up recall list','Track patients due, overdue or lost to follow-up.'],
  ]),
  ...make('Personalisation & governance','settings','enterprise','settings',[
    ['clinical-templates','Clinical templates','Create speciality-specific note, order and procedure templates.'],
    ['favourite-order-sets','Favourite order sets','Save safe reusable order bundles for common pathways.'],
    ['diagnosis-favourites','Diagnosis favourites','Manage frequently used terminology with coding support.'],
    ['personal-audit','Personal audit trail','Review patient records, prescriptions and documents accessed or signed.'],
    ['professional-credentials','Professional credentials','Track licence verification, expiry and renewal evidence.', ['verification_scan']],
    ['professional-subscription','Professional subscription','Manage plan, billing, limits and invoices.'],
  ]),
]

const nurse = [
  ...make('Patient assignment','users','visits','nursing',[
    ['assigned-patients','Assigned patients board','See acuity, ward, bed, pending care and latest observation.'],
    ['ward-patient-list','Ward patient list','Filter admitted patients by ward, isolation and responsible nurse.'],
    ['patient-nursing-chart','Patient nursing chart','Open a bedside chart with observations, tasks, medicines and notes.'],
    ['nursing-care-plan','Nursing care plan','Create goals, interventions, frequency, evaluation and handover.', ['care_plan']],
  ]),
  ...make('Medication & observation','pill','enterprise','clinical',[
    ['emar','Electronic medication administration','Review due doses, verify five rights, record administration and witness.', ['medication_schedule','medication_dose']],
    ['due-medications','Due medications','Prioritise medicines due within the current round.', ['medication_schedule']],
    ['overdue-medications','Overdue medication alerts','Escalate late, omitted or unavailable doses.', ['medication_dose']],
    ['medication-omissions','Medication omission review','Document omission reason, notification and corrective action.', ['medication_dose']],
    ['fluid-balance','Fluid balance chart','Record intake, output and cumulative balance visually.', ['fluid_balance']],
    ['intake-output','Intake & output','Enter fluids, feeds, urine, drains, stool and losses.', ['fluid_balance']],
    ['early-warning','Early-warning & escalation','Calculate deterioration score and follow escalation protocol.', ['observation_chart','risk_assessment']],
    ['blood-transfusion','Blood-transfusion monitoring','Complete identity, baseline, interval observations and reaction response.', ['transfusion']],
  ]),
  ...make('Assessments & safety','shield','enterprise','clinical',[
    ['wound-assessment','Wound assessment','Record wound location, dimensions, tissue, exudate and dressing plan.', ['risk_assessment']],
    ['pain-assessment','Pain assessment','Track pain score, intervention and reassessment.', ['observation_chart']],
    ['fall-risk','Fall-risk assessment','Assess risk and activate prevention measures.', ['risk_assessment']],
    ['pressure-injury-risk','Pressure-injury risk','Calculate risk and schedule repositioning and skin review.', ['risk_assessment']],
    ['infection-control','Infection-control checklist','Record screening, precautions, PPE and isolation compliance.', ['risk_assessment']],
    ['isolation-board','Isolation status board','See isolation type, reason, start date and pending reviews.', ['risk_assessment']],
  ]),
  ...make('Shift coordination','refresh','enterprise','coordination',[
    ['nursing-handover','Nursing handover board','Prepare and acknowledge structured shift handover.', ['handover']],
    ['shift-summary','Shift summary','Summarise census, incidents, pending work and staffing.'],
    ['discharge-checklist','Nursing discharge checklist','Confirm education, medicines, devices, follow-up and transport.', ['handover']],
    ['patient-education','Patient education','Record education topic, understanding and supporting materials.'],
    ['supply-requests','Nursing supply requests','Request ward supplies and track fulfilment.'],
    ['equipment-checklist','Equipment checklist','Verify emergency trolley, devices and ward equipment readiness.'],
  ]),
]

const reception = [
  ...make('Scheduling','calendar','appointments','calendar',[
    ['appointment-calendar','Appointment calendar','View provider, department and service schedules by day, week or month.'],
    ['provider-schedules','Provider schedule viewer','Find available clinicians, rooms and service capacity.'],
    ['create-appointment','Create appointment','Book a verified service for an existing or newly registered patient.'],
    ['reschedule-appointment','Reschedule appointment','Move an appointment while checking conflicts and notifying parties.'],
    ['cancel-appointment','Cancel appointment','Capture reason, policy outcome and refund requirement.'],
    ['walk-in-conversion','Walk-in conversion','Convert a walk-in visit into an appointment-linked encounter.'],
  ]),
  ...make('Patient flow','users','visits','queue',[
    ['service-routing','Service & department routing','Direct patients to the correct department, service and queue.'],
    ['patient-arrival-board','Patient arrival board','See expected, arrived, late, waiting and no-show patients.'],
    ['referral-reception','Referral reception','Receive referral documents, validate destination and schedule care.'],
    ['admission-registration','Inpatient admission registration','Capture admission demographics, payer, next of kin and destination ward.'],
    ['discharge-checkout','Discharge checkout coordination','Coordinate final documents, billing, pharmacy and transport clearance.'],
    ['missing-information','Missing patient information','Resolve incomplete identity, contact and payer information.'],
    ['duplicate-warning','Duplicate-patient warnings','Review possible matches before creating another patient identity.'],
  ]),
  ...make('Access & communication','message','enterprise','operations',[
    ['insurance-check','Insurance membership check','Validate member identity and active coverage.'],
    ['preauthorization-check','Preauthorization status','Confirm service approval before check-in.'],
    ['deposit-request','Deposit request','Create and track a required service or admission deposit.'],
    ['appointment-slip','Appointment slip printing','Print branded appointment confirmation with QR check-in.'],
    ['queue-ticket','Queue ticket printing','Issue queue number, department and estimated waiting guidance.'],
    ['visitor-management','Visitor management','Register visitors, issue passes and track exit.'],
    ['call-centre','Call-centre workspace','Manage inbound calls, callback tasks and booking support.'],
    ['sms-confirmation','SMS appointment confirmation','Send and track booking, reminder and reschedule messages.'],
  ]),
]

const records = [
  ...make('Master patient index','users','enterprise','records',[
    ['master-patient-index','Master patient index','Search the canonical patient identity across facilities and record systems.'],
    ['duplicate-inbox','Duplicate-candidate inbox','Review ranked potential duplicate identities.'],
    ['patient-comparison','Side-by-side patient comparison','Compare identifiers, demographics, contacts and clinical relationships.'],
    ['merge-wizard','Patient merge wizard','Select survivor, migrate references and obtain approval.'],
    ['unmerge-review','Unmerge review','Assess and reverse an incorrect merge safely.'],
    ['identity-conflicts','Identity-conflict queue','Resolve incompatible demographic or identifier evidence.'],
  ]),
  ...make('Record administration','file','enterprise','records',[
    ['demographic-correction','Demographic correction','Review evidence, approve change and retain previous values.', ['record_correction']],
    ['scan-upload','Scan & upload','Capture, quarantine-scan, classify and index paper records.', ['scanned_document']],
    ['document-classification','Document classification','Assign patient, encounter, document type and confidentiality level.', ['scanned_document']],
    ['record-release','Record release','Process authorised release with minimum-necessary controls.', ['release_information']],
    ['disclosure-authorization','Disclosure authorization','Validate consent, requester identity and scope.'],
    ['legal-holds','Legal holds','Prevent deletion and record legal authority, scope and review date.', ['legal_hold']],
    ['record-restriction','Record restriction','Apply privacy or safety restrictions to sensitive content.'],
    ['confidential-segmentation','Confidential segmentation','Separate psychotherapy, sexual health or protected notes.'],
    ['retention-schedules','Retention schedules','Configure retention by record class and jurisdiction.', ['retention_action']],
    ['archival-queue','Archival queue','Prepare inactive records for protected long-term storage.', ['retention_action']],
    ['destruction-approval','Destruction approval','Require dual approval, legal-hold check and certificate.'],
    ['data-export','Data export','Produce a complete, logged patient export package.'],
    ['patient-access-request','Patient access requests','Track identity proof, scope, redaction and delivery.'],
    ['record-movement','Record movement tracking','Track physical and digital record custody.'],
    ['unmatched-documents','Unmatched document queue','Resolve incoming documents without a confident patient match.'],
  ]),
]

const cashier = make('Collections','money','invoices','finance',[
  ['patient-account','Patient account lookup','Review invoices, payments, deposits, credits and payer responsibility.'],['pending-payments','Pending-payment queue','Prioritise invoices awaiting collection or payment confirmation.'],['deposit-collection','Deposit collection','Collect and allocate consultation, procedure or admission deposits.'],['split-payment','Split payment','Allocate one invoice across cash, card, mobile money, insurer and credit.'],['payment-methods','Multiple payment methods','Record approved payment methods with reference validation.'],['mobile-money-collections','Mobile-money status','Monitor request, customer approval, provider callback and reversal.'],['payer-split','Insurance & patient split','Collect copayment and track insurer responsibility.'],['credit-balance','Patient credit balance','Apply, transfer or refund authorised account credit.'],['refund-request','Refund request','Submit a documented refund for approval and processing.'],['cash-drawer','Cash drawer','Track opening float, collections, withdrawals and expected balance.'],['shift-transactions','Shift transaction details','Review all payments, receipts, voids and variances in the shift.'],['end-of-day','End-of-day report','Close and sign daily collection summary.'],['receipt-history','Receipt reprint history','Reprint receipts with reason and audit trail.'],['void-payment','Void-payment request','Request controlled reversal of an incorrect payment.'],
])

const accounting = [
  ...make('Accounting','money','enterprise','finance',[
    ['daily-cashbook','Daily cashbook','Post and reconcile daily receipts and payments.', ['bank_transaction']],['bank-reconciliation','Bank reconciliation','Match bank statement lines to ledger transactions.', ['reconciliation']],['mobile-money-reconciliation','Mobile-money reconciliation','Match collection and disbursement callbacks to invoices.', ['reconciliation']],['gateway-reconciliation','Gateway settlement reconciliation','Reconcile gateway fees, settlements, reversals and chargebacks.', ['reconciliation']],['accounts-receivable','Accounts receivable','Track patient, corporate and insurer ageing.'],['accounts-payable','Accounts payable','Track supplier invoices, due dates and payment approval.', ['supplier_bill']],['expense-register','Expense register','Record, classify and approve operating expenses.', ['expense']],['supplier-invoices','Supplier invoices','Three-way match invoice, order and goods received.', ['supplier_bill']],['supplier-payments','Supplier payments','Prepare, approve and reconcile vendor payments.'],['credit-notes','Credit notes','Create approved reductions to receivables.', ['credit_note']],['debit-notes','Debit notes','Record additional amounts owed with reason.', ['debit_note']],['journal-entries','Journal entries','Create balanced manual entries with approval.'],['general-ledger','General ledger','Review account activity and drill into source transactions.'],['trial-balance','Trial balance','Validate account balances before reporting.'],['income-statement','Income statement','Review revenue, cost and operating result.'],['balance-sheet','Balance sheet','Review assets, liabilities and equity.'],['cash-flow','Cash-flow statement','Review operating, investing and financing cash movement.'],['tax-report','Tax report','Prepare fiscal and withholding information.', ['fiscal_document']],['period-close','Financial-period closing','Lock period after reconciliation and approval.', ['financial_period']],
  ]),
  ...make('Finance management','chart','enterprise','analytics',[
    ['budget-management','Budget management','Create, approve and monitor organizational budgets.'],['department-budgets','Department budgets','Allocate and compare spend by department.'],['approval-limits','Approval limits','Configure amount-based approval authority.'],['financial-exceptions','Financial exceptions','Investigate unusual refunds, discounts and write-offs.'],['revenue-analytics','Revenue analytics','Analyse revenue by service, department, payer and branch.'],['ageing-analysis','Ageing analysis','Review overdue patient, insurer and corporate balances.'],['insurance-settlement','Insurance settlement','Reconcile approved claims and provider payment.', ['settlement']],['revenue-leakage','Revenue leakage','Find unbilled services, missing charges and pricing exceptions.'],['department-profitability','Department profitability','Compare contribution margin by department.'],['forecasting','Financial forecasting','Project revenue, cash and expense scenarios.'],['consolidated-reporting','Consolidated branch reporting','Aggregate finance across branches and entities.'],
  ]),
]

const pharmacy = [
  ...make('Dispensing','pill','enterprise','medication',[
    ['prescription-workspace','Prescription-detail workspace','Review patient, diagnosis, medicines, allergies, interactions and dispensing status.'],['label-designer','Dispensing label designer','Create readable, localised medicine labels.', ['dispensing_label']],['label-printing','Label printing','Print medicine labels with patient and safety instructions.', ['dispensing_label']],['medication-history','Patient medication history','Review current, prior and discontinued medicines.'],['clarification-chat','Prescription clarification','Message the prescriber and document the response.'],['substitution-authorization','Substitution authorization','Record clinical and patient approval for substitution.'],['pharmacist-intervention','Pharmacist intervention','Document safety, dose, interaction or adherence intervention.'],['controlled-drug-register','Controlled-drug register','Maintain signed receipt, supply and balance entries.', ['controlled_drug_entry']],['narcotics-balance','Narcotics balance','Reconcile physical and recorded controlled stock.', ['controlled_drug_entry']],['witness-confirmation','Witness confirmation','Capture dual-signature controlled-drug actions.', ['controlled_drug_entry']],
  ]),
  ...make('Inventory & supply','box','enterprise','inventory',[
    ['product-recalls','Product recall','Identify affected batches, quarantine, notify and close recall.', ['recall']],['drug-returns','Drug returns','Receive, inspect and disposition returned medicine.'],['stock-transfers','Stock transfer','Move stock between locations with dispatch and receipt confirmation.'],['stock-adjustments','Stock adjustment','Request and approve stock corrections.'],['stock-count','Stock-count session','Freeze, count, recount and approve variance.', ['stock_count']],['variance-investigation','Variance investigation','Investigate significant stock discrepancies.', ['stock_count']],['goods-received','Goods-received note','Receive purchase-order lines, batches and expiry.'],['purchase-order-detail','Purchase-order detail','Review approval, supplier, lines, receiving and invoice match.'],['supplier-invoice-match','Supplier invoice matching','Match supplier invoice to order and receipt.'],['reorder-recommendations','Reorder recommendations','Use stock, demand, lead time and safety level.'],['stock-valuation','Stock valuation','View quantity and value by product, batch and location.'],['expiry-calendar','Expiry calendar','See products expiring by month and required action.'],['cold-chain-chart','Cold-chain graph','Visualise temperature and excursions.', ['cold_chain']],['temperature-excursion','Temperature excursion','Quarantine affected stock and document assessment.', ['cold_chain']],['damaged-stock','Damaged stock','Record damage, quarantine and approved write-off.'],['quarantine-stock','Quarantine stock','Manage non-dispensable batches and release decision.'],['pharmacy-sales','Pharmacy sales reports','Review prescription and retail sales, margins and taxes.'],
  ]),
]

const laboratory = [
  ...make('Specimens','flask','enterprise','laboratory',[
    ['collection-worklist','Specimen collection worklist','Prioritise collections by location, fasting and urgency.'],['phlebotomy-queue','Phlebotomy queue','Call patients, verify identity and collect safely.'],['accessioning','Accessioning workspace','Receive, inspect and accession specimens.'],['barcode-labels','Barcode-label printing','Print patient, specimen, container and test labels.'],['barcode-scanner','Barcode scanning','Scan collection, receipt, processing and storage events.'],['rejected-specimens','Rejected-specimen queue','Record rejection reason and recollection notification.'],['transport-manifest','Specimen transport manifest','Create dispatch and receipt chain of custody.'],['aliquot-creation','Aliquot creation','Create derived containers and preserve traceability.', ['specimen_aliquot']],['storage-map','Storage-location map','Locate rack, box, freezer and retention date.', ['specimen_storage']],
  ]),
  ...make('Testing & results','activity','enterprise','laboratory',[
    ['result-entry','Test result entry','Enter results by order with units, ranges and flags.', ['analyzer_result']],['result-comparison','Previous result comparison','Compare current and previous results with delta checks.', ['analyzer_result']],['validation-queue','Validation queue','Review technical validity, QC and critical flags.'],['release-queue','Release queue','Authorise patient and clinician result release.'],['critical-escalation','Critical-result escalation','Notify, escalate and capture clinician acknowledgement.'],['microbiology','Microbiology culture','Track specimen, organism, growth and final interpretation.', ['microbiology_culture']],['susceptibility-grid','Antibiotic susceptibility','Record organism–antibiotic interpretation matrix.', ['susceptibility']],['histopathology','Histopathology workspace','Track specimen grossing, blocks, slides and diagnosis.'],['blood-bank','Blood-bank inventory','Track units, groups, expiry, quarantine and issue.', ['blood_bank']],['crossmatch','Crossmatch','Record compatibility testing and reservation.', ['blood_bank']],['transfusion-compatibility','Transfusion compatibility','Verify patient and component compatibility.', ['blood_bank']],
  ]),
  ...make('Quality & operations','shield','enterprise','laboratory',[
    ['reagent-inventory','Reagent inventory','Track lot, expiry, storage and analyser assignment.', ['reagent_lot']],['equipment-register','Equipment register','Manage analysers, service and downtime.'],['calibration-calendar','Calibration calendar','Schedule and evidence calibration.', ['calibration']],['quality-control','Quality-control charts','Review control results and rule violations.', ['quality_control']],['levey-jennings','Levey–Jennings charts','Visualise QC mean and standard-deviation limits.', ['quality_control']],['turnaround-time','Turnaround-time dashboard','Monitor collection-to-release time and SLA exceptions.'],['report-printing','Laboratory report printing','Print signed reports with verification code.'],
  ]),
]

const radiology = make('Imaging operations','activity','enterprise','imaging',[
  ['imaging-calendar','Imaging scheduling calendar','Schedule modality, room, staff and preparation.'],['modality-worklist','Modality worklist','Prioritise scheduled and urgent imaging studies.', ['modality_worklist']],['patient-preparation','Patient preparation checklist','Confirm fasting, contrast, pregnancy, renal function and consent.'],['room-assignment','Imaging-room assignment','Assign room and modality without conflicts.'],['acquisition-status','Imaging acquisition status','Track arrived, prepared, acquired, quality checked and sent to PACS.'],['pacs-viewer','Embedded PACS viewer','Open DICOM study in an authorised viewer.'],['study-comparison','Study comparison','Compare prior and current studies.'],['reporting-editor','Radiology reporting editor','Create structured findings and impression.', ['structured_report']],['report-templates','Structured report templates','Manage modality and anatomy templates.'],['voice-dictation','Voice dictation','Capture and review report dictation.'],['report-verification','Report verification','Verify, sign and release a report.', ['structured_report']],['critical-notification','Critical-result notification','Notify clinician and track acknowledgement.', ['critical_imaging_alert']],['doctor-acknowledgement','Referring-doctor acknowledgement','Confirm clinical receipt and planned action.', ['critical_imaging_alert']],['radiation-dose','Radiation-dose dashboard','Monitor dose and diagnostic reference levels.', ['radiation_dose']],['repeat-analysis','Repeat-study analysis','Review repeats, causes and corrective actions.'],['imaging-export','Imaging export','Prepare authorised study export.'],['secure-study-link','Secure study link','Generate expiring access link or media export.'],
])

const emergency = make('Emergency operations','alert','enterprise','emergency',[
  ['command-dashboard','Emergency command dashboard','See active incidents, triage acuity, resources and escalations.'],['dispatch-map','Live dispatch map','Coordinate incident, vehicle, crew, pickup and destination.', ['prehospital_record']],['call-intake','Emergency call intake','Capture caller, location, symptoms, hazards and priority.'],['incident-detail','Incident details','Review dispatch timeline, care and receiving facility.'],['ambulance-detail','Ambulance details','View crew, vehicle, equipment, telemetry and status.'],['crew-roster','Crew roster','Manage shift, skills and availability.'],['live-telemetry','Live telemetry','View location, speed, heading and last contact.'],['route-eta','Route & ETA','Monitor route and estimated arrival.'],['emergency-triage','Emergency triage chart','Record acuity, vitals, symptoms and reassessment.'],['trauma-chart','Trauma chart','Record primary survey, injuries and activation.', ['trauma_assessment']],['resuscitation-timeline','Resuscitation timeline','Record CPR, rhythm, shock, airway, medicines and outcome.', ['resuscitation_event']],['medication-timeline','Emergency medication timeline','Track time-critical medication.'],['procedure-timeline','Emergency procedure timeline','Track procedures, team and response.'],['gcs-chart','Glasgow Coma Scale','Record eye, verbal, motor and total score.', ['trauma_assessment']],['observation-chart','Emergency observation chart','Track repeated assessment and disposition.', ['emergency_observation']],['transfer-form','Emergency transfer form','Prepare clinical transfer and transport risk.'],['receiving-handover','Receiving-facility handover','Send structured pre-arrival and arrival handover.', ['handover']],['mass-casualty','Mass-casualty board','Track victims, triage category and destination.', ['mass_casualty']],['equipment-check','Ambulance equipment checklist','Verify consumables, medicines and devices.'],['cleaning-check','Ambulance cleaning checklist','Record decontamination and readiness.'],['offline-paramedic','Offline paramedic mode','Capture care offline and synchronise safely.'],
])

const theatre = make('Theatre & anaesthesia','hospital','enterprise','theatre',[
  ['theatre-calendar','Theatre calendar','Schedule rooms, teams, procedures and equipment.'],['operating-room-schedule','Operating-room schedule','Coordinate daily room list and turnaround.'],['surgical-waiting-list','Surgical waiting list','Prioritise elective, urgent and delayed cases.'],['surgical-case-detail','Surgical case details','Review diagnosis, procedure, team, status and documents.'],['team-assignment','Theatre team assignment','Assign surgeon, anaesthetist, nurses and support.'],['patient-preparation','Patient preparation','Confirm investigations, fasting, site, blood and readiness.'],['consent-checklist','Consent checklist','Verify patient, procedure, site and authorised consent.'],['pre-anaesthetic','Pre-anaesthetic assessment','Assess ASA, airway, risk, fasting and plan.', ['pre_anaesthetic_assessment']],['anaesthesia-chart','Anaesthesia chart','Record technique, medicines, airway, fluids and events.', ['anaesthesia_chart']],['intraoperative-timeline','Intraoperative timeline','Track milestones, observations and events.', ['intraoperative_observation']],['vital-sign-graph','Intraoperative vital graph','Visualise HR, BP, SpO₂, ETCO₂ and temperature.', ['intraoperative_observation']],['medication-fluid-chart','Medication & fluid chart','Record agents, infusion, fluid and output.'],['blood-product-chart','Blood-product chart','Track units, checks, start, observations and completion.', ['transfusion']],['instrument-count','Instrument & swab count','Complete initial, cavity and final counts.', ['surgical_count']],['implant-register','Implant register','Record device identifiers and traceability.', ['implant_usage']],['consumable-usage','Consumable usage','Capture theatre consumables for stock and billing.'],['operation-note','Operation-note editor','Document findings, procedure, complications and plan.'],['recovery-score','Recovery score','Calculate discharge from post-anaesthesia care.', ['recovery_observation']],['recovery-observation','Recovery observation chart','Track airway, breathing, circulation, pain and nausea.', ['recovery_observation']],['post-op-orders','Post-operative orders','Create monitoring, analgesia, fluids and review orders.'],['specimen-tracking','Surgical specimen tracking','Label, send and reconcile pathology specimens.'],['sterilization','Sterilization dashboard','Track cycles, loads, indicators and release.', ['sterilization_cycle']],['turnaround','Theatre cleaning & turnaround','Coordinate cleaning, setup and room ready time.'],['utilization','Theatre utilization reports','Analyse utilisation, cancellations, delays and turnaround.'],
])

const maternity = make('Maternity & child health','users','enterprise','maternity',[
  ['antenatal-dashboard','Antenatal dashboard','Appointments, high-risk pregnancies and due investigations.'],['pregnancy-detail','Pregnancy episode detail','Complete obstetric history, risks, plan and timeline.'],['antenatal-timeline','Antenatal visit timeline','Review visits, observations, investigations and counselling.', ['antenatal_visit']],['high-risk-pregnancy','High-risk pregnancy list','Prioritise maternal and foetal risks.'],['labour-ward-board','Labour ward board','See stage, risk, partograph status and assigned midwife.'],['visual-partograph','Visual partograph','Plot dilation, descent, contractions, foetal and maternal observations.', ['partograph_observation']],['delivery-suite','Delivery suite','Document labour, delivery and immediate care.', ['delivery_record']],['delivery-team','Delivery team','Assign and record attendance.'],['caesarean-escalation','Caesarean escalation','Escalate indication, decision time and theatre readiness.'],['birth-record','Birth record','Record delivery, baby identifiers and legal notification.', ['delivery_record']],['newborn-assessment','Newborn assessment','Record APGAR, examination, weight and immediate care.', ['newborn_assessment']],['apgar-chart','APGAR chart','Record 1, 5 and 10-minute components.', ['newborn_assessment']],['mother-baby-link','Mother–baby linking','Link newborn identities to maternal episode.'],['postnatal-monitoring','Postnatal monitoring','Track maternal and newborn danger signs.'],['immunization-calendar','Immunization calendar','See vaccines due and overdue.', ['immunization']],['vaccination-administration','Vaccination administration','Record product, batch, site and provider.', ['immunization']],['growth-chart','Growth chart','Plot weight, height and head circumference.', ['growth_measurement']],['child-health-visit','Child-health visit','Record development, feeding, illness and counselling.'],['nutrition-monitoring','Nutrition monitoring','Track feeding and malnutrition risk.', ['nutrition_plan']],['family-planning','Family planning','Document counselling, method, consent and follow-up.', ['family_planning']],
])

const facility = make('Facility operations','hospital','enterprise','facility',[
  ['multi-branch-dashboard','Multi-branch dashboard','Compare capacity, staffing, finance and quality by branch.'],['branch-detail','Branch details','Manage contacts, hours, services, staff and licence.'],['licence-renewal','Facility licence renewal','Track expiry, evidence, submission and approval.', ['verification_scan']],['department-detail','Department details','Manage leadership, services, rooms, staff and performance.'],['room-management','Room management','Manage consultation, theatre, imaging and procedure rooms.'],['service-catalogue','Service catalogue','Configure service, duration, eligibility and availability.'],['price-lists','Price-list management','Version cash, corporate and insurer prices.'],['provider-schedules','Provider schedule','Coordinate availability across service, room and branch.'],['queue-configuration','Queue configuration','Define stages, priorities, routing and display.'],['visual-bed-map','Visual bed map','See ward, bed, patient, cleaning and maintenance status.'],['ward-detail','Ward details','Review census, acuity, staff and pending tasks.'],['bed-turnover','Bed cleaning & maintenance','Coordinate discharge, cleaning, inspection and release.', ['bed_turnover']],['admission-detail','Admission details','Review patient, bed, care team, tasks and payer.'],['discharge-clearance','Discharge clearance','Coordinate clinical, pharmacy, billing and transport.'],['staff-profile','Staff profile','Review identity, role, department, shifts and status.'],['staff-credential','Staff credentials','Review verification, expiry and renewal.'],['staff-onboarding','Staff onboarding checklist','Track invitation, documents, orientation and access.'],['shift-calendar','Shift calendar','View and assign staffing by department.'],['leave-calendar','Leave calendar','Review approved leave and coverage gaps.'],['payroll-integration','Payroll integration','Export approved attendance, shift and allowance data.'],['equipment-register','Equipment register','Track asset, location, service, calibration and status.'],['maintenance-requests','Maintenance requests','Triage facility and equipment faults.'],['biomedical-equipment','Biomedical equipment','Manage preventive maintenance and safety.'],['supplier-management','Supplier management','Review qualification, contracts and performance.'],['inventory-valuation','Inventory valuation','Review quantity and value across stores.'],['financial-reports','Facility financial reports','Review revenue, collections, debt and cost by service.'],['incident-detail','Incident details','Review event, severity, investigation and actions.', ['clinical_safety_case']],['corrective-action','Corrective action','Assign, evidence and verify corrective actions.'],['infection-control','Infection-control dashboard','Monitor surveillance, precautions and audits.'],['complaint-detail','Patient complaint details','Track communication, investigation and resolution.'],['regulatory-reporting','Regulatory reporting centre','Prepare required licence, quality and safety reports.'],
])

const insurance = make('Insurance operations','insurance','enterprise','insurance',[
  ['member-directory','Member directory','Search member, policy, dependents and eligibility.'],['member-profile','Member profile','Review demographics, plan, utilization and claims.'],['plan-designer','Plan designer','Create benefits, exclusions, limits and cost sharing.'],['benefit-comparison','Benefit comparison','Compare plans and member entitlements.'],['provider-network','Provider network','Manage participating facilities and specialists.'],['provider-contract','Provider contract','Review effective dates, terms and obligations.'],['tariff-editor','Tariff editor','Configure contracted service rates and versions.'],['eligibility-detail','Eligibility details','Explain coverage, limits and patient responsibility.'],['preauthorization-workbench','Preauthorization workbench','Review clinical evidence and decide requested services.'],['claim-detail','Claim details','Review header, lines, codes, evidence and history.', ['claim_event']],['claim-line-adjudication','Claim-line adjudication','Approve, reject or query each claim line.'],['diagnosis-procedure-coding','Diagnosis & procedure coding','Validate ICD and procedure codes.'],['document-review','Document review','Review referral, notes, results and invoices.'],['medical-review','Medical review','Assess necessity, appropriateness and policy rules.'],['claim-query','Claim query conversation','Exchange structured provider questions and responses.', ['claim_message']],['appeal-review','Appeal review','Review grounds, evidence and prior decision.', ['claim_appeal']],['fraud-investigation','Fraud investigation','Investigate risk signals and linked activity.', ['fraud_flag']],['remittance-import','Remittance import','Import insurer decision and payment files.', ['settlement_import']],['settlement-reconciliation','Settlement reconciliation','Allocate payment to approved claim lines.'],['provider-payment','Provider payment','Prepare and confirm provider settlement.'],['claims-ageing','Claims ageing','Track pending and overdue claims by stage.'],['loss-ratio','Loss-ratio analytics','Compare premium and claims cost.'],['utilization-analytics','Utilization analytics','Analyse service use, cost and trends.'],
])

const admin = make('Platform administration','settings','enterprise','admin',[
  ['user-detail','User details','Review identity, roles, verification, activity and restrictions.'],['account-activity','Account activity','Review login, device, session and security events.'],['session-management','Session management','Revoke active sessions and investigate devices.'],['role-matrix','Role matrix','Compare role permissions across modules and actions.'],['permission-comparison','Permission comparison','Compare two roles or contexts.'],['organization-detail','Organization details','Review licence, branches, staff, subscription and status.'],['branch-detail','Branch details','Review branch operations, licence and capacity.'],['professional-detail','Professional details','Review profile, cadres, workplaces and credentials.'],['verification-case','Verification case','Review evidence, extracted fields, checks and decision.'],['licence-viewer','Licence document viewer','Compare protected document and submitted profile.'],['ocr-comparison','OCR comparison','Compare extracted and declared identity fields.'],['verification-timeline','Verification timeline','Review requests, evidence, decisions and renewals.'],['credential-renewals','Credential renewal queue','Prioritise expiring and submitted renewals.'],['subscription-detail','Subscription details','Review plan, limits, invoices and lifecycle.'],['payment-reconciliation','Payment reconciliation','Review gateway, mobile-money and bank settlement.'],['refund-detail','Refund details','Review reason, evidence, approval and processing.'],['notification-monitor','Notification delivery monitor','Review attempts, callbacks, provider and failure reason.'],['template-editor','Message template editor','Create localised email, SMS, WhatsApp and push templates.'],['cms-editor','CMS visual editor','Edit and schedule public content.'],['integration-detail','Integration details','Review configuration, health and delivery metrics.'],['event-delivery','Event delivery details','Inspect payload, attempts and response.'],['dead-letter','Dead-letter queue','Investigate and quarantine failed events.'],['event-replay','Event replay wizard','Select safe scope, dry run and replay.'],['worker-health','Worker & queue health','Monitor Celery, Kafka, RabbitMQ and scheduled jobs.'],['system-metrics','System metrics','Review API, database, cache, storage and latency.'],['audit-explorer','Audit-log explorer','Search actor, patient, action, resource and time.'],['security-incident','Security incident details','Investigate, contain, communicate and close incident.'],['backup-restore','Backup & restore','Review backup, retention, restore test and recovery point.'],['data-export-centre','Data export centre','Manage user, patient and regulatory exports.'],['retention-controls','Data retention controls','Configure retention and legal hold precedence.'],['feature-flags','Feature-flag editor','Enable by platform, country, organization and role.'],['localization','Country & localization','Manage languages, currency, time zone and rules.'],['maintenance-mode','Maintenance mode','Schedule and communicate controlled downtime.'],['regulatory-reporting','Regulatory reporting centre','Prepare compliance, safety and operational reports.'],
])

export const PAGE_CATALOG = {
  patient, doctor, clinical_officer: doctor, dentist: doctor, physiotherapist: doctor, nutritionist: doctor, psychologist: doctor, medical_director: doctor,
  nurse, midwife: maternity, theatre_nurse: theatre,
  receptionist: reception, records_officer: records,
  cashier, accountant: accounting, finance_manager: accounting,
  pharmacist: pharmacy, storekeeper: pharmacy,
  lab_technician: laboratory, radiologist: radiology, radiographer: radiology,
  paramedic: emergency, ambulance_dispatcher: emergency, anaesthetist: theatre,
  facility_manager: facility, procurement_officer: facility, quality_officer: facility, compliance_officer: facility, hr_officer: facility, it_support: admin,
  insurance, insurance_officer: insurance, claims_reviewer: insurance,
  hospital: facility, pharmacy, lab: laboratory,
  admin,
}

export function pagesForRole(role) {
  return PAGE_CATALOG[role] || []
}
