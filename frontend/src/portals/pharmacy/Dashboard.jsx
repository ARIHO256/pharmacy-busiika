import { Link } from 'react-router-dom'
import { servicesApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Card, Stat, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from './shared'

export default function Dashboard() {
  const { user } = useAuth()
  const { data, loading, error } = useApi(() =>
    Promise.all([servicesApi.medicines({ pharmacy: user.id }), servicesApi.orders(), servicesApi.pharmacyOrders()]).then(
      ([meds, orders, rx]) => ({
        medicines: meds.data || [],
        orders: orders.data || [],
        rxOrders: rx.data || [],
      }),
    ),
  )

  const meds = data?.medicines || []
  const orders = data?.orders || []
  const rxOrders = data?.rxOrders || []
  const pendingOrders = orders.filter((o) => o.status === 'pending').length
  const newRx = rxOrders.filter((o) => o.status === 'new').length

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Medicines in inventory" value={meds.length} icon="💊" />
          <Stat label="Pending orders" value={pendingOrders} icon="📦" />
          <Stat label="New Rx orders" value={newRx} icon="📋" />
          <Stat
            label="Revenue (delivered)"
            value={money(orders.filter((o) => o.status === 'delivered').reduce((s, o) => s + Number(o.total || 0), 0))}
            icon="💰"
            tone="text-emerald-600"
          />
        </div>
        <Card
          title="Recent orders"
          actions={
            <Link to="orders" className="text-sm text-primary-600 hover:underline">
              View all
            </Link>
          }
        >
          <Table
            empty="No orders yet"
            columns={[
              { key: 'id', label: 'Order', render: (o) => `#${o.id}` },
              { key: 'patient_name', label: 'Patient' },
              { key: 'total', label: 'Total', render: (o) => money(o.total) },
              { key: 'created_at', label: 'Placed', render: (o) => fmtDate(o.created_at) },
              { key: 'status', label: 'Status', render: (o) => <StatusBadge status={o.status} /> },
            ]}
            rows={orders.slice(0, 5)}
          />
        </Card>
      </div>
    </LoadingOrError>
  )
}
