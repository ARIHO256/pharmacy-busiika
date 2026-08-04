import { Link } from 'react-router-dom'
import { workforceApi } from '../../api/endpoints'
import { Alert, Card, Spinner, Stat, Table } from '../../components/ui'
import { statusBadge, useRemote } from '../staff/shared'

export default function Dashboard() {
  const summary = useRemote(() => workforceApi.summary(), [])
  const visits = useRemote(() => workforceApi.visits(), [])
  if (summary.loading || visits.loading) return <Spinner />
  if (summary.error || visits.error) return <Alert tone="danger">{summary.error || visits.error}</Alert>
  const data = summary.data || {}
  const queue = (visits.data || []).filter((v) => !['completed', 'cancelled'].includes(v.status)).slice(0, 8)
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Waiting for triage" value={data.waiting_triage || 0} icon="activity" caption="Patients awaiting observations" />
      <Stat label="Waiting clinician" value={data.waiting_clinician || 0} icon="doctor" caption="Triaged and ready" />
      <Stat label="In consultation" value={data.in_consultation || 0} icon="heart" caption="Active care episodes" />
      <Stat label="Today's visits" value={data.today_visits || 0} icon="calendar" caption="All facility visits" />
    </div>
    <Card title="Current patient flow" subtitle="Use triage urgency and queue position to prioritise care" actions={<Link className="text-sm font-semibold text-primary-700" to="/nurse/triage">Open triage →</Link>}>
      <Table rows={queue} empty="No patients are currently waiting" columns={[
        { key: 'queue_number', label: 'Queue', render: (v) => <strong>#{v.queue_number || '—'}</strong> },
        { key: 'patient_name', label: 'Patient' },
        { key: 'reason', label: 'Reason' },
        { key: 'priority', label: 'Priority', render: (v) => statusBadge(v.priority) },
        { key: 'status', label: 'Stage', render: (v) => statusBadge(v.status) },
      ]}/>
    </Card>
  </div>
}
