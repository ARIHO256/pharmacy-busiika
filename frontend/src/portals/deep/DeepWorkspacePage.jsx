import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { accessApi, appointmentApi, billingApi, chatApi, enterpriseApi, journeyApi, operationsApi, prescriptionApi, servicesApi, workforceApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, Spinner, Stat, Textarea } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'
import ClinicalVisualization from '../enterprise/components/ClinicalVisualizations'
import SpecializedBoard, { specializedVariants } from './SpecializedBoards'
import WorkflowCasePanel from '../journeys/WorkflowCasePanel'

const rowsFrom = (data) => Array.isArray(data) ? data : data?.results || data?.items || []
const titleOf = (row) => row.title || row.name || row.reference || row.invoice_number || row.admission_number || row.visit_number || row.patient_name || row.patient?.name || row.patient?.display_name || `Record #${row.id || row.public_id}`
const statusOf = (row) => row.status || row.state || row.active && 'active' || 'open'
const tone = (status) => ['completed','paid','approved','released','active','verified','healthy','acknowledged'].includes(String(status).toLowerCase()) ? 'green' : ['failed','rejected','cancelled','critical','overdue','suspended'].includes(String(status).toLowerCase()) ? 'red' : ['pending','draft','queued','processing','under_review','submitted'].includes(String(status).toLowerCase()) ? 'yellow' : 'blue'
const errorText = (error, fallback) => error?.response?.data?.detail || error?.message || fallback

const operationalRows = (data) => {
  if (!data || data.configured === false) return []
  const preferred = ['records','appointments','availability','consultations','prescriptions','laboratory','imaging','admissions','referrals','claims','preauthorizations','coverages','invoices','payments','receipts','consents','relationships','notifications','laboratory_results','imaging_results','tasks','renewals','conferences','documents','shifts','entries','accounts']
  const output = []
  preferred.forEach((key) => {
    const value = data[key]
    if (Array.isArray(value)) output.push(...value.map((row) => ({ ...row, _dataset: key })))
  })
  return output
}

async function loadSource(page) {
  try {
    const { data } = await journeyApi.data(page.slug)
    if (data?.configured) return operationalRows(data)
  } catch (error) {
    if (![403,404].includes(error?.response?.status)) throw error
  }
  if (page.source === 'appointments') return rowsFrom((await appointmentApi.list()).data)
  if (page.source === 'conversations') return rowsFrom((await chatApi.conversations()).data)
  if (page.source === 'prescriptions') return rowsFrom((await prescriptionApi.list()).data)
  if (page.source === 'invoices') return rowsFrom((await billingApi.invoices()).data)
  if (page.source === 'visits') return rowsFrom((await workforceApi.visits()).data)
  if (page.source === 'admissions') return rowsFrom((await operationsApi.admissions()).data)
  if (page.source === 'claims') {
    try { return rowsFrom((await servicesApi.claimsManage()).data) } catch { return rowsFrom((await servicesApi.myClaims()).data) }
  }
  if (page.source === 'enterprise' && page.recordTypes?.length) {
    const chunks = await Promise.all(page.recordTypes.map((record_type) => enterpriseApi.records({ record_type })))
    return chunks.flatMap(({ data }) => rowsFrom(data))
  }
  return []
}

