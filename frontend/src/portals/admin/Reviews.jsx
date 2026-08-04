import { useEffect, useState } from 'react'
import { Card, Spinner, Stars, Table } from '../../components/ui'
import { adminApi } from '../../api/endpoints'
import { fmtDateTime } from './helpers'

export default function Reviews() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi
      .reviews()
      .then((res) => setItems(res.data))
      .catch(() => {
        setItems([])
        setError('Failed to load reviews.')
      })
  }, [])

  const columns = [
    { key: 'patient_name', label: 'Patient', render: (r) => r.patient_name || '—' },
    { key: 'doctor_name', label: 'Doctor', render: (r) => r.doctor_name || '—' },
    { key: 'rating', label: 'Rating', render: (r) => <Stars value={r.rating} /> },
    {
      key: 'comment',
      label: 'Comment',
      render: (r) =>
        r.comment ? (
          <span className="text-slate-600">{r.comment}</span>
        ) : (
          <span className="text-slate-300">—</span>
        ),
    },
    { key: 'created_at', label: 'Created', render: (r) => fmtDateTime(r.created_at) },
  ]

  return (
    <div className="space-y-4">
      {error && (
        <div className="text-sm text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-4 py-2">
          {error}
        </div>
      )}
      <Card title={`Reviews${items ? ` (${items.length})` : ''}`}>
        {items === null ? (
          <Spinner label="Loading reviews…" />
        ) : (
          <Table columns={columns} rows={items} empty="No reviews yet" />
        )}
      </Card>
    </div>
  )
}
