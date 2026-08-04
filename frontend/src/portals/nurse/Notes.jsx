import { useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { displayDate, getError, useRemote } from '../staff/shared'

export default function Notes() {
  const visits = useRemote(() => workforceApi.visits(), [])
  const notes = useRemote(() => workforceApi.nursingNotes(), [])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ visit: '', note_type: 'progress', note: '' })
  const [error, setError] = useState('')
  const save = async (e) => { e.preventDefault(); setError(''); try { await workforceApi.addNursingNote(form); setOpen(false); setForm({ visit: '', note_type: 'progress', note: '' }); notes.reload() } catch (err) { setError(getError(err)) } }
  if (notes.loading || visits.loading) return <Spinner />
  return <>
    <Card title="Nursing notes" subtitle="Assessment, progress, procedure, handover and discharge documentation" actions={<Button onClick={() => setOpen(true)}>Add note</Button>}>
      {(notes.error || visits.error) && <Alert tone="danger">{notes.error || visits.error}</Alert>}
      <Table rows={notes.data || []} empty="No nursing notes recorded" columns={[
        { key: 'recorded_at', label: 'Recorded', render: (n) => displayDate(n.recorded_at) },
        { key: 'visit_number', label: 'Visit' }, { key: 'patient_name', label: 'Patient' },
        { key: 'note_type', label: 'Type' }, { key: 'note', label: 'Note' }, { key: 'nurse_name', label: 'Recorded by' },
      ]}/>
    </Card>
    <Modal open={open} onClose={() => setOpen(false)} title="Add nursing note"><form onSubmit={save} className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      <Select required label="Patient visit" value={form.visit} onChange={(e) => setForm({ ...form, visit: e.target.value })}><option value="">Select visit</option>{(visits.data || []).filter((v) => !['completed','cancelled'].includes(v.status)).map((v) => <option key={v.id} value={v.id}>{v.visit_number} — {v.patient_name}</option>)}</Select>
      <Select label="Note type" value={form.note_type} onChange={(e) => setForm({ ...form, note_type: e.target.value })}><option value="assessment">Assessment</option><option value="progress">Progress</option><option value="procedure">Procedure</option><option value="handover">Handover</option><option value="discharge">Discharge</option></Select>
      <Textarea required label="Clinical note" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} />
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button>Save note</Button></div>
    </form></Modal>
  </>
}
