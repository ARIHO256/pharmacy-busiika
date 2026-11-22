import { useCallback, useEffect, useRef, useState } from 'react'
import { useOutletContext, useSearchParams } from 'react-router-dom'
import { operationsApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { displayDate, getError, statusBadge } from '../staff/shared'

const sections = [
  ['admissions', 'Admissions'], ['medication-schedules', 'Medication schedules'],
  ['procedures', 'Procedures'], ['referrals', 'Referrals'],
  ['imaging', 'Imaging'], ['offline-nodes', 'Offline review'],
]
const inpatient = new Set(['admissions', 'medication-schedules', 'procedures'])
const numberField = (key, label, required = true) => ({ key, label, type: 'number', required })
const textField = (key, label, required = true) => ({ key, label, type: 'text', required })
const longField = (key, label, required = true) => ({ key, label, type: 'textarea', required })
const dateField = (key, label) => ({ key, label, type: 'datetime-local', required: true })

export default function Operations({ resource, resources, facilityOnly = false }) {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const recordId = searchParams.get('record')
  const originatingVisit = searchParams.get('visit') || ''
  const activeFacility = useOutletContext()?.organization?.id
  const [context, setContext] = useState(null)
  const [organization, setOrganization] = useState('')
  const matching = context?.organizations.find((org) => String(org.id) === organization)
  const availableSections = sections.filter(([key]) => {
    if (resources && !resources.includes(key)) return false
    if (user?.role === 'nurse' && ['referrals', 'imaging'].includes(key)) return false
    return !matching || matching.type === 'hospital' || !inpatient.has(key)
  })
  const [selected, setSection] = useState('')
  const section = resource || availableSections.find(([key]) => key === selected)?.[0] || availableSections[0]?.[0]
  const [rows, setRows] = useState([])
  const [page, setPage] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [patients, setPatients] = useState([])
  const [patientLoading, setPatientLoading] = useState(false)
  const [patientSearch, setPatientSearch] = useState('')
  const [node, setNode] = useState(null)
  const [changes, setChanges] = useState([])
  const [changePreview, setChangePreview] = useState(null)
  const requestId = useRef(0)
  const label = sections.find(([key]) => key === section)?.[1]

  useEffect(() => {
    let active = true
    operationsApi.context().then(({ data }) => {
      if (!active) return
      const inScope = data.organizations.filter((org) => {
        if (facilityOnly && org.id !== activeFacility) return false
        if (resource && inpatient.has(resource)) return org.type === 'hospital'
        return ['clinic', 'hospital'].includes(org.type)
      })
      setContext({ ...data, organizations: inScope })
      setOrganization(String(inScope[0]?.id || ''))
      if (!inScope.length) setLoading(false)
    }).catch((err) => { if (active) { setError(getError(err)); setLoading(false) } })
    return () => { active = false }
  }, [facilityOnly, activeFacility, resource])

  useEffect(() => {
    if (!organization || !section) return undefined
    const id = ++requestId.current
    setLoading(true)
    setError('')
    Promise.all([
      operationsApi.context(organization),
      recordId ? operationsApi.record(section, recordId) : operationsApi.list(section, { organization, page }),
    ]).then(([scope, result]) => {
      if (id !== requestId.current) return
      setContext((current) => ({ ...scope.data, organizations: current.organizations }))
      setRows(recordId ? [result.data] : result.data.results || [])
      setHasNext(Boolean(result.data.next))
    }).catch((err) => { if (id === requestId.current) setError(getError(err)) })
      .finally(() => { if (id === requestId.current) setLoading(false) })
    return () => { requestId.current += 1 }
  }, [organization, section, page, refresh, recordId])

  useEffect(() => {
    if (!modal?.patientPicker || !organization) return undefined
    let active = true
    setPatientLoading(true)
    const timer = setTimeout(() => operationsApi.context(organization, patientSearch).then(({ data }) => {
      if (active) setPatients(data.patients || [])
    }).catch((err) => { if (active) setSaveError(getError(err)) })
      .finally(() => { if (active) setPatientLoading(false) }), 250)
    return () => { active = false; clearTimeout(timer) }
  }, [modal, organization, patientSearch])

  const open = (definition) => {
    setSaveError('')
    setForm({})
    setPatients([])
    setPatientSearch('')
    setModal(definition)
  }

  const save = async (event) => {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setSaveError('')
    try {
      const data = { ...modal.defaults }
      for (const field of modal.fields) {
        const value = form[field.key]
        if (value === '' || value === undefined) continue
        data[field.key] = field.type === 'number' || field.numeric ? Number(value)
          : field.type === 'datetime-local' ? new Date(value).toISOString() : value
      }
      if (!data.visit) delete data.visit
      if (modal.create) await operationsApi.create(modal.resource, { organization: Number(organization), ...data })
      else await operationsApi.action(modal.resource, modal.id, modal.action || 'transition', data)
      setModal(null)
      setRefresh((value) => value + 1)
      if (node) await loadChanges(node)
    } catch (err) {
      setSaveError(getError(err))
    } finally {
      setSaving(false)
    }
  }

  const loadChanges = useCallback(async (record) => {
    setNode(record)
    setChanges([])
    try {
      const { data } = await operationsApi.offlineChanges(record.id)
      setChanges(data.results || [])
    } catch (err) { setError(getError(err)) }
  }, [])

  const doctorField = { key: 'attending_doctor', label: 'Attending doctor', type: 'select', required: true, numeric: true,
    options: context?.doctors || [] }
  const bedField = { key: 'bed', label: 'Bed', type: 'select', required: true, numeric: true,
    options: (context?.beds || []).filter((bed) => !bed.is_occupied) }
  const patientField = { key: 'patient', label: 'Patient', type: 'select', required: true, numeric: true, options: patients }

  const createRecord = () => {
    const shared = { resource: section, create: true, title: section === 'admissions' ? 'Admit patient' : `Create ${label.toLowerCase()}` }
    if (section === 'admissions') open({ ...shared, defaults: { visit: originatingVisit }, patientPicker: true, fields: [patientField, doctorField, { ...bedField, required: false }, numberField('visit', 'Originating visit ID', false), longField('reason', 'Admission reason')] })
    if (section === 'medication-schedules') open({ ...shared, fields: [numberField('admission', 'Admission ID'), numberField('prescription', 'Prescription ID'), textField('medication_name', 'Medicine'), textField('dose', 'Prescribed dose'), textField('route', 'Route'), dateField('due_at', 'Due at')] })
    if (section === 'procedures') open({ ...shared, patientPicker: true, fields: [patientField, { ...doctorField, key: 'surgeon', label: 'Surgeon' }, numberField('admission', 'Admission ID (optional)', false), textField('theatre', 'Theatre'), textField('procedure', 'Procedure'), dateField('starts_at', 'Starts at'), dateField('ends_at', 'Ends at')] })
    if (section === 'referrals') open({ ...shared, fields: [numberField('referral', 'Sent referral ID')] })
    if (section === 'imaging') open({ ...shared, patientPicker: true, fields: [patientField, { ...doctorField, key: 'referring_doctor', label: 'Referring doctor' }, { key: 'modality', label: 'Modality', type: 'select', required: true, options: ['CT', 'MR', 'US', 'CR', 'DX', 'NM', 'MG', 'OT'].map((id) => ({ id, name: id })) }, textField('body_site', 'Body site'), longField('indication', 'Clinical indication')] })
    if (section === 'offline-nodes') open({ ...shared, fields: [textField('name', 'Facility terminal name')] })
  }

  const transition = (row, status, fields = [], defaults = {}) => open({
    resource: section, id: row.id, title: status.replaceAll('_', ' '), fields,
    defaults: { status, ...(row.version ? { version: row.version } : {}), ...defaults },
  })

  const actions = (row) => {
    if (section === 'admissions' && row.status === 'admitted') return <div className="flex gap-2">
      <Button variant="outline" onClick={() => open({ resource: section, id: row.id, title: 'Transfer patient', defaults: { action: 'transfer', version: row.version }, fields: [bedField] })}>Transfer</Button>
      {context.can_discharge && <Button variant="outline" onClick={() => open({ resource: section, id: row.id, title: 'Discharge patient', defaults: { action: 'discharge', version: row.version }, fields: [longField('summary', 'Discharge summary'), longField('follow_up', 'Follow-up', false)] })}>Discharge</Button>}
    </div>
    if (section === 'medication-schedules' && row.status === 'scheduled' && context.can_administer) return <Button variant="outline" onClick={() => open({ resource: section, id: row.id, action: 'administer', title: 'Record medication administration', fields: [{ key: 'status', label: 'Outcome', type: 'select', required: true, options: ['given', 'withheld', 'refused', 'cancelled'].map((id) => ({ id, name: id })) }, longField('notes', 'Administration notes', false)] })}>Record administration</Button>
    if (section === 'procedures') return <div className="flex gap-2">
      {row.status === 'scheduled' && <Button variant="outline" onClick={() => transition(row, 'cancelled', [longField('notes', 'Cancellation reason')])}>Cancel</Button>}
      {context.can_prescribe && row.status === 'scheduled' && <Button variant="outline" onClick={() => transition(row, 'in_progress')}>Start</Button>}
      {context.can_prescribe && row.status === 'in_progress' && <Button variant="outline" onClick={() => transition(row, 'completed', [longField('notes', 'Procedure outcome')])}>Complete</Button>}
    </div>
    if (section === 'referrals' && context.can_close_referrals) return <div className="flex flex-wrap gap-2">
      {row.outcome && <p>{row.outcome}</p>}
      {context.organizations.some((org) => org.id === row.organization) && row.status === 'sent' && <Button variant="outline" onClick={() => transition(row, 'accepted')}>Accept</Button>}
      {context.organizations.some((org) => org.id === row.organization) && row.status === 'sent' && <Button variant="outline" onClick={() => transition(row, 'declined', [longField('outcome', 'Reason')])}>Decline</Button>}
      {context.organizations.some((org) => org.id === row.organization) && row.status === 'accepted' && <Button variant="outline" onClick={() => transition(row, 'in_progress')}>Start</Button>}
      {context.organizations.some((org) => org.id === row.organization) && row.status === 'in_progress' && <Button variant="outline" onClick={() => transition(row, 'completed', [longField('outcome', 'Referral outcome')])}>Complete</Button>}
    </div>
    if (section === 'imaging') return <div className="flex flex-wrap gap-2">
      {row.report && <p>{row.report}</p>}
      {row.status === 'ordered' && <Button variant="outline" onClick={() => transition(row, 'scheduled', [dateField('scheduled_at', 'Appointment time')])}>Schedule</Button>}
      {context.can_acquire_imaging && row.status === 'scheduled' && <Button variant="outline" onClick={() => transition(row, 'acquired', [textField('study_uid', 'DICOM study UID')])}>Link acquired study</Button>}
      {context.can_report_imaging && row.status === 'acquired' && <Button variant="outline" onClick={() => transition(row, 'reported', [longField('report', 'Diagnostic report')])}>Report</Button>}
    </div>
    if (section === 'offline-nodes') return <Button variant="outline" onClick={() => loadChanges(row)}>Review changes</Button>
    return null
  }

  const canCreate = ['admissions', 'procedures', 'offline-nodes'].includes(section)
    || (section === 'medication-schedules' && context?.can_prescribe)
    || (section === 'referrals' && context?.can_close_referrals)
    || (section === 'imaging' && context?.can_report_imaging)
  const columns = [
    { key: 'id', label: 'Reference', render: (row) => `#${row.id}` },
    ...(section === 'offline-nodes' ? [{ key: 'name', label: 'Terminal' }] : [{ key: 'patient_name', label: 'Patient' }]),
    ...(section === 'admissions' ? [
      { key: 'bed', label: 'Ward / bed', render: (row) => context?.beds?.find((bed) => bed.id === row.bed)?.name || (row.bed ? `Bed #${row.bed}` : 'Unassigned') },
      { key: 'attending_doctor', label: 'Attending doctor', render: (row) => context?.doctors?.find((doctor) => doctor.id === row.attending_doctor)?.name || `#${row.attending_doctor}` },
      { key: 'admitted_at', label: 'Admitted', render: (row) => displayDate(row.admitted_at) },
    ] : []),
    ...(section === 'medication-schedules' ? [{ key: 'medication_name', label: 'Medicine' }, { key: 'dose', label: 'Dose' }, { key: 'due_at', label: 'Due', render: (row) => displayDate(row.due_at) }] : []),
    ...(section === 'procedures' ? [{ key: 'procedure', label: 'Procedure' }, { key: 'theatre', label: 'Theatre' }, { key: 'starts_at', label: 'Starts', render: (row) => displayDate(row.starts_at) }] : []),
    ...(section === 'referrals' ? [{ key: 'specialty', label: 'Specialty' }, { key: 'reason', label: 'Reason' }] : []),
    ...(section === 'imaging' ? [{ key: 'modality', label: 'Modality' }, { key: 'body_site', label: 'Body site' }] : []),
    { key: 'status', label: 'Status', render: (row) => statusBadge(section === 'offline-nodes' ? row.active ? 'active' : 'inactive' : row.status) },
    { key: 'actions', label: 'Actions', render: actions },
  ]

  if (!loading && context && !context.organizations.length) {
    return <Alert>{resource && inpatient.has(resource)
      ? 'A verified hospital assignment is required for this workflow.'
      : 'A verified clinic or hospital assignment is required.'}</Alert>
  }

  return <div className="space-y-5">
    {error && <Alert tone="danger">{error}</Alert>}
    {context && !facilityOnly && <Select label="Facility" value={organization} onChange={(event) => { setOrganization(event.target.value); setPage(1); setNode(null) }}>
      {!context.organizations.length && <option value="">No verified facility membership</option>}
      {context.organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
    </Select>}
    {!resource && <div className="flex flex-wrap gap-2">{availableSections.map(([key, title]) => <Button key={key} variant={section === key ? 'primary' : 'outline'} onClick={() => { setSection(key); setPage(1); setNode(null) }} aria-pressed={section === key}>{title}</Button>)}</div>}
    <Card title={label} actions={<div className="flex gap-2"><Button variant="outline" disabled={loading || !organization} onClick={() => setRefresh((value) => value + 1)}>Refresh</Button>{canCreate && <Button disabled={!organization || loading || Boolean(error)} onClick={createRecord}>{section === 'admissions' ? 'Admit patient' : 'Add record'}</Button>}</div>}>
      {loading ? <Spinner /> : !error && <Table rows={rows} columns={columns} empty="No records in this facility" />}
      {(page > 1 || hasNext) && <div className="flex justify-end gap-2 mt-4"><Button variant="outline" disabled={loading || Boolean(error) || page === 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button variant="outline" disabled={loading || Boolean(error) || !hasNext} onClick={() => setPage((value) => value + 1)}>Next</Button></div>}
    </Card>
    {node && <Card title={`Changes from ${node.name}`} subtitle="Captured records enter the clinical record only after review by an authorized clinician.">
      <Table rows={changes} empty="No submitted changes" columns={[
        { key: 'change_id', label: 'Change' }, { key: 'kind', label: 'Record type' },
        { key: 'status', label: 'Status', render: (row) => statusBadge(row.status) },
        { key: 'actions', label: 'Review', render: (row) => row.status === 'pending' && context.can_review_offline ? <div className="flex gap-2"><Button variant="outline" onClick={async () => { try { const { data } = await operationsApi.offlinePreview(node.id, row.id); setChangePreview(data) } catch (err) { setError(getError(err)) } }}>View captured record</Button>{['apply', 'reject'].map((decision) => <Button key={decision} variant="outline" onClick={() => open({ resource: 'offline-nodes', id: node.id, action: 'review', title: `${decision} offline change`, defaults: { change: row.id, decision }, fields: [longField('reason', 'Review reason')] })}>{decision === 'apply' ? 'Apply' : 'Reject'}</Button>)}</div> : '—' },
      ]} />
    </Card>}
    <Modal open={Boolean(modal)} onClose={() => { if (!saving) setModal(null) }} title={modal?.title}>
      {modal && <form onSubmit={save} className="space-y-4">
        {saveError && <Alert tone="danger">{saveError}</Alert>}
        {modal.patientPicker && <Input label="Find patient" value={patientSearch} onChange={(event) => { setPatientSearch(event.target.value); setPatients([]); setForm((current) => ({ ...current, patient: '' })) }} placeholder="Search by patient name" hint="Shows patients registered for care at the selected facility." />}
        {modal.patientPicker && !saveError && (patientLoading
          ? <p role="status" className="text-sm text-slate-600">Searching facility patients…</p>
          : !patients.length && <Alert title="No matching patients">
              Try another name. For a patient new to this facility, complete check-in first.
            </Alert>)}
        {modal.resource === 'admissions' && modal.create && !doctorField.options.length &&
          <Alert tone="warning" title="No verified attending doctors">Assign a verified doctor to this facility before admitting a patient.</Alert>}
        {modal.fields.map((field) => {
          const shared = { key: field.key, label: field.label, required: field.required, value: form[field.key] || '', onChange: (event) => setForm((current) => ({ ...current, [field.key]: event.target.value })) }
          if (field.type === 'textarea') return <Textarea {...shared} />
          if (field.type === 'select') return <Select {...shared}><option value="">Select…</option>{(field.key === 'patient' ? patients : field.options || []).map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}</Select>
          return <Input {...shared} type={field.type} min={field.type === 'number' ? 1 : undefined} />
        })}
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="outline" disabled={saving} onClick={() => setModal(null)}>Cancel</Button>
          <Button type="submit" disabled={saving || (modal.patientPicker && !form.patient)}>
            {saving ? 'Saving…' : modal.resource === 'admissions' && modal.create ? 'Confirm admission' : 'Save'}
          </Button>
        </div>
      </form>}
    </Modal>
    <Modal open={Boolean(changePreview)} onClose={() => setChangePreview(null)} title="Captured record">
      {changePreview && <dl className="space-y-3">{Object.entries(changePreview.payload).map(([key, value]) => <div key={key}><dt className="font-medium text-slate-800">{key.replaceAll('_', ' ')}</dt><dd className="text-sm text-slate-600">{String(value)}</dd></div>)}</dl>}
    </Modal>
  </div>
}
