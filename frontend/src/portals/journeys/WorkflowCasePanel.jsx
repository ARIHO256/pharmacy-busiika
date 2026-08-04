import { useEffect, useMemo, useState } from 'react'
import { enterpriseApi, journeyApi } from '../../api/endpoints'
import { Alert, Badge, Button, EmptyState, Input, Modal, Select, Spinner, Textarea } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'

const tone = (value) => ['completed','closed','approved','released','signed','active','acknowledged'].includes(String(value).toLowerCase()) ? 'green' : ['rejected','revoked','cancelled','failed','critical','overdue'].includes(String(value).toLowerCase()) ? 'red' : ['submitted','pending','pending_review','awaiting_information','under_review','assigned','processing'].includes(String(value).toLowerCase()) ? 'yellow' : 'blue'
const labelize = (value='') => String(value).replaceAll('_',' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const normalizeError = (error) => {
  const data = error?.response?.data
  if (!data) return error?.message || 'The request could not be completed.'
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return Object.entries(data).map(([key,value]) => `${labelize(key)}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' · ')
}

function EntityPicker({ spec, value, onChange, error }) {
  const [query,setQuery]=useState('')
  const [options,setOptions]=useState([])
  const [loading,setLoading]=useState(false)
  useEffect(()=>{
    if (!query && !value) { setOptions([]); return }
    const timer=setTimeout(async()=>{
      setLoading(true)
      try {
        const {data}=await enterpriseApi.lookup(spec.entity || 'patient', query, { limit: 20 })
        setOptions(Array.isArray(data) ? data : data.results || [])
      } catch { setOptions([]) }
      finally { setLoading(false) }
    },250)
    return()=>clearTimeout(timer)
  },[query,spec.entity,value])
  const selected=options.find((item)=>String(item.id)===String(value))
  return <div>
    <label className="block text-sm font-semibold text-slate-700">{spec.label}{spec.required ? ' *' : ''}</label>
    <div className="relative mt-1.5">
      <Input value={selected ? selected.label || selected.name : query} onChange={(event)=>{setQuery(event.target.value); if(value)onChange('')}} placeholder={`Search ${spec.label.toLowerCase()}…`} aria-label={spec.label}/>
      {loading?<span className="absolute right-3 top-3 h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-primary-600"/>:null}
      {query && options.length ? <div className="absolute z-40 mt-1 max-h-60 w-full overflow-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl">{options.map((item)=><button key={item.id} type="button" onClick={()=>{onChange(item.id);setQuery(item.label||item.name||String(item.id));setOptions([])}} className="block w-full rounded-lg px-3 py-2 text-left hover:bg-primary-50"><strong className="block text-sm text-slate-800">{item.label||item.name||item.display_name}</strong>{item.meta||item.subtitle?<small className="text-slate-500">{item.meta||item.subtitle}</small>:null}</button>)}</div>:null}
    </div>
    {error?<span className="mt-1 block text-xs text-rose-600">{error}</span>:null}
  </div>
}

function DefinitionField({ spec, value, onChange, error }) {
  const common={label:`${spec.label}${spec.required?' *':''}`,value:value??'',onChange:(event)=>onChange(event.target.value),error,hint:spec.help_text}
  if(spec.type==='entity') return <EntityPicker spec={spec} value={value} onChange={onChange} error={error}/>
  if(spec.type==='textarea') return <Textarea {...common}/>
  if(spec.type==='choice') return <Select label={common.label} value={common.value} onChange={common.onChange}><option value="">Select…</option>{(spec.choices||[]).map((choice)=><option key={choice} value={choice}>{labelize(choice)}</option>)}</Select>
  if(spec.type==='boolean') return <label className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3"><input type="checkbox" checked={Boolean(value)} onChange={(event)=>onChange(event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-primary-600"/><span className="text-sm font-semibold text-slate-700">{spec.label}</span></label>
  if(spec.type==='json') return <Textarea {...common} value={typeof value==='string'?value:JSON.stringify(value||{},null,2)} onChange={(event)=>onChange(event.target.value)} hint="Enter valid JSON data."/>
  if(spec.type==='list') return <Input {...common} value={Array.isArray(value)?value.join(', '):value||''} onChange={(event)=>onChange(event.target.value)} hint="Separate values with commas."/>
  const type={datetime:'datetime-local',date:'date',time:'time',number:'number',money:'number'}[spec.type]||'text'
  return <Input {...common} type={type}/>
}

function cleanPayload(definition, form) {
  const relational=new Set(['patient','subject_user','assigned_to','appointment','admission','invoice','parent','title','summary','priority','due_at'])
  const payload={}
  const data={}
  for(const spec of definition.fields||[]){
    let value=form[spec.name]
    if(value===''||value===undefined) continue
    if(spec.type==='list'&&typeof value==='string') value=value.split(',').map((item)=>item.trim()).filter(Boolean)
    if(spec.type==='json'&&typeof value==='string'){
      try{value=JSON.parse(value||'{}')}catch{throw new Error(`${spec.label} must contain valid JSON.`)}
    }
    if(relational.has(spec.name)) payload[spec.name]=value
    else data[spec.name]=value
  }
  return {...payload,data}
}

function WorkflowCaseCard({ item, onOpen }) {
  return <button type="button" onClick={()=>onOpen(item)} className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-primary-300 hover:shadow-md"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><strong className="block truncate text-sm text-slate-900">{item.title}</strong><span className="mt-1 block text-xs text-slate-500">{item.reference} · {item.patient_name||item.assigned_to_name||'Role-scoped workflow'}</span></div><Badge color={tone(item.status)}>{labelize(item.status)}</Badge></div>{item.summary?<p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-500">{item.summary}</p>:null}<div className="mt-3 flex items-center justify-between text-xs"><span className="font-semibold capitalize text-slate-500">{item.priority}</span><span className="text-slate-400">{new Date(item.updated_at).toLocaleString()}</span></div></button>
}

export default function WorkflowCasePanel({ slug, onRows, onDefinition, compact=false }) {
  const [definition,setDefinition]=useState(null)
  const [cases,setCases]=useState([])
  const [counts,setCounts]=useState({})
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [success,setSuccess]=useState('')
  const [createOpen,setCreateOpen]=useState(false)
  const [form,setForm]=useState({priority:'routine'})
  const [formErrors,setFormErrors]=useState({})
  const [selected,setSelected]=useState(null)
  const [actionConfig,setActionConfig]=useState(null)
  const [actionForm,setActionForm]=useState({note:''})
  const [comment,setComment]=useState('')
  const [saving,setSaving]=useState(false)
  const [offlineDraft,setOfflineDraft]=useState(null)
  const draftKey=`mydoctor:workflow-draft:${slug}`
  const visibleFields=useMemo(()=>{
    const all=definition?.fields||[]
    const catalog=definition?.record_type_fields||{}
    const types=Object.keys(catalog)
    if(!types.length)return all
    const selectedType=form.record_type||types[0]
    const relations=all.filter((spec)=>!spec.schema_field)
    return [...relations,...(catalog[selectedType]||[])]
  },[definition,form.record_type])

  const reload=async()=>{
    setLoading(true);setError('')
    try{
      const {data}=await journeyApi.cases(slug)
      setDefinition(data.definition);onDefinition?.(data.definition);setCases(data.results||[]);setCounts(data.counts||{})
      onRows?.(data.results||[])
      if(selected){const updated=(data.results||[]).find((item)=>item.public_id===selected.public_id);if(updated)setSelected(updated)}
    }catch(err){setError(normalizeError(err))}
    finally{setLoading(false)}
  }
  useEffect(()=>{reload()},[slug])
  useEffect(()=>{
    try{const raw=localStorage.getItem(draftKey);setOfflineDraft(raw?JSON.parse(raw):null)}catch{setOfflineDraft(null)}
  },[draftKey])

  const create=async(event)=>{
    event.preventDefault();setSaving(true);setError('');setFormErrors({})
    try{
      const payload=cleanPayload({...definition,fields:visibleFields},form)
      const {data}=await journeyApi.createCase(slug,payload)
      setCreateOpen(false);setForm({priority:'routine'});setSuccess(`${data.reference} was created.`);await reload();setSelected(data)
    }catch(err){
      const body=err?.response?.data
      if(body&&typeof body==='object'&&!body.detail)setFormErrors(body)
      const networkFailure=!err?.response
      if(networkFailure){
        try{const payload=cleanPayload({...definition,fields:visibleFields},form);const draft={form,payload,saved_at:new Date().toISOString()};localStorage.setItem(draftKey,JSON.stringify(draft));setOfflineDraft(draft);setError('The network is unavailable. This workflow was saved locally and has not been submitted. Retry it after connectivity returns.')}catch(payloadError){setError(normalizeError(payloadError))}
      }else setError(normalizeError(err))
    }finally{setSaving(false)}
  }
  const retryOfflineDraft=async()=>{
    if(!offlineDraft)return
    setSaving(true);setError('')
    try{const {data}=await journeyApi.createCase(slug,offlineDraft.payload);localStorage.removeItem(draftKey);setOfflineDraft(null);setSuccess(`${data.reference} was submitted from the saved offline draft.`);await reload();setSelected(data)}catch(err){setError(normalizeError(err))}finally{setSaving(false)}
  }
  const discardOfflineDraft=()=>{localStorage.removeItem(draftKey);setOfflineDraft(null)}
  const act=async(event)=>{
    event.preventDefault();if(!selected||!actionConfig)return
    setSaving(true);setError('')
    try{
      const payload={action:actionConfig.code,...actionForm}
      const {data}=await journeyApi.act(selected.public_id,payload)
      setSelected(data);setActionConfig(null);setActionForm({note:''});setSuccess(`${actionConfig.label} completed.`);await reload()
    }catch(err){setError(normalizeError(err))}finally{setSaving(false)}
  }
  const addComment=async(event)=>{
    event.preventDefault();if(!comment.trim()||!selected)return
    setSaving(true)
    try{await journeyApi.addComment(selected.public_id,{body:comment});setComment('');const {data}=await journeyApi.case(selected.public_id);setSelected(data);await reload()}catch(err){setError(normalizeError(err))}finally{setSaving(false)}
  }
  const openAction=(code,config)=>{setActionConfig({code,...config});setActionForm({note:''})}
  const actionFields=actionConfig?.fields||[]
  const openCount=Object.entries(counts).filter(([status])=>!['completed','closed','cancelled','rejected','revoked'].includes(status)).reduce((sum,[,count])=>sum+Number(count),0)

  if(loading&&!definition)return <Spinner label="Loading transactional workflow…"/>
  return <div className="space-y-4">
    {error?<Alert tone="danger" title="Workflow action failed">{error}</Alert>:null}
    {offlineDraft?<Alert tone="warning" title="Offline draft waiting to be submitted"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><span>Saved {offlineDraft.saved_at?new Date(offlineDraft.saved_at).toLocaleString():'locally'}. It is not part of the clinical record until submission succeeds.</span><div className="flex gap-2"><Button onClick={retryOfflineDraft} disabled={saving}>Retry submission</Button><Button variant="outline" onClick={discardOfflineDraft}>Discard</Button></div></div></Alert>:null}
    {success?<Alert tone="success" title="Workflow updated">{success}</Alert>:null}
    <div className="flex flex-col gap-3 rounded-2xl border border-primary-200 bg-primary-50/50 p-4 sm:flex-row sm:items-center sm:justify-between"><div><div className="text-xs font-bold uppercase tracking-[.14em] text-primary-600">Transactional workflow</div><h3 className="mt-1 font-bold text-slate-900">{definition?.label||labelize(slug)}</h3><p className="mt-1 text-xs text-slate-500">Every action is persisted, role-checked and added to the audit timeline.</p></div><div className="flex items-center gap-2"><Badge color="blue">{openCount} open</Badge>{definition?.create_allowed!==false?<Button onClick={()=>setCreateOpen(true)}><HealthIcon name="plus" size={16}/> New workflow</Button>:<Badge color="slate">Read only</Badge>}</div></div>
    {!cases.length?<EmptyState icon="clipboard" title="No workflow cases" description={definition?.create_allowed===false?"This page is driven by canonical operational records and supported actions.":"Create the first case to begin this role-specific process."} action={definition?.create_allowed===false?null:<Button onClick={()=>setCreateOpen(true)}>Create case</Button>}/>:<div className={`grid gap-3 ${compact?'md:grid-cols-2':'md:grid-cols-2 xl:grid-cols-3'}`}>{cases.map((item)=><WorkflowCaseCard key={item.public_id} item={item} onOpen={setSelected}/>)}</div>}

    <Modal open={createOpen} onClose={()=>setCreateOpen(false)} title={`Create ${definition?.label||'workflow case'}`} wide><form onSubmit={create} className="grid gap-4 sm:grid-cols-2">{visibleFields.map((spec)=><div key={spec.name} className={spec.type==='textarea'||spec.type==='json'?'sm:col-span-2':''}><DefinitionField spec={spec} value={form[spec.name]} onChange={(value)=>setForm((old)=>({...old,[spec.name]:value}))} error={formErrors[spec.name]}/></div>)}<div className="flex justify-end gap-2 sm:col-span-2"><Button type="button" variant="outline" onClick={()=>setCreateOpen(false)}>Cancel</Button><Button type="submit" disabled={saving}>{saving?'Saving…':'Create workflow'}</Button></div></form></Modal>

    <Modal open={Boolean(selected)} onClose={()=>setSelected(null)} title={selected?.title||'Workflow details'} wide>{selected?<div className="space-y-5"><div className="grid gap-3 sm:grid-cols-4"><div className="rounded-xl bg-primary-50 p-3"><small className="text-primary-600">Status</small><strong className="mt-1 block">{labelize(selected.status)}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Reference</small><strong className="mt-1 block">{selected.reference}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Patient</small><strong className="mt-1 block truncate">{selected.patient_name||'Not linked'}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Assigned to</small><strong className="mt-1 block truncate">{selected.assigned_to_name||'Unassigned'}</strong></div></div>
      <section className="rounded-xl border border-slate-200 p-4"><h4 className="font-bold text-slate-900">Case information</h4><dl className="mt-3 grid gap-3 sm:grid-cols-2">{Object.entries({...selected.data,...selected.result}).filter(([,value])=>value!==null&&value!==''&&typeof value!=='object').map(([key,value])=><div key={key}><dt className="text-xs font-bold text-slate-400">{labelize(key)}</dt><dd className="mt-1 text-sm text-slate-700">{String(value)}</dd></div>)}</dl>{selected.summary?<p className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">{selected.summary}</p>:null}</section>
      {Object.keys(selected.available_actions||{}).length?<section><h4 className="font-bold text-slate-900">Available actions</h4><div className="mt-3 flex flex-wrap gap-2">{Object.entries(selected.available_actions).map(([code,config])=><Button key={code} variant={config.tone==='danger'?'danger':config.tone==='outline'?'outline':'primary'} onClick={()=>openAction(code,config)}>{config.label}</Button>)}</div></section>:<Alert tone="info">No further actions are available for your active role at this status.</Alert>}
      <section className="grid gap-4 lg:grid-cols-2"><div><h4 className="font-bold text-slate-900">Audit timeline</h4><div className="mt-3 max-h-72 space-y-2 overflow-auto">{(selected.events||[]).map((event)=><div key={event.id} className="rounded-xl border border-slate-200 p-3"><div className="flex justify-between gap-2"><strong className="text-sm">{labelize(event.action)}</strong><small className="text-slate-400">{new Date(event.created_at).toLocaleString()}</small></div><p className="mt-1 text-xs text-slate-500">{event.actor_name||event.actor_role||'System'} · {labelize(event.from_status)} → {labelize(event.to_status)}</p>{event.note?<p className="mt-2 text-sm text-slate-600">{event.note}</p>:null}</div>)}</div></div><div><h4 className="font-bold text-slate-900">Collaboration</h4><div className="mt-3 max-h-56 space-y-2 overflow-auto">{(selected.comments||[]).map((item)=><div key={item.id} className="rounded-xl bg-slate-50 p-3"><div className="flex justify-between"><strong className="text-xs">{item.author_name||'Team member'}</strong><small className="text-slate-400">{new Date(item.created_at).toLocaleString()}</small></div><p className="mt-1 text-sm text-slate-600">{item.body}</p></div>)}</div><form onSubmit={addComment} className="mt-3 flex gap-2"><Input className="flex-1" value={comment} onChange={(event)=>setComment(event.target.value)} placeholder="Add a secure update…"/><Button type="submit" disabled={saving||!comment.trim()}><HealthIcon name="send" size={15}/></Button></form></div></section>
    </div>:null}</Modal>

    <Modal open={Boolean(actionConfig)} onClose={()=>setActionConfig(null)} title={actionConfig?.label||'Workflow action'}><form onSubmit={act} className="space-y-4"><Textarea label={actionConfig?.note_required?'Reason or clinical note *':'Reason or clinical note'} value={actionForm.note||''} onChange={(event)=>setActionForm((old)=>({...old,note:event.target.value}))}/>{actionFields.map((spec)=><DefinitionField key={spec.name} spec={spec} value={actionForm[spec.name]} onChange={(value)=>setActionForm((old)=>({...old,[spec.name]:value}))}/>) }<div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setActionConfig(null)}>Cancel</Button><Button type="submit" variant={actionConfig?.tone==='danger'?'danger':'primary'} disabled={saving}>{saving?'Working…':actionConfig?.label}</Button></div></form></Modal>
  </div>
}
