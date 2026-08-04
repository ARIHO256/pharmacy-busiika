import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Card, Select, Table } from '../../components/ui'
import { errMsg, fmtDate, LoadingOrError, StatusBadge, useApi } from '../pharmacy/shared'

const nextOptions = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['completed', 'cancelled'],
}

export default function Bookings() {
  const { data: bookings, loading, error, reload } = useApi(() => servicesApi.hospitalBookingsManage())
  const [updating, setUpdating] = useState(null)

  const setStatus = async (booking, status) => {
    if (!status) return
    setUpdating(booking.id)
    try {
      await servicesApi.updateHospitalBooking(booking.id, status)
      reload()
    } catch (e) {
      alert(errMsg(e))
    } finally {
      setUpdating(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Bookings">
        <Table
          empty="No bookings yet"
          columns={[
            { key: 'id', label: 'Booking', render: (b) => <span className="font-medium text-slate-800">#{b.id}</span> },
            { key: 'patient_name', label: 'Patient' },
            { key: 'service_name', label: 'Service', render: (b) => b.service_name || '—' },
            { key: 'date', label: 'Date' },
            { key: 'created_at', label: 'Booked', render: (b) => fmtDate(b.created_at) },
            { key: 'status', label: 'Status', render: (b) => <StatusBadge status={b.status} /> },
            {
              key: 'actions',
              label: 'Update',
              render: (b) =>
                nextOptions[b.status] ? (
                  <Select
                    value=""
                    disabled={updating === b.id}
                    onChange={(e) => setStatus(b, e.target.value)}
                    className="min-w-36"
                  >
                    <option value="">Set status…</option>
                    {nextOptions[b.status].map((s) => (
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
          rows={bookings || []}
        />
      </Card>
    </LoadingOrError>
  )
}
