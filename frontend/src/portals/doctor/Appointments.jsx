import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { appointmentApi, chatApi } from '../../api/endpoints'
import { Badge, Button, Card, Spinner, Table } from '../../components/ui'
import { statusColor } from './util'

const TABS = ['all', 'pending', 'confirmed', 'completed', 'cancelled', 'missed']

const patientName = (a) =>
  a.patient_name || [a.patient_first_name, a.patient_last_name].filter(Boolean).join(' ') || `Patient #${a.patient}`

export default function Appointments() {
  const [tab, setTab] = useState('all')
  const [rows, setRows] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback((status) => {
    setRows(null)
    const params = status === 'all' ? {} : { status }
    appointmentApi.list(params).then((r) => setRows(r.data || [])).catch(() => setRows([]))
  }, [])

  useEffect(() => { load(tab) }, [tab, load])

  async function act(id, action) {
    setBusyId(id)
    setError('')
    try {
      await appointmentApi.act(id, action)
      load(tab)
    } catch (err) {
      setError(err.response?.data?.detail || `Could not ${action} appointment`)
      setBusyId(null)
    }
  }

  async function joinVideo(id) {
    setBusyId(id)
    setError('')
    try {
      const { data } = await chatApi.videoRoom(id)
      window.open(data.url, '_blank', 'noopener')
    } catch (err) {
      setError(err.response?.data?.detail || 'Video room unavailable')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3.5 py-1.5 rounded-full text-sm font-medium capitalize transition ${
              tab === t ? 'bg-primary-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {error && <div className="text-sm text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-4 py-2.5">{error}</div>}

      <Card title={`Appointments${tab !== 'all' ? ` — ${tab}` : ''}`}>
        {!rows ? (
          <Spinner label="Loading appointments…" />
        ) : (
          <Table
            columns={[
              { key: 'date', label: 'Date' },
              { key: 'time', label: 'Time', render: (a) => `${(a.start_time || '').slice(0, 5)} – ${(a.end_time || '').slice(0, 5)}` },
              { key: 'patient', label: 'Patient', render: patientName },
              { key: 'type', label: 'Type', render: (a) => <Badge color={a.type === 'online' ? 'blue' : 'purple'}>{a.type}</Badge> },
              { key: 'reason', label: 'Reason', render: (a) => a.reason || '—' },
              { key: 'status', label: 'Status', render: (a) => <Badge color={statusColor(a.status)}>{a.status}</Badge> },
              {
                key: 'actions',
                label: 'Actions',
                render: (a) => (
                  <div className="flex flex-wrap gap-1.5">
                    {a.status === 'pending' && (
                      <>
                        <Button className="!px-2.5 !py-1 !text-xs" disabled={busyId === a.id} onClick={() => act(a.id, 'confirm')}>Confirm</Button>
                        <Button variant="danger" className="!px-2.5 !py-1 !text-xs" disabled={busyId === a.id} onClick={() => act(a.id, 'cancel')}>Cancel</Button>
                      </>
                    )}
                    {a.status === 'confirmed' && (
                      <>
                        {a.type === 'online' && (
                          <Button variant="outline" className="!px-2.5 !py-1 !text-xs" disabled={busyId === a.id} onClick={() => joinVideo(a.id)}>🎥 Join Video</Button>
                        )}
                        <Button className="!px-2.5 !py-1 !text-xs" disabled={busyId === a.id} onClick={() => act(a.id, 'complete')}>Complete</Button>
                        <Button variant="outline" className="!px-2.5 !py-1 !text-xs" disabled={busyId === a.id} onClick={() => act(a.id, 'miss')}>Miss</Button>
                        <Link to={`/doctor/prescriptions?appointment=${a.id}`}>
                          <Button variant="outline" className="!px-2.5 !py-1 !text-xs">📋 Write Rx</Button>
                        </Link>
                      </>
                    )}
                  </div>
                ),
              },
            ]}
            rows={rows}
            empty="No appointments found."
          />
        )}
      </Card>
    </div>
  )
}
