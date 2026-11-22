import { useState } from 'react'
import { createPortal } from 'react-dom'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Input, Modal, Select, Textarea } from '../../components/ui'
import { errMsg, fmtDate } from './shared'

export function PrescriptionAction({ mode, order, medicines, onClose, onSaved }) {
  const [form, setForm] = useState({})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (mode === 'review') {
        await servicesApi.reviewPharmacyPrescription(order.id, {
          notes: form.notes, counselling: form.counselling, product_ids: form.product_ids || {},
          other_medicines: (form.other_medicines || '').split('\n').map((name) => name.trim()).filter(Boolean),
        })
      } else if (mode === 'substitute') {
        await servicesApi.requestPharmacySubstitution(order.id, form)
      } else {
        await servicesApi.updatePharmacyOrder(order.id, 'delivered', { handover_reference: form.handover_reference })
      }
      onSaved()
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  const titles = { review: 'Pharmacist review', substitute: 'Request a substitution', handover: 'Record handover' }

  return <Modal open title={titles[mode]} onClose={() => { if (!busy) onClose() }}>
    <form onSubmit={submit} className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      {mode === 'review' && <>
        {order.prescription_items.map((item) => {
          const approved = order.substitutions.find((entry) => entry.item === item.id && entry.status === 'approved')
          const eligible = medicines.filter((product) => product.sale_type !== 'unclassified' &&
            (approved ? product.id === approved.replacement : product.name.trim().toLowerCase() === item.medicine_name.trim().toLowerCase()))
          return <Select key={item.id} required label={`Confirm product for ${item.medicine_name} · ${item.dosage}`}
            value={form.product_ids?.[item.id] || ''} onChange={(event) => setForm((current) => ({
              ...current, product_ids: { ...current.product_ids, [item.id]: event.target.value },
            }))}>
            <option value="">{eligible.length ? 'Choose verified product' : 'No matching classified product'}</option>
            {eligible.map((product) => <option key={product.id} value={product.id}>
              {product.name}{product.description && ` · ${product.description}`} · Product #{product.id}
            </option>)}
          </Select>
        })}
        <Textarea required label="Review notes, including allergies and product strength checks" maxLength={2000}
          value={form.notes || ''} onChange={update('notes')} />
        <Textarea label="Other patient medicines, one name per line" value={form.other_medicines || ''} onChange={update('other_medicines')} />
        <Textarea required label="Counselling instructions or reason counselling could not be given" maxLength={2000}
          value={form.counselling || ''} onChange={update('counselling')} />
      </>}
      {mode === 'substitute' && <>
        <Select required label="Prescribed item" value={form.item || ''} onChange={update('item')}>
          <option value="">Select item</option>
          {order.prescription_items.filter((item) => !item.dispensed_quantity).map((item) => (
            <option key={item.id} value={item.id}>{item.medicine_name} · {item.dosage}</option>
          ))}
        </Select>
        <Select required label="Proposed product" value={form.replacement || ''} onChange={update('replacement')}>
          <option value="">Select product</option>
          {medicines.filter((medicine) => ['otc', 'prescription'].includes(medicine.sale_type)).map((medicine) => (
            <option key={medicine.id} value={medicine.id}>{medicine.name}</option>
          ))}
        </Select>
        <Textarea required label="Reason and proposed strength and formulation" maxLength={2000}
          value={form.reason || ''} onChange={update('reason')} />
      </>}
      {mode === 'handover' && <Input required label="Collection or delivery confirmation reference" maxLength={200}
        value={form.handover_reference || ''} onChange={update('handover_reference')} />}
      <Button disabled={busy} type="submit">{busy ? 'Saving…' : 'Save'}</Button>
    </form>
  </Modal>
}

function LabelSheets({ order }) {
  return <div className="space-y-3">
    {order.dispensed_batches.map((movement) => {
      const item = order.prescription_items.find((entry) => entry.id === movement.item)
      return <article className="break-inside-avoid border p-3 text-sm" key={movement.id}>
        <p className="font-semibold">{order.patient_name} · Rx order #{order.id}</p>
        <p className="font-semibold">{movement.medicine} · {movement.quantity} units</p>
        <p>{[item?.dosage, item?.route, item?.frequency, item?.duration].filter(Boolean).join(' · ')}</p>
        <p>{item?.instructions}</p>
        <p>Batch {movement.batch} · Dispensed {fmtDate(movement.dispensed_at)}</p>
        <p>{order.pharmacy_name}</p>
      </article>
    })}
  </div>
}

export function PrescriptionLabels({ order, onClose }) {
  return <>
    <Modal open title="Dispensing labels" onClose={onClose} wide>
      <Button className="mb-3" onClick={() => window.print()}>Print labels</Button>
      <LabelSheets order={order} />
    </Modal>
    {createPortal(
      <section id="print-pharmacy-labels" className="hidden print:block"><LabelSheets order={order} /></section>,
      document.body,
    )}
  </>
}
