import { useAuth } from '../../auth/AuthContext'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Spinner, Table } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

const managerFlow = {
  registered: 'waiting_triage',
  waiting_triage: 'triaged',
  triaged: 'waiting_clinician',
  waiting_clinician: 'in_consultation',
  in_consultation: 'billing',
  billing: 'completed',
}
const frontDeskFlow = { registered: 'waiting_triage' }

export default function Queue() {
  const { user } = useAuth()
  const visits = useRemote(() => workforceApi.visits(), [])
  const canSuperviseFlow = ['admin', 'hospital', 'facility_manager', 'medical_director'].includes(user?.role)
  const transitions = canSuperviseFlow ? managerFlow : frontDeskFlow
  const advance = async (visit) => {
    try {
      await workforceApi.updateVisit(visit.id, { status: transitions[visit.status] })
      visits.reload()
    } catch (err) {
      window.alert(getError(err))
    }
  }
  if (visits.loading) return <Spinner />
  return (
    <Card title="Patient flow board" subtitle="Track checked-in patients while respecting clinical separation of duties">
      {visits.error && <Alert tone="danger" className="mb-4">{visits.error}</Alert>}
      {!canSuperviseFlow && <Alert tone="info" className="mb-4">Front-desk users may register, check in, route or cancel patients. Triage, consultation and clinical stage transitions are completed by the responsible clinical team.</Alert>}
      <Table
        rows={visits.data || []}
        empty="No visits recorded"
        columns={[
          { key: 'queue_number', label: 'Queue', render: (visit) => <strong>#{visit.queue_number || '—'}</strong> },
          { key: 'patient_name', label: 'Patient' },
          { key: 'reason', label: 'Reason' },
          { key: 'priority', label: 'Priority', render: (visit) => statusBadge(visit.priority) },
          { key: 'status', label: 'Stage', render: (visit) => statusBadge(visit.status) },
          { key: 'checked_in_at', label: 'Checked in', render: (visit) => displayDate(visit.checked_in_at) },
          { key: 'action', label: '', render: (visit) => transitions[visit.status] ? <Button variant="outline" onClick={() => advance(visit)}>Move to {transitions[visit.status].replaceAll('_', ' ')}</Button> : null },
        ]}
      />
    </Card>
  )
}
