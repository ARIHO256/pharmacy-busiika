import { useMemo, useState } from 'react'
import { operationsApi, workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Stat, Table, Textarea } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

export default function EmergencyBoard() {
  const cases = useRemote(() => operationsApi.emergencyCases(), [])
  const dispatches = useRemote(() => operationsApi.ambulanceDispatches(), [])
  const [modal, setModal] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [patients, setPatients] = useState([])
  const [search, setSearch] = useState('')
  const [caseForm, setCaseForm] = useState({ patient: '', arrival_mode: 'walk_in', acuity: 'urgent', chief_complaint: '', triage_notes: '' })
  const [dispatch, setDispatch] = useState({ patient: '', caller_name: '', caller_phone: '', pickup_location: '', destination: '', priority: 'urgent', ambulance_identifier: '' })
  const stats = useMemo(() => {
    const rows = cases.data || []
    return {
      open: rows.filter((x) => !['referred', 'admitted', 'discharged', 'left', 'deceased'].includes(x.status)).length,
      critical: rows.filter((x) => ['resuscitation', 'emergent'].includes(x.acuity)).length,
      treatment: rows.filter((x) => ['in_treatment', 'observation'].includes(x.status)).length,
      ambulances: (dispatches.data || []).filter((x) => !['completed', 'cancelled'].includes(x.status)).length,
    }
  }, [cases.data, dispatches.data])
  const findPatients = async () => { try { setPatients((await workforceApi.patients(search)).data) } catch (e) { setError(getError(e)) } }
  const run = async (fn, reload = true) => { setBusy(true); setError(''); try { await fn(); if (reload) { cases.reload(); dispatches.reload() } } catch (e) { setError(getError(e)) } finally { setBusy(false) } }
  const createCase = (e) => { e.preventDefault(); run(async () => { await operationsApi.createEmergencyCase(caseForm); setModal(''); setCaseForm({ patient: '', arrival_mode: 'walk_in', acuity: 'urgent', chief_complaint: '', triage_notes: '' }) }) }
  const createDispatch = (e) => { e.preventDefault(); run(async () => { const payload = { ...dispatch, patient: dispatch.patient || null }; await operationsApi.createAmbulanceDispatch(payload); setModal(''); setDispatch({ patient: '', caller_name: '', caller_phone: '', pickup_location: '', destination: '', priority: 'urgent', ambulance_identifier: '' }) }) }
  const actCase = (id, action) => run(() => operationsApi.actEmergencyCase(id, { action }))
  const actDispatch = (id, action) => run(() => operationsApi.actAmbulanceDispatch(id, { action }))
  if (cases.loading || dispatches.loading) return <Spinner />
  const err = error || cases.error || dispatches.error
  return <div className="space-y-5">
    {err && <Alert tone="danger">{err}</Alert>}
    <div className="flex flex-wrap justify-end gap-2"><Button variant="outline" onClick={() => setModal('dispatch')}>New ambulance dispatch</Button><Button onClick={() => setModal('case')}>Register emergency case</Button></div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Open emergency cases" value={stats.open} icon="activity"/><Stat label="Critical acuity" value={stats.critical} icon="alert"/><Stat label="In treatment / observation" value={stats.treatment} icon="clipboard"/><Stat label="Active ambulance jobs" value={stats.ambulances} icon="hospital"/></div>
    <Card title="Emergency and casualty board" subtitle="Acuity, assignment, treatment and disposition in one live view"><Table rows={cases.data || []} empty="No emergency cases registered." columns={[
      { key:'case_number', label:'Case', render:r=><strong>{r.case_number}<small className="block font-normal text-slate-400">{displayDate(r.arrival_at)}</small></strong> },
      { key:'patient_name', label:'Patient' },
      { key:'chief_complaint', label:'Presentation' },
      { key:'acuity', label:'Acuity', render:r=>statusBadge(r.acuity) },
      { key:'status', label:'Status', render:r=>statusBadge(r.status) },
      { key:'actions', label:'', render:r=><div className="flex flex-wrap gap-1">{r.status==='arrived'&&<Button variant="outline" onClick={()=>actCase(r.id,'triage')}>Triage</Button>}{['arrived','triaged'].includes(r.status)&&<Button variant="outline" onClick={()=>actCase(r.id,'start_treatment')}>Treat</Button>}{['in_treatment','observation'].includes(r.status)&&<Button variant="outline" onClick={()=>actCase(r.id,'admit')}>Admit</Button>}{!['discharged','admitted','referred','left','deceased'].includes(r.status)&&<Button variant="ghost" onClick={()=>actCase(r.id,'discharge')}>Discharge</Button>}</div> },
    ]}/></Card>
    <Card title="Ambulance dispatch board" subtitle="Request, assignment, transport and destination status"><Table rows={dispatches.data || []} empty="No ambulance dispatches." columns={[
      {key:'dispatch_number',label:'Dispatch',render:r=><strong>{r.dispatch_number}<small className="block font-normal text-slate-400">{r.ambulance_identifier||'Vehicle not assigned'}</small></strong>},
      {key:'caller_name',label:'Caller',render:r=><span>{r.caller_name}<small className="block text-slate-400">{r.caller_phone}</small></span>},
      {key:'pickup_location',label:'Pickup'}, {key:'priority',label:'Priority',render:r=>statusBadge(r.priority)}, {key:'status',label:'Status',render:r=>statusBadge(r.status)},
      {key:'actions',label:'',render:r=><div className="flex flex-wrap gap-1">{r.status==='requested'&&<Button variant="outline" onClick={()=>actDispatch(r.id,'assign')}>Assign</Button>}{['assigned'].includes(r.status)&&<Button variant="outline" onClick={()=>actDispatch(r.id,'depart')}>Depart</Button>}{r.status==='en_route'&&<Button variant="outline" onClick={()=>actDispatch(r.id,'on_scene')}>On scene</Button>}{r.status==='on_scene'&&<Button variant="outline" onClick={()=>actDispatch(r.id,'transport')}>Transport</Button>}{['transporting','arrived'].includes(r.status)&&<Button onClick={()=>actDispatch(r.id,'complete')}>Complete</Button>}</div>},
    ]}/></Card>
    <Modal open={modal==='case'} onClose={()=>setModal('')} title="Register emergency case" wide><form className="space-y-4" onSubmit={createCase}><div className="flex gap-2"><Input className="flex-1" label="Find patient" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Name, email or phone"/><Button type="button" variant="outline" onClick={findPatients}>Search</Button></div><Select required label="Patient" value={caseForm.patient} onChange={e=>setCaseForm({...caseForm,patient:e.target.value})}><option value="">Select patient</option>{patients.map(p=><option key={p.id} value={p.id}>{p.name} — {p.phone||p.email}</option>)}</Select><div className="grid gap-3 sm:grid-cols-2"><Select label="Arrival mode" value={caseForm.arrival_mode} onChange={e=>setCaseForm({...caseForm,arrival_mode:e.target.value})}>{['walk_in','ambulance','referral','police','other'].map(x=><option key={x} value={x}>{x.replaceAll('_',' ')}</option>)}</Select><Select label="Acuity" value={caseForm.acuity} onChange={e=>setCaseForm({...caseForm,acuity:e.target.value})}>{['resuscitation','emergent','urgent','less_urgent','non_urgent'].map(x=><option key={x} value={x}>{x.replaceAll('_',' ')}</option>)}</Select></div><Textarea required label="Chief complaint" value={caseForm.chief_complaint} onChange={e=>setCaseForm({...caseForm,chief_complaint:e.target.value})}/><Textarea label="Initial triage notes" value={caseForm.triage_notes} onChange={e=>setCaseForm({...caseForm,triage_notes:e.target.value})}/><Button disabled={busy}>{busy?'Saving…':'Register case'}</Button></form></Modal>
    <Modal open={modal==='dispatch'} onClose={()=>setModal('')} title="Create ambulance dispatch" wide><form className="grid gap-4 sm:grid-cols-2" onSubmit={createDispatch}><Input required label="Caller name" value={dispatch.caller_name} onChange={e=>setDispatch({...dispatch,caller_name:e.target.value})}/><Input required label="Caller phone" value={dispatch.caller_phone} onChange={e=>setDispatch({...dispatch,caller_phone:e.target.value})}/><Textarea required className="sm:col-span-2" label="Pickup location" value={dispatch.pickup_location} onChange={e=>setDispatch({...dispatch,pickup_location:e.target.value})}/><Textarea className="sm:col-span-2" label="Destination" value={dispatch.destination} onChange={e=>setDispatch({...dispatch,destination:e.target.value})}/><Select label="Priority" value={dispatch.priority} onChange={e=>setDispatch({...dispatch,priority:e.target.value})}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="critical">Critical</option></Select><Input label="Ambulance / vehicle" value={dispatch.ambulance_identifier} onChange={e=>setDispatch({...dispatch,ambulance_identifier:e.target.value})}/><Button className="sm:col-span-2" disabled={busy}>{busy?'Dispatching…':'Create dispatch'}</Button></form></Modal>
  </div>
}
