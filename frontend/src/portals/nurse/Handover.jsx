import { useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { displayDate, getError, useRemote } from '../staff/shared'

const fields = [
  ['situation', 'Current situation'],
  ['background', 'Relevant background'],
  ['assessment', 'Assessment'],
  ['next_actions', 'Next actions and who owns them'],
]

export default function Handover() {
  const visits = useRemote(() => workforceApi.visits(), [])
  const notes = useRemote(() => workforceApi.nursingNotes({ note_type: 'handover' }), [])
  const [creating, setCreating] = useState(false)
  const [selected, setSelected] = useState(null)
  const [visit, setVisit] = useState('')
  const [handover, setHandover] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const active = (visits.data || []).filter((item) => !['completed', 'cancelled'].includes(item.status))

  const save = async (event) => {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setError('')
    const structured = Object.fromEntries(fields.map(([key]) => [key, (handover[key] || '').trim()]))
    try {
      await workforceApi.addNursingNote({ visit, note_type: 'handover', note: structured.situation, handover: structured })
      setCreating(false)
      notes.reload()
    } catch (err) {
      setError(getError(err))
    } finally {
      setSaving(false)
    }
  }

  if (notes.loading || visits.loading) return <Spinner />
  return <>
    <Card title="Shift handover" subtitle="Review the latest assessment and the next actions for each visit" icon="clipboard"
      actions={<Button disabled={!active.length} onClick={() => {
        setVisit('')
        setHandover({})
        setError('')
        setCreating(true)
      }}>Record handover</Button>}>
      {(notes.error || visits.error) && <Alert tone="danger">{notes.error || visits.error}</Alert>}
      {!active.length && !visits.error && <Alert>Check in a patient before recording a handover.</Alert>}
      <Table rows={notes.data || []} empty="No handovers recorded" columns={[
        { key: 'patient_name', label: 'Patient' },
        { key: 'visit_number', label: 'Visit' },
        { key: 'note', label: 'Situation' },
        { key: 'nurse_name', label: 'Recorded by' },
        { key: 'recorded_at', label: 'Recorded', render: (row) => displayDate(row.recorded_at) },
        { key: 'review', label: 'Actions', render: (row) => <Button variant="outline" onClick={() => setSelected(row)}>Review</Button> },
      ]} />
    </Card>
    <Modal open={creating} title="Record shift handover" onClose={() => { if (!saving) setCreating(false) }}>
      <form onSubmit={save} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Select required label="Patient visit" value={visit} onChange={(event) => setVisit(event.target.value)}>
          <option value="">Select a visit</option>
          {active.map((item) => <option key={item.id} value={item.id}>{item.visit_number} · {item.patient_name}</option>)}
        </Select>
        {fields.map(([key, label]) => <Textarea key={key} required={key !== 'background'} label={label}
          maxLength={2000} value={handover[key] || ''} onChange={(event) => setHandover({ ...handover, [key]: event.target.value })} />)}
        <Button disabled={saving}>{saving ? 'Saving…' : 'Save handover'}</Button>
      </form>
    </Modal>
    <Modal open={Boolean(selected)} title={selected ? `Handover for ${selected.patient_name}` : 'Handover'} onClose={() => setSelected(null)}>
      {selected && <dl className="space-y-4">
        {(Object.keys(selected.handover || {}).length ? fields : [['note', 'Note']]).map(([key, label]) => (
          <div key={key}><dt className="font-semibold">{label}</dt>
            <dd className="whitespace-pre-wrap text-sm text-slate-700">{key === 'note' ? selected.note : selected.handover[key] || '—'}</dd></div>
        ))}
      </dl>}
    </Modal>
  </>
}
