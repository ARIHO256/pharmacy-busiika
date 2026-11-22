import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

export default function Medications() {
  const visits = useRemote(() => workforceApi.visits(), [])
  const administrations = useRemote(() => workforceApi.medicationAdministrations(), [])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ visit: '', medication: '', dose: '', route: '', status: 'given', notes: '' })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const submitting = useRef(false)
  const save = async (event) => {
    event.preventDefault()
    if (submitting.current) return
    submitting.current = true
    setSaving(true)
    setError('')
    try {
      await workforceApi.recordMedicationAdministration(form)
      setOpen(false)
      administrations.reload()
    } catch (err) {
      setError(getError(err))
    } finally {
      submitting.current = false
      setSaving(false)
    }
  }
  if (visits.loading || administrations.loading) return <Spinner />
  return <>
    <Card title="Medication administration record" subtitle="Record what was given, held, refused or missed" actions={<div className="flex items-center gap-3">
      <Link to="/nurse/scheduled-doses" className="text-sm font-semibold text-primary-700 hover:underline">Scheduled doses</Link>
      <Button onClick={() => { setError(''); setOpen(true) }}>Record administration</Button>
    </div>}>
      {(visits.error || administrations.error) && <Alert tone="danger">{visits.error || administrations.error}</Alert>}
      <Table rows={administrations.data || []} empty="No medication administrations recorded" columns={[
        { key: 'administered_at', label: 'Time', render: (r) => displayDate(r.administered_at) }, { key: 'patient_name', label: 'Patient' },
        { key: 'medication', label: 'Medication' }, { key: 'dose', label: 'Dose' }, { key: 'route', label: 'Route' },
        { key: 'status', label: 'Status', render: (r) => statusBadge(r.status) }, { key: 'nurse_name', label: 'Recorded by' },
      ]}/>
    </Card>
    <Modal open={open} onClose={() => { if (!submitting.current) setOpen(false) }} title="Record medication administration"><form onSubmit={save} className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      <Select required label="Patient visit" value={form.visit} onChange={(e) => setForm({ ...form, visit: e.target.value })}><option value="">Select visit</option>{(visits.data || []).filter((v) => !['completed','cancelled'].includes(v.status)).map((v) => <option key={v.id} value={v.id}>{v.visit_number} — {v.patient_name}</option>)}</Select>
      <Input required label="Medication" value={form.medication} onChange={(e) => setForm({ ...form, medication: e.target.value })} />
      <div className="grid grid-cols-2 gap-3"><Input required label="Dose" value={form.dose} onChange={(e) => setForm({ ...form, dose: e.target.value })}/><Input label="Route" placeholder="Oral, IV, IM…" value={form.route} onChange={(e) => setForm({ ...form, route: e.target.value })}/></div>
      <Select label="Outcome" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="given">Given</option><option value="held">Held</option><option value="refused">Refused</option><option value="missed">Missed</option></Select>
      <Textarea label="Notes / reason" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}/>
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" disabled={saving} onClick={() => setOpen(false)}>Cancel</Button><Button disabled={saving}>{saving ? 'Saving…' : 'Save administration'}</Button></div>
    </form></Modal>
  </>
}
