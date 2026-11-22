import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Table } from '../../components/ui'
import { errMsg, ErrorNote, fmtDate, LoadingOrError, StatusBadge, useApi } from '../pharmacy/shared'

const nextStep = {
  booked: { status: 'sample_collected', label: 'Collect sample' },
  ready_for_collection: { status: 'sample_collected', label: 'Collect sample' },
  sample_collected: { status: 'sample_received', label: 'Receive specimen' },
  sample_received: { status: 'processing', label: 'Start processing' },
}

export default function Orders() {
  const { data: orders, loading, error, reload } = useApi(() => servicesApi.labOrdersManage())
  const [specimenAction, setSpecimenAction] = useState(null)
  const [specimenValue, setSpecimenValue] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [updateError, setUpdateError] = useState('')
  const [updating, setUpdating] = useState(null)
  const [resultModal, setResultModal] = useState(null) // order being completed / edited
  const [versions, setVersions] = useState([])
  const [file, setFile] = useState(null)
  const [notes, setNotes] = useState('')
  const [structured, setStructured] = useState({ name: '', value_numeric: '', value_text: '', unit: '', reference_low: '', reference_high: '', interpretation: 'unknown', status: 'final' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const advance = async (order, status, fields = {}) => {
    setUpdateError('')
    setUpdating(order.id)
    try {
      const fd = new FormData()
      if (status) fd.append('status', status)
      for (const [field, value] of Object.entries(fields)) fd.append(field, value)
      await servicesApi.updateLabOrder(order.id, fd)
      setSpecimenAction(null)
      reload()
    } catch (e) {
      setUpdateError(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  const openSpecimenAction = (order, status, field, label) => {
    setUpdateError('')
    setSpecimenValue('')
    setSpecimenAction({ order, status, field, label })
  }

  const openComplete = async (order) => {
    setUpdateError('')
    setVersions([])
    if (order.result_released) {
      setUpdating(order.id)
      try {
        const { data } = await servicesApi.labResults(order.id)
        const amendable = data.filter((result) => result.released_at && !result.is_superseded)
        if (!amendable.length) {
          setUpdateError('This order has no structured result to amend.')
          return
        }
        setVersions(amendable)
      } catch (err) {
        setUpdateError(errMsg(err))
        return
      } finally {
        setUpdating(null)
      }
    }
    setResultModal(order)
    setFile(null)
    setNotes(order.result_notes || '')
    setStructured({ name: order.test_name || '', value_numeric: '', value_text: '', unit: '', reference_low: '', reference_high: '', interpretation: 'unknown', status: order.result_released ? 'amended' : 'final' })
    setSaveError('')
  }

  const saveResult = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const fd = new FormData()
      if (structured.name && (structured.value_numeric !== '' || structured.value_text.trim())) {
        for (const [key, value] of Object.entries(structured)) {
          if (value !== '' && value !== null && value !== undefined) fd.append(key, value)
        }
        if (!resultModal.result_released) {
          if (file) fd.append('result_file', file)
          fd.append('result_notes', notes)
        }
        await servicesApi.publishLabResult(resultModal.id, fd)
      } else {
        if (resultModal.result_released || (!file && !notes.trim())) {
          setSaveError('Enter a structured result or attach the report and add notes as appropriate.')
          return
        }
        fd.append('status', 'completed')
        if (file) fd.append('result_file', file)
        fd.append('result_notes', notes)
        await servicesApi.updateLabOrder(resultModal.id, fd)
      }
      setResultModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const orderRows = orders || []
  const statuses = [...new Set(orderRows.map((order) => order.status))].filter(Boolean).sort()
  const search = query.trim().replace(/^#/, '').toLowerCase()
  const visible = orderRows.filter((order) =>
    (!status || order.status === status) &&
    [order.id, order.visit_number, order.patient_name, order.test_name, order.specimen_id].some((value) =>
      String(value ?? '').toLowerCase().includes(search),
    ),
  )

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Laboratory worklist" icon="flask">
        {updateError && <Alert tone="danger" className="mb-4">{updateError}</Alert>}
        <div className="mb-4 grid gap-3 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <Input label="Search orders" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Order, patient, test or specimen" />
          <Select label="Status" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All statuses</option>
            {[...new Set([...statuses, status])].filter(Boolean).map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
          </Select>
        </div>
        {(search || status) && <p role="status" className="mb-3 text-sm text-slate-600">{visible.length} of {orderRows.length} orders</p>}
        <Table
          empty={search || status ? "No orders match these filters" : "No lab orders yet"}
          columns={[
            { key: 'id', label: 'Order', render: (o) => <span className="font-medium text-slate-800">#{o.id}</span> },
            { key: 'patient_name', label: 'Patient', render: (o) => <div>{o.patient_name}{o.visit_number && <div className="text-xs text-slate-600">{o.visit_number}</div>}</div> },
            { key: 'arrived_at', label: 'Arrival', render: (o) => o.arrived_at ? fmtDate(o.arrived_at) : '—' },
            { key: 'test_name', label: 'Test' },
            { key: 'specimen_id', label: 'Specimen', render: (o) => o.specimen_id || '—' },
            { key: 'rejection_reason', label: 'Rejection reason', render: (o) => o.rejection_reason || '—' },
            { key: 'priority', label: 'Priority', render: (o) => o.priority === 'stat' ? 'STAT' : o.priority || '—' },
            { key: 'referring_doctor_name', label: 'Referred by', render: (o) => o.referring_doctor_name || 'Self requested' },
            { key: 'created_at', label: 'Booked', render: (o) => fmtDate(o.created_at) },
            { key: 'status', label: 'Status', render: (o) => <StatusBadge status={o.status} /> },
            {
              key: 'result_file',
              label: 'Result',
              render: (o) =>
                o.result_file ? (
                  <a href={o.result_file} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">
                    Download
                  </a>
                ) : (
                  <span className="text-slate-300">—</span>
                ),
            },
            {
              key: 'actions',
              label: 'Update',
              render: (o) => (
                <div className="flex gap-2">
                  {!o.arrived_at && ['booked', 'ready_for_collection'].includes(o.status) && (
                    <Button variant="outline" disabled={updating !== null} onClick={() => advance(o, null, { action: 'record_arrival' })}>Record arrival</Button>
                  )}
                  {nextStep[o.status] && (
                    <Button
                      variant="outline"
                      disabled={updating !== null}
                      onClick={() => nextStep[o.status].status === 'sample_collected'
                        ? openSpecimenAction(o, 'sample_collected', 'specimen_id', 'Specimen identifier')
                        : advance(o, nextStep[o.status].status)}
                    >
                      {nextStep[o.status].label}
                    </Button>
                  )}
                  {['sample_collected', 'sample_received'].includes(o.status) && (
                    <Button variant="danger" disabled={updating !== null} onClick={() => openSpecimenAction(o, 'rejected', 'rejection_reason', 'Rejection reason')}>Reject specimen</Button>
                  )}
                  {o.status === 'rejected' && (
                    <Button variant="outline" disabled={updating !== null} onClick={() => advance(o, 'ready_for_collection')}>Request recollection</Button>
                  )}
                  {(['processing', 'awaiting_validation', 'validated', 'completed', 'amended'].includes(o.status)) && (
                    <Button disabled={updating !== null} onClick={() => openComplete(o)}>
                      {o.result_released ? 'Amend result' : 'Enter & release result'}
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
          rows={visible}
        />
      </Card>

      <Modal open={Boolean(specimenAction)} title={specimenAction?.status === 'rejected' ? 'Reject specimen' : 'Collect specimen'}
        onClose={() => { if (updating === null) setSpecimenAction(null) }}>
        {specimenAction && <form className="space-y-4" onSubmit={(event) => {
          event.preventDefault()
          if (updating !== null || !specimenValue.trim()) return
          advance(specimenAction.order, specimenAction.status, { [specimenAction.field]: specimenValue.trim() })
        }}>
          <p className="text-sm text-slate-600">{specimenAction.order.patient_name} · Order #{specimenAction.order.id}</p>
          <ErrorNote error={updateError} />
          <Input required label={specimenAction.label} value={specimenValue} onChange={(event) => setSpecimenValue(event.target.value)} />
          <Button disabled={updating !== null || !specimenValue.trim()}>Confirm</Button>
        </form>}
      </Modal>

      <Modal
        open={!!resultModal}
        onClose={() => { if (!saving) setResultModal(null) }}
        title={`Result for order #${resultModal?.id} — ${resultModal?.test_name || ''}`}
      >
        <form onSubmit={saveResult} className="space-y-4">
          <ErrorNote error={saveError} />
          {resultModal?.result_released ? <>
            <Select required label="Result to amend" value={structured.supersedes || ''} onChange={(event) => {
              const previous = versions.find((result) => String(result.id) === event.target.value)
              setStructured({
                ...structured, supersedes: previous?.id, name: previous?.name || '', code: previous?.code || '',
                code_system: previous?.code_system || 'local', value_numeric: previous?.value_numeric ?? '',
                value_text: previous?.value_text || '', unit: previous?.unit || '',
                reference_low: previous?.reference_low ?? '', reference_high: previous?.reference_high ?? '',
                interpretation: previous?.interpretation || 'unknown',
              })
            }}>
              <option value="">Select a released result</option>
              {versions.map((result) => <option key={result.id} value={result.id}>{result.name} · {result.value_numeric ?? result.value_text} {result.unit}</option>)}
            </Select>
            <Input required label="Amendment reason" value={structured.amendment_reason || ''} onChange={(event) => setStructured({ ...structured, amendment_reason: event.target.value })} />
          </> : <Input
            label="Result file (PDF / image)"
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />}
          <Alert tone="info" title="Structured result">Structured values can be searched, trended and safely interpreted; the PDF remains available as the original report.</Alert>
          <Input label="Result name" value={structured.name} onChange={(e) => setStructured({ ...structured, name: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Numeric value" type="number" step="any" value={structured.value_numeric} onChange={(e) => setStructured({ ...structured, value_numeric: e.target.value, value_text: e.target.value ? '' : structured.value_text })} />
            <Input label="Unit" value={structured.unit} onChange={(e) => setStructured({ ...structured, unit: e.target.value })} placeholder="e.g. mmol/L" />
          </div>
          <Input label="Text value (when not numeric)" value={structured.value_text} onChange={(e) => setStructured({ ...structured, value_text: e.target.value, value_numeric: e.target.value ? '' : structured.value_numeric })} />
          <div className="grid grid-cols-2 gap-3">
            <Input label="Reference low" type="number" step="any" value={structured.reference_low} onChange={(e) => setStructured({ ...structured, reference_low: e.target.value })} />
            <Input label="Reference high" type="number" step="any" value={structured.reference_high} onChange={(e) => setStructured({ ...structured, reference_high: e.target.value })} />
          </div>
          <Select label="Interpretation" value={structured.interpretation} onChange={(e) => setStructured({ ...structured, interpretation: e.target.value })}>
            <option value="unknown">Not interpreted</option><option value="normal">Normal</option><option value="high">High</option><option value="low">Low</option><option value="abnormal">Abnormal</option><option value="critical">Critical</option>
          </Select>
          {!resultModal?.result_released && <label className="block">
            <span className="block text-sm font-medium text-slate-600 mb-1">Result notes</span>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Summary of findings for the patient…"
            />
          </label>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" disabled={saving} onClick={() => setResultModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : 'Validate and release result'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
