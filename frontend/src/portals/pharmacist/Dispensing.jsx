import { useMemo, useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Stat, Table, Textarea } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

export default function Dispensing() {
  const { user } = useAuth()
  const orders = useRemote(() => servicesApi.pharmacyOrders(), [])
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({ status: 'dispensed', clarification_note: '', substitution_authorised_by: '', counselling_notes: '', items: [] })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const mayDispense = ['pharmacist', 'pharmacy'].includes(user?.role)
  const stats = useMemo(() => {
    const rows = orders.data || []
    return {
      new: rows.filter((row) => row.status === 'new').length,
      prepared: rows.filter((row) => row.status === 'prepared').length,
      delivered: rows.filter((row) => row.status === 'delivered').length,
      clarification: rows.filter((row) => (row.dispensing_records || []).some((record) => record.status === 'clarification')).length,
    }
  }, [orders.data])

  const open = (order) => {
    setSelected(order)
    setError('')
    setForm({
      status: 'dispensed',
      clarification_note: '',
      substitution_authorised_by: '',
      counselling_notes: '',
      items: (order.prescription_items || []).map((item, index) => ({
        prescription_item_id: item.id || index + 1,
        medicine_name: item.medicine_name,
        prescribed_quantity: Number(item.quantity || 0),
        dispensed_quantity: Number(item.quantity || 0),
        batch_number: '',
        expiry_date: '',
        substituted_product: '',
        label_instructions: [item.dosage, item.frequency, item.duration].filter(Boolean).join(' · '),
      })),
    })
  }

  const updateItem = (index, key, value) => {
    setForm((current) => ({ ...current, items: current.items.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: value } : item) }))
  }

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = {
        ...form,
        items: form.items.map((item) => ({
          ...item,
          prescribed_quantity: Number(item.prescribed_quantity || 0),
          dispensed_quantity: Number(item.dispensed_quantity || 0),
          expiry_date: item.expiry_date || null,
        })),
      }
      await servicesApi.recordDispensing(selected.id, payload)
      setSelected(null)
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
      {!mayDispense && <Alert tone="info">Your store or operations role may review the queue, but only a verified pharmacist or pharmacy owner can record dispensing.</Alert>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="New prescriptions" value={stats.new} icon="prescription" />
        <Stat label="Prepared" value={stats.prepared} icon="box" />
        <Stat label="Dispensed" value={stats.delivered} icon="check" />
        <Stat label="Needs clarification" value={stats.clarification} icon="alert" />
      </div>
      <Card title="Clinical dispensing workspace" subtitle="Review, partial fulfilment, batch traceability, substitutions, counselling and patient notification.">
        <Table
          rows={orders.data || []}
          empty="No prescriptions are waiting for pharmacy review."
          columns={[
            { key: 'id', label: 'Order', render: (row) => <strong>RX-{String(row.id).padStart(6, '0')}</strong> },
            { key: 'patient_name', label: 'Patient' },
            { key: 'created_at', label: 'Received', render: (row) => displayDate(row.created_at) },
            { key: 'prescription_items', label: 'Items', render: (row) => `${row.prescription_items?.length || 0} medicine(s)` },
            { key: 'status', label: 'Status', render: (row) => statusBadge(row.status) },
            { key: 'records', label: 'Dispensing history', render: (row) => `${row.dispensing_records?.length || 0} record(s)` },
            { key: 'actions', label: '', render: (row) => mayDispense ? <Button onClick={() => open(row)}>Review & dispense</Button> : <Button variant="outline" onClick={() => open(row)}>View</Button> },
          ]}
        />
      </Card>
      <Modal open={!!selected} onClose={() => setSelected(null)} title={`Dispense prescription RX-${String(selected?.id || '').padStart(6, '0')}`} wide>
        <form className="space-y-5" onSubmit={save}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Select disabled={!mayDispense} label="Decision" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
              <option value="reviewed">Reviewed / prepare</option><option value="clarification">Clarification required</option><option value="partial">Partially dispensed</option><option value="dispensed">Fully dispensed</option><option value="held">Hold</option><option value="cancelled">Cancel</option>
            </Select>
            <Input disabled={!mayDispense} label="Substitution authorised by" value={form.substitution_authorised_by} onChange={(event) => setForm({ ...form, substitution_authorised_by: event.target.value })} placeholder="Prescriber name / approval reference" />
          </div>
          {form.status === 'clarification' && <Textarea required disabled={!mayDispense} label="Clarification request" value={form.clarification_note} onChange={(event) => setForm({ ...form, clarification_note: event.target.value })} />}
          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="min-w-full text-sm"><thead className="bg-slate-50 text-left text-slate-500"><tr><th className="p-3">Medicine</th><th className="p-3">Prescribed</th><th className="p-3">Dispense</th><th className="p-3">Batch</th><th className="p-3">Expiry</th><th className="p-3">Substitution</th></tr></thead><tbody>{form.items.map((item, index) => <tr key={`${item.medicine_name}-${index}`} className="border-t border-slate-100"><td className="p-3"><strong>{item.medicine_name}</strong><small className="block max-w-xs text-slate-400">{item.label_instructions}</small></td><td className="p-3">{item.prescribed_quantity}</td><td className="p-3"><input disabled={!mayDispense} className="w-20 rounded-lg border border-slate-300 p-2" min="0" max={item.prescribed_quantity} type="number" value={item.dispensed_quantity} onChange={(event) => updateItem(index, 'dispensed_quantity', event.target.value)} /></td><td className="p-3"><input disabled={!mayDispense} className="w-32 rounded-lg border border-slate-300 p-2" value={item.batch_number} onChange={(event) => updateItem(index, 'batch_number', event.target.value)} /></td><td className="p-3"><input disabled={!mayDispense} className="rounded-lg border border-slate-300 p-2" type="date" value={item.expiry_date} onChange={(event) => updateItem(index, 'expiry_date', event.target.value)} /></td><td className="p-3"><input disabled={!mayDispense} className="w-40 rounded-lg border border-slate-300 p-2" value={item.substituted_product} onChange={(event) => updateItem(index, 'substituted_product', event.target.value)} /></td></tr>)}</tbody></table>
          </div>
          <Textarea disabled={!mayDispense} label="Patient counselling and label notes" value={form.counselling_notes} onChange={(event) => setForm({ ...form, counselling_notes: event.target.value })} />
          {(selected?.dispensing_records || []).length > 0 && <div><h3 className="mb-2 font-semibold text-slate-800">Previous dispensing records</h3><div className="space-y-2">{selected.dispensing_records.map((record) => <div key={record.id} className="rounded-xl bg-slate-50 p-3 text-sm"><div className="flex items-center justify-between"><strong>{record.pharmacist_name}</strong>{statusBadge(record.status)}</div><p className="mt-1 text-slate-500">{record.counselling_notes || record.clarification_note || 'No additional notes.'}</p><small className="text-slate-400">{displayDate(record.created_at)}</small></div>)}</div></div>}
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setSelected(null)}>Close</Button>{mayDispense && <Button disabled={busy}>{busy ? 'Saving…' : 'Save dispensing record'}</Button>}</div>
        </form>
      </Modal>
    </div>
  )
}
