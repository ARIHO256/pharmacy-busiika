import { useMemo, useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Badge, Card, EmptyState, Select, Spinner, Table } from '../../components/ui'
import { useRemote, displayDate } from './shared'

const statusTone = (status) => ({ confirmed: 'green', pending: 'yellow', completed: 'blue' }[status] || 'slate')

export default function TeamSchedule() {
  const schedule = useRemote(() => workforceApi.teamSchedule(), [])
  const [providerFilter, setProviderFilter] = useState('')

  const providers = useMemo(() => schedule.data?.providers || [], [schedule.data])
  const visible = useMemo(
    () => (providerFilter ? providers.filter((p) => String(p.provider_id) === providerFilter) : providers),
    [providers, providerFilter]
  )
  const rows = useMemo(
    () =>
      visible.flatMap((provider) =>
        provider.appointments.map((appointment) => ({
          id: `${provider.provider_id}-${appointment.id}`,
          provider: provider.provider_name,
          role: provider.role?.replaceAll('_', ' '),
          ...appointment,
        }))
      ),
    [visible]
  )

  if (schedule.loading) return <Spinner label="Loading team schedule…" />
  if (schedule.error) return <Card className="text-sm text-rose-600">{schedule.error}</Card>

  return (
    <div className="space-y-5">
      <Card
        title="Team schedule"
        subtitle={`${schedule.data?.organization || 'Your organization'} · ${schedule.data?.from} → ${schedule.data?.to} · ${rows.length} upcoming appointments across ${providers.length} providers`}
        icon="calendar"
        actions={
          <Select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)} className="w-64" aria-label="Filter by provider">
            <option value="">All providers</option>
            {providers.map((provider) => (
              <option key={provider.provider_id} value={provider.provider_id}>{provider.provider_name}</option>
            ))}
          </Select>
        }
      >
        {rows.length === 0 ? (
          <EmptyState icon="calendar" title="No upcoming appointments" description="Appointments booked for any provider in your organization appear here." />
        ) : (
          <Table
            rows={rows}
            columns={[
              { key: 'date', label: 'Date', render: (row) => displayDate(row.date, false) },
              { key: 'time', label: 'Time', render: (row) => `${row.start_time} – ${row.end_time}` },
              { key: 'provider', label: 'Provider', render: (row) => <span className="font-semibold text-slate-800">{row.provider}<small className="block text-xs font-normal capitalize text-slate-400">{row.role}</small></span> },
              { key: 'patient_name', label: 'Patient' },
              { key: 'reason', label: 'Reason', render: (row) => row.reason || '—' },
              { key: 'type', label: 'Type', render: (row) => <Badge color={row.type === 'online' ? 'blue' : 'purple'}>{row.type}</Badge> },
              { key: 'status', label: 'Status', render: (row) => <Badge color={statusTone(row.status)}>{row.status}</Badge> },
            ]}
          />
        )}
      </Card>
    </div>
  )
}
