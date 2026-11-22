import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Modal, Select, Spinner, Textarea } from '../../components/ui'
import { displayDate, getError, useRemote } from '../staff/shared'

const saleCategories = {
  failed_delivery: 'Failed delivery', missed_pickup: 'Missed pickup', contact_needed: 'Customer contact needed',
  cancellation_request: 'Cancellation request', order_help: 'Order help',
}
const rxCategories = { partial_fill: 'Partial fill', unavailable: 'Medicine unavailable', clarification: 'Prescriber clarification' }

export default function OrderIssues({ order, kind = 'sales', buyer = false, canWrite = true, onClose }) {
  const rows = useRemote(() => servicesApi.pharmacyWorkspaceData(`issues/${kind}/${order.id}`), [kind, order.id])
  const [category, setCategory] = useState(kind === 'rx' ? 'partial_fill' : buyer ? 'order_help' : 'contact_needed')
  const [note, setNote] = useState('')
  const [resolving, setResolving] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const labels = kind === 'rx' ? rxCategories : saleCategories
  const canCancel = !['delivered', 'dispatched', 'cancelled'].includes(order.status)

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      if (resolving) await servicesApi.resolvePharmacyIssue(kind, order.id, resolving.id, note)
      else await servicesApi.savePharmacyWorkspace(`issues/${kind}/${order.id}`, { category, note })
      setNote('')
      setResolving(null)
      rows.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(false)
    }
  }

  return <Modal open wide title={`${buyer ? 'Order help' : 'Order exceptions'} · #${order.id}`} onClose={() => { if (!busy) onClose() }}>
    <div className="space-y-4">
      {rows.error ? <Alert tone="danger">{rows.error}</Alert> : rows.loading ? <Spinner /> :
        <ul className="space-y-3">
          {!rows.data?.length && <li>No issues recorded.</li>}
          {rows.data?.map((row) => <li key={row.id} className="rounded-lg border p-3">
            <strong>{labels[row.category]}</strong> · {row.resolved_at ? 'Resolved' : 'Open'} · {displayDate(row.created_at)}
            <p>{row.note}</p>
            {row.outcome && <p>Outcome {row.outcome}</p>}
            {!buyer && canWrite && !row.resolved_at && <Button type="button" variant="outline" onClick={() => { setNote(''); setResolving(row) }}>Record outcome</Button>}
          </li>)}
        </ul>}
      {canWrite && <form onSubmit={submit} className="space-y-3">
        {resolving ? <p>Resolve {labels[resolving.category]}</p> :
          <Select label="Issue type" value={category} onChange={(event) => setCategory(event.target.value)}>
            {Object.entries(labels).filter(([key]) => !buyer || key === 'order_help' || key === 'cancellation_request' && canCancel)
              .map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>}
        <Textarea label={resolving ? 'Outcome' : 'Details'} required maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} />
        {error && <Alert tone="danger">{error}</Alert>}
        <Button disabled={busy}>{resolving ? 'Save outcome' : buyer ? 'Send request' : 'Record issue'}</Button>
        {resolving && <Button type="button" variant="outline" onClick={() => { setResolving(null); setNote('') }}>Cancel</Button>}
      </form>}
    </div>
  </Modal>
}
