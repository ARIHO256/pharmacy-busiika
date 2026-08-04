import { useMemo, useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { getError, statusBadge, useRemote } from '../staff/shared'

const empty = { level: 'green', chief_complaint: '', temperature_c: '', pulse_bpm: '', respiratory_rate: '', systolic_bp: '', diastolic_bp: '', oxygen_saturation: '', weight_kg: '', height_cm: '', pain_score: '', allergies: '', notes: '' }

export default function Triage() {
  const visits = useRemote(() => workforceApi.visits(), [])
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState(empty)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const queue = useMemo(() => (visits.data || []).filter((v) => ['waiting_triage', 'registered'].includes(v.status)), [visits.data])
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const open = (visit) => { setSelected(visit); setForm({ ...empty, chief_complaint: visit.reason || '' }); setError('') }
  const submit = async (e) => {
    e.preventDefault(); setSaving(true); setError('')
    try {
      const payload = { visit: selected.id, ...form }
      Object.keys(payload).forEach((key) => { if (payload[key] === '') payload[key] = null })
      await workforceApi.saveTriage(payload)
      setSelected(null); visits.reload()
    } catch (err) { setError(getError(err)) } finally { setSaving(false) }
  }
  if (visits.loading) return <Spinner />
  return <div className="space-y-4">
    {visits.error && <Alert tone="danger">{visits.error}</Alert>}
    <Card title="Triage queue" subtitle="Record observations, allergies, pain and clinical urgency before clinician review">
      <Table rows={queue} empty="No patients are waiting for triage" columns={[
        { key: 'queue_number', label: 'Queue', render: (v) => <strong>#{v.queue_number || '—'}</strong> },
        { key: 'patient_name', label: 'Patient' },
        { key: 'patient_phone', label: 'Contact' },
        { key: 'reason', label: 'Chief complaint' },
        { key: 'priority', label: 'Priority', render: (v) => statusBadge(v.priority) },
        { key: 'action', label: '', render: (v) => <Button onClick={() => open(v)}>Start triage</Button> },
      ]}/>
    </Card>
    <Modal open={!!selected} onClose={() => setSelected(null)} wide title={`Triage — ${selected?.patient_name || ''}`}>
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="grid gap-3 md:grid-cols-2">
          <Select label="Urgency level" value={form.level} onChange={set('level')}><option value="red">Red — immediate</option><option value="orange">Orange — very urgent</option><option value="yellow">Yellow — urgent</option><option value="green">Green — standard</option><option value="blue">Blue — non-urgent</option></Select>
          <Input label="Pain score (0–10)" min="0" max="10" type="number" value={form.pain_score} onChange={set('pain_score')} />
        </div>
        <Textarea label="Chief complaint" required value={form.chief_complaint} onChange={set('chief_complaint')} />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input label="Temperature °C" type="number" step="0.1" value={form.temperature_c} onChange={set('temperature_c')} />
          <Input label="Pulse / min" type="number" value={form.pulse_bpm} onChange={set('pulse_bpm')} />
          <Input label="Respirations / min" type="number" value={form.respiratory_rate} onChange={set('respiratory_rate')} />
          <Input label="Oxygen saturation %" type="number" value={form.oxygen_saturation} onChange={set('oxygen_saturation')} />
          <Input label="Systolic BP" type="number" value={form.systolic_bp} onChange={set('systolic_bp')} />
          <Input label="Diastolic BP" type="number" value={form.diastolic_bp} onChange={set('diastolic_bp')} />
          <Input label="Weight kg" type="number" step="0.01" value={form.weight_kg} onChange={set('weight_kg')} />
          <Input label="Height cm" type="number" step="0.01" value={form.height_cm} onChange={set('height_cm')} />
        </div>
        <Textarea label="Known allergies" value={form.allergies} onChange={set('allergies')} />
        <Textarea label="Triage notes" value={form.notes} onChange={set('notes')} />
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setSelected(null)}>Cancel</Button><Button disabled={saving}>{saving ? 'Saving…' : 'Save and send to clinician'}</Button></div>
      </form>
    </Modal>
  </div>
}
