import { Link } from 'react-router-dom'
import { servicesApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Card, Stat, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, StatusBadge, useApi } from '../pharmacy/shared'

export default function Dashboard() {
  const { user } = useAuth()
  const { data, loading, error } = useApi(() =>
    Promise.all([servicesApi.labTests({ lab: user.id }), servicesApi.labOrdersManage()]).then(([tests, orders]) => ({
      tests: tests.data || [],
      orders: orders.data || [],
    })),
  )

  const tests = data?.tests || []
  const orders = data?.orders || []
  const active = orders.filter((o) => o.status !== 'completed').length
  const completed = orders.filter((o) => o.status === 'completed').length

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Tests offered" value={tests.length} icon="🧪" />
          <Stat label="Active orders" value={active} icon="📋" />
          <Stat label="Completed orders" value={completed} icon="✅" tone="text-emerald-600" />
          <Stat label="Awaiting sample" value={orders.filter((o) => o.status === 'booked').length} icon="🩸" />
        </div>
        <Card
          title="Recent lab orders"
          actions={
            <Link to="orders" className="text-sm text-primary-600 hover:underline">
              View all
            </Link>
          }
        >
          <Table
            empty="No lab orders yet"
            columns={[
              { key: 'id', label: 'Order', render: (o) => `#${o.id}` },
              { key: 'patient_name', label: 'Patient' },
              { key: 'test_name', label: 'Test' },
              { key: 'created_at', label: 'Booked', render: (o) => fmtDate(o.created_at) },
              { key: 'status', label: 'Status', render: (o) => <StatusBadge status={o.status} /> },
            ]}
            rows={orders.slice(0, 5)}
          />
        </Card>
      </div>
    </LoadingOrError>
  )
}
