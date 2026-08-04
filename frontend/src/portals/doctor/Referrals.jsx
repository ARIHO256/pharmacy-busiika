import { useCallback, useEffect, useState } from 'react'
import { clinicalApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, Modal, Spinner, Table, Textarea } from '../../components/ui'

const tone = { sent:'blue', accepted:'green', in_progress:'purple', completed:'green', declined:'red', cancelled:'slate' }
const label = (value) => String(value || '').replaceAll('_', ' ')

export default function Referrals() {
  const [incoming, setIncoming] = useState(null)
  const [outgoing, setOutgoing] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [selected, setSelected] = useState(null)
  const [action, setAction] = useState('')
  const [reason, setReason] = useState('')
  const [outcome, setOutcome] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    Promise.all([clinicalApi.referrals(null,{scope:'incoming'}), clinicalApi.referrals(null,{scope:'outgoing'})])
      .then(([a,b]) => { setIncoming(a.data); setOutgoing(b.data) })
      .catch((err) => setError(err.response?.data?.detail || 'Could not load the referral workspace.'))
  }, [])
  useEffect(() => load(), [load])

  const openAction = (row, nextAction) => { setSelected(row); setAction(nextAction); setReason(''); setOutcome('') }
  const submit = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      await clinicalApi.referralAction(selected.id, action, { reason, outcome_summary: outcome })
      setSelected(null); setNotice(`Referral ${label(action)} recorded and the care team was notified.`); load()
    } catch (err) { setError(err.response?.data?.detail || 'Could not update the referral.') }
    finally { setBusy(false) }
  }

  if (!incoming || !outgoing) return <Spinner label="Loading referral coordination…" />
  const common = [
    {key:'patient_name',label:'Patient'},
    {key:'target',label:'Destination',render:r=><div><div className="font-medium text-slate-800">{r.target_provider_name || r.target_specialty}</div><div className="text-xs text-slate-400">{r.target_organization_name || r.target_facility || r.target_specialty}</div></div>},
    {key:'priority',label:'Priority',render:r=><Badge color={r.priority==='emergency'?'red':r.priority==='urgent'?'amber':'blue'}>{r.priority}</Badge>},
    {key:'status',label:'Status',render:r=><Badge color={tone[r.status]||'slate'}>{label(r.status)}</Badge>},
    {key:'reason',label:'Reason',render:r=><span className="line-clamp-2 max-w-xs text-slate-600">{r.reason}</span>},
  ]
  return <div className="space-y-5">
    {notice && <Alert tone="success">{notice}</Alert>}{error && <Alert tone="danger">{error}</Alert>}
    <Card>
      <p className="text-xs font-semibold uppercase tracking-[.16em] text-primary-600">Closed-loop referral management</p>
      <h2 className="mt-1 text-xl font-semibold text-slate-900">Coordinate specialist care from referral to feedback</h2>
      <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-500">Receiving clinicians accept or decline referrals, start the referred episode and return a signed outcome summary. Referring clinicians can acknowledge the feedback, while every transition is audited and notified.</p>
    </Card>
    <Card title="Incoming referrals" subtitle="Patients referred directly to you for specialist review.">
      <Table rows={incoming} empty="No incoming referrals assigned to you." columns={[...common,{key:'actions',label:'Actions',render:r=><div className="flex flex-wrap gap-2">{r.status==='sent'&&<><Button className="px-3 py-1 text-xs" onClick={()=>openAction(r,'accept')}>Accept</Button><Button variant="outline" className="px-3 py-1 text-xs" onClick={()=>openAction(r,'decline')}>Decline</Button></>}{r.status==='accepted'&&<Button className="px-3 py-1 text-xs" onClick={()=>openAction(r,'start')}>Start care</Button>}{r.status==='in_progress'&&<Button className="px-3 py-1 text-xs" onClick={()=>openAction(r,'complete')}>Complete & return feedback</Button>}</div>}]} />
    </Card>
    <Card title="Outgoing referrals" subtitle="Track acceptance, delivery and specialist feedback.">
      <Table rows={outgoing} empty="No outgoing referrals created." columns={[...common,{key:'feedback',label:'Outcome',render:r=><span className="line-clamp-2 max-w-xs text-slate-500">{r.outcome_summary || r.decline_reason || 'Awaiting feedback'}</span>},{key:'actions',label:'Actions',render:r=><div className="flex gap-2">{!['completed','cancelled','declined'].includes(r.status)&&<Button variant="outline" className="px-3 py-1 text-xs" onClick={()=>openAction(r,'cancel')}>Cancel</Button>}{r.status==='completed'&&!r.feedback_acknowledged_at&&<Button className="px-3 py-1 text-xs" onClick={()=>openAction(r,'acknowledge')}>Acknowledge</Button>}</div>}]} />
    </Card>
    <Modal open={!!selected} onClose={()=>setSelected(null)} title={`${label(action)} referral`} wide>
      {selected&&<div className="space-y-4"><div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm"><div className="font-semibold text-slate-800">{selected.patient_name} · {selected.target_specialty}</div><p className="mt-1 text-slate-600">{selected.reason}</p></div>{action==='complete'&&<Textarea required label="Specialist outcome and recommendations" rows={6} value={outcome} onChange={e=>setOutcome(e.target.value)} />}{['decline','cancel'].includes(action)&&<Textarea required={action==='decline'} label="Reason" value={reason} onChange={e=>setReason(e.target.value)} />}{action==='acknowledge'&&<p className="text-sm text-slate-600">Confirm that the specialist outcome has been reviewed and incorporated into the patient's ongoing care.</p>}<div className="flex justify-end gap-2"><Button variant="outline" onClick={()=>setSelected(null)}>Back</Button><Button disabled={busy || (action==='complete'&&!outcome.trim()) || (action==='decline'&&!reason.trim())} onClick={submit}>{busy?'Saving…':'Confirm action'}</Button></div></div>}
    </Modal>
  </div>
}
