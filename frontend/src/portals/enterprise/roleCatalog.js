const records = (id, label, icon, description, recordTypes, group = 'Clinical operations') => ({ id, label, icon, description, recordTypes, group, kind: 'records' })
const resource = (id, label, icon, description, resourceName, fields = [], group = 'Administration') => ({ id, label, icon, description, resourceName, fields, group, kind: 'resource' })

export const RESOURCE_FIELDS = {
  'clinical-codes': [
    ['system', 'Coding system', 'select', ['ICD-10', 'ICD-11', 'SNOMED-CT', 'LOINC', 'CPT', 'LOCAL']],
    ['version', 'Version'], ['code', 'Code'], ['display', 'Display'], ['description', 'Description', 'textarea'], ['category', 'Category'], ['active', 'Active', 'boolean'],
  ],
  'tariffs': [['payer', 'Payer organization ID', 'number'], ['provider', 'Provider organization ID', 'number'], ['name', 'Schedule name'], ['currency', 'Currency'], ['valid_from', 'Valid from', 'date'], ['valid_to', 'Valid to', 'date'], ['items', 'Tariff items', 'json'], ['active', 'Active', 'boolean']],
  'payer-contracts': [['payer', 'Payer organization ID', 'number'], ['provider', 'Provider organization ID', 'number'], ['contract_number', 'Contract number'], ['status', 'Status'], ['starts_on', 'Starts on', 'date'], ['ends_on', 'Ends on', 'date'], ['tariff', 'Tariff schedule ID', 'number'], ['terms', 'Contract terms', 'json']],
  'medication-knowledge': [['generic_name', 'Generic name'], ['brand_names', 'Brand names', 'list'], ['atc_code', 'ATC code'], ['strengths', 'Strengths', 'list'], ['dosage_forms', 'Dosage forms', 'list'], ['contraindications', 'Contraindications', 'list'], ['pregnancy_category', 'Pregnancy category'], ['renal_guidance', 'Renal guidance', 'textarea'], ['hepatic_guidance', 'Hepatic guidance', 'textarea'], ['max_dose_guidance', 'Maximum dose guidance', 'json'], ['active', 'Active', 'boolean']],
  'medication-interactions': [['medicine_a', 'Medicine A ID', 'number'], ['medicine_b', 'Medicine B ID', 'number'], ['severity', 'Severity', 'select', ['minor', 'moderate', 'major', 'contraindicated']], ['mechanism', 'Mechanism', 'textarea'], ['clinical_effect', 'Clinical effect', 'textarea'], ['management', 'Management', 'textarea'], ['evidence', 'Evidence'], ['active', 'Active', 'boolean']],
  'pacs-nodes': [['organization', 'Organization ID', 'number'], ['name', 'Node name'], ['ae_title', 'AE title'], ['host', 'Host'], ['port', 'DICOM port', 'number'], ['dicomweb_base_url', 'DICOMweb base URL'], ['tls_enabled', 'TLS enabled', 'boolean'], ['active', 'Active', 'boolean'], ['configuration', 'Configuration', 'json']],
  'imaging-studies': [['study_instance_uid', 'Study Instance UID'], ['organization', 'Organization ID', 'number'], ['patient', 'Patient ID', 'number'], ['imaging_order', 'Imaging order ID', 'number'], ['pacs_node', 'PACS node ID', 'number'], ['accession_number', 'Accession number'], ['modality', 'Modality'], ['description', 'Description'], ['study_date', 'Study date', 'datetime'], ['series_count', 'Series count', 'number'], ['instance_count', 'Instance count', 'number'], ['viewer_url', 'Viewer URL'], ['metadata', 'Metadata', 'json']],
  'ambulance-vehicles': [['organization', 'Organization ID', 'number'], ['call_sign', 'Call sign'], ['registration_number', 'Registration number'], ['vehicle_type', 'Vehicle type'], ['status', 'Status'], ['equipment', 'Equipment', 'list'], ['last_service_on', 'Last service', 'date'], ['active', 'Active', 'boolean']],
  'ambulance-telemetry': [['vehicle', 'Vehicle ID', 'number'], ['dispatch', 'Dispatch ID', 'number'], ['latitude', 'Latitude', 'number'], ['longitude', 'Longitude', 'number'], ['speed_kph', 'Speed km/h', 'number'], ['heading', 'Heading', 'number'], ['accuracy_m', 'Accuracy metres', 'number'], ['recorded_at', 'Recorded at', 'datetime']],
  'notification-providers': [['channel', 'Channel', 'select', ['email', 'sms', 'whatsapp', 'push', 'voice']], ['name', 'Provider name'], ['provider_type', 'Provider type'], ['priority', 'Priority', 'number'], ['active', 'Active', 'boolean'], ['configuration', 'Configuration', 'json'], ['credentials_reference', 'Secret reference'], ['cost_per_message', 'Cost per message', 'number'], ['currency', 'Currency']],
  'communication-consents': [['user', 'User ID', 'number'], ['channel', 'Channel'], ['purpose', 'Purpose'], ['granted', 'Granted', 'boolean'], ['source', 'Source'], ['evidence', 'Evidence', 'json']],
  'escalation-policies': [['organization', 'Organization ID', 'number'], ['name', 'Policy name'], ['event_type', 'Event type'], ['conditions', 'Trigger conditions', 'json'], ['active', 'Active', 'boolean']],
  'event-schemas': [['name', 'Schema name'], ['version', 'Version', 'number'], ['subject', 'Event subject'], ['json_schema', 'JSON schema', 'json'], ['compatibility', 'Compatibility', 'select', ['backward', 'forward', 'full', 'none']], ['active', 'Active', 'boolean']],
  'integration-endpoints': [['name', 'Endpoint name'], ['endpoint_type', 'Type', 'select', ['webhook', 'kafka', 'rabbitmq', 'fhir', 'sftp', 'warehouse']], ['base_url', 'Base URL'], ['topic', 'Topic or route'], ['credentials_reference', 'Secret reference'], ['configuration', 'Configuration', 'json'], ['active', 'Active', 'boolean']],
  'event-deliveries': [['event', 'Outbox event ID', 'number'], ['endpoint', 'Endpoint ID', 'number'], ['schema', 'Event schema ID', 'number'], ['status', 'Status'], ['next_attempt_at', 'Next attempt', 'datetime'], ['idempotency_key', 'Idempotency key']],
  'content': [['content_type', 'Content type', 'select', ['page', 'banner', 'promotion', 'faq', 'template', 'category', 'legal']], ['slug', 'Slug'], ['locale', 'Locale'], ['title', 'Title'], ['summary', 'Summary', 'textarea'], ['body', 'Body', 'textarea'], ['target_url', 'Target URL'], ['audience', 'Audiences', 'list'], ['placement', 'Placement'], ['starts_at', 'Starts at', 'datetime'], ['ends_at', 'Ends at', 'datetime'], ['status', 'Status', 'select', ['draft', 'review', 'published', 'archived']], ['metadata', 'Metadata', 'json'], ['version', 'Version', 'number']],
  'feature-config': [['key', 'Key'], ['scope_type', 'Scope type', 'select', ['platform', 'organization', 'role', 'country']], ['scope_id', 'Scope identifier'], ['value', 'Value', 'json'], ['enabled', 'Enabled', 'boolean'], ['requires_restart', 'Requires restart', 'boolean']],
  'patient-index': [['patient', 'Patient ID', 'number'], ['national_identifier', 'National identifier'], ['identifiers', 'Other identifiers', 'json'], ['normalized_name', 'Normalized name'], ['normalized_phone', 'Normalized phone'], ['date_of_birth', 'Date of birth', 'date'], ['sex', 'Sex'], ['status', 'Status'], ['confidence_score', 'Confidence score', 'number']],
  'duplicate-patients': [['patient_a', 'MPI patient A ID', 'number'], ['patient_b', 'MPI patient B ID', 'number'], ['score', 'Match score', 'number'], ['matching_fields', 'Matching fields', 'list'], ['status', 'Status'], ['notes', 'Review notes', 'textarea']],
  'patient-merges': [['survivor', 'Surviving MPI ID', 'number'], ['duplicate', 'Duplicate MPI ID', 'number'], ['reason', 'Reason', 'textarea'], ['field_decisions', 'Field decisions', 'json'], ['status', 'Status']],
  'records-requests': [['organization', 'Organization ID', 'number'], ['patient', 'Patient ID', 'number'], ['request_type', 'Request type', 'select', ['correction', 'release', 'legal_hold', 'retention', 'export', 'deletion', 'scan']], ['status', 'Status'], ['reason', 'Reason', 'textarea'], ['details', 'Request details', 'json'], ['due_at', 'Due at', 'datetime'], ['assigned_to', 'Assigned user ID', 'number']],
  'fhir-resources': [['resource_type', 'Resource type'], ['organization', 'Organization ID', 'number'], ['patient', 'Patient ID', 'number'], ['source_model', 'Source model'], ['source_id', 'Source identifier'], ['data', 'FHIR resource', 'json'], ['status', 'Status']],
  'partner-apps': [['organization', 'Organization ID', 'number'], ['name', 'Application name'], ['redirect_uris', 'Redirect URIs', 'list'], ['scopes', 'Allowed scopes', 'list'], ['jwks_uri', 'JWKS URI'], ['active', 'Active', 'boolean']],
  'fhir-subscriptions': [['application', 'Partner application ID', 'number'], ['criteria', 'Criteria'], ['endpoint', 'Notification endpoint'], ['payload_type', 'Payload type'], ['secret_reference', 'Secret reference'], ['status', 'Status']],
  'regulator-connectors': [['profession', 'Profession'], ['authority', 'Authority'], ['country_code', 'Country code'], ['base_url', 'Base URL'], ['lookup_template', 'Lookup template', 'json'], ['credentials_reference', 'Secret reference'], ['active', 'Active', 'boolean']],
  'verification-automation': [['credential', 'Credential ID', 'number'], ['organization', 'Organization ID', 'number'], ['model_name', 'Model name'], ['model_version', 'Model version'], ['extracted_fields', 'Extracted fields', 'json'], ['document_quality_score', 'Document quality', 'number'], ['match_score', 'Match score', 'number'], ['fraud_score', 'Fraud score', 'number'], ['flags', 'Flags', 'list'], ['regulator_response', 'Regulator response', 'json'], ['recommendation', 'Recommendation'], ['human_decision', 'Human decision']],
  'security-operations': [['operation_type', 'Operation type', 'select', ['upload_scan', 'alert', 'vulnerability_scan', 'backup', 'restore_test', 'disaster_recovery', 'dpia', 'clinical_safety', 'pen_test']], ['status', 'Status'], ['severity', 'Severity'], ['title', 'Title'], ['description', 'Description', 'textarea'], ['scope', 'Scope', 'json'], ['findings', 'Findings', 'json'], ['evidence', 'Evidence', 'json'], ['started_at', 'Started at', 'datetime'], ['completed_at', 'Completed at', 'datetime'], ['next_due_at', 'Next due', 'datetime'], ['owner', 'Owner user ID', 'number'], ['approved_by', 'Approver user ID', 'number']],
  'saved-reports': [['organization', 'Organization ID', 'number'], ['name', 'Report name'], ['domain', 'Domain'], ['definition', 'Definition', 'json'], ['visibility', 'Visibility', 'select', ['private', 'organization', 'platform']]],
  'report-schedules': [['report', 'Saved report ID', 'number'], ['cron_expression', 'Cron expression'], ['recipients', 'Recipients', 'list'], ['formats', 'Formats', 'list'], ['active', 'Active', 'boolean'], ['next_run_at', 'Next run', 'datetime']],
}


