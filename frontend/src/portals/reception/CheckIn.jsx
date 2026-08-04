import { useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Select, Table, Textarea } from '../../components/ui'
import { getError } from '../staff/shared'

export default function CheckIn() {
  const [search, setSearch] = useState('')
  const [patients, setPatients] = useState([])
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({ visit_type: 'walk_in', priority: 'routine', reason: '' })
  const [message, setMessage] = useState(null)
  const [error, setError] = useState('')
  const find = async (e) => { e.preventDefault(); setError(''); try { const { data } = await workforceApi.patients(search); setPatients(data) } catch (err) { setError(getError(err)) } }
  const checkIn = async (e) => { e.preventDefault(); setError(''); try { const { data } = await workforceApi.checkIn({ patient: selected.id, ...form }); setMessage(data); setSelected(null); setPatients([]); setSearch(''); setForm({ visit_type: 'walk_in', priority: 'routine', reason: '' }) } catch (err) { setError(getError(err)) } }
  return <div className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
    <Card title="1. Find patient" subtitle="Locate the existing patient before check-in">
      {error && <Alert tone="danger" className="mb-4">{error}</Alert>}
      <form onSubmit={find} className="mb-4 flex gap-2"><Input className="flex-1" required value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Phone, email or patient name"/><Button>Find</Button></form>
      <Table rows={patients} empty="No search results yet" columns={[{ key: 'name', label: 'Patient' }, { key: 'phone', label: 'Contact' }, { key: 'location', label: 'Location' }, { key: 'action', label: '', render: (p) => <Button variant={selected?.id === p.id ? 'primary' : 'outline'} onClick={() => setSelected(p)}>{selected?.id === p.id ? 'Selected' : 'Select'}</Button> }]}/>
    </Card>
    <Card title="2. Check in" subtitle="Create the visit and place the patient in the triage queue">
      {message && <Alert tone="success" className="mb-4" title="Check-in complete">Visit {message.visit_number}; queue number <strong>#{message.queue_number}</strong>.</Alert>}
      {!selected ? <p className="text-sm text-slate-500">Select a patient from the directory first.</p> : <form onSubmit={checkIn} className="space-y-4">
        <Alert tone="info"><strong>{selected.name}</strong><br/>{selected.phone} · {selected.email}</Alert>
        <Select label="Visit type" value={form.visit_type} onChange={(e) => setForm({ ...form, visit_type: e.target.value })}><option value="walk_in">Walk-in</option><option value="appointment">Appointment</option><option value="follow_up">Follow-up</option><option value="emergency">Emergency</option></Select>
        <Select label="Initial priority" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option></Select>
        <Textarea required label="Reason for visit" value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })}/><Button className="w-full">Complete check-in</Button>
      </form>}
    </Card>
  </div>
}
