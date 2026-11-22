import { Link } from 'react-router-dom'
import { registryApi, servicesApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Card, Spinner, Stat, Table } from '../../components/ui'
import { LoadingOrError, StatusBadge, useApi } from '../pharmacy/shared'

export default function Dashboard() {
  const { user } = useAuth()
  const { data, loading, error } = useApi(() =>
    Promise.all([servicesApi.hospitalServices({ hospital: user.id }), servicesApi.hospitalBookingsManage(), servicesApi.beds()]).then(
      ([services, bookings, beds]) => ({
        services: services.data || [],
        bookings: bookings.data || [],
        beds: beds.data || [],
      }),
    ),
  )

  const facilityPharmacies = useApi(async () => {
    const { data: organizations } = await registryApi.myOrganizations()
    const facilities = organizations.filter((org) => ['clinic', 'hospital'].includes(org.organization_type))
    const responses = await Promise.all(facilities.map(async (facility) => {
      const { data: pharmacies } = await registryApi.organizations({ type: 'pharmacy', parent_facility: facility.id })
      return pharmacies.map((pharmacy) => ({ ...pharmacy, facility: facility.legal_name }))
    }))
    return { data: responses.flat() }
  })

  const services = data?.services || []
  const bookings = data?.bookings || []
  const beds = data?.beds || []
  const occupied = beds.filter((b) => b.is_occupied).length

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Services offered" value={services.length} icon="🏥" />
          <Stat label="Pending bookings" value={bookings.filter((b) => b.status === 'pending').length} icon="📅" />
          <Stat label="Beds occupied" value={`${occupied} / ${beds.length}`} icon="🛏️" tone="text-rose-600" />
          <Stat label="Beds available" value={beds.length - occupied} icon="✅" tone="text-emerald-600" />
        </div>
        <Card title="Facility pharmacies" subtitle="Affiliated dispensaries available for prescription routing">
          {facilityPharmacies.loading ? <Spinner label="Loading pharmacies…" /> : facilityPharmacies.error ?
            <Alert tone="danger">{facilityPharmacies.error}</Alert> :
            <Table rows={facilityPharmacies.data || []} empty="No pharmacy is affiliated with this facility." columns={[
              { key: 'legal_name', label: 'Pharmacy' }, { key: 'facility', label: 'Facility' },
              { key: 'phone', label: 'Contact', render: (row) => row.phone || row.contact_email || '—' },
            ]} />}
        </Card>
        <Card
          title="Recent bookings"
          actions={
            <Link to="bookings" className="text-sm text-primary-600 hover:underline">
              View all
            </Link>
          }
        >
          <Table
            empty="No bookings yet"
            columns={[
              { key: 'id', label: 'Booking', render: (b) => `#${b.id}` },
              { key: 'patient_name', label: 'Patient' },
              { key: 'service_name', label: 'Service', render: (b) => b.service_name || '—' },
              { key: 'date', label: 'Date' },
              { key: 'status', label: 'Status', render: (b) => <StatusBadge status={b.status} /> },
            ]}
            rows={bookings.slice(0, 5)}
          />
        </Card>
      </div>
    </LoadingOrError>
  )
}
