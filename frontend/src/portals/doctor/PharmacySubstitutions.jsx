import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Modal, Textarea } from '../../components/ui'
import { errMsg, LoadingOrError, useApi } from '../pharmacy/shared'

export default function PharmacySubstitutions() {
  const { data, loading, error, reload } = useApi(() => servicesApi.pharmacySubstitutions())
  const [selection, setSelection] = useState(null)
  const [note, setNote] = useState('')
  const [failure, setFailure] = useState('')
  const [busy, setBusy] = useState(false)

  function choose(row, decision) {
    setNote('')
    setFailure('')
    setSelection({ row, decision })
  }

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setFailure('')
    try {
      await servicesApi.decidePharmacySubstitution(selection.row.id, { decision: selection.decision, note })
      setSelection(null)
      reload()
    } catch (err) {
      setFailure(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  return <LoadingOrError loading={loading} error={error}>
    <div className="space-y-3">
      {data?.length === 0 && <Card title="No substitution requests" />}
      {data?.map((row) => <Card key={row.id} title={`${row.prescribed_medicine} → ${row.replacement_name}`}
        subtitle={`Pharmacy order #${row.order} · ${row.status}`}>
        <div className="space-y-3 text-sm">
          <p>{[row.prescribed_dose, row.prescribed_route, row.prescribed_frequency, row.prescribed_duration].filter(Boolean).join(' · ')} · {row.prescribed_quantity} units</p>
          {row.replacement_description && <p>{row.replacement_description}</p>}
          <p>{row.reason}</p>
          {row.decision_note && <p>{row.decision_note}</p>}
          {row.status === 'pending' && <div className="flex flex-wrap gap-2">
            <Button onClick={() => choose(row, 'approved')}>Approve substitute</Button>
            <Button variant="outline" onClick={() => choose(row, 'rejected')}>Reject</Button>
          </div>}
        </div>
      </Card>)}
    </div>
    {selection && <Modal open title={selection.decision === 'approved' ? 'Approve substitute' : 'Reject substitution'}
      onClose={() => { if (!busy) setSelection(null) }}>
      <form onSubmit={submit} className="space-y-3">
        {failure && <Alert tone="danger">{failure}</Alert>}
        <Textarea required maxLength={2000} label={selection.decision === 'approved'
          ? 'Confirm that the original directions and quantity apply to this replacement' : 'Reason for rejection'}
          value={note} onChange={(event) => setNote(event.target.value)} />
        <Button disabled={busy} type="submit">{busy ? 'Saving…' : 'Save decision'}</Button>
      </form>
    </Modal>}
  </LoadingOrError>
}
