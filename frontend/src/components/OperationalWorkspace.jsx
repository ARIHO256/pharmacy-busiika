import { useEffect, useRef, useState } from 'react'
import { operationsApi } from '../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from './ui'
import { getError, statusBadge } from '../portals/staff/shared'

export const field = (key, label, type = 'text', extra = {}) => ({ key, label, type, required: true, ...extra })

export default function OperationalWorkspace({ title, sections, organizationType }) {
  const [selected, setSelected] = useState(sections[0].resource)
  const [context, setContext] = useState(null)
  const [organization, setOrganization] = useState('')
  const [rows, setRows] = useState([])
  const [page, setPage] = useState(1)
  const [hasNext, setHasNext] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refresh, setRefresh] = useState(0)
  const [error, setError] = useState('')
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [preview, setPreview] = useState(null)
  const request = useRef(0)
  const section = sections.find((item) => item.resource === selected) || sections[0]

  useEffect(() => {
    let active = true
    operationsApi.context().then(({ data }) => {
      if (active) {
        const organizations = data.organizations.filter((org) => !organizationType || org.type === organizationType)
        setContext({ ...data, organizations })
        setOrganization(String(organizations[0]?.id || ''))
      }
    }).catch((err) => { if (active) { setError(getError(err)); setLoading(false) } })
    return () => { active = false }
  }, [organizationType])

  useEffect(() => {
    if (!context) return undefined
    if (section.organization && !organization) { setRows([]); setLoading(false); return undefined }
    const id = ++request.current
    setLoading(true)
    setError('')
    operationsApi.list(section.resource, { page, ...(section.organization ? { organization } : {}) })
      .then(({ data }) => { if (id === request.current) { setRows(data.results || []); setHasNext(Boolean(data.next)) } })
      .catch((err) => { if (id === request.current) setError(getError(err)) })
      .finally(() => { if (id === request.current) setLoading(false) })
    return () => { request.current += 1 }
  }, [selected, organization, context, page, refresh])

  useEffect(() => {
    if (!organization) return undefined
    let active = true
    operationsApi.context(organization).then(({ data }) => {
      if (active) setContext((current) => ({ ...data, organizations: current.organizations }))
    }).catch((err) => { if (active) setError(getError(err)) })
    return () => { active = false }
  }, [organization])

  const open = (definition, row = null) => {
    setSaveError('')
    setForm(definition.prefill && row ? { ...row } : {})
    const scope = { context, organization, row }
    setModal({ ...definition, defaults: typeof definition.defaults === 'function' ? definition.defaults() : definition.defaults, row, resource: section.resource,
      fields: typeof definition.fields === 'function' ? definition.fields(scope) : definition.fields || [] })
  }

  const act = async (definition, row) => {
    if (definition.preview) {
      setPreview({ title: definition.label, data: row })
      return
    }
    if (definition.immediate) {
      try {
        const result = await definition.request({ row, context, organization })
        if (result?.data) setPreview({ title: definition.label, data: result.data })
        setRefresh((value) => value + 1)
      } catch (err) { setError(getError(err)) }
      return
    }
    open(definition, row)
  }

  const save = async (event) => {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setSaveError('')
    try {
      let payload = { ...(modal.defaults || {}), ...(modal.create && section.organization ? { organization: Number(organization) } : {}) }
      for (const input of modal.fields) {
        const value = form[input.key]
        if (value === '' || value === undefined) continue
        payload[input.key] = input.type === 'number' || input.numeric ? Number(value)
          : input.type === 'date' ? value
            : input.type === 'datetime-local' ? new Date(value).toISOString() : value
      }
      if (modal.multipart) {
        const data = new FormData()
        for (const [key, value] of Object.entries(payload)) data.append(key, value)
        payload = data
      }
      const result = modal.request
        ? await modal.request({ payload, row: modal.row, context, organization })
        : modal.create ? await operationsApi.create(modal.resource, payload)
          : await operationsApi.action(modal.resource, modal.row.id, modal.action, payload)
      if (modal.showResult && result?.data) setPreview({ title: modal.label, data: result.data })
      setModal(null)
      setRefresh((value) => value + 1)
    } catch (err) { setSaveError(getError(err)) }
    finally { setSaving(false) }
  }

  const columns = [
    { key: 'id', label: 'Reference', render: (row) => `#${row.id}` },
    ...section.columns,
    { key: 'actions', label: 'Actions', render: (row) => <div className="flex flex-wrap gap-2">
      {(section.actions?.(row, context) || []).map((definition) => <Button key={definition.label} variant="outline" onClick={() => act(definition, row)}>{definition.label}</Button>)}
    </div> },
  ]

  return <div className="space-y-5">
    <Card title={title} subtitle={section.description}>
      <div className="flex flex-wrap gap-2">{sections.map((item) => <Button key={item.resource} variant={selected === item.resource ? 'primary' : 'outline'} onClick={() => { setSelected(item.resource); setPage(1) }}>{item.label}</Button>)}</div>
    </Card>
    {error && <Alert tone="danger">{error}</Alert>}
    {section.organization && context && <Select label="Organization" value={organization} onChange={(event) => { setOrganization(event.target.value); setPage(1) }}>
      {!context.organizations.length && <option value="">No verified organization membership</option>}
      {context.organizations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
    </Select>}
    <Card title={section.label} actions={<div className="flex gap-2"><Button variant="outline" disabled={loading} onClick={() => setRefresh((value) => value + 1)}>Refresh</Button>{section.create && <Button disabled={!context || (section.organization && !organization)} onClick={() => open({ ...section.create, create: true })}>{section.create.label || 'Add record'}</Button>}</div>}>
      {loading ? <Spinner /> : <Table rows={rows} columns={columns} empty="No records yet" />}
      <div className="flex justify-end gap-2 mt-4"><Button variant="outline" disabled={loading || page === 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button variant="outline" disabled={loading || !hasNext} onClick={() => setPage((value) => value + 1)}>Next</Button></div>
    </Card>
    <Modal open={Boolean(modal)} title={modal?.label} onClose={() => { if (!saving) setModal(null) }}>
      {modal && <form onSubmit={save} className="space-y-4">
        {saveError && <Alert tone="danger">{saveError}</Alert>}
        {modal.fields.map((input) => {
          const props = { label: input.label, required: input.required, value: form[input.key] ?? '', onChange: (event) => setForm((current) => ({ ...current, [input.key]: event.target.value })) }
          if (input.type === 'textarea') return <Textarea key={input.key} {...props} />
          if (input.type === 'select') return <Select key={input.key} {...props}><option value="">Select…</option>{(input.options || []).map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}</Select>
          if (input.type === 'file') return <Input key={input.key} label={input.label} type="file" required={input.required} onChange={(event) => setForm((current) => ({ ...current, [input.key]: event.target.files?.[0] }))} />
          if (input.type === 'checkbox') return <label key={input.key} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(form[input.key])} onChange={(event) => setForm((current) => ({ ...current, [input.key]: event.target.checked }))} />{input.label}</label>
          return <Input key={input.key} {...props} type={input.type} min={input.min} max={input.max} step={input.step} />
        })}
        <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save'}</Button>
      </form>}
    </Modal>
    <Modal open={Boolean(preview)} title={preview?.title} onClose={() => setPreview(null)} wide>
      <pre className="whitespace-pre-wrap break-words text-sm text-slate-700">{preview ? JSON.stringify(preview.data, null, 2) : ''}</pre>
    </Modal>
  </div>
}

export const statusColumn = { key: 'status', label: 'Status', render: (row) => statusBadge(row.status) }
