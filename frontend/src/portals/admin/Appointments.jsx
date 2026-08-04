import { useCallback, useEffect, useState } from 'react'
import { Badge, Card, Spinner, Table } from '../../components/ui'
import { adminApi } from '../../api/endpoints'
import { appointmentStatusColor, fmtDate, fmtTime } from './helpers'

const TABS = ['', 'pending', 'confirmed', 'completed', 'cancelled', 'missed']

export default function Appointments() {
  const [items, setItems] = useState(null)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    adminApi
      .appointments(status ? { status } : {})
      .then((res) => setItems(res.data))
      .catch(() => {
        setItems([])
        setError('Failed to load appointments.')
      })
  }, [status])

  useEffect(() => {
    setItems(null)
    load()
  }, [load])

  const columns = [
    { key: 'patient_name', label: 'Patient', render: (a) => a.patient_name || '—' },
    { key: 'doctor_name', label: 'Doctor', render: (a) => a.doctor_name || '—' },
    { key: 'date', label: 'Date', render: (a) => fmtDate(a.date) },
    {
      key: 'time',
      label: 'Time',
      render: (a) => `${fmtTime(a.start_time)} – ${fmtTime(a.end_time)}`,
    },
    {
      key: 'type',
      label: 'Type',
      render: (a) => <Badge color={a.type === 'online' ? 'blue' : 'slate'}>{a.type}</Badge>,
    },
    {
      key: 'status',
      label: 'Status',
      render: (a) => (
        <Badge color={appointmentStatusColor[a.status] || 'slate'}>{a.status}</Badge>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t || 'all'}
            onClick={() => setStatus(t)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium capitalize transition ${
              status === t
                ? 'bg-primary-600 text-white'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {t || 'all'}
          </button>
        ))}
      </div>

      {error && (
        <div className="text-sm text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      <Card title={`Appointments${items ? ` (${items.length})` : ''}`}>
        {items === null ? (
          <Spinner label="Loading appointments…" />
        ) : (
          <Table columns={columns} rows={items} empty="No appointments found" />
        )}
      </Card>
    </div>
  )
}
