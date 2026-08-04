import { Link } from 'react-router-dom'
import { workforceApi } from '../../api/endpoints'
import { Alert, Card, Spinner, Stat, Table } from '../../components/ui'
import { statusBadge, useRemote } from '../staff/shared'

export default function Dashboard() {
  const summary = useRemote(() => workforceApi.summary(), [])
  const visits = useRemote(() => workforceApi.visits(), [])
  if (summary.loading || visits.loading) return <Spinner />
  if (summary.error || visits.error) return <Alert tone="danger">{summary.error || visits.error}</Alert>
  const info = summary.data || {}
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Today's visits" value={info.today_visits || 0} icon="calendar" caption="Walk-ins and appointments" />
      <Stat label="Waiting triage" value={info.waiting_triage || 0} icon="activity" caption="Check-in completed" />
      <Stat label="Waiting clinician" value={info.waiting_clinician || 0} icon="doctor" caption="Ready after triage" />
      <Stat label="Active staff" value={info.active_staff || 0} icon="users" caption="Facility team" />
    </div>
    <Card title="Live front-desk queue" actions={<Link to="/reception/check-in" className="text-sm font-semibold text-primary-700">Check in patient →</Link>}>
      <Table rows={(visits.data || []).filter((v) => !['completed','cancelled'].includes(v.status)).slice(0, 10)} empty="No patients currently queued" columns={[
        { key: 'queue_number', label: 'Queue', render: (v) => <strong>#{v.queue_number || '—'}</strong> }, { key: 'patient_name', label: 'Patient' },
        { key: 'visit_type', label: 'Type', render: (v) => statusBadge(v.visit_type) }, { key: 'reason', label: 'Reason' },
        { key: 'status', label: 'Stage', render: (v) => statusBadge(v.status) },
      ]}/>
    </Card>
  </div>
}
