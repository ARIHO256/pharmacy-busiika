import { useMemo, useState } from 'react'
import { appointmentApi, servicesApi, workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

function ResultReview({ order, onClose, onAcknowledged, canResume, onResumed }) {
  const results = useRemote(() => servicesApi.labResults(order.id), [order.id])
  const [notes, setNotes] = useState({})
  const [pending, setPending] = useState(null)
  const [resuming, setResuming] = useState(false)
  const [error, setError] = useState('')

  const acknowledge = async (result) => {
    setPending(result.id)
    setError('')
    try {
      await servicesApi.acknowledgeCriticalResult(result.id, notes[result.id] || '')
      await results.reload()
      onAcknowledged()
    } catch (err) {
      setError(getError(err))
    } finally {
      setPending(null)
    }
  }

  const resume = async () => {
    setResuming(true)
    setError('')
    try {
      await workforceApi.updateVisit(order.visit, { action: 'resume_after_lab' })
      onResumed()
    } catch (err) {
      setError(getError(err))
    } finally {
      setResuming(false)
    }
  }

  return (
    <Modal open wide title={`Results for order #${order.id}`} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-slate-600">{order.patient_name} · {order.test_name}</p>
        <div className="flex flex-wrap items-center gap-3">
          {order.result_file && <a className="text-sm font-semibold text-primary-700 underline" href={order.result_file} target="_blank" rel="noreferrer">Open laboratory report</a>}
          {canResume && <Button variant="outline" disabled={resuming || pending !== null} onClick={resume}>Resume consultation</Button>}
        </div>
        {(error || results.error) && <Alert tone="danger">{error || results.error}</Alert>}
        {results.loading && <Spinner label="Loading results…" />}
        {!results.loading && !results.error && !results.data?.length && <p className="text-sm text-slate-600">No structured results are available.</p>}
        {(results.data || []).map((result) => (
          <Card key={result.id} title={result.name} actions={statusBadge(result.interpretation)}>
            <div className="space-y-3">
              <p className="font-semibold">{result.value_numeric ?? result.value_text} {result.unit}</p>
              <p className="text-sm text-slate-600">{result.released_at ? `Released ${displayDate(result.released_at)}` : 'Awaiting release'}</p>
              {result.escalated_at && !result.is_superseded && <Alert tone="warning">Escalated {displayDate(result.escalated_at)}.</Alert>}
              {result.is_superseded && <Alert>Superseded by a newer result.</Alert>}
              {result.amendment_reason && <p className="text-sm text-slate-700">Amendment reason: {result.amendment_reason}</p>}
              {result.interpretation === 'critical' && result.released_at && !result.is_superseded && (
                result.acknowledged
                  ? <Alert tone="success">Acknowledged by {result.acknowledged_by_name || 'the care team'}.</Alert>
                  : <div className="space-y-3">
                    <Alert tone="warning">Critical result awaiting acknowledgement.</Alert>
                    <Textarea label="Follow-up notes" value={notes[result.id] || ''} onChange={(event) => setNotes({ ...notes, [result.id]: event.target.value })} />
                    <Button type="button" disabled={pending !== null} onClick={() => acknowledge(result)}>Acknowledge critical result</Button>
                  </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </Modal>
  )
}

export default function LabReferrals(){
 const [reviewOrder,setReviewOrder]=useState(null)
 const [criticalOnly,setCriticalOnly]=useState(false)
 const visits=useRemote(()=>workforceApi.visits(),[])
 const referrals=useRemote(()=>servicesApi.myLabOrders(),[]); const appointments=useRemote(()=>appointmentApi.list(),[]); const labs=useRemote(()=>servicesApi.providers('labs'),[]); const [tests,setTests]=useState([]); const [open,setOpen]=useState(false); const [error,setError]=useState(''); const [form,setForm]=useState({patient_id:'',lab_id:'',test_id:'',clinical_indication:'',provisional_diagnosis:'',priority:'routine',specimen_type:'',referring_facility:''})
 const patients=useMemo(()=>{const map=new Map();(appointments.data||[]).forEach(a=>map.set(a.patient,{id:a.patient,name:a.patient_name||`Patient #${a.patient}`}));return [...map.values()]},[appointments.data])
 const selectLab=async(value)=>{setForm({...form,lab_id:value,test_id:''});if(!value)return setTests([]);try{const{data}=await servicesApi.labTests({lab:value});setTests(data)}catch(e){setError(getError(e))}}
 const save=async(e)=>{e.preventDefault();setError('');try{await servicesApi.bookLab(form);setOpen(false);referrals.reload();visits.reload()}catch(err){setError(getError(err))}}
 const activeVisits = (visits.data || []).filter((visit) => visit.assigned_doctor && !['completed', 'cancelled'].includes(visit.status))
 const orders = referrals.data || []
 const criticalCount = orders.filter((order) => order.critical_review_pending).length
 if((referrals.loading && !referrals.data)||appointments.loading||labs.loading)return <Spinner/>;return <><Card title="Laboratory referrals" subtitle="Request a test, provide clinical indication and track specimen-to-result status" actions={<Button onClick={()=>setOpen(true)}>New laboratory order</Button>}>{(error||referrals.error)&&<Alert tone="danger" className="mb-4">{error||referrals.error}</Alert>}<div className="mb-4 flex flex-wrap gap-2">
   <Button variant={criticalOnly ? 'outline' : 'primary'} aria-pressed={!criticalOnly} onClick={() => setCriticalOnly(false)}>All referrals</Button>
   <Button variant={criticalOnly ? 'primary' : 'outline'} aria-pressed={criticalOnly} onClick={() => setCriticalOnly(true)}>Critical review pending ({criticalCount})</Button>
 </div><Table rows={criticalOnly ? orders.filter((order) => order.critical_review_pending) : orders} empty={criticalOnly ? "No critical results awaiting acknowledgement" : "No laboratory referrals created"} columns={[{key:'created_at',label:'Ordered',render:o=>displayDate(o.created_at)},{key:'patient_name',label:'Patient'},{key:'test_name',label:'Test'},{key:'lab_name',label:'Laboratory'},{key:'priority',label:'Priority',render:o=>statusBadge(o.priority)},{key:'status',label:'Status',render:o=>statusBadge(o.status)},{key:'result',label:'Result',render:o=>o.result_released?<Button variant="outline" onClick={()=>setReviewOrder(o)}>{o.has_critical_result ? 'Review critical result' : 'Review results'}</Button>:<span className="text-slate-400">Pending</span>}]}/></Card><Modal open={open} onClose={()=>setOpen(false)} wide title="Order laboratory test"><form onSubmit={save} className="space-y-4"><Select required label="Patient or assigned visit" value={form.visit_id ? `visit:${form.visit_id}` : form.patient_id} onChange={(event) => {
   const choice = event.target.value
   const visit = activeVisits.find((row) => `visit:${row.id}` === choice)
   setForm({ ...form, patient_id: visit ? visit.patient : choice, visit_id: visit?.id || '' })
 }}><option value="">Select patient or visit</option>
   <optgroup label="Facility visits">{activeVisits.map((visit) => <option key={visit.id} value={`visit:${visit.id}`}>{visit.visit_number} · {visit.patient_name}</option>)}</optgroup>
   <optgroup label="Appointment patients">{patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.name}</option>)}</optgroup>
 </Select><div className="grid gap-3 sm:grid-cols-2"><Select required label="Verified laboratory" value={form.lab_id} onChange={e=>selectLab(e.target.value)}><option value="">Select laboratory</option>{(labs.data||[]).map(l=><option key={l.id} value={l.id}>{l.org_name}</option>)}</Select><Select required label="Test" value={form.test_id} onChange={e=>setForm({...form,test_id:e.target.value})}><option value="">Select test</option>{tests.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</Select></div><Select label="Priority" value={form.priority} onChange={e=>setForm({...form,priority:e.target.value})}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="stat">STAT / emergency</option></Select><Textarea required label="Clinical indication" value={form.clinical_indication} onChange={e=>setForm({...form,clinical_indication:e.target.value})}/><Input label="Provisional diagnosis" value={form.provisional_diagnosis} onChange={e=>setForm({...form,provisional_diagnosis:e.target.value})}/><div className="grid gap-3 sm:grid-cols-2"><Input label="Specimen type" value={form.specimen_type} onChange={e=>setForm({...form,specimen_type:e.target.value})}/><Input label="Referring facility" value={form.referring_facility} onChange={e=>setForm({...form,referring_facility:e.target.value})}/></div><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setOpen(false)}>Cancel</Button><Button>Send laboratory order</Button></div></form></Modal>{reviewOrder && <ResultReview order={reviewOrder} onClose={()=>setReviewOrder(null)} onAcknowledged={referrals.reload} canResume={activeVisits.some((visit) => visit.id === reviewOrder.visit && visit.status === 'laboratory')} onResumed={visits.reload} />}</>
}
