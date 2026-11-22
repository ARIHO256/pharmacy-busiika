import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Modal, Spinner, Table, Textarea } from '../../components/ui'
import { getError, useRemote } from '../staff/shared'

export default function PharmacyClarifications() {
  const rows = useRemote(() => servicesApi.pharmacyWorkspaceData('prescriber-issues'), [])
  const [issue, setIssue] = useState(null)
  const [outcome, setOutcome] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await servicesApi.answerPharmacyClarification(issue.id, outcome)
      setIssue(null)
      rows.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(false)
    }
  }
  return <Card title="Pharmacy clarifications">
    {rows.error ? <Alert tone="danger">{rows.error}</Alert> : rows.loading ? <Spinner /> :
      <Table rows={rows.data || []} empty="No pharmacy clarifications." columns={[
        { key: 'prescription_order_id', label: 'Pharmacy order' }, { key: 'note', label: 'Question' },
        { key: 'outcome', label: 'Response', render: (row) => row.outcome || <Button variant="outline"
          onClick={() => { setOutcome(''); setError(''); setIssue(row) }}>Respond</Button> },
      ]} />}
    {issue && <Modal open title="Respond to pharmacy" onClose={() => { if (!busy) setIssue(null) }}>
      <form className="space-y-3" onSubmit={submit}>
        <p>{issue.note}</p>
        <Textarea label="Response to pharmacist" required maxLength={1000} value={outcome}
          onChange={(event) => setOutcome(event.target.value)} />
        {error && <Alert tone="danger">{error}</Alert>}
        <Button disabled={busy}>Send response</Button>
      </form>
    </Modal>}
  </Card>
}