const ROLE_PORTALS = {
  clinical_officer: {
    path: 'clinical-officer', title: 'Clinical Officer Workspace', eyebrow: 'Primary and emergency clinical care', icon: 'doctor',
    description: 'Assess patients, create treatment plans, manage admissions, perform procedures and coordinate referrals under facility scope.',
    modules: [
      records('clinical-care', 'Clinical Care', 'clipboard', 'Care plans, observations, risks, handovers and medication schedules.', ['care_plan', 'observation_chart', 'risk_assessment', 'handover', 'medication_schedule']),
      records('emergency-care', 'Emergency Care', 'alert', 'Trauma, resuscitation and emergency observation records.', ['trauma_assessment', 'resuscitation_event', 'emergency_observation'], 'Urgent care'),
      records('maternity-support', 'Maternity Support', 'heart', 'Antenatal, delivery and newborn care within clinical-officer scope.', ['antenatal_visit', 'partograph_observation', 'delivery_record', 'newborn_assessment'], 'Specialist services'),
      records('patient-safety', 'Medication & Transfusion Safety', 'shield', 'Medication administration and blood-transfusion safeguards.', ['medication_dose', 'transfusion'], 'Safety'),
    ],
  },
  dentist: {
    path: 'dentist', title: 'Dental Practice Workspace', eyebrow: 'Oral health and dental procedures', icon: 'doctor',
    description: 'Maintain odontograms, periodontal findings, treatment plans, medicines, imaging and follow-up documentation.',
    modules: [
      records('dental-chart', 'Dental Charts', 'clipboard', 'Structured odontograms, periodontal charts and treatment plans.', ['dental_chart']),
      records('dental-safety', 'Medication Safety', 'pill', 'Interaction, allergy and contraindication checks for dental prescribing.', ['medication_safety_check'], 'Safety'),
      records('dental-imaging', 'Imaging & Critical Findings', 'activity', 'Imaging reports and critical-result acknowledgement.', ['structured_report', 'critical_imaging_alert'], 'Diagnostics'),
      resource('medicine-reference', 'Medicine Reference', 'pill', 'Clinical medication knowledge used during prescribing.', 'medication-knowledge', RESOURCE_FIELDS['medication-knowledge'], 'Reference'),
    ],
  },
  physiotherapist: {
    path: 'physiotherapy', title: 'Physiotherapy Workspace', eyebrow: 'Rehabilitation and functional recovery', icon: 'activity',
    description: 'Document functional assessments, goals, therapy plans, outcomes and safe inpatient mobility.',
    modules: [
      records('therapy-plans', 'Therapy Plans', 'activity', 'Assessments, rehabilitation goals, interventions and home programmes.', ['physiotherapy_plan']),
      records('observations', 'Patient Observations', 'heart', 'Pain, mobility and physiological observations supporting therapy.', ['observation_chart', 'risk_assessment']),
      records('care-coordination', 'Care Coordination', 'users', 'Shared care plans and handovers with the multidisciplinary team.', ['care_plan', 'handover']),
    ],
  },
  nutritionist: {
    path: 'nutrition', title: 'Nutrition & Dietetics Workspace', eyebrow: 'Clinical nutrition and growth monitoring', icon: 'heart',
    description: 'Assess nutritional status, prescribe meal plans and monitor growth and clinical outcomes.',
    modules: [
      records('nutrition-plans', 'Nutrition Plans', 'clipboard', 'Anthropometry, diagnosis, requirements, meal plans and monitoring.', ['nutrition_plan']),
      records('growth-monitoring', 'Growth Monitoring', 'chart', 'Paediatric growth, MUAC and nutrition-status tracking.', ['growth_measurement']),
      records('inpatient-nutrition', 'Inpatient Nutrition', 'bed', 'Risk assessments, fluid balance and multidisciplinary care plans.', ['risk_assessment', 'fluid_balance', 'care_plan']),
    ],
  },
  psychologist: {
    path: 'psychology', title: 'Psychology & Counselling Workspace', eyebrow: 'Mental health and confidential care', icon: 'heart',
    description: 'Document mental-state examinations, risk assessments, interventions and restricted psychotherapy notes.',
    modules: [
      records('sessions', 'Clinical Sessions', 'message', 'Confidential psychology and counselling session records.', ['psychology_session']),
      records('risk-safety', 'Risk & Safety', 'shield', 'Self-harm, suicide and safeguarding risk assessments.', ['risk_assessment'], 'Safety'),
      records('care-planning', 'Care Plans & Handovers', 'users', 'Coordinate approved multidisciplinary follow-up.', ['care_plan', 'handover'], 'Care coordination'),
    ],
  },
  medical_director: {
    path: 'medical-director', title: 'Medical Director Command Centre', eyebrow: 'Clinical governance and patient safety', icon: 'shield',
    description: 'Oversee clinical quality, professional practice, high-risk events, safety cases and regulatory readiness.',
    modules: [
      records('clinical-reviews', 'Clinical Reviews', 'audit', 'Clinical governance reviews, recommendations and action follow-up.', ['medical_director_review']),
      records('safety-cases', 'Clinical Safety Cases', 'shield', 'Hazards, controls, verification evidence and residual risk.', ['clinical_safety_case'], 'Governance'),
      records('quality-risks', 'Quality & Risk', 'alert', 'Patient risks, laboratory quality and critical imaging alerts.', ['risk_assessment', 'quality_control', 'critical_imaging_alert'], 'Governance'),
      resource('clinical-codes', 'Terminology Catalogue', 'file', 'Manage coding systems used in clinical and claims workflows.', 'clinical-codes', RESOURCE_FIELDS['clinical-codes'], 'Standards'),
      resource('reports', 'Executive Reports', 'chart', 'Build and schedule clinical quality reports.', 'saved-reports', RESOURCE_FIELDS['saved-reports'], 'Analytics'),
    ],
  },
  midwife: {
    path: 'midwife', title: 'Midwifery & Maternal Care', eyebrow: 'Pregnancy, labour, delivery and newborn care', icon: 'heart',
    description: 'Deliver continuous maternity care from antenatal assessment through postnatal and child-health follow-up.',
    modules: [
      records('antenatal', 'Antenatal Care', 'calendar', 'Antenatal visits, maternal observations, risk and care planning.', ['antenatal_visit', 'risk_assessment', 'care_plan']),
      records('labour', 'Labour & Partograph', 'activity', 'Digital partograph, contractions, fetal heart rate and maternal monitoring.', ['partograph_observation']),
      records('delivery', 'Delivery & Newborn', 'heart', 'Delivery record, APGAR, newborn assessment and early feeding.', ['delivery_record', 'newborn_assessment']),
      records('child-health', 'Immunisation & Growth', 'shield', 'Vaccine batches, schedules, growth measurements and nutrition status.', ['immunization', 'growth_measurement']),
      records('family-planning', 'Family Planning', 'users', 'Consent, counselling, methods and scheduled follow-up.', ['family_planning']),
      records('medication-rounds', 'Medication & Fluids', 'pill', 'Medication schedules, administered doses, observations and fluid balance.', ['medication_schedule', 'medication_dose', 'fluid_balance'], 'Inpatient care'),
    ],
  },
  theatre_nurse: {
    path: 'theatre-nurse', title: 'Theatre Nursing Workspace', eyebrow: 'Safe surgery and sterile operations', icon: 'activity',
    description: 'Coordinate surgical preparation, counts, implants, recovery, handover and sterilisation traceability.',
    modules: [
      records('theatre-safety', 'Surgical Safety', 'shield', 'Instrument, swab and needle counts with discrepancy escalation.', ['surgical_count']),
      records('implants', 'Implants & Consumables', 'box', 'Implant traceability, lot numbers and surgical usage.', ['implant_usage']),
      records('recovery', 'Recovery & Handover', 'activity', 'Post-anaesthesia observations, recovery scoring and clinical handover.', ['recovery_observation', 'handover']),
      records('sterilisation', 'Sterilisation', 'refresh', 'Sterilisation cycles, indicators and load release.', ['sterilization_cycle']),
      records('theatre-medications', 'Theatre Medications', 'pill', 'Dose administration and intraoperative medication documentation.', ['medication_dose', 'anaesthesia_chart']),
    ],
  },
  records_officer: {
    path: 'records', title: 'Medical Records & Identity', eyebrow: 'Master patient index and information governance', icon: 'file',
    description: 'Resolve duplicate identities, process legal records requests, corrections, release and retention actions.',
    modules: [
      resource('master-index', 'Master Patient Index', 'users', 'Canonical patient identities and matching keys.', 'patient-index', RESOURCE_FIELDS['patient-index']),
      resource('duplicates', 'Duplicate Review', 'alert', 'Review scored duplicate-patient candidates.', 'duplicate-patients', RESOURCE_FIELDS['duplicate-patients']),
      resource('merges', 'Patient Merge Control', 'refresh', 'Approve, execute and reverse controlled patient merges.', 'patient-merges', RESOURCE_FIELDS['patient-merges']),
      resource('requests', 'Records Requests', 'file', 'Access, correction, portability and release-of-information requests.', 'records-requests', RESOURCE_FIELDS['records-requests']),
      records('record-integrity', 'Record Integrity', 'audit', 'Corrections, legal holds, retention and authorised release.', ['record_correction', 'legal_hold', 'retention_action', 'release_information']),
      records('scanning', 'Scanning & Indexing', 'file', 'Classify, OCR and quality-check legacy documents.', ['scanned_document']),
    ],
  },
  accountant: {
    path: 'accounting', title: 'Accounting Workspace', eyebrow: 'Financial control and reconciliation', icon: 'money',
    description: 'Manage periods, bank transactions, reconciliation, supplier liabilities, expenses and adjustment documents.',
    modules: [
      records('periods', 'Financial Periods', 'calendar', 'Open, close and lock reporting periods.', ['financial_period']),
      records('banking', 'Banking & Reconciliation', 'wallet', 'Import bank transactions and reconcile settlements.', ['bank_transaction', 'reconciliation']),
      records('payables', 'Supplier Bills & Expenses', 'invoice', 'Supplier liabilities, expenses and approvals.', ['supplier_bill', 'expense']),
      records('adjustments', 'Credit & Debit Notes', 'file', 'Controlled invoice adjustments with reasons and approvals.', ['credit_note', 'debit_note']),
      records('fiscal', 'Fiscal Documents & Settlements', 'shield', 'Electronic fiscal documents and gateway settlement batches.', ['fiscal_document', 'settlement']),
      resource('reports', 'Financial Reports', 'chart', 'Run financial, revenue, receivable and reconciliation reports.', 'saved-reports', RESOURCE_FIELDS['saved-reports']),
    ],
  },
  finance_manager: {
    path: 'finance', title: 'Finance Management Centre', eyebrow: 'Revenue, controls and financial performance', icon: 'chart',
    description: 'Approve adjustments, oversee revenue cycles, reconcile payers and manage reporting and financial governance.',
    modules: [
      records('financial-control', 'Financial Controls', 'shield', 'Periods, reconciliations, disputes and settlement controls.', ['financial_period', 'reconciliation', 'payment_dispute', 'settlement']),
      records('payables', 'Payables & Expenses', 'invoice', 'Supplier bills, expenses, credit notes and debit notes.', ['supplier_bill', 'expense', 'credit_note', 'debit_note']),
      resource('tariffs', 'Tariff Schedules', 'money', 'Payer and provider service tariffs.', 'tariffs', RESOURCE_FIELDS['tariffs']),
      resource('contracts', 'Payer Contracts', 'file', 'Contract terms, effective dates and linked tariffs.', 'payer-contracts', RESOURCE_FIELDS['payer-contracts']),
      resource('reports', 'Executive Financial Reports', 'chart', 'Create and schedule finance reports.', 'saved-reports', RESOURCE_FIELDS['saved-reports']),
    ],
  },
  procurement_officer: {
    path: 'procurement', title: 'Procurement & Supply Chain', eyebrow: 'Purchasing, inventory and supplier control', icon: 'truck',
    description: 'Control procurement, stock counting, cold chain, recalls and supplier financial documentation.',
    modules: [
      records('stock-counts', 'Stock Counts', 'box', 'Count sessions, variances, approvals and corrective movements.', ['stock_count']),
      records('cold-chain', 'Cold Chain', 'activity', 'Temperature observations, excursions and corrective action.', ['cold_chain']),
      records('recalls', 'Product Recalls', 'alert', 'Recall notices, affected batches and completion tracking.', ['recall']),
      records('supplier-bills', 'Supplier Bills', 'invoice', 'Supplier invoice, purchase-order and receiving references.', ['supplier_bill']),
      resource('medicine-catalogue', 'Medicine Catalogue', 'pill', 'Reference data for medicine purchasing and formulary control.', 'medication-knowledge', RESOURCE_FIELDS['medication-knowledge'], 'Reference'),
    ],
  },
  quality_officer: {
    path: 'quality', title: 'Quality & Patient Safety', eyebrow: 'Incidents, risk, quality control and improvement', icon: 'shield',
    description: 'Monitor clinical risks, quality controls, safety cases, corrective actions and assurance evidence.',
    modules: [
      records('patient-risks', 'Patient Risk Assessments', 'alert', 'Falls, pressure injuries, infection and other clinical risks.', ['risk_assessment']),
      records('laboratory-quality', 'Laboratory Quality', 'flask', 'Quality-control runs, calibrations and remediation.', ['quality_control', 'calibration']),
      records('clinical-safety', 'Clinical Safety', 'shield', 'Safety cases, hazards and control evidence.', ['clinical_safety_case']),
      records('security-quality', 'Operational Assurance', 'audit', 'Vulnerability scans, backup restore tests and upload scans.', ['vulnerability_scan', 'backup_restore', 'upload_scan']),
      resource('reports', 'Quality Reports', 'chart', 'Save and schedule quality and patient-safety reports.', 'saved-reports', RESOURCE_FIELDS['saved-reports']),
    ],
  },
  compliance_officer: {
    path: 'compliance', title: 'Privacy, Compliance & Verification', eyebrow: 'Data protection and regulatory assurance', icon: 'shield',
    description: 'Control privacy requests, licence verification, DPIAs, legal holds, audit evidence and security investigations.',
    modules: [
      records('privacy-assessments', 'Data Protection Impact Assessments', 'shield', 'Processing purposes, lawful basis, risks and controls.', ['dpia']),
      records('records-governance', 'Records Governance', 'file', 'Corrections, legal holds, retention and release.', ['record_correction', 'legal_hold', 'retention_action', 'release_information']),
      records('verification-screening', 'Verification Screening Records', 'doctor', 'Trace OCR findings, regulator results, mismatch flags and human decisions.', ['verification_scan']),
      resource('verification', 'Verification Automation', 'doctor', 'OCR, quality, matching, regulator checks and human review.', 'verification-automation', RESOURCE_FIELDS['verification-automation']),
      resource('regulators', 'Regulator Connectors', 'globe', 'Configure professional regulator lookup services.', 'regulator-connectors', RESOURCE_FIELDS['regulator-connectors']),
      resource('security', 'Security Operations', 'alert', 'Track privacy, security and resilience operations.', 'security-operations', RESOURCE_FIELDS['security-operations']),
      resource('reports', 'Compliance Reports', 'chart', 'Create and schedule compliance reports.', 'saved-reports', RESOURCE_FIELDS['saved-reports']),
    ],
  },
  hr_officer: {
    path: 'hr', title: 'Human Resources & Workforce', eyebrow: 'Roles, credentials, shifts and staff lifecycle', icon: 'users',
    description: 'Maintain role contexts, temporary delegation, workforce scope and staff compliance across facilities.',
    modules: [
      resource('role-contexts', 'Role Contexts', 'users', 'Assign a user to a role, organization, branch and department.', 'contexts', [['user', 'User ID', 'number'], ['organization', 'Organization ID', 'number'], ['location', 'Branch ID', 'number'], ['department', 'Department ID', 'number'], ['role_code', 'Role code'], ['title', 'Title'], ['permissions', 'Additional permissions', 'list'], ['is_primary', 'Primary context', 'boolean'], ['active', 'Active', 'boolean'], ['starts_on', 'Starts on', 'date'], ['ends_on', 'Ends on', 'date']]),
      resource('delegations', 'Temporary Delegations', 'refresh', 'Time-bound delegation with explicit permissions.', 'delegations', [['delegator_context', 'Delegator context ID', 'number'], ['delegatee_context', 'Delegatee context ID', 'number'], ['permissions', 'Delegated permissions', 'list'], ['reason', 'Reason', 'textarea'], ['starts_at', 'Starts at', 'datetime'], ['ends_at', 'Ends at', 'datetime']]),
      records('staff-risk', 'Workforce Safety & Handover', 'shield', 'Clinical handovers and role-related safety tracking.', ['handover', 'clinical_safety_case'], 'Governance'),
    ],
  },
  it_support: {
    path: 'it-operations', title: 'Technology Operations Centre', eyebrow: 'Integrations, security, observability and resilience', icon: 'settings',
    description: 'Operate channels, FHIR, event delivery, PACS, security, backup, feature configuration and external integrations.',
    modules: [
      resource('providers', 'Communication Providers', 'message', 'Email, SMS, WhatsApp, push and voice provider routing.', 'notification-providers', RESOURCE_FIELDS['notification-providers']),
      resource('integrations', 'Integration Endpoints', 'globe', 'Webhooks, Kafka REST, RabbitMQ bridges, FHIR and data platforms.', 'integration-endpoints', RESOURCE_FIELDS['integration-endpoints']),
      resource('events', 'Event Delivery', 'send', 'Delivery status, retries and event payloads.', 'event-deliveries', RESOURCE_FIELDS['event-deliveries']),
      resource('schemas', 'Event Schemas', 'file', 'Versioned schemas for system integration events.', 'event-schemas', RESOURCE_FIELDS['event-schemas']),
      resource('fhir', 'FHIR Resource Store', 'activity', 'Versioned FHIR resources and search data.', 'fhir-resources', RESOURCE_FIELDS['fhir-resources']),
      resource('partners', 'Partner Applications', 'users', 'Partner clients, scopes and token issuance.', 'partner-apps', RESOURCE_FIELDS['partner-apps']),
      resource('subscriptions', 'FHIR Subscriptions', 'bell', 'Partner subscription criteria and callbacks.', 'fhir-subscriptions', RESOURCE_FIELDS['fhir-subscriptions']),
      resource('pacs', 'PACS & DICOM Nodes', 'activity', 'PACS endpoints, AE titles and DICOMweb access.', 'pacs-nodes', RESOURCE_FIELDS['pacs-nodes']),
      records('security-alerts', 'Security Alerts', 'alert', 'Investigate suspicious access, provider failures and response actions.', ['security_alert']),
      resource('security', 'Security Operations', 'shield', 'Vulnerability, backup, restore and incident operations.', 'security-operations', RESOURCE_FIELDS['security-operations']),
      resource('feature-config', 'Feature Configuration', 'settings', 'Feature flags, country configuration and maintenance controls.', 'feature-config', RESOURCE_FIELDS['feature-config']),
    ],
  },
  claims_reviewer: {
    path: 'claims-review', title: 'Claims Medical Review', eyebrow: 'Clinical claims adjudication and payer assurance', icon: 'insurance',
    description: 'Review claim events, queries, appeals, fraud flags, contracts, tariffs and remittance evidence.',
    modules: [
      records('claim-lifecycle', 'Claim Lifecycle', 'insurance', 'Submission, queries, review, decisions and payments.', ['claim_event']),
      records('appeals', 'Appeals', 'refresh', 'Appeal grounds, evidence, review and decisions.', ['claim_appeal']),
      records('claim-messages', 'Claim Queries & Messages', 'message', 'Structured payer-provider claim conversations.', ['claim_message']),
      records('fraud', 'Fraud & Abuse Flags', 'alert', 'Rules, evidence, risk scoring and investigation status.', ['fraud_flag']),
      records('remittance', 'Settlement Import', 'money', 'Remittance batches, allocations and reconciliation.', ['settlement_import']),
      resource('tariffs', 'Tariff Schedules', 'money', 'Contracted service pricing.', 'tariffs', RESOURCE_FIELDS['tariffs']),
      resource('contracts', 'Provider Contracts', 'file', 'Payer-provider contracts and terms.', 'payer-contracts', RESOURCE_FIELDS['payer-contracts']),
    ],
  },
  radiographer: {
    path: 'radiography', title: 'Radiography & Modality Workspace', eyebrow: 'Imaging acquisition and radiation safety', icon: 'activity',
    description: 'Manage modality worklists, acquisition metadata, dose records and secure PACS handoff.',
    modules: [
      records('worklist', 'Modality Worklist', 'clipboard', 'Scheduled imaging tasks, modality, room and patient preparation.', ['modality_worklist']),
      records('dose', 'Radiation Dose', 'shield', 'CTDI, DLP, exposure, repeats and dose alerts.', ['radiation_dose']),
      resource('studies', 'Imaging Studies', 'activity', 'DICOM studies, accessions, series and viewer links.', 'imaging-studies', RESOURCE_FIELDS['imaging-studies']),
      resource('pacs', 'PACS Connections', 'globe', 'PACS nodes and DICOMweb connectivity.', 'pacs-nodes', RESOURCE_FIELDS['pacs-nodes']),
    ],
  },
  anaesthetist: {
    path: 'anaesthesia', title: 'Anaesthesia Workspace', eyebrow: 'Perioperative assessment and monitoring', icon: 'activity',
    description: 'Complete pre-anaesthetic assessment, airway planning, intraoperative charting and recovery transfer.',
    modules: [
      records('pre-op', 'Pre-Anaesthetic Assessment', 'clipboard', 'ASA classification, airway, fasting, comorbidities and consent.', ['pre_anaesthetic_assessment']),
      records('anaesthesia-chart', 'Anaesthesia Chart', 'activity', 'Technique, induction, medicines, fluids and clinical events.', ['anaesthesia_chart']),
      records('intraoperative', 'Intraoperative Monitoring', 'heart', 'Time-stamped vital signs and ventilator observations.', ['intraoperative_observation']),
      records('recovery', 'Recovery & Handover', 'refresh', 'Recovery scoring, airway, pain and transfer readiness.', ['recovery_observation', 'handover']),
    ],
  },
  paramedic: {
    path: 'paramedic', title: 'Paramedic Mobile Workspace', eyebrow: 'Pre-hospital emergency care', icon: 'activity',
    description: 'Capture scene assessment, trauma, interventions, resuscitation, observations and receiving-facility handover.',
    modules: [
      records('prehospital', 'Pre-Hospital Care', 'truck', 'Scene, mechanism, primary survey, interventions and destination.', ['prehospital_record']),
      records('trauma', 'Trauma Assessment', 'alert', 'GCS, injuries, haemorrhage control and trauma activation.', ['trauma_assessment']),
      records('resuscitation', 'Resuscitation', 'heart', 'CPR timeline, rhythm, shocks, medications and outcome.', ['resuscitation_event']),
      records('observation', 'Emergency Observations', 'activity', 'Observation episodes, reassessment and disposition.', ['emergency_observation', 'observation_chart']),
      resource('vehicles', 'Ambulance Vehicles', 'truck', 'Assigned vehicle, equipment and operational status.', 'ambulance-vehicles', RESOURCE_FIELDS['ambulance-vehicles']),
    ],
  },
  ambulance_dispatcher: {
    path: 'dispatch', title: 'Ambulance Dispatch Centre', eyebrow: 'Live fleet coordination and emergency response', icon: 'truck',
    description: 'Coordinate vehicles, crews, GPS telemetry, response status and mass-casualty incidents.',
    modules: [
      resource('fleet', 'Fleet & Crews', 'truck', 'Ambulance availability, equipment and crew assignment.', 'ambulance-vehicles', RESOURCE_FIELDS['ambulance-vehicles']),
      resource('telemetry', 'Live Telemetry', 'activity', 'Vehicle location, speed, heading and dispatch association.', 'ambulance-telemetry', RESOURCE_FIELDS['ambulance-telemetry']),
      records('incidents', 'Emergency Incidents', 'alert', 'Pre-hospital incidents, emergency observations and mass casualty.', ['prehospital_record', 'emergency_observation', 'mass_casualty']),
    ],
  },
  insurance_officer: {
    path: 'insurance-officer', title: 'Insurance Operations Workspace', eyebrow: 'Eligibility, authorisation, claims and settlement', icon: 'insurance',
    description: 'Coordinate claim events, payer queries, appeals, remittance and contracted coverage controls.',
    modules: [
      records('claims', 'Claims Lifecycle', 'insurance', 'Claim submission, query, adjudication, approval and payment events.', ['claim_event']),
      records('appeals', 'Appeals & Queries', 'message', 'Appeals and structured claim communication.', ['claim_appeal', 'claim_message']),
      records('fraud', 'Fraud Review', 'alert', 'Potential fraud, waste and abuse flags.', ['fraud_flag']),
      records('remittance', 'Remittance & Settlement', 'money', 'Import and reconcile insurer remittance.', ['settlement_import']),
      resource('tariffs', 'Tariffs', 'money', 'Coverage tariffs and service prices.', 'tariffs', RESOURCE_FIELDS['tariffs']),
      resource('contracts', 'Contracts', 'file', 'Payer-provider contract management.', 'payer-contracts', RESOURCE_FIELDS['payer-contracts']),
    ],
  },
  storekeeper: {
    path: 'storekeeping', title: 'Storekeeping & Inventory Control', eyebrow: 'Batches, cold chain, counts and recalls', icon: 'box',
    description: 'Maintain safe stock levels, physical counts, cold-chain evidence, expiry controls and product recalls.',
    modules: [
      records('counts', 'Stock Counts', 'box', 'Physical counts, book quantities, variance and approval.', ['stock_count']),
      records('cold-chain', 'Cold Chain', 'activity', 'Temperature monitoring and excursion response.', ['cold_chain']),
      records('recalls', 'Product Recalls', 'alert', 'Affected batches, quarantine, returns and closure.', ['recall']),
      records('controlled-drugs', 'Controlled Medicines', 'shield', 'Controlled-drug receipts, dispensing, balances and witnesses.', ['controlled_drug_entry']),
      resource('medicine-reference', 'Medicine Reference', 'pill', 'Medication catalogue and safety guidance.', 'medication-knowledge', RESOURCE_FIELDS['medication-knowledge']),
    ],
  },
}

export function portalForRole(role) {
  return ROLE_PORTALS[role]
}

export function portalRoles() {
  return Object.keys(ROLE_PORTALS)
}

export { ROLE_PORTALS }
