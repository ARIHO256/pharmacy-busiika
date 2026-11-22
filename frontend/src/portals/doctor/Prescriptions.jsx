import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { appointmentApi, prescriptionApi, workforceApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Spinner, Table } from '../../components/ui'

const emptyItem = { medicine_name: '', dosage: '', frequency: '', duration: '', quantity: 1 }

const apptLabel = (a) =>
  `${a.date} ${(a.start_time || '').slice(0, 5)} — ${
    a.patient_name || [a.patient_first_name, a.patient_last_name].filter(Boolean).join(' ') || `Patient #${a.patient}`
  }`

export function NewPrescription({ appointments = [], preselect, visit, onCreated }) {
  const [appointmentId, setAppointmentId] = useState(preselect || '')
  const [items, setItems] = useState([{ ...emptyItem }])
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { if (preselect) setAppointmentId(String(preselect)) }, [preselect])

  const setItem = (i, k) => (e) =>
    setItems((rows) => rows.map((r, j) => (j === i ? { ...r, [k]: e.target.value } : r)))

  async function submit(e) {
    e.preventDefault()
    setError('')
    const clean = items.filter((it) => it.medicine_name.trim())
    if (!appointmentId && !visit) return setError('Select an appointment')
    if (!clean.length) return setError('Add at least one medicine')
    setBusy(true)
    try {
      const { data } = await (visit ? workforceApi.signVisitPrescription : prescriptionApi.create)(visit || appointmentId, {
        notes,
        items: clean.map((it) => ({ ...it, quantity: Number(it.quantity) || 1 })),
      })
      setItems([{ ...emptyItem }])
      setNotes('')
      setAppointmentId('')
      onCreated(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not create prescription')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {!visit && <Select label="Confirmed appointment" value={appointmentId} onChange={(e) => setAppointmentId(e.target.value)} required>
        <option value="">Select an appointment…</option>
        {appointments.map((a) => (
          <option key={a.id} value={a.id}>{apptLabel(a)}</option>
        ))}
      </Select>}

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-slate-600">Medicines</span>
          <Button type="button" variant="outline" className="!px-2.5 !py-1 !text-xs" onClick={() => setItems((r) => [...r, { ...emptyItem }])}>
            + Add medicine
          </Button>
        </div>
        {items.map((it, i) => (
          <div key={i} className="border border-slate-200 rounded-lg p-3 grid grid-cols-2 md:grid-cols-3 gap-3 relative">
            <Input label="Medicine name" value={it.medicine_name} onChange={setItem(i, 'medicine_name')} placeholder="Amoxicillin" />
            <Input label="Route" value={it.route || ''} onChange={setItem(i, 'route')} />
            <Input label="Dosage" value={it.dosage} onChange={setItem(i, 'dosage')} placeholder="500mg" />
            <Input label="Frequency" value={it.frequency} onChange={setItem(i, 'frequency')} placeholder="3x daily" />
            <Input label="Duration" value={it.duration} onChange={setItem(i, 'duration')} placeholder="7 days" />
            <Input label="Quantity" type="number" min="1" value={it.quantity} onChange={setItem(i, 'quantity')} />
            <div className="flex items-end justify-end">
              {items.length > 1 && (
                <button type="button" className="text-xs text-rose-500 hover:text-rose-700" onClick={() => setItems((r) => r.filter((_, j) => j !== i))}>
                  Remove
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <label className="block">
        <span className="block text-sm font-medium text-slate-600 mb-1">Notes</span>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          placeholder="Additional instructions for the patient…"
        />
      </label>

      {error && <p className="text-sm text-rose-600">{error}</p>}
      <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Create prescription'}</Button>
    </form>
  )
}

export default function Prescriptions() {
  const [params, setParams] = useSearchParams()
  const [mode, setMode] = useState(params.get('appointment') ? 'new' : 'history')
  const [appointments, setAppointments] = useState([])
  const [history, setHistory] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailBusy, setDetailBusy] = useState(false)

  const loadHistory = useCallback(() => {
    prescriptionApi.list().then((r) => setHistory(r.data || [])).catch(() => setHistory([]))
  }, [])

  useEffect(() => {
    appointmentApi.list({ status: 'confirmed' }).then((r) => setAppointments(r.data || [])).catch(() => {})
    loadHistory()
  }, [loadHistory])

  async function openDetail(id) {
    setDetailBusy(true)
    setDetail({ id })
    try {
      const r = await prescriptionApi.detail(id)
      setDetail(r.data)
    } catch {
      setDetail(null)
    } finally {
      setDetailBusy(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {[
          ['new', '✍️ Write new'],
          ['history', '📚 History'],
        ].map(([m, label]) => (
          <button
            key={m}
            onClick={() => { setMode(m); if (m === 'history') setParams({}, { replace: true }) }}
            className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition ${
              mode === m ? 'bg-primary-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === 'new' ? (
        <Card title="New e-prescription">
          {appointments.length === 0 ? (
            <p className="text-sm text-slate-400">No confirmed appointments waiting for a prescription.</p>
          ) : (
            <NewPrescription
              appointments={appointments}
              preselect={params.get('appointment')}
              onCreated={() => { setParams({}, { replace: true }); loadHistory(); setMode('history') }}
            />
          )}
        </Card>
      ) : (
        <Card title="Prescription history">
          {!history ? (
            <Spinner label="Loading prescriptions…" />
          ) : (
            <Table
              columns={[
                { key: 'number', label: 'Rx #', render: (p) => p.number || `RX-${p.id}` },
                {
                  key: 'patient',
                  label: 'Patient',
                  render: (p) => p.patient_name || [p.patient_first_name, p.patient_last_name].filter(Boolean).join(' ') || `Patient #${p.patient}`,
                },
                { key: 'created_at', label: 'Date', render: (p) => (p.created_at || '').slice(0, 10) },
                {
                  key: 'items',
                  label: 'Items',
                  render: (p) => <Badge color="blue">{Array.isArray(p.items) ? p.items.length : p.item_count ?? p.items_count ?? '—'}</Badge>,
                },
                {
                  key: 'view',
                  label: '',
                  render: (p) => (
                    <Button variant="outline" className="!px-2.5 !py-1 !text-xs" onClick={() => openDetail(p.id)}>View</Button>
                  ),
                },
              ]}
              rows={history}
              empty="No prescriptions written yet."
            />
          )}
        </Card>
      )}

      <Modal open={!!detail} onClose={() => setDetail(null)} title={`Prescription ${detail?.number || `RX-${detail?.id ?? ''}`}`} wide>
        {detailBusy || !detail?.items ? (
          <Spinner label="Loading…" />
        ) : (
          <div className="space-y-4">
            <div className="text-sm text-slate-500">
              Patient: <span className="text-slate-700 font-medium">
                {detail.patient_name || [detail.patient_first_name, detail.patient_last_name].filter(Boolean).join(' ') || `Patient #${detail.patient}`}
              </span>
              <span className="mx-2">·</span> {(detail.created_at || '').slice(0, 10)}
            </div>
            <Table
              columns={[
                { key: 'medicine_name', label: 'Medicine' },
                { key: 'dosage', label: 'Dosage', render: (i) => i.dosage || '—' },
                { key: 'frequency', label: 'Frequency', render: (i) => i.frequency || '—' },
                { key: 'duration', label: 'Duration', render: (i) => i.duration || '—' },
                { key: 'quantity', label: 'Qty' },
              ]}
              rows={detail.items}
            />
            {detail.notes && (
              <div className="bg-slate-50 rounded-lg p-3 text-sm text-slate-600">
                <span className="font-medium text-slate-700">Notes: </span>{detail.notes}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
