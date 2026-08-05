import { useEffect, useMemo, useState } from 'react'
import { enterpriseApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'
import FormField, { initialFieldValue, normalizeFieldValue } from './FormField'

const rowsFrom = (data) => Array.isArray(data) ? data : data?.results || []
const normalizeSpec = ([name, label, kind = 'text', options]) => [name, { label, kind, options, required: !['active', 'enabled', 'provider', 'location', 'department'].includes(name) }]
const PAGE_SIZE = 12

function displayValue(row, key) {
  const value = row[key]
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.map((item) => (item && typeof item === 'object' ? JSON.stringify(item) : String(item))).join(', ')
  if (typeof value === 'object') return Object.entries(value).map(([k, v]) => `${k.replaceAll('_', ' ')}: ${v && typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ')
  return String(value)
}

function statusTone(value) {
  const text = String(value || '').toLowerCase()
  if (['active', 'completed', 'published', 'healthy', 'delivered', 'approved', 'resolved', 'verified'].includes(text)) return 'green'
  if (['failed', 'rejected', 'inactive', 'infected', 'critical', 'suspended', 'quarantined'].includes(text)) return 'red'
  if (['pending', 'processing', 'under_review', 'queued', 'draft'].includes(text)) return 'yellow'
  return 'blue'
}

function csv(rows, fields) {
  const headers = ['id', ...fields]
  const escape = (value) => `"${String(value ?? '').replaceAll('"', '""')}"`
  return [headers.join(','), ...rows.map((row) => headers.map((key) => escape(typeof row[key] === 'object' ? JSON.stringify(row[key]) : row[key])).join(','))].join('\n')
}

function download(name, contents) {
  const url = URL.createObjectURL(new Blob([contents], { type: 'text/csv' }))
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url)
}

export default function ResourceConsole({ module }) {
  const fieldEntries = useMemo(() => (module.fields || []).map(normalizeSpec), [module.fields])
  const storageKey = `healthpilot:resource-filter:${module.resourceName}`
  const [rows, setRows] = useState([])
  const [editing, setEditing] = useState(false)
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [query, setQuery] = useState(() => localStorage.getItem(storageKey) || '')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)
  const [checked, setChecked] = useState([])
  const [detailTab, setDetailTab] = useState('details')
  const [actionReason, setActionReason] = useState('')
  const [visibleKeys, setVisibleKeys] = useState(() => fieldEntries.slice(0, 5).map(([name]) => name))

  const load = async () => {
    setBusy(true)
    setError('')
    try {
      const { data } = await enterpriseApi.resource(module.resourceName)
      setRows(rowsFrom(data))
      setChecked([])
    } catch (err) {
      setError(err.response?.data?.detail || `Unable to load ${module.label.toLowerCase()}.`)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { load() }, [module.resourceName])
  useEffect(() => { localStorage.setItem(storageKey, query) }, [query, storageKey])
  useEffect(() => { setVisibleKeys(fieldEntries.slice(0, 5).map(([name]) => name)) }, [module.resourceName])

  const openCreate = () => {
    setForm(Object.fromEntries(fieldEntries.map(([name, spec]) => [name, initialFieldValue(spec)])))
    setError('')
    setEditing('create')
  }

  const openEdit = (row) => {
    setForm(Object.fromEntries(fieldEntries.map(([name, spec]) => [name, row[name] ?? initialFieldValue(spec)])))
    setSelected(null)
    setEditing(row.id)
  }

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = Object.fromEntries(fieldEntries.map(([name, spec]) => [name, normalizeFieldValue(spec.kind, form[name])]).filter(([, value]) => value !== null && value !== ''))
      if (editing === 'create') await enterpriseApi.createResource(module.resourceName, payload)
      else await enterpriseApi.updateResource(module.resourceName, editing, payload)
      setEditing(false)
      await load()
    } catch (err) {
      const detail = err.response?.data
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail || { detail: err.message }))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (row) => {
    if (!window.confirm(`Delete ${module.label} #${row.id}? This action is audited and may be rejected when the record is in use.`)) return
    setBusy(true)
    try { await enterpriseApi.deleteResource(module.resourceName, row.id); setSelected(null); await load() }
    catch (err) { setError(err.response?.data?.detail || 'This record cannot be deleted.') }
    finally { setBusy(false) }
  }

  const archive = async (row) => {
    const key = Object.prototype.hasOwnProperty.call(row, 'active') ? 'active' : Object.prototype.hasOwnProperty.call(row, 'enabled') ? 'enabled' : null
    if (!key) return
    setBusy(true)
    try { await enterpriseApi.updateResource(module.resourceName, row.id, { [key]: !row[key] }); setSelected(null); await load() }
    catch (err) { setError(err.response?.data?.detail || 'The status could not be changed.') }
    finally { setBusy(false) }
  }

  const action = async (row, name) => {
    setBusy(true)
    setError('')
    try {
      if (module.resourceName === 'content' && name === 'publish') await enterpriseApi.publishContent(row.id)
      else if (module.resourceName === 'patient-merges') await enterpriseApi.patientMergeAction(row.id, name)
      else if (module.resourceName === 'event-deliveries') await enterpriseApi.eventDeliveryAction(row.id, name, actionReason)
      else if (module.resourceName === 'verification-automation') await enterpriseApi.verificationAction(row.id, name === 'run' ? { action: 'run' } : { action: 'decide', decision: name, notes: actionReason })
      else if (module.resourceName === 'saved-reports' && name === 'run') await enterpriseApi.runReport(row.id)
      else if (module.resourceName === 'notification-providers' && name === 'health_check') await enterpriseApi.providerHealth(row.id)
      else if (module.resourceName === 'pacs-nodes' && name === 'health_check') await enterpriseApi.pacsHealth(row.id)
      else if (module.resourceName === 'replay-requests' && name === 'run') await enterpriseApi.runReplay(row.id)
      else if (module.resourceName === 'delegations' && name === 'revoke') await enterpriseApi.revokeDelegation(row.id)
      await load(); setSelected(null); setActionReason('')
    } catch (err) {
      setError(err.response?.data?.detail || 'The requested action could not be completed.')
    } finally { setBusy(false) }
  }

  const actionsFor = (row) => {
    if (module.resourceName === 'content' && row.status !== 'published') return ['publish']
    if (module.resourceName === 'patient-merges') return row.status === 'proposed' ? ['approve'] : row.status === 'approved' ? ['complete'] : row.status === 'completed' ? ['reverse'] : []
    if (module.resourceName === 'event-deliveries') return ['retry', 'quarantine']
    if (module.resourceName === 'verification-automation') return ['run', 'approve', 'reject']
    if (module.resourceName === 'saved-reports') return ['run']
    if (module.resourceName === 'notification-providers' || module.resourceName === 'pacs-nodes') return ['health_check']
    if (module.resourceName === 'replay-requests') return ['run']
    if (module.resourceName === 'delegations' && !row.revoked_at) return ['revoke']
    return []
  }

  const statusValues = useMemo(() => [...new Set(rows.map((row) => row.status ?? row.active ?? row.enabled).filter((value) => value !== undefined))], [rows])
  const filtered = useMemo(() => rows.filter((row) => {
    const text = JSON.stringify(row).toLowerCase()
    const matchesQuery = !query || text.includes(query.toLowerCase())
    const rowStatus = row.status ?? row.active ?? row.enabled
    return matchesQuery && (!statusFilter || String(rowStatus) === statusFilter)
  }), [query, rows, statusFilter])
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const exportRows = checked.length ? rows.filter((row) => checked.includes(row.id)) : filtered

  const columns = [
    { key: '_select', label: <input type="checkbox" checked={paged.length > 0 && paged.every((row) => checked.includes(row.id))} onChange={() => setChecked(paged.every((row) => checked.includes(row.id)) ? checked.filter((id) => !paged.some((row) => row.id === id)) : [...new Set([...checked, ...paged.map((row) => row.id)])])} aria-label="Select all rows"/>, render: (row) => <span onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={checked.includes(row.id)} onChange={() => setChecked((current) => current.includes(row.id) ? current.filter((id) => id !== row.id) : [...current, row.id])} aria-label={`Select ${row.name || row.reference || row.id}`}/></span> },
    { key: 'id', label: 'Reference', render: (row) => <button onClick={(event) => { event.stopPropagation(); setSelected(row); setDetailTab('details') }} className="font-bold text-primary-700 hover:underline">#{row.id}</button> },
    ...fieldEntries.filter(([name]) => visibleKeys.includes(name)).map(([name, spec]) => ({ key: name, label: spec.label, render: (row) => name === 'status' || name === 'active' || name === 'enabled' ? <Badge color={statusTone(displayValue(row, name))}>{displayValue(row, name)}</Badge> : <span className="block max-w-[260px] truncate" title={displayValue(row, name)}>{displayValue(row, name)}</span> })),
    { key: '_actions', label: 'Actions', render: (row) => <Button variant="ghost" onClick={(event) => { event.stopPropagation(); setSelected(row); setDetailTab('details') }}><HealthIcon name="more" size={16}/> View</Button> },
  ]

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-[26px] border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-4 bg-gradient-to-r from-slate-950 via-primary-950 to-primary-800 p-6 text-white md:flex-row md:items-center md:justify-between">
          <div><div className="text-xs font-bold uppercase tracking-[.14em] text-primary-200">{module.group}</div><h2 className="mt-1 text-2xl font-bold">{module.label}</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-primary-100">{module.description}</p></div>
          <Button onClick={openCreate} className="bg-white !text-primary-800"><HealthIcon name="plus" size={16}/> Add record</Button>
        </div>
        <div className="grid gap-3 p-4 lg:grid-cols-[1fr_190px_auto_auto]">
          <Input value={query} onChange={(event) => { setQuery(event.target.value); setPage(1) }} placeholder={`Search ${module.label.toLowerCase()}…`} />
          <Select value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1) }}><option value="">All statuses</option>{statusValues.map((value) => <option key={String(value)} value={String(value)}>{typeof value === 'boolean' ? value ? 'Active' : 'Inactive' : String(value).replaceAll('_',' ')}</option>)}</Select>
          <Button variant="outline" onClick={() => download(`${module.resourceName}.csv`, csv(exportRows, visibleKeys))}><HealthIcon name="download" size={15}/> Export</Button>
          <Button variant="outline" onClick={() => window.print()}><HealthIcon name="file" size={15}/> Print</Button>
        </div>
      </section>

      {error && <Alert tone="danger" title="Action required">{error}</Alert>}

      <Card title={module.label} subtitle={`${filtered.length} accessible record${filtered.length === 1 ? '' : 's'}`} icon={module.icon} actions={<div className="flex gap-2"><details className="relative"><summary className="flex cursor-pointer list-none items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"><HealthIcon name="settings" size={15}/> Columns</summary><div className="absolute right-0 z-30 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl">{fieldEntries.map(([name,spec]) => <label key={name} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-slate-50"><input type="checkbox" checked={visibleKeys.includes(name)} onChange={() => setVisibleKeys((keys) => keys.includes(name) ? keys.filter((key)=>key!==name) : [...keys,name])}/>{spec.label}</label>)}</div></details><Button variant="outline" onClick={load}><HealthIcon name="refresh" size={15}/> Refresh</Button></div>}>
        {checked.length ? <div className="mb-4 flex items-center justify-between rounded-xl border border-primary-200 bg-primary-50 px-4 py-3 text-sm"><strong>{checked.length} selected</strong><Button variant="ghost" onClick={() => setChecked([])}>Clear selection</Button></div> : null}
        {busy && !rows.length ? <Spinner /> : paged.length ? <Table rows={paged} columns={columns} onRowClick={(row) => { setSelected(row); setDetailTab('details') }}/> : <EmptyState icon={module.icon} title={`No ${module.label.toLowerCase()} found`} description="Create the first record or adjust the filters." action={<Button onClick={openCreate}>Create record</Button>} />}
        {filtered.length > PAGE_SIZE ? <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-4 text-sm text-slate-500"><span>Page {page} of {pages}</span><div className="flex gap-2"><Button variant="outline" disabled={page <= 1} onClick={() => setPage((n)=>n-1)}>Previous</Button><Button variant="outline" disabled={page >= pages} onClick={() => setPage((n)=>n+1)}>Next</Button></div></div> : null}
      </Card>

      <Modal open={Boolean(editing)} onClose={() => setEditing(false)} title={`${editing === 'create' ? 'Add' : 'Edit'} ${module.label}`} wide>
        <form className="space-y-5" onSubmit={save}>
          <div className="grid gap-4 md:grid-cols-2">{fieldEntries.map(([name, spec]) => <FormField key={name} name={name} spec={spec} value={form[name]} onChange={(field, value) => setForm((current) => ({ ...current, [field]: value }))}/>)}</div>
          <Alert tone="info"><strong>Governance:</strong> configuration changes are role-protected and included in platform audit events. Credentials must remain in the deployment secret manager.</Alert>
          <div className="flex justify-end gap-3"><Button type="button" variant="outline" onClick={() => setEditing(false)}>Cancel</Button><Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</Button></div>
        </form>
      </Modal>

      <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title={`${module.label} #${selected?.id || ''}`} wide>
        {selected && <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
            {(selected.status !== undefined) && <Badge color={statusTone(selected.status)}>{String(selected.status).replaceAll('_', ' ')}</Badge>}
            {(selected.severity || selected.priority) && <Badge color={statusTone(selected.severity || selected.priority)}>{String(selected.severity || selected.priority).replaceAll('_', ' ')}</Badge>}
            {(selected.operation_type || selected.record_type || selected.kind) && <Badge color="blue">{String(selected.operation_type || selected.record_type || selected.kind).replaceAll('_', ' ')}</Badge>}
            {(selected.title || selected.name) && <strong className="ml-1 text-sm text-slate-800">{selected.title || selected.name}</strong>}
          </div>
          <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-3">{['details','configuration','activity'].map((tab) => <button key={tab} onClick={() => setDetailTab(tab)} className={`rounded-lg px-3 py-2 text-sm font-semibold capitalize ${detailTab===tab?'bg-primary-600 text-white':'text-slate-500 hover:bg-slate-100'}`}>{tab}</button>)}</div>
          {detailTab === 'details' ? <div className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2">{Object.entries(selected).filter(([key, value]) => typeof value !== 'object' && !['configuration','resource','payload','definition','schema','findings','metadata'].includes(key)).map(([key, value]) => <div key={key} className="rounded-xl border border-slate-100 bg-slate-50/60 p-3"><small className="capitalize text-slate-500">{key.replaceAll('_', ' ')}</small><div className="mt-1 break-words text-sm font-medium text-slate-800">{String(value ?? '—')}</div></div>)}</div>
            {Object.entries(selected).filter(([key, value]) => ['findings','metadata','scope'].includes(key) && value && typeof value === 'object' && !Array.isArray(value)).map(([key, value]) => (
              <section key={key} className="rounded-xl border border-slate-200 p-4">
                <h4 className="text-sm font-bold capitalize text-slate-700">{key.replaceAll('_', ' ')}</h4>
                <dl className="mt-3 grid gap-2 sm:grid-cols-2">{Object.entries(value).map(([k, v]) => <div key={k} className="flex items-start justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm"><dt className="capitalize text-slate-500">{k.replaceAll('_', ' ')}</dt><dd className="break-words text-right font-medium text-slate-800">{v && typeof v === 'object' ? JSON.stringify(v) : String(v ?? '—')}</dd></div>)}</dl>
              </section>
            ))}
          </div> : null}
          {detailTab === 'configuration' ? <div className="space-y-4">{Object.entries(selected).filter(([, value]) => value && typeof value === 'object').map(([key, value]) => <div key={key}><h4 className="mb-2 text-sm font-bold capitalize text-slate-700">{key.replaceAll('_', ' ')}</h4><pre className="max-h-80 overflow-auto rounded-xl bg-slate-950 p-4 text-xs leading-6 text-slate-100">{JSON.stringify(value, null, 2)}</pre></div>)}{!Object.values(selected).some((value)=>value&&typeof value==='object') && <EmptyState icon="file" title="No structured configuration" description="This resource stores scalar values only."/>}</div> : null}
          {detailTab === 'activity' ? <div className="space-y-3">{['created_at','updated_at','published_at','last_health_check_at','last_delivery_at'].filter((key)=>selected[key]).map((key) => <div key={key} className="flex items-center justify-between rounded-xl border border-slate-100 p-3 text-sm"><span className="capitalize">{key.replaceAll('_',' ')}</span><strong>{new Date(selected[key]).toLocaleString()}</strong></div>)}<Alert tone="info">Full field-level history is also retained in the platform audit log when this resource is changed through the API.</Alert></div> : null}
          {(actionsFor(selected).length > 0 || fieldEntries.length) && <div className="border-t border-slate-100 pt-4"><h4 className="mb-3 text-sm font-bold text-slate-700">Available actions</h4>{actionsFor(selected).some((name)=>['reject','quarantine'].includes(name)) ? <Textarea label="Action reason" value={actionReason} onChange={(event)=>setActionReason(event.target.value)} /> : null}<div className="mt-3 flex flex-wrap gap-2">{actionsFor(selected).map((name) => <Button key={name} onClick={() => action(selected, name)} variant={name === 'reject' || name === 'quarantine' ? 'danger' : 'outline'} disabled={busy}>{name.replaceAll('_', ' ')}</Button>)}<Button variant="outline" onClick={() => openEdit(selected)}><HealthIcon name="file" size={15}/> Edit</Button>{Object.prototype.hasOwnProperty.call(selected,'active') || Object.prototype.hasOwnProperty.call(selected,'enabled') ? <Button variant="outline" onClick={() => archive(selected)}>{selected.active === false || selected.enabled === false ? 'Reactivate' : 'Deactivate'}</Button> : null}<Button variant="danger" onClick={() => remove(selected)}>Delete</Button></div></div>}
        </div>}
      </Modal>
    </div>
  )
}
