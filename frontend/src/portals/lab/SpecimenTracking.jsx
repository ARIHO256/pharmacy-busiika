import { useMemo, useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Stat, Table, Textarea } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

const eventOptions = [
  ['labelled', 'Generate label'], ['collected', 'Collected'], ['received', 'Received'],
  ['aliquoted', 'Aliquoted'], ['transferred', 'Transferred'], ['processing', 'Processing'],
  ['stored', 'Stored'], ['rejected', 'Rejected'], ['disposed', 'Disposed'],
]

export default function SpecimenTracking() {
  const orders = useRemote(() => servicesApi.labOrdersManage(), [])
  const [selected, setSelected] = useState(null)
  const [events, setEvents] = useState([])
  const [loadingEvents, setLoadingEvents] = useState(false)
  const [form, setForm] = useState({ event_type: 'labelled', barcode: '', location: '', notes: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const stats = useMemo(() => {
    const rows = orders.data || []
    return {
      awaiting: rows.filter((row) => ['booked', 'ready_for_collection'].includes(row.status)).length,
      collected: rows.filter((row) => row.status === 'sample_collected').length,
      received: rows.filter((row) => row.status === 'sample_received').length,
      rejected: rows.filter((row) => row.status === 'rejected').length,
    }
  }, [orders.data])

  const open = async (order) => {
    setSelected(order)
    setForm({ event_type: order.specimen_id ? 'collected' : 'labelled', barcode: order.specimen_id || '', location: '', notes: '' })
    setLoadingEvents(true)
    setError('')
    try {
      const { data } = await servicesApi.specimenEvents(order.id)
      setEvents(data)
    } catch (err) {
      setError(getError(err))
    } finally {
      setLoadingEvents(false)
    }
  }

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { data } = await servicesApi.addSpecimenEvent(selected.id, form)
      setEvents((current) => [...current, data])
      setForm({ ...form, event_type: 'processing', notes: '' })
      orders.reload()
    } catch (err) {
      setError(getError(err))
    } finally {
      setBusy(false)
    }
  }

  if (orders.loading) return <Spinner />
  return (
    <div className="space-y-5">
      {(error || orders.error) && <Alert tone="danger">{error || orders.error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Awaiting collection" value={stats.awaiting} icon="clock" />
        <Stat label="Collected" value={stats.collected} icon="check" />
        <Stat label="Received" value={stats.received} icon="flask" />
        <Stat label="Rejected" value={stats.rejected} icon="alert" />
      </div>
      <Card title="Specimen custody board" subtitle="Barcode, collection, handover, processing, storage and disposal are captured as an immutable timeline.">
        <Table
          rows={orders.data || []}
          empty="No laboratory orders available."
          columns={[
            { key: 'specimen_id', label: 'Barcode', render: (row) => <strong>{row.specimen_id || `Pending label · #${row.id}`}</strong> },
            { key: 'patient_name', label: 'Patient' },
            { key: 'test_name', label: 'Test' },
            { key: 'priority', label: 'Priority', render: (row) => statusBadge(row.priority) },
            { key: 'status', label: 'Status', render: (row) => statusBadge(row.status) },
            { key: 'collected_at', label: 'Collected', render: (row) => row.collected_at ? displayDate(row.collected_at) : '—' },
            { key: 'actions', label: '', render: (row) => <Button variant="outline" onClick={() => open(row)}>Open custody trail</Button> },
          ]}
        />
      </Card>
      <Modal open={!!selected} onClose={() => setSelected(null)} title={`Specimen custody · order #${selected?.id}`} wide>
        {loadingEvents ? <Spinner /> : <div className="grid gap-5 lg:grid-cols-[1fr_.9fr]">
          <div>
            <h3 className="mb-3 font-semibold text-slate-800">Custody timeline</h3>
            <div className="space-y-3">
              {!events.length && <Alert tone="info">No custody events have been recorded yet.</Alert>}
              {events.map((item) => <div key={item.id} className="rounded-xl border border-slate-200 p-3"><div className="flex items-center justify-between gap-3"><strong className="capitalize text-slate-800">{item.event_type.replaceAll('_', ' ')}</strong>{statusBadge(item.event_type)}</div><p className="mt-1 text-sm text-slate-600">{item.notes || 'No notes'}</p><p className="mt-2 text-xs text-slate-400">{item.barcode} · {item.location || 'Location not recorded'} · {item.performed_by_name || 'System'} · {displayDate(item.occurred_at)}</p></div>)}
            </div>
          </div>
          <form className="space-y-4 rounded-2xl bg-slate-50 p-4" onSubmit={save}>
            <h3 className="font-semibold text-slate-800">Record custody event</h3>
            <Select label="Event" value={form.event_type} onChange={(event) => setForm({ ...form, event_type: event.target.value })}>{eventOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select>
            <Input label="Barcode / specimen ID" value={form.barcode} onChange={(event) => setForm({ ...form, barcode: event.target.value })} placeholder={`LAB-${String(selected?.id || '').padStart(8, '0')}`} />
            <Input label="Location" value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="Collection room, accession desk, analyser bay…" />
            <Textarea label="Notes / rejection reason" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} />
            {error && <Alert tone="danger">{error}</Alert>}
            <Button disabled={busy}>{busy ? 'Recording…' : 'Record event'}</Button>
          </form>
        </div>}
      </Modal>
    </div>
  )
}
