import { Link, useOutletContext } from 'react-router-dom'
import { registryApi, servicesApi, workforceApi } from '../../api/endpoints'
import { Alert, Card, Spinner, Stat, Table } from '../../components/ui'
import { statusBadge, useRemote } from '../staff/shared'

export default function Dashboard() {
  const summary = useOutletContext()
  const facility = summary.organization
  const isHospital = facility.type === 'hospital'
  const visits = useRemote(() => workforceApi.visits({ organization: facility.id }), [facility.id])
  const serviceInfo = useRemote(async () => {
    const [bookings, beds] = await Promise.all([
      servicesApi.hospitalBookingsManage(),
      isHospital ? servicesApi.beds() : Promise.resolve({ data: [] }),
    ])
    return { data: { bookings: bookings.data, beds: beds.data } }
  }, [facility.id, isHospital])
  const pharmacies = useRemote(() => facility.has_pharmacy
    ? registryApi.organizations({ type: 'pharmacy', parent_facility: facility.id })
    : Promise.resolve({ data: [] }), [facility.id, facility.has_pharmacy])

  const beds = serviceInfo.data?.beds || []
  const occupied = beds.filter((bed) => bed.is_occupied).length
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Today’s visits" value={summary.today_visits} icon="calendar" />
      <Stat label="Active staff" value={summary.active_staff} icon="users" />
      <Stat label="Waiting for clinician" value={summary.waiting_clinician} icon="doctor" />
      <Stat label="Completed today" value={summary.completed} icon="check" />
    </div>
    {!serviceInfo.loading && (serviceInfo.error
      ? <Alert tone="danger">{serviceInfo.error}</Alert>
      : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Pending bookings" value={serviceInfo.data.bookings.filter((booking) => booking.status === 'pending').length} icon="calendar" />
        {isHospital && <>
          <Stat label="Occupied beds" value={occupied} icon="bed" />
          <Stat label="Available beds" value={beds.length - occupied} icon="bed" />
        </>}
      </div>)}
    <div className="grid gap-5 xl:grid-cols-2">
      <Card title="Current patient flow" actions={<Link to="queue" className="text-sm font-semibold text-primary-700">Open queue</Link>}>
        {visits.loading ? <Spinner /> : visits.error ? <Alert tone="danger">{visits.error}</Alert> :
          <Table rows={(visits.data || []).filter((visit) => !['completed', 'cancelled'].includes(visit.status)).slice(0, 8)}
            empty="No active visits" columns={[
              { key: 'queue_number', label: 'Queue' },
              { key: 'patient_name', label: 'Patient' },
              { key: 'status', label: 'Stage', render: (visit) => statusBadge(visit.status) },
            ]} />}
      </Card>
      <Card title="Team" actions={<Link to="staff" className="text-sm font-semibold text-primary-700">Staff & Access</Link>}>
        <Table rows={(summary.staff_by_role || []).map((row) => ({ ...row, id: row.role }))} empty="No staff memberships"
          columns={[
            { key: 'role', label: 'Role', render: (row) => row.role.replaceAll('_', ' ') },
            { key: 'count', label: 'Active staff' },
          ]} />
      </Card>
    </div>
    {facility.has_pharmacy && <Card title="Affiliated pharmacies">
      {pharmacies.loading ? <Spinner /> : pharmacies.error ? <Alert tone="danger">{pharmacies.error}</Alert> :
        <Table rows={pharmacies.data || []} columns={[
          { key: 'legal_name', label: 'Pharmacy' },
          { key: 'phone', label: 'Contact', render: (row) => row.phone || row.contact_email || '—' },
        ]} />}
    </Card>}
  </div>
}
