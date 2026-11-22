import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { operationsApi, servicesApi } from '../../api/endpoints'
import { Card, Stat, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from './shared'

export default function Dashboard() {
  const { user } = useAuth()
  const facilityContext = useApi(() => operationsApi.context())
  const { data, loading, error } = useApi(() =>
    Promise.all([servicesApi.medicines(), servicesApi.orders(), servicesApi.pharmacyOrders()]).then(
      ([meds, orders, rx]) => ({
        medicines: meds.data || [],
        orders: orders.data || [],
        rxOrders: rx.data || [],
      }),
    ),
  )

  const pharmacies = (facilityContext.data?.organizations || []).filter((organization) => organization.type === 'pharmacy')
  const meds = data?.medicines || []
  const orders = data?.orders || []
  const rxOrders = data?.rxOrders || []
  const pendingOrders = orders.filter((o) => o.status === 'pending').length
  const newRx = rxOrders.filter((o) => o.status === 'new').length

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        {pharmacies.length > 0 && <Card title="Pharmacy setup" icon="pill">
          <ul className="space-y-2 text-sm text-slate-700">
            {pharmacies.map((pharmacy) => <li key={pharmacy.id}>
              <strong>{pharmacy.name}</strong> · {pharmacy.parent_facility_name || 'Standalone pharmacy'}
            </li>)}
          </ul>
          {user?.role === 'pharmacy' && <div className="mt-4 flex flex-wrap gap-4 text-sm font-semibold text-primary-700">
            <Link to="staff">Invite staff</Link>
            <Link to="stock-control">Enter opening batches</Link>
            <Link to="counter">Start a walk-in sale</Link>
            <Link to="shifts">Open or reconcile cash shifts</Link>
          </div>}
        </Card>}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Medicines in inventory" value={meds.length} icon="💊" />
          <Stat label="Pending orders" value={pendingOrders} icon="📦" />
          <Stat label="New Rx orders" value={newRx} icon="📋" />
          <Stat
            label="Recorded sales"
            value={money(orders.filter((o) => o.payment_recorded).reduce((s, o) => s + Number(o.total || 0), 0))}
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
