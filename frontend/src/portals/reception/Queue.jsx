import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Modal, Select, Spinner, Table } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

const managerTransitions = {
  waiting_triage: 'triaged', triaged: 'waiting_clinician', waiting_clinician: 'in_consultation',
  in_consultation: 'billing', billing: 'completed',
}

export default function Queue() {
  const { user } = useAuth()
  const canManage = ['facility_manager', 'hospital', 'admin'].includes(user?.role)
  const visits = useRemote(() => workforceApi.visits(), [])
  const [selected, setSelected] = useState(null)
  const [choices, setChoices] = useState(null)
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const update = async (visit, payload) => {
    setBusy(true)
    setError('')
    try {
      await workforceApi.updateVisit(visit.id, payload)
      setSelected(null)
      visits.reload()
    } catch (err) {
      setError(getError(err))
    } finally {
      setBusy(false)
    }
  }

  const assign = async (visit) => {
    setSelected(visit)
    setChoices(null)
    setError('')
    setForm({ assigned_doctor: visit.assigned_doctor || '', assigned_nurse: visit.assigned_nurse || '' })
    setBusy(true)
    try {
      const { data } = await workforceApi.visitCareTeam(visit.id)
      setChoices(data)
    } catch (err) {
      setError(getError(err))
    } finally {
      setBusy(false)
    }
  }

  if (visits.loading) return <Spinner />
  return <>
    <Card title="Patient flow board" subtitle="Assign the care team and track arrivals at the receiving laboratory">
      {(visits.error || (!selected && error)) && <Alert tone="danger" className="mb-4">{visits.error || error}</Alert>}
      <Table rows={visits.data || []} empty="No visits recorded" columns={[
        { key: 'queue_number', label: 'Queue', render: (v) => <strong>#{v.queue_number || '—'}</strong> },
        { key: 'patient_name', label: 'Patient' },
        { key: 'reason', label: 'Reason' },
        { key: 'priority', label: 'Priority', render: (v) => statusBadge(v.priority) },
        { key: 'status', label: 'Stage', render: (v) => statusBadge(v.status) },
        { key: 'checked_in_at', label: 'Checked in', render: (v) => displayDate(v.checked_in_at) },
        { key: 'team', label: 'Care team', render: (v) => <div className="space-y-1">
          <div>Doctor: {v.assigned_doctor_name || 'Unassigned'}</div>
          <div>Nurse: {v.assigned_nurse_name || 'Unassigned'}</div>
          {!['completed', 'cancelled'].includes(v.status) && <Button variant="outline" disabled={busy} onClick={() => assign(v)}>Assign team</Button>}
        </div> },
        { key: 'laboratory_handoffs', label: 'Laboratory handoff', render: (v) => (
          <div className="min-w-44 space-y-2">
            {!v.laboratory_handoffs?.length && <span className="text-slate-500">—</span>}
            {v.laboratory_handoffs?.map((order) => <div key={order.id} className="space-y-1">
              <div className="font-medium">{order.destination} · #{order.id}</div>
              {statusBadge(order.status)}
              {order.arrived_at ? <div className="text-xs text-slate-600">Arrival recorded {displayDate(order.arrived_at)}</div>
                : !['completed', 'cancelled'].includes(v.status) && ['booked', 'ready_for_collection'].includes(order.status) &&
                  <div><Button variant="outline" disabled={busy} onClick={() => update(v, { action: 'lab_arrival', order: order.id })}>Record lab arrival</Button></div>}
            </div>)}
          </div>
        ) },
        ...(canManage ? [{ key: 'actions', label: 'Actions', render: (visit) => managerTransitions[visit.status] &&
          <Button variant="outline" disabled={busy} onClick={() => update(visit, { status: managerTransitions[visit.status] })}>
            Move to {managerTransitions[visit.status].replaceAll('_', ' ')}
          </Button>,
        }] : []),
      ]}/>
    </Card>
    <Modal open={Boolean(selected)} title={selected ? `Assign care team · ${selected.patient_name}` : 'Assign care team'}
      onClose={() => { if (!busy) setSelected(null) }}>
      {error && <Alert tone="danger">{error}</Alert>}
      {!choices && busy && <Spinner />}
      {choices && <form className="space-y-4" onSubmit={(event) => {
        event.preventDefault()
        if (!busy) update(selected, { action: 'assign_care_team', ...form })
      }}>
        {['doctor', 'nurse'].map((role) => <Select key={role} label={role === 'doctor' ? 'Assigned doctor' : 'Assigned nurse'}
          value={form[`assigned_${role}`]} onChange={(event) => setForm({ ...form, [`assigned_${role}`]: event.target.value })}>
          <option value="">Unassigned</option>
          {choices.filter((person) => person.role === role).map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
        </Select>)}
        <Button disabled={busy}>Save assignment</Button>
      </form>}
    </Modal>
  </>
}
