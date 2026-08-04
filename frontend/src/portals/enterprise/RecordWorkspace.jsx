import { useEffect, useMemo, useState } from 'react'
import { enterpriseApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'
import FormField, { initialFieldValue, normalizeFieldValue } from './FormField'
import EntitySearchSelect from './components/EntitySearchSelect'
import ClinicalVisualization from './components/ClinicalVisualizations'

const statusColor = (status) => ['completed', 'closed', 'resolved', 'given', 'acknowledged', 'verified', 'released', 'approved'].includes(status) ? 'green' : ['rejected', 'cancelled', 'infected', 'failed', 'omitted'].includes(status) ? 'red' : ['critical', 'escalated', 'overdue'].includes(status) ? 'orange' : ['draft', 'pending', 'scheduled'].includes(status) ? 'yellow' : 'blue'
const rowsFrom = (data) => Array.isArray(data) ? data : data?.results || []
const PAGE_SIZE = 10

function defaultStatus(schema) {
  const states = Object.keys(schema?.workflow || {})
  return states.includes('draft') ? 'draft' : states[0] || 'draft'
}

function emptyPayload(schema) {
  return Object.fromEntries(Object.entries(schema?.fields || {}).map(([name, spec]) => [name, initialFieldValue(spec)]))
}

function toCsv(rows) {
  const headers = ['reference', 'record_type', 'title', 'patient_name', 'priority', 'status', 'occurred_at', 'summary']
  const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
  return [headers.join(','), ...rows.map((row) => headers.map((key) => escape(row[key])).join(','))].join('\n')
}

function download(name, contents, type = 'text/csv') {
  const url = URL.createObjectURL(new Blob([contents], { type }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  URL.revokeObjectURL(url)
}

function entityValue(form, key) {
  return form[key] || ''
}

export default function RecordWorkspace({ module }) {
  const draftKey = `mydoctor:draft:${module.id}`
  const [catalog, setCatalog] = useState({})
  const [records, setRecords] = useState([])
  const [selectedType, setSelectedType] = useState(module.recordTypes[0])
  const [selected, setSelected] = useState(null)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [detailTab, setDetailTab] = useState('overview')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [page, setPage] = useState(1)
  const [checked, setChecked] = useState([])
  const [attachment, setAttachment] = useState(null)
  const [form, setForm] = useState({ title: '', summary: '', patient: '', admission: '', appointment: '', assigned_to: '', priority: 'routine', payload: {} })

  const schema = catalog[selectedType]
  const load = async () => {
    setBusy(true)
    setError('')
    try {
      const [{ data: schemas }, { data }] = await Promise.all([
        enterpriseApi.schema(),
        enterpriseApi.records({ record_type: selectedType, q: query || undefined, status: statusFilter || undefined, priority: priorityFilter || undefined }),
      ])
      setCatalog(schemas?.schemas || schemas || {})
      setRecords(rowsFrom(data))
      setPage(1)
      setChecked([])
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Unable to load this workflow.')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { load() }, [selectedType, statusFilter, priorityFilter])
  useEffect(() => {
    if (schema && creating && !Object.keys(form.payload || {}).length) setForm((value) => ({ ...value, payload: emptyPayload(schema) }))
  }, [schema, creating])
  useEffect(() => {
    if (!creating || editing) return
    const timer = setTimeout(() => localStorage.setItem(draftKey, JSON.stringify({ selectedType, form, savedAt: new Date().toISOString() })), 400)
    return () => clearTimeout(timer)
  }, [creating, editing, draftKey, form, selectedType])
  useEffect(() => {
    const warn = (event) => {
      if (!creating) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [creating])

  const availableStatuses = useMemo(() => [...new Set(records.map((r) => r.status).filter(Boolean))], [records])
  const filtered = useMemo(() => records.filter((row) => (!statusFilter || row.status === statusFilter) && (!priorityFilter || row.priority === priorityFilter)), [priorityFilter, records, statusFilter])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const selectedRows = records.filter((row) => checked.includes(row.id))

  const openCreate = (type = selectedType) => {
    const nextSchema = catalog[type]
    const saved = localStorage.getItem(draftKey)
    let restored = null
    try { restored = saved ? JSON.parse(saved) : null } catch { restored = null }
    setSelectedType(type)
    setEditing(false)
    setForm(restored?.selectedType === type ? restored.form : { title: nextSchema?.label || '', summary: '', patient: '', admission: '', appointment: '', assigned_to: '', priority: 'routine', payload: emptyPayload(nextSchema) })
    setError('')
    setCreating(true)
  }

  const openEdit = (record) => {
    setSelectedType(record.record_type)
    setEditing(true)
    setForm({
      id: record.id,
      title: record.title || '',
      summary: record.summary || '',
      patient: record.patient || '',
      admission: record.admission || '',
      appointment: record.appointment || '',
      assigned_to: record.assigned_to || '',
      priority: record.priority || 'routine',
      payload: { ...(record.payload || {}) },
    })
    setSelected(null)
    setCreating(true)
  }

  const changePayload = (name, value) => setForm((current) => ({ ...current, payload: { ...current.payload, [name]: value } }))

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = Object.fromEntries(Object.entries(form.payload).map(([name, value]) => [name, normalizeFieldValue(schema?.fields?.[name]?.kind, value)]))
      const body = {
        domain: schema.domain,
        record_type: selectedType,
        status: editing ? undefined : defaultStatus(schema),
        title: form.title || schema.label,
        summary: form.summary,
        priority: form.priority,
        payload,
        patient: form.patient ? Number(form.patient) : null,
        admission: form.admission ? Number(form.admission) : null,
        appointment: form.appointment ? Number(form.appointment) : null,
        assigned_to: form.assigned_to ? Number(form.assigned_to) : null,
      }
      Object.keys(body).forEach((key) => body[key] === undefined && delete body[key])
      if (editing) await enterpriseApi.updateRecord(form.id, body)
      else await enterpriseApi.createRecord(body)
      localStorage.removeItem(draftKey)
      setCreating(false)
      setEditing(false)
      await load()
    } catch (err) {
      const detail = err.response?.data
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail || { detail: err.message }))
    } finally {
      setBusy(false)
    }
  }

  const transition = async (record, action) => {
    setBusy(true)
    setError('')
    try {
      const { data } = await enterpriseApi.transitionRecord(record.id, { action })
      setSelected(data.record)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'The workflow transition could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  const uploadAttachment = async () => {
    if (!selected || !attachment) return
    setBusy(true)
    try {
      const data = new FormData()
      data.append('file', attachment)
      data.append('title', attachment.name)
      const response = await enterpriseApi.attachRecord(selected.id, data)
      setSelected((current) => ({ ...current, attachments: [...(current.attachments || []), response.data] }))
      setAttachment(null)
    } catch (err) {
      setError(err.response?.data?.detail || 'Attachment upload failed.')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (record) => {
    if (!window.confirm(`Delete ${record.reference}? Only draft or cancelled records can be removed.`)) return
    setBusy(true)
    try {
      await enterpriseApi.deleteRecord(record.id)
      setSelected(null)
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'This record cannot be deleted.')
    } finally { setBusy(false) }
  }

  const actionsFor = (record) => Object.entries(catalog[record.record_type]?.workflow?.[record.status] || {})
  const toggleAll = () => setChecked(checked.length === paged.length ? [] : paged.map((row) => row.id))
  const exportRows = selectedRows.length ? selectedRows : filtered

  const columns = [
    { key: '_select', label: <input type="checkbox" checked={paged.length > 0 && checked.length === paged.length} onChange={toggleAll} aria-label="Select all rows"/>, render: (row) => <input type="checkbox" checked={checked.includes(row.id)} onChange={() => setChecked((items) => items.includes(row.id) ? items.filter((id) => id !== row.id) : [...items, row.id])} aria-label={`Select ${row.reference}`}/> },
    { key: 'reference', label: 'Reference', render: (row) => <button className="font-semibold text-primary-700 hover:underline" onClick={() => { setSelected(row); setDetailTab('overview') }}>{row.reference}</button> },
    { key: 'title', label: 'Record', render: (row) => <div><strong className="block text-slate-800">{row.title}</strong><small className="capitalize text-slate-500">{row.record_type.replaceAll('_', ' ')}</small></div> },
    { key: 'patient_name', label: 'Patient', render: (row) => row.patient_name || '—' },
    { key: 'priority', label: 'Priority', render: (row) => <Badge color={row.priority === 'critical' ? 'red' : row.priority === 'urgent' ? 'orange' : 'slate'}>{row.priority}</Badge> },
    { key: 'status', label: 'Status', render: (row) => <Badge color={statusColor(row.status)}>{row.status.replaceAll('_', ' ')}</Badge> },
    { key: 'occurred_at', label: 'Date', render: (row) => new Date(row.occurred_at).toLocaleString() },
  ]

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-sm">
        <div className="bg-gradient-to-r from-slate-950 via-primary-950 to-primary-800 p-5 text-white sm:p-6">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
            <div><div className="text-xs font-bold uppercase tracking-[.16em] text-primary-200">{module.group}</div><h2 className="mt-1 text-2xl font-bold">{module.label}</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-primary-100">{module.description}</p></div>
            <Button onClick={() => openCreate()} className="bg-white !text-primary-800"><HealthIcon name="plus" size={16}/> New {schema?.label || 'record'}</Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 p-4 sm:p-5">
          {module.recordTypes.map((type) => (
            <button key={type} onClick={() => setSelectedType(type)} className={`rounded-full border px-3 py-1.5 text-xs font-semibold capitalize transition ${selectedType === type ? 'border-primary-600 bg-primary-600 text-white shadow' : 'border-slate-200 bg-slate-50 text-slate-600 hover:border-primary-300'}`}>{catalog[type]?.label || type.replaceAll('_', ' ')}</button>
          ))}
        </div>
      </section>

      {error && <Alert tone="danger" title="Action required">{error}</Alert>}

      <ClinicalVisualization recordType={selectedType} records={records}/>

      <Card title={schema?.label || module.label} subtitle={`${filtered.length} accessible record${filtered.length === 1 ? '' : 's'}`} icon={module.icon} actions={<div className="flex flex-wrap gap-2"><Button variant="outline" onClick={() => download(`${selectedType}-${new Date().toISOString().slice(0,10)}.csv`, toCsv(exportRows))}><HealthIcon name="download" size={15}/> Export</Button><Button variant="outline" onClick={() => window.print()}><HealthIcon name="file" size={15}/> Print</Button></div>}>
        <div className="mb-4 grid gap-3 lg:grid-cols-[1fr_190px_190px_auto]">
          <form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); load() }}><Input aria-label="Search records" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search reference, patient or summary" className="flex-1"/><Button type="submit" variant="outline"><HealthIcon name="search" size={15}/></Button></form>
          <Select aria-label="Filter by status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option>{availableStatuses.map((value) => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}</Select>
          <Select aria-label="Filter by priority" value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}><option value="">All priorities</option><option value="routine">Routine</option><option value="high">High</option><option value="urgent">Urgent</option><option value="critical">Critical</option></Select>
          <Button variant="ghost" onClick={() => { setQuery(''); setStatusFilter(''); setPriorityFilter(''); setTimeout(load, 0) }}><HealthIcon name="refresh" size={15}/> Reset</Button>
        </div>
        {checked.length ? <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-primary-200 bg-primary-50 px-4 py-3 text-sm"><strong className="text-primary-900">{checked.length} record{checked.length === 1 ? '' : 's'} selected</strong><div className="flex gap-2"><Button variant="outline" onClick={() => download(`${selectedType}-selection.csv`, toCsv(selectedRows))}>Export selection</Button><Button variant="ghost" onClick={() => setChecked([])}>Clear</Button></div></div> : null}
        {busy && !records.length ? <Spinner /> : paged.length ? <Table columns={columns} rows={paged} /> : <EmptyState icon={module.icon} title="No matching records" description="Change filters or create the first structured record for this workflow." action={<Button onClick={() => openCreate()}>Create record</Button>} />}
        {filtered.length > PAGE_SIZE ? <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 text-sm text-slate-500"><span>Page {page} of {pages}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button variant="outline" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>Next</Button></div></div> : null}
      </Card>

      <Modal open={creating} onClose={() => { setCreating(false); setEditing(false) }} title={`${editing ? 'Edit' : 'Create'} ${schema?.label || 'record'}`} wide>
        <form onSubmit={save} className="space-y-5">
          {!editing && localStorage.getItem(draftKey) ? <Alert tone="info" title="Draft restored">Your last unsaved work was restored automatically. Saving this record clears the local draft.</Alert> : null}
          <div className="grid gap-4 md:grid-cols-2">
            <Input label="Record title" required value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })}/>
            <Select label="Priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}><option value="low">Low</option><option value="routine">Routine</option><option value="high">High</option><option value="urgent">Urgent</option><option value="critical">Critical</option></Select>
            <EntitySearchSelect kind="patient" label="Patient" value={entityValue(form,'patient')} onChange={(id, item) => setForm((current) => ({ ...current, patient: id, patientObject: item }))} placeholder="Search by name, phone, email or MRN"/>
            <EntitySearchSelect kind="staff" label="Assigned professional" value={entityValue(form,'assigned_to')} onChange={(id, item) => setForm((current) => ({ ...current, assigned_to: id, staffObject: item }))} placeholder="Search staff by name, role or department"/>
            <EntitySearchSelect kind="admission" label="Admission" value={entityValue(form,'admission')} onChange={(id, item) => setForm((current) => ({ ...current, admission: id, admissionObject: item, patient: current.patient || item?.meta?.patient_id || '' }))} placeholder="Search admission number, patient or ward"/>
            <EntitySearchSelect kind="appointment" label="Appointment" value={entityValue(form,'appointment')} onChange={(id, item) => setForm((current) => ({ ...current, appointment: id, appointmentObject: item, patient: current.patient || item?.meta?.patient_id || '' }))} placeholder="Search patient, clinician or reason"/>
          </div>
          <Textarea label="Clinical or operational summary" value={form.summary} onChange={(event) => setForm({ ...form, summary: event.target.value })}/>
          <div className="border-t border-slate-100 pt-5"><div className="mb-4 flex items-center justify-between"><div><h3 className="font-bold text-slate-800">Structured {schema?.label?.toLowerCase()} fields</h3><p className="mt-1 text-xs text-slate-500">Fields are validated against the workflow schema and retained in the audit trail.</p></div><Badge color="blue">Autosave on</Badge></div><div className="grid gap-4 md:grid-cols-2">{Object.entries(schema?.fields || {}).map(([name, spec]) => <FormField key={name} name={name} spec={spec} value={form.payload?.[name]} onChange={changePayload}/>)}</div></div>
          <div className="sticky bottom-0 flex justify-end gap-3 border-t border-slate-100 bg-white pt-4"><Button type="button" variant="outline" onClick={() => { setCreating(false); setEditing(false) }}>Cancel</Button><Button type="submit" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save changes' : 'Save record'}</Button></div>
        </form>
      </Modal>

      <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.title || 'Record detail'} wide>
        {selected && <div className="space-y-5">
          <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-3">{['overview','attachments','audit'].map((tab) => <button key={tab} onClick={() => setDetailTab(tab)} className={`rounded-lg px-3 py-2 text-sm font-semibold capitalize ${detailTab === tab ? 'bg-primary-600 text-white' : 'text-slate-500 hover:bg-slate-100'}`}>{tab}</button>)}</div>
          {detailTab === 'overview' ? <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Reference</small><strong className="mt-1 block text-sm">{selected.reference}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Status</small><div className="mt-1"><Badge color={statusColor(selected.status)}>{selected.status}</Badge></div></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Patient</small><strong className="mt-1 block text-sm">{selected.patient_name || 'Not linked'}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Assigned</small><strong className="mt-1 block text-sm">{selected.assigned_to_name || 'Unassigned'}</strong></div></div>
            {selected.summary && <div><h4 className="text-sm font-bold text-slate-700">Summary</h4><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-slate-600">{selected.summary}</p></div>}
            <ClinicalVisualization recordType={selected.record_type} records={[selected]}/>
            <div><h4 className="mb-3 text-sm font-bold text-slate-700">Structured data</h4><div className="grid gap-3 md:grid-cols-2">{Object.entries(selected.payload || {}).map(([key, value]) => <div key={key} className="rounded-xl border border-slate-100 p-3"><small className="capitalize text-slate-500">{key.replaceAll('_', ' ')}</small><div className="mt-1 break-words text-sm font-medium text-slate-800">{typeof value === 'object' ? <pre className="overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(value, null, 2)}</pre> : String(value ?? '—')}</div></div>)}</div></div>
            <div><h4 className="mb-3 text-sm font-bold text-slate-700">Workflow actions</h4><div className="flex flex-wrap gap-2">{actionsFor(selected).length ? actionsFor(selected).map(([action, target]) => <Button key={action} variant={['cancel', 'reject'].includes(action) ? 'danger' : 'outline'} onClick={() => transition(selected, action)} disabled={busy}><HealthIcon name="arrow" size={14}/>{action.replaceAll('_', ' ')} → {target.replaceAll('_', ' ')}</Button>) : <span className="text-sm text-slate-400">No further transitions are available.</span>}<Button variant="outline" onClick={() => openEdit(selected)}><HealthIcon name="file" size={14}/> Edit</Button>{['draft','cancelled'].includes(selected.status) ? <Button variant="danger" onClick={() => remove(selected)}>Delete</Button> : null}<Button variant="ghost" onClick={() => window.print()}>Print</Button></div></div>
          </> : null}
          {detailTab === 'attachments' ? <div className="space-y-4"><div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5"><label className="text-sm font-semibold text-slate-700">Attach clinical document, image or report<input type="file" className="mt-3 block w-full text-sm" onChange={(event) => setAttachment(event.target.files?.[0] || null)}/></label><Button className="mt-3" disabled={!attachment || busy} onClick={uploadAttachment}>Upload attachment</Button></div><div className="space-y-2">{(selected.attachments || []).map((item) => <div key={item.id} className="flex items-center justify-between rounded-xl border border-slate-200 p-3"><span><strong className="block text-sm text-slate-800">{item.title || item.file?.split('/').at(-1)}</strong><small className="text-slate-500">Scan: {item.malware_status || 'pending'} · {item.uploaded_by_name || 'staff'}</small></span><Badge color={item.malware_status === 'clean' ? 'green' : item.malware_status === 'infected' ? 'red' : 'yellow'}>{item.malware_status || 'pending'}</Badge></div>)}{!(selected.attachments || []).length && <EmptyState icon="file" title="No attachments" description="Upload supporting documents through the protected file workflow."/>}</div></div> : null}
          {detailTab === 'audit' ? <div><h4 className="mb-3 text-sm font-bold text-slate-700">Immutable activity timeline</h4><div className="space-y-2">{(selected.transitions || []).map((transition) => <div key={transition.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 p-3 text-sm"><span><strong className="capitalize">{transition.action.replaceAll('_', ' ')}</strong><small className="ml-2 text-slate-500">{transition.from_status || 'new'} → {transition.to_status}</small>{transition.reason ? <small className="mt-1 block text-slate-500">{transition.reason}</small> : null}</span><small className="text-slate-400">{new Date(transition.created_at).toLocaleString()}</small></div>)}</div></div> : null}
        </div>}
      </Modal>
    </div>
  )
}
