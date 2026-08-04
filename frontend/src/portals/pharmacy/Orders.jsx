import { servicesApi } from '../../api/endpoints'
import { Card, Select, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from './shared'
import { useState } from 'react'
import { errMsg } from './shared'

const nextOptions = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['delivered', 'cancelled'],
}

export default function Orders() {
  const { data: orders, loading, error, reload } = useApi(() => servicesApi.orders())
  const [updating, setUpdating] = useState(null)

  const setStatus = async (order, status) => {
    if (!status) return
    setUpdating(order.id)
    try {
      await servicesApi.updateOrder(order.id, status)
      reload()
    } catch (e) {
      alert(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Customer orders">
        <Table
          empty="No orders yet"
          columns={[
            { key: 'id', label: 'Order', render: (o) => <span className="font-medium text-slate-800">#{o.id}</span> },
            { key: 'patient_name', label: 'Patient' },
            {
              key: 'items',
              label: 'Items',
              render: (o) => (
                <ul className="text-slate-600 space-y-0.5">
                  {(o.items || []).map((it) => (
                    <li key={it.id}>
                      {it.name} <span className="text-slate-400">× {it.qty}</span>
                    </li>
                  ))}
                </ul>
              ),
            },
            { key: 'total', label: 'Total', render: (o) => money(o.total) },
            {
              key: 'delivery',
              label: 'Delivery',
              render: (o) =>
                o.delivery ? (
                  <span className="text-slate-600" title={o.address}>
                    🚚 {o.address || 'Yes'}
                  </span>
                ) : (
                  <span className="text-slate-400">Pickup</span>
                ),
            },
            { key: 'created_at', label: 'Placed', render: (o) => fmtDate(o.created_at) },
            { key: 'status', label: 'Status', render: (o) => <StatusBadge status={o.status} /> },
            {
              key: 'actions',
              label: 'Update',
              render: (o) =>
                nextOptions[o.status] ? (
                  <Select
                    value=""
                    disabled={updating === o.id}
                    onChange={(e) => setStatus(o, e.target.value)}
                    className="min-w-36"
                  >
                    <option value="">Set status…</option>
                    {nextOptions[o.status].map((s) => (
                      <option key={s} value={s}>
                        Mark {s}
                      </option>
                    ))}
                  </Select>
                ) : (
                  <span className="text-slate-300 text-xs">—</span>
                ),
            },
          ]}
          rows={orders || []}
        />
      </Card>
    </LoadingOrError>
  )
}