function QueueBoard({ rows, onSelect }) {
  const lanes = ['new','pending','in_progress','completed']
  return <div className="grid gap-4 xl:grid-cols-4">{lanes.map((lane) => { const laneRows = rows.filter((row) => { const value=String(statusOf(row)).toLowerCase(); return lane==='new' ? ['new','draft','registered','scheduled','submitted'].includes(value) : lane==='pending' ? value.includes('pending')||value.includes('waiting')||value==='queued'||value==='awaiting_information' : lane==='in_progress' ? ['active','in_progress','processing','under_review','admitted','assigned'].includes(value) : ['completed','closed','resolved','released','paid','approved','acknowledged'].includes(value) }).slice(0,8); return <section key={lane} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-3"><div className="mb-3 flex items-center justify-between"><strong className="capitalize text-slate-700">{lane.replaceAll('_',' ')}</strong><Badge color="slate">{laneRows.length}</Badge></div><div className="space-y-2">{laneRows.map((row)=><button type="button" onClick={()=>onSelect?.(row)} key={row.id||row.public_id} className="w-full rounded-xl border border-slate-200 bg-white p-3 text-left shadow-sm hover:border-primary-300"><strong className="block truncate text-sm text-slate-800">{titleOf(row)}</strong><small className="mt-1 block truncate text-slate-500">{row.patient_name || row.summary || row.reason || 'Role-scoped work item'}</small><div className="mt-2"><Badge color={tone(statusOf(row))}>{String(statusOf(row)).replaceAll('_',' ')}</Badge></div></button>)}{!laneRows.length&&<div className="py-5 text-center text-xs text-slate-400">No items</div>}</div></section>})}</div>
}

function CalendarBoard({ rows, onSelect }) {
  const days = Array.from({length:7},(_,i)=>{const date=new Date();date.setDate(date.getDate()+i);return date})
  return <div className="grid gap-3 lg:grid-cols-7">{days.map((day,index)=><section key={day.toISOString()} className={`min-h-44 rounded-2xl border p-3 ${index===0?'border-primary-300 bg-primary-50':'border-slate-200 bg-white'}`}><small className="font-bold uppercase text-slate-400">{day.toLocaleDateString([],{weekday:'short'})}</small><strong className="mt-1 block text-2xl text-slate-800">{day.getDate()}</strong><div className="mt-3 space-y-2">{rows.filter((row)=>String(row.date||row.scheduled_for||row.due_at||'').slice(0,10)===day.toISOString().slice(0,10)).slice(0,5).map((row)=><button type="button" onClick={()=>onSelect?.(row)} key={row.id||row.public_id} className="w-full rounded-lg bg-white p-2 text-left text-xs shadow-sm hover:ring-1 hover:ring-primary-300"><strong className="block truncate">{titleOf(row)}</strong><span className="text-slate-500">{row.start_time||statusOf(row)}</span></button>)}</div></section>)}</div>
}

function FinanceBoard({ rows, onSelect }) {
  const amount=(row)=>Number(row.total||row.total_amount||row.amount||row.balance||row.data?.amount||0)
  const total=rows.reduce((sum,row)=>sum+amount(row),0)
  const paid=rows.filter((row)=>['paid','completed','settled','posted'].includes(String(statusOf(row)).toLowerCase())).reduce((sum,row)=>sum+amount(row),0)
  return <div className="grid gap-4 xl:grid-cols-[.8fr_1.2fr]"><section className="rounded-2xl bg-slate-950 p-6 text-white"><small className="uppercase tracking-[.16em] text-primary-200">Financial position</small><strong className="mt-3 block text-4xl">{total.toLocaleString()}</strong><p className="mt-1 text-sm text-slate-300">Calculated from the current authorized records</p><div className="mt-5 h-3 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-emerald-400" style={{width:`${total?Math.min(100,(paid/total)*100):0}%`}}/></div><div className="mt-2 flex justify-between text-xs"><span>Posted {paid.toLocaleString()}</span><span>Outstanding {(total-paid).toLocaleString()}</span></div></section><section className="rounded-2xl border border-slate-200 bg-white p-4"><h3 className="font-bold text-slate-800">Recent financial activity</h3><div className="mt-3 divide-y divide-slate-100">{rows.slice(0,10).map((row)=><button type="button" onClick={()=>onSelect?.(row)} key={row.id||row.public_id} className="flex w-full items-center justify-between gap-4 py-3 text-left hover:bg-slate-50"><div><strong className="block text-sm text-slate-800">{titleOf(row)}</strong><small className="text-slate-500">{row.created_at?new Date(row.created_at).toLocaleString():statusOf(row)}</small></div><div className="text-right"><strong className="block">{amount(row).toLocaleString()}</strong><Badge color={tone(statusOf(row))}>{statusOf(row)}</Badge></div></button>)}</div></section></div>
}

function ConversationBoard({ rows }) {
  const [selected,setSelected]=useState(rows[0]||null)
  const [messages,setMessages]=useState([])
  const [body,setBody]=useState('')
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')
  useEffect(()=>{if(!selected?.id){setMessages([]);return}setLoading(true);chatApi.messages(selected.id).then(({data})=>setMessages(rowsFrom(data))).catch((err)=>setError(errorText(err,'Unable to load messages.'))).finally(()=>setLoading(false))},[selected?.id])
  const send=async(event)=>{event.preventDefault();if(!selected?.id||!body.trim())return;setLoading(true);setError('');try{const form=new FormData();form.append('body',body.trim());await chatApi.send(selected.id,form);setBody('');const {data}=await chatApi.messages(selected.id);setMessages(rowsFrom(data))}catch(err){setError(errorText(err,'Unable to send message.'))}finally{setLoading(false)}}
  return <div className="space-y-3">{error?<Alert tone="danger">{error}</Alert>:null}<div className="grid min-h-[430px] gap-4 lg:grid-cols-[.75fr_1.25fr]"><section className="rounded-2xl border border-slate-200 bg-white p-3"><div className="mt-1 space-y-2">{rows.slice(0,15).map((row)=><button type="button" onClick={()=>setSelected(row)} key={row.id} className={`w-full rounded-xl p-3 text-left ${selected?.id===row.id?'bg-primary-50 ring-1 ring-primary-200':'hover:bg-slate-50'}`}><strong className="block truncate text-sm">{titleOf(row)}</strong><small className="text-slate-500">{row.last_message||row.summary||'Secure clinical conversation'}</small></button>)}{!rows.length?<EmptyState icon="message" title="No conversations" description="A conversation appears after a patient and care professional open a secure thread."/>:null}</div></section><section className="flex flex-col rounded-2xl border border-slate-200 bg-white"><div className="border-b border-slate-100 p-4"><strong>{selected?titleOf(selected):'Select a conversation'}</strong><p className="text-xs text-slate-500">Secure clinical messaging · access logged</p></div><div className="flex-1 space-y-3 overflow-auto bg-slate-50/60 p-4">{loading&&!messages.length?<Spinner label="Loading messages…"/>:messages.map((message)=><div key={message.id} className={`max-w-[80%] rounded-2xl p-3 text-sm shadow-sm ${message.is_mine||message.sender_is_me?'ml-auto rounded-tr-sm bg-primary-600 text-white':'rounded-tl-sm bg-white text-slate-700'}`}><p>{message.body||message.text}</p><small className="mt-1 block opacity-70">{message.created_at?new Date(message.created_at).toLocaleString():''}</small></div>)}{selected&&!loading&&!messages.length?<p className="text-center text-sm text-slate-400">No messages yet.</p>:null}</div><form onSubmit={send} className="flex gap-2 border-t border-slate-100 p-3"><Input className="flex-1" value={body} onChange={(event)=>setBody(event.target.value)} placeholder="Write a secure message…"/><Button type="submit" disabled={!selected||loading||!body.trim()}><HealthIcon name="send" size={16}/></Button></form></section></div></div>
}

function ImagingBoard({ rows, onSelect }) {
  const [selected,setSelected]=useState(rows[0]||null)
  const [error,setError]=useState('')
  const [opening,setOpening]=useState(false)
  const openViewer=async()=>{if(!selected?.id)return;setOpening(true);setError('');try{const {data}=await enterpriseApi.imagingViewer(selected.id);const url=data.viewer_url||data.url;if(!url)throw new Error('The PACS node did not return a viewer URL.');window.open(url,'_blank','noopener,noreferrer')}catch(err){setError(errorText(err,'Unable to open the diagnostic viewer.'))}finally{setOpening(false)}}
  return <div className="space-y-3">{error?<Alert tone="danger">{error}</Alert>:null}<div className="grid gap-4 xl:grid-cols-[1.25fr_.75fr]"><section className="relative min-h-[420px] overflow-hidden rounded-2xl bg-slate-950 p-5 text-white"><div className="absolute inset-0 opacity-20" style={{backgroundImage:'radial-gradient(circle at center, #94a3b8 0 1px, transparent 1px)',backgroundSize:'22px 22px'}}/><div className="relative flex h-full min-h-[380px] flex-col items-center justify-center"><span className="grid h-20 w-20 place-items-center rounded-full border border-white/20 bg-white/10"><HealthIcon name="activity" size={34}/></span><h3 className="mt-4 text-xl font-bold">Authorized diagnostic viewer</h3><p className="mt-2 max-w-lg text-center text-sm text-slate-300">{selected?titleOf(selected):'Select a study from the worklist.'}</p><Button className="mt-5 bg-white !text-slate-900" onClick={openViewer} disabled={!selected||opening}>{opening?'Opening viewer…':'Open selected study'}</Button></div></section><section className="rounded-2xl border border-slate-200 bg-white p-4"><h3 className="font-bold text-slate-800">Imaging worklist</h3><div className="mt-3 space-y-2">{rows.slice(0,12).map((row)=><button type="button" onClick={()=>{setSelected(row);onSelect?.(row)}} key={row.id} className={`w-full rounded-xl border p-3 text-left ${selected?.id===row.id?'border-primary-300 bg-primary-50':'border-slate-100 hover:border-primary-200'}`}><strong className="block text-sm">{titleOf(row)}</strong><small className="text-slate-500">{row.patient_name||row.summary||'Imaging study'}</small><div className="mt-2"><Badge color={tone(statusOf(row))}>{statusOf(row)}</Badge></div></button>)}{!rows.length?<EmptyState icon="activity" title="No imaging studies" description="Authorized imaging studies appear here after acquisition and PACS registration."/>:null}</div></section></div></div>
}

function NotificationBoard({ rows, onRefresh }) {
  const [working,setWorking]=useState(null)
  const [error,setError]=useState('')
  const markRead=async(id)=>{setWorking(id);setError('');try{await chatApi.markRead(id);await onRefresh?.()}catch(err){setError(errorText(err,'Unable to update the notification.'))}finally{setWorking(null)}}
  const markAll=async()=>{setWorking('all');setError('');try{await chatApi.markAllRead();await onRefresh?.()}catch(err){setError(errorText(err,'Unable to mark notifications as read.'))}finally{setWorking(null)}}
  return <div className="space-y-3">{error?<Alert tone="danger">{error}</Alert>:null}<div className="flex justify-end"><Button variant="outline" onClick={markAll} disabled={working==='all'}>{working==='all'?'Updating…':'Mark all as read'}</Button></div><div className="space-y-2">{rows.map((row)=><article key={row.id} className={`rounded-2xl border p-4 ${row.is_read||row.read_at?'border-slate-200 bg-white':'border-primary-200 bg-primary-50'}`}><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div><strong className="text-sm text-slate-900">{row.title||row.subject||'Notification'}</strong><p className="mt-1 text-sm text-slate-600">{row.message||row.body||row.summary}</p><small className="mt-2 block text-slate-400">{row.created_at?new Date(row.created_at).toLocaleString():''}</small></div>{!(row.is_read||row.read_at)?<Button onClick={()=>markRead(row.id)} disabled={working===row.id}>Mark read</Button>:<Badge color="green">Read</Badge>}</div></article>)}{!rows.length?<EmptyState icon="bell" title="No notifications" description="Clinical, payment and operational notifications will appear here."/>:null}</div></div>
}

function StructuredValue({ value, depth=0 }) {
  if(value===null||value===undefined||value==='')return <span className="text-slate-400">Not recorded</span>
  if(typeof value==='boolean')return <Badge color={value?'green':'slate'}>{value?'Yes':'No'}</Badge>
  if(typeof value!=='object')return <span className="break-words text-sm text-slate-700">{String(value)}</span>
  if(Array.isArray(value))return <div className="space-y-2">{value.map((item,index)=><div key={index} className="rounded-lg border border-slate-100 bg-slate-50 p-2"><StructuredValue value={item} depth={depth+1}/></div>)}</div>
  return <dl className={`grid gap-3 ${depth<1?'sm:grid-cols-2':''}`}>{Object.entries(value).map(([key,item])=><div key={key} className="rounded-xl border border-slate-100 bg-white p-3"><dt className="text-xs font-bold capitalize text-slate-400">{key.replaceAll('_',' ')}</dt><dd className="mt-1"><StructuredValue value={item} depth={depth+1}/></dd></div>)}</dl>
}

async function downloadResponse(request, filename) {
  const {data}=await request
  const url=URL.createObjectURL(data)
  const link=document.createElement('a');link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url)
}

function OperationsBoard({ rows, variant, onSelect, page, auxiliary, onRefresh }) {
  if(page.slug==='notification-inbox')return <NotificationBoard rows={rows} onRefresh={onRefresh}/>
  if(page.source==='conversations')return <ConversationBoard rows={rows}/>
  if(variant==='imaging')return <ImagingBoard rows={rows} onSelect={onSelect}/>
  if(specializedVariants.has(variant))return <SpecializedBoard variant={variant} rows={rows} onSelect={onSelect} page={page} auxiliary={auxiliary}/>
  if(variant==='calendar')return <CalendarBoard rows={rows} onSelect={onSelect}/>
  if(variant==='finance'||variant==='analytics')return <FinanceBoard rows={rows} onSelect={onSelect}/>
  return <QueueBoard rows={rows} onSelect={onSelect}/>
}

export default function DeepWorkspacePage({ page, basePath }) {
  const [sourceRows,setSourceRows]=useState([])
  const [workflowRows,setWorkflowRows]=useState([])
  const [loading,setLoading]=useState(true)
  const [sourceError,setSourceError]=useState('')
  const [query,setQuery]=useState('')
  const [selected,setSelected]=useState(null)
  const [auxiliary,setAuxiliary]=useState({})
  const [refreshTick,setRefreshTick]=useState(0)
  const [detailWorking,setDetailWorking]=useState(false)
  const [detailError,setDetailError]=useState('')
  const [pageDefinition,setPageDefinition]=useState(null)

  useEffect(()=>{
    let live=true;setLoading(true);setSourceError('');setSourceRows([]);setAuxiliary({});setPageDefinition(null)
    const sourcePromise=loadSource(page)
    const auxiliaryPromise=(async()=>{
      if(['role-matrix','permission-comparison'].includes(page.slug)){
        const [roles,permissions]=await Promise.all([accessApi.roles(),accessApi.permissions()]);return {roles:rowsFrom(roles.data),permissions:rowsFrom(permissions.data)}
      }
      if(['worker-health','system-metrics','backup-restore','security-incident','event-delivery','dead-letter','event-replay'].includes(page.slug))return (await enterpriseApi.readiness()).data
      return {}
    })()
    const definitionPromise=journeyApi.definition(page.slug)
    Promise.allSettled([sourcePromise,auxiliaryPromise,definitionPromise]).then(([sourceResult,auxiliaryResult,definitionResult])=>{
      if(!live)return
      if(sourceResult.status==='fulfilled')setSourceRows(sourceResult.value);else setSourceError(errorText(sourceResult.reason,`Unable to load ${page.label.toLowerCase()} source data.`))
      if(auxiliaryResult.status==='fulfilled')setAuxiliary(auxiliaryResult.value)
      if(definitionResult.status==='fulfilled')setPageDefinition(definitionResult.value.data)
    }).finally(()=>{if(live)setLoading(false)})
    return()=>{live=false}
  },[page.slug,page.source,refreshTick])

  useEffect(()=>{
    if(!['virtual-waiting-room','notification-inbox','ambulance-telemetry','live-telemetry','emergency-command-dashboard'].includes(page.slug))return undefined
    const timer=setInterval(()=>setRefreshTick((value)=>value+1),20000)
    return()=>clearInterval(timer)
  },[page.slug])

  const filtered=useMemo(()=>sourceRows.filter((row)=>!query||JSON.stringify(row).toLowerCase().includes(query.toLowerCase())),[query,sourceRows])
  const allRows=workflowRows.length?workflowRows:filtered
  const urgent=workflowRows.filter((row)=>row.priority==='critical'||['overdue','failed','rejected','escalated'].includes(String(statusOf(row)).toLowerCase())).length
  const completed=workflowRows.filter((row)=>['completed','closed','resolved','released','paid','approved','acknowledged'].includes(String(statusOf(row)).toLowerCase())).length

  return <div className="space-y-6">
    <section className="relative overflow-hidden rounded-[28px] border border-slate-200 bg-gradient-to-br from-white via-primary-50/60 to-sky-50 p-6 shadow-sm"><div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-primary-200/40 blur-3xl"/><div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between"><div className="flex items-start gap-4"><span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-primary-700 text-white shadow-lg"><HealthIcon name={page.icon} size={26}/></span><div><div className="text-xs font-bold uppercase tracking-[.16em] text-primary-600">{page.group}</div><h2 className="mt-1 text-3xl font-bold tracking-tight text-slate-950">{page.label}</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{page.description}</p></div></div><div className="flex flex-wrap gap-2"><Link to={`/${basePath}`}><Button variant="outline">Back to dashboard</Button></Link><Button onClick={()=>window.print()}><HealthIcon name="file" size={16}/> Print view</Button></div></div></section>

    {sourceError?<Alert tone="warning" title="Supplementary data unavailable">{sourceError} The transactional workflow remains available.</Alert>:null}
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Workflow cases" value={workflowRows.length} icon={page.icon} caption="Persisted and audited"/><Stat label="Attention required" value={urgent} icon="alert" tone="text-rose-700" caption="Critical, failed, rejected or escalated"/><Stat label="Completed" value={completed} icon="check" tone="text-emerald-700" caption="Completed workflow outcomes"/><Stat label="Live source records" value={sourceRows.length} icon="activity" caption="Existing clinical or operational source data"/></section>

    {pageDefinition && (pageDefinition.create_allowed !== false || pageDefinition.page_mode === 'work_queue') ? <Card
      title={pageDefinition.page_mode === 'work_queue' ? `${page.label} work queue` : `${page.label} transactions`}
      subtitle={pageDefinition.page_mode === 'work_queue' ? 'Review, assign and complete the scoped work queue' : 'Create, assign, review, approve and complete the canonical workflow'}
      icon={page.icon}
    ><WorkflowCasePanel slug={page.slug} onRows={setWorkflowRows} onDefinition={setPageDefinition}/></Card> : null}

    {loading?<Spinner label={`Loading ${page.label.toLowerCase()} source data…`}/>:sourceRows.length||Object.keys(auxiliary||{}).length?<Card title={`${page.label} operational view`} subtitle="Live source records and role-specific visualization" icon={page.icon} actions={<Input value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Search source records" className="w-64"/>}>{page.recordTypes?.length?<ClinicalVisualization recordType={page.recordTypes[0]} records={filtered}/>:null}<div className={page.recordTypes?.length?'mt-5':''}><OperationsBoard rows={filtered} variant={page.variant} onSelect={setSelected} page={page} auxiliary={auxiliary} onRefresh={()=>setRefreshTick((value)=>value+1)}/></div></Card>:null}

    <Modal open={Boolean(selected)} onClose={()=>{setSelected(null);setDetailError('')}} title={selected?titleOf(selected):'Details'} wide>{selected?<div className="space-y-4">{detailError?<Alert tone="danger">{detailError}</Alert>:null}<div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-primary-50 p-3"><small className="text-primary-600">Status</small><strong className="mt-1 block capitalize">{String(statusOf(selected)).replaceAll('_',' ')}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Reference</small><strong className="mt-1 block">{selected.reference||selected.invoice_number||selected.receipt_number||`#${selected.id}`}</strong></div><div className="rounded-xl bg-slate-50 p-3"><small className="text-slate-500">Updated</small><strong className="mt-1 block">{selected.updated_at?new Date(selected.updated_at).toLocaleString():'Current'}</strong></div></div>{(page.slug.includes('invoice')||selected.invoice_number)?<div className="flex flex-wrap gap-2"><Button disabled={detailWorking} onClick={async()=>{setDetailWorking(true);setDetailError('');try{await downloadResponse(billingApi.invoicePdf(selected.id),`${selected.invoice_number||'invoice'}.pdf`)}catch(err){setDetailError(errorText(err,'Unable to download the invoice.'))}finally{setDetailWorking(false)}}}>Download invoice PDF</Button>{selected.receipt_id?<Button variant="outline" disabled={detailWorking} onClick={async()=>{setDetailWorking(true);setDetailError('');try{await downloadResponse(billingApi.receiptPdf(selected.receipt_id),`${selected.receipt_number||'receipt'}.pdf`)}catch(err){setDetailError(errorText(err,'Unable to download the receipt.'))}finally{setDetailWorking(false)}}}>Download receipt PDF</Button>:null}</div>:null}<div className="rounded-xl border border-slate-200 bg-white p-4"><h3 className="font-bold text-slate-900">Source record information</h3><dl className="mt-3 grid gap-3 sm:grid-cols-2">{Object.entries(selected).filter(([key,value])=>!['payload','audit','attachments','data','result'].includes(key)&&value!==null&&typeof value!=='object').slice(0,18).map(([key,value])=><div key={key}><dt className="text-xs font-bold capitalize text-slate-400">{key.replaceAll('_',' ')}</dt><dd className="mt-1 break-words text-sm text-slate-700">{String(value)}</dd></div>)}</dl></div>{selected.payload||selected.data||selected.result?<div className="rounded-xl border border-slate-200 bg-slate-50 p-4"><h3 className="font-bold text-slate-900">Structured clinical and operational information</h3><div className="mt-3 max-h-[32rem] overflow-auto"><StructuredValue value={selected.payload||selected.data||selected.result}/></div></div>:null}</div>:null}</Modal>
  </div>
}
