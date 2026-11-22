import OrderIssues from './OrderIssues'
import { usePharmacyPermissions } from './PharmacyPermissions'
import { PrescriptionAction, PrescriptionLabels } from './PrescriptionActions'
import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner } from '../../components/ui'
import { errMsg, fmtDate, LoadingOrError, StatusBadge, useApi } from './shared'

export default function RxOrders() {
  const allows = usePharmacyPermissions()
  const { data: orders, loading, error, reload } = useApi(() => servicesApi.pharmacyOrders())
  const { user } = useAuth()
  const { data: products } = useApi(() => allows('inventory') ? servicesApi.medicines() : Promise.resolve({ data: [] }), [allows('inventory')])
  const [issues, setIssues] = useState(null)
  const [exceptionsOnly, setExceptionsOnly] = useState(false)
  const [clinicalAction, setClinicalAction] = useState(null)
  const [labels, setLabels] = useState(null)
  const [updating, setUpdating] = useState(null)
  const [actionError, setActionError] = useState('')
  const [reversing, setReversing] = useState(null)
  const [dispensing, setDispensing] = useState(null)
  const [batches, setBatches] = useState(null)
  const [form, setForm] = useState({})
  const item = dispensing?.prescription_items.find((entry) => String(entry.id) === form.item)
  const productID = dispensing?.review?.product_ids?.[item?.id]
  const matchingBatches = (batches || []).filter((batch) => batch.medicine === productID)
  const batch = matchingBatches.find((entry) => String(entry.id) === form.batch)

  const openDispensing = async (order) => {
    setActionError('')
    setBatches(null)
    setForm({ item: '', batch: '', quantity: '', reason: '', witness: '', reference: crypto.randomUUID() })
    setDispensing(order)
    try {
      const { data } = await servicesApi.dispensingBatches(order.id)
      setBatches(data)
    } catch (err) {
      setActionError(errMsg(err))
    }
  }

  const dispense = async (event) => {
    event.preventDefault()
    if (updating !== null || !item || !batch) return
    setUpdating(dispensing.id)
    setActionError('')
    try {
      const { witness, ...fields } = form
      await servicesApi.dispensePrescription(dispensing.id, { ...fields, ...(batch.controlled ? { witness } : {}) })
      setDispensing(null)
      reload()
    } catch (err) {
      setActionError(errMsg(err))
    } finally {
      setUpdating(null)
    }
  }

  const reverse = async (event) => {
    event.preventDefault()
    if (updating !== null || !form.unhanded) return
    setUpdating(reversing.id)
    setActionError('')
    try {
      const { witness, ...fields } = form
      await servicesApi.reverseDispense(reversing.id, { ...fields, ...(witness ? { witness } : {}) })
      setReversing(null)
      reload()
    } catch (err) {
      setActionError(errMsg(err))
    } finally {
      setUpdating(null)
    }
  }

  const setStatus = async (order, status) => {
    setActionError('')
    setUpdating(order.id)
    try {
      await servicesApi.updatePharmacyOrder(order.id, status)
      reload()
    } catch (e) {
      setActionError(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      {actionError && !dispensing && !reversing && <Alert tone="danger" className="mb-4">{actionError}</Alert>}
      <div className="mb-3 flex justify-end"><Button variant="outline" aria-pressed={exceptionsOnly}
        onClick={() => setExceptionsOnly(!exceptionsOnly)}>{exceptionsOnly ? 'Show all prescriptions' : 'Show open issues'}</Button></div>
      {issues && <OrderIssues order={issues} kind="rx" canWrite={allows('rx_manage') && user?.role === 'pharmacist'} onClose={() => { setIssues(null); reload() }} />}
      {!orders?.length ? (
        <Card>
          <div className="text-sm text-slate-400 text-center py-8">No prescription orders yet</div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {orders.filter((row) => !exceptionsOnly || row.open_issues).map((o) => (
            <Card
              key={o.id}
              title={
                <span>
                  Rx Order <span className="text-primary-600">#{o.id}</span>
                </span>
              }
              actions={<div className="flex gap-2"><StatusBadge status={o.status} /><Button variant="outline" onClick={() => setIssues(o)}>
                {o.open_issues ? `Issues (${o.open_issues})` : 'Issues'}
              </Button></div>}
            >
              <div className="space-y-4">
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <span className="text-slate-600">
                    <span className="text-slate-400">Patient:</span> {o.patient_name || '—'}
                  </span>
                  <span className="text-slate-600">
                    <span className="text-slate-400">Received:</span> {fmtDate(o.created_at)}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-100 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left text-slate-500">
                        <th className="px-3 py-2 font-medium">Medicine</th>
                        <th className="px-3 py-2 font-medium">Dosage</th>
                        <th className="px-3 py-2 font-medium">Frequency</th>
                        <th className="px-3 py-2 font-medium">Duration</th>
                        <th className="px-3 py-2 font-medium text-right">Dispensed / prescribed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(o.prescription_items || []).map((it, i) => (
                        <tr key={it.id ?? i} className="border-t border-slate-100">
                          <td className="px-3 py-2 text-slate-700">{it.medicine_name}</td>
                          <td className="px-3 py-2 text-slate-500">{it.dosage || '—'}</td>
                          <td className="px-3 py-2 text-slate-500">{it.frequency || '—'}</td>
                          <td className="px-3 py-2 text-slate-500">{it.duration || '—'}</td>
                          <td className="px-3 py-2 text-right text-slate-700">{it.dispensed_quantity || 0} / {it.quantity}</td>
                        </tr>
                      ))}
                      {!o.prescription_items?.length && (
                        <tr className="border-t border-slate-100">
                          <td colSpan={5} className="px-3 py-3 text-center text-slate-400">
                            No items on this prescription
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {o.review && <div className="space-y-2 text-sm">
                  <p>Pharmacist review recorded · {o.review.medication_check.knowledge_rules} medicine rules available</p>
                  {o.review.medication_check.alerts.map((alert) => <Alert key={alert.code} tone="warning">{alert.severity} · {alert.message}</Alert>)}
                </div>}
                {o.substitutions.map((entry) => <p key={entry.id} className="text-sm">
                  {entry.prescribed_medicine} → {entry.replacement_name} · {entry.status}
                  {entry.decision_note && ` · ${entry.decision_note}`}
                </p>)}
                {!!o.dispensed_batches.length && <div className="space-y-1 text-sm">
                  {o.dispensed_batches.map((movement) => <p key={movement.id}>
                    {movement.medicine} · Batch {movement.batch} · Movement #{movement.id}
                  </p>)}
                  <Button variant="outline" onClick={() => setLabels(o)}>Dispensing labels</Button>
                </div>}
                {allows('rx_manage') && (o.status === 'new' || o.status === 'prepared') && (
                  <div className="flex flex-wrap justify-end gap-2">
                    {o.status === 'new' && (
                      <>
                        <Button variant="danger" disabled={updating === o.id} onClick={() => setStatus(o, 'rejected')}>
                          Reject
                        </Button>
                        <Button disabled={updating === o.id} onClick={() => setStatus(o, 'prepared')}>
                          Mark prepared
                        </Button>
                      </>
                    )}
                    {o.status === 'prepared' && user?.role === 'pharmacist' && <>
                      <Button variant="outline" onClick={() => setClinicalAction({ mode: 'review', order: o })}>Record review</Button>
                      {allows('inventory') && o.prescription_items.some((entry) => !entry.dispensed_quantity) && (
                        <Button variant="outline" onClick={() => setClinicalAction({ mode: 'substitute', order: o })}>Request substitution</Button>
                      )}
                    </>}
                    {o.status === 'prepared' && o.review && user?.role === 'pharmacist' && o.prescription_items.some((entry) => entry.dispensed_quantity < entry.quantity) && (
                      <Button disabled={updating !== null} onClick={() => openDispensing(o)}>Dispense from batch</Button>
                    )}
                    {o.reversible_dispenses?.length > 0 && <Button variant="outline" disabled={updating !== null} onClick={() => {
                      setActionError('')
                      setForm({ movement: '', reason: '', unhanded: false, witness: '' })
                      setReversing(o)
                    }}>Reverse dispense</Button>}
                    {o.status === 'prepared' && o.prescription_status === 'dispensed' && user?.role === 'pharmacist' && (
                      <Button disabled={updating === o.id} onClick={() => setClinicalAction({ mode: 'handover', order: o })}>
                        Record handover
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
      {clinicalAction && <PrescriptionAction {...clinicalAction} medicines={products || []}
        onClose={() => setClinicalAction(null)} onSaved={() => { setClinicalAction(null); reload() }} />}
      {labels && <PrescriptionLabels order={labels} onClose={() => setLabels(null)} />}
      {dispensing && <Modal open title={`Dispense order #${dispensing.id}`} onClose={() => { if (updating === null && batches !== null) setDispensing(null); else if (actionError) setDispensing(null) }}>
        <form onSubmit={dispense} className="space-y-4">
          <p className="text-sm text-slate-700">{dispensing.patient_name}</p>
          {actionError && <Alert tone="danger">{actionError}</Alert>}
          {!batches && !actionError && <Spinner label="Loading eligible batches…" />}
          {batches && <>
            <Select required label="Prescription item" value={form.item} onChange={(event) => setForm({ ...form, item: event.target.value, batch: '', quantity: '', witness: '' })}>
              <option value="">Select an item</option>
              {dispensing.prescription_items.filter((entry) => entry.dispensed_quantity < entry.quantity).map((entry) => (
                <option key={entry.id} value={entry.id}>{entry.medicine_name} · {entry.quantity - entry.dispensed_quantity} remaining</option>
              ))}
            </Select>
            <Select required disabled={!item} label="Batch" value={form.batch} onChange={(event) => setForm({ ...form, batch: event.target.value, quantity: '', witness: '' })}>
              <option value="">Select a batch</option>
              {matchingBatches.map((entry) => <option key={entry.id} value={entry.id}>{entry.batch_number} · Expires {entry.expires_on} · {entry.quantity} available</option>)}
            </Select>
            {item && !matchingBatches.length && <Alert tone="warning">No usable stock matches this prescribed medicine.</Alert>}
            {batch && <>
              <Input required type="number" label="Quantity to dispense" min="1" max={Math.min(batch.quantity, item.quantity - item.dispensed_quantity)} value={form.quantity} onChange={(event) => setForm({ ...form, quantity: event.target.value })} />
              <Input required label="Dispensing note" maxLength={2000} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} />
              {batch.controlled && <Input required type="number" min="1" label="Independent witness account ID" value={form.witness} onChange={(event) => setForm({ ...form, witness: event.target.value })} />}
            </>}
          </>}
          {!!dispensing.review?.medication_check.alerts.length && <label className="flex gap-2 text-sm">
            <input type="checkbox" required checked={Boolean(form.alerts_reviewed)}
              onChange={(event) => setForm({ ...form, alerts_reviewed: event.target.checked })} />
            I reviewed the medication alerts and documented my decision in the dispensing note.
          </label>}
          <Button disabled={!batch || updating !== null}>{updating === null ? 'Record dispensing' : 'Recording…'}</Button>
        </form>
      </Modal>}
      {reversing && <Modal open title={`Reverse dispensing · Order #${reversing.id}`} onClose={() => { if (updating === null) setReversing(null) }}>
        <form className="space-y-4" onSubmit={reverse}>
          {actionError && <Alert tone="danger">{actionError}</Alert>}
          <Select required label="Dispensing record" value={form.movement} onChange={(event) => setForm({ ...form, movement: event.target.value, witness: '' })}>
            <option value="">Select a record</option>
            {reversing.reversible_dispenses.map((row) => <option key={row.id} value={row.id}>{row.medicine} · Batch {row.batch} · {row.quantity} units</option>)}
          </Select>
          <Input required label="Reversal reason" maxLength={2000} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} />
          {reversing.reversible_dispenses.find((row) => String(row.id) === form.movement)?.controlled &&
            <Input required type="number" min="1" label="Independent witness account ID" value={form.witness} onChange={(event) => setForm({ ...form, witness: event.target.value })} />}
          <label className="flex items-center gap-2 text-sm">
            <input required type="checkbox" checked={form.unhanded} onChange={(event) => setForm({ ...form, unhanded: event.target.checked })} />
            The medicine never left pharmacy custody.
          </label>
          <Button variant="danger" disabled={updating !== null || !form.unhanded}>Confirm reversal</Button>
        </form>
      </Modal>}
    </LoadingOrError>
  )
}
