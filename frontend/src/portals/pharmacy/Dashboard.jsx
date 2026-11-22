import { usePharmacyPermissions } from './PharmacyPermissions'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { operationsApi, servicesApi } from '../../api/endpoints'
import { Card, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from './shared'

export default function Dashboard() {
  const { user } = useAuth()
  const allows = usePharmacyPermissions()
  const inventoryAccess = allows('inventory')
  const ordersAccess = allows('orders')
  const rxAccess = allows('rx-orders')
  const read = (allowed, fetch) => allowed ? fetch() : Promise.resolve({ data: [] })
  const facilityContext = useApi(() => operationsApi.context())
  const { data, loading, error } = useApi(() =>
    Promise.all([read(inventoryAccess, servicesApi.medicines), read(ordersAccess, servicesApi.orders), read(rxAccess, servicesApi.pharmacyOrders)]).then(
      ([meds, orders, rx]) => ({
        data: {
          medicines: meds.data || [],
          orders: orders.data || [],
          rxOrders: rx.data || [],
        },
      }),
    ),
    [inventoryAccess, ordersAccess, rxAccess],
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
        {pharmacies.length > 0 && <Card title="Your pharmacy">
          <ul className="space-y-2 text-sm text-slate-700">
            {pharmacies.map((pharmacy) => <li key={pharmacy.id}>
              <strong>{pharmacy.name}</strong> · {pharmacy.parent_facility_name || 'Standalone pharmacy'}
            </li>)}
          </ul>
          {user?.role === 'pharmacy' && <div className="mt-4 flex flex-wrap gap-4 text-sm font-semibold text-primary-700">
            <Link to="staff">Invite staff</Link>
            <Link to="stock-control">Enter opening batches</Link>
            <Link to="counter">New sale</Link>
            <Link to="shifts">Open or reconcile cash shifts</Link>
          </div>}
        </Card>}
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-slate-200 bg-slate-200 sm:grid-cols-4">
          {[
            ['Medicines', inventoryAccess ? meds.length : '—'],
            ['Pending orders', ordersAccess ? pendingOrders : '—'],
            ['New prescriptions', rxAccess ? newRx : '—'],
            ['Recorded sales', ordersAccess ? money(orders.filter((order) => order.payment_recorded).reduce((sum, order) => sum + Number(order.total), 0)) : '—'],
          ].map(([label, value]) => <div key={label} className="bg-white p-4">
            <dt className="text-sm text-slate-600">{label}</dt>
            <dd className="mt-1 text-xl font-semibold tabular-nums text-slate-900">{value}</dd>
          </div>)}
        </dl>
        {ordersAccess && <Card
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
        </Card>}
      </div>
    </LoadingOrError>
  )
}
