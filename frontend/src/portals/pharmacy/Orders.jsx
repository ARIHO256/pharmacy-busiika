import OrderReceipt from './OrderReceipt'
import { useAuth } from '../../auth/AuthContext'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from './shared'
import { useState } from 'react'
import { errMsg } from './shared'

const nextOptions = {
  pending: ['confirmed', 'cancelled'],
  ready: ['delivered', 'cancelled'],
  dispatched: ['delivered'],
}

const statusLabel = {
  confirmed: 'Confirm order', ready: 'Ready for pickup', dispatched: 'Dispatch',
  delivered: 'Record handover', cancelled: 'Cancel order',
}

export default function Orders() {
  const { data: orders, loading, error, reload } = useApi(() => servicesApi.orders())
  const { user } = useAuth()
  const [receiptOrder, setReceiptOrder] = useState(null)
  const canRecordPayment = ['pharmacy', 'pharmacist', 'facility_manager', 'cashier'].includes(user?.role)
  const [updating, setUpdating] = useState(null)
  const [handover, setHandover] = useState(null)
  const [reference, setReference] = useState('')
  const [actionError, setActionError] = useState('')

  const setStatus = async (order, status, fields) => {
    if (!status) return
    setActionError('')
    if (status === 'delivered' && !fields) {
      setHandover(order)
      setReference('')
      return
    }
    setUpdating(order.id)
    try {
      await servicesApi.updateOrder(order.id, status, fields)
      setHandover(null)
      reload()
    } catch (e) {
      setActionError(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Customer orders">
        {actionError && !handover && <Alert tone="danger">{actionError}</Alert>}
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
            { key: 'payment_recorded', label: 'Payment', render: (o) => (
              o.payment_recorded || (canRecordPayment && o.status !== 'cancelled' && o.total > 0)
                ? <Button variant="outline" onClick={() => setReceiptOrder(o)}>
                    {o.payment_recorded ? 'Print receipt' : 'Record payment'}
                  </Button>
                : '—'
            ) },
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
            { key: 'status', label: 'Status', render: (o) => ['ready', 'dispatched'].includes(o.status)
              ? statusLabel[o.status] : <StatusBadge status={o.status} /> },
            { key: 'dispensed_batches', label: 'Handover and batch trace', render: (o) => <div>
              {o.handed_over_at && <p>{fmtDate(o.handed_over_at)}</p>}
              {o.dispensed_batches.map((movement) => <p key={movement.id}>{movement.medicine} · Batch {movement.batch} · Movement #{movement.id}</p>)}
            </div> },
            {
              key: 'actions',
              label: 'Update',
              render: (o) =>
                (user?.role !== 'cashier' && (o.status === 'confirmed' || nextOptions[o.status])) ? (
                  <Select
                    value=""
                    disabled={updating === o.id}
                    onChange={(e) => setStatus(o, e.target.value)}
                    className="min-w-36"
                  >
                    <option value="">Set status…</option>
                    {(o.status === 'confirmed' ? [o.delivery ? 'dispatched' : 'ready', 'cancelled'] : nextOptions[o.status]).filter((s) => s !== 'cancelled' || !o.payment_recorded).map((s) => (
                      <option key={s} value={s}>
                        {statusLabel[s]}
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
      {receiptOrder && <OrderReceipt order={receiptOrder} onClose={() => setReceiptOrder(null)} onRecorded={reload} />}
      {handover && <Modal open title={`Record handover · Order #${handover.id}`}
        onClose={() => { if (updating === null) setHandover(null) }}>
        <form className="space-y-3" onSubmit={(event) => {
          event.preventDefault()
          setStatus(handover, 'delivered', { handover_reference: reference })
        }}>
          {actionError && <Alert tone="danger">{actionError}</Alert>}
          <Input required maxLength={200} label="Collection or delivery confirmation reference" value={reference}
            onChange={(event) => setReference(event.target.value)} />
          <Button disabled={updating !== null} type="submit">Confirm handover</Button>
        </form>
      </Modal>}
    </LoadingOrError>
  )
}
