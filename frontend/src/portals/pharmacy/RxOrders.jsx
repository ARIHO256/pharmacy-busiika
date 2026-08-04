import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Button, Card } from '../../components/ui'
import { errMsg, fmtDate, LoadingOrError, StatusBadge, useApi } from './shared'

export default function RxOrders() {
  const { data: orders, loading, error, reload } = useApi(() => servicesApi.pharmacyOrders())
  const [updating, setUpdating] = useState(null)

  const setStatus = async (order, status) => {
    setUpdating(order.id)
    try {
      await servicesApi.updatePharmacyOrder(order.id, status)
      reload()
    } catch (e) {
      alert(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      {!orders?.length ? (
        <Card>
          <div className="text-sm text-slate-400 text-center py-8">No prescription orders yet</div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {orders.map((o) => (
            <Card
              key={o.id}
              title={
                <span>
                  Rx Order <span className="text-primary-600">#{o.id}</span>
                </span>
              }
              actions={<StatusBadge status={o.status} />}
            >
              <div className="space-y-4">
                <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
                  <span className="text-slate-600">
                    <span className="text-slate-400">Patient:</span> {o.patient_name || '—'}
                  </span>
                  <span className="text-slate-600">
                    <span className="text-slate-400">Received:</span> {fmtDate(o.created_at)}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-100 overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-slate-50 text-left text-slate-500">
                        <th className="px-3 py-2 font-medium">Medicine</th>
                        <th className="px-3 py-2 font-medium">Dosage</th>
                        <th className="px-3 py-2 font-medium">Frequency</th>
                        <th className="px-3 py-2 font-medium">Duration</th>
                        <th className="px-3 py-2 font-medium text-right">Qty</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(o.prescription_items || []).map((it, i) => (
                        <tr key={i} className="border-t border-slate-100">
                          <td className="px-3 py-2 text-slate-700">{it.medicine_name}</td>
                          <td className="px-3 py-2 text-slate-500">{it.dosage || '—'}</td>
                          <td className="px-3 py-2 text-slate-500">{it.frequency || '—'}</td>
                          <td className="px-3 py-2 text-slate-500">{it.duration || '—'}</td>
                          <td className="px-3 py-2 text-right text-slate-700">{it.quantity}</td>
                        </tr>
                      ))}
                      {!o.prescription_items?.length && (
                        <tr className="border-t border-slate-100">
                          <td colSpan={5} className="px-3 py-3 text-center text-slate-400">
                            No items on this prescription
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {(o.status === 'new' || o.status === 'prepared') && (
                  <div className="flex justify-end gap-2">
                    {o.status === 'new' && (
                      <>
                        <Button variant="danger" disabled={updating === o.id} onClick={() => setStatus(o, 'rejected')}>
                          Reject
                        </Button>
                        <Button disabled={updating === o.id} onClick={() => setStatus(o, 'prepared')}>
                          Mark prepared
                        </Button>
                      </>
                    )}
                    {o.status === 'prepared' && (
                      <Button disabled={updating === o.id} onClick={() => setStatus(o, 'delivered')}>
                        Mark delivered
                      </Button>
                    )}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </LoadingOrError>
  )
}
