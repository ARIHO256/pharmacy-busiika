import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import HealthIcon from '../../components/icons/HealthIcon'
import { Alert, Badge, Card, Spinner, Stat } from '../../components/ui'

const rowsFrom = (value) => {
  const data = value?.data ?? value ?? []
  if (Array.isArray(data)) return data
  return data.results || data.items || data.orders || data.records || []
}
const statusOf = (row) => String(row.status || row.state || 'open').toLowerCase()
const titleOf = (row) => row.title || row.name || row.patient_name || row.reference || row.order_number || row.admission_number || `Record #${row.id}`
const urgent = (row) => ['critical','urgent','stat','failed','overdue','rejected'].includes(String(row.priority || row.severity || statusOf(row)).toLowerCase())
const done = (row) => ['completed','closed','released','verified','dispensed','paid','resolved'].includes(statusOf(row))

export default function RoleOperationsDashboard({ config }) {
  const [datasets, setDatasets] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setDatasets(null); setError('')
    Promise.all(config.sources.map(async (source) => {
      try { return { ...source, rows: rowsFrom(await source.load()) } }
      catch (err) { return { ...source, rows: [], error: err?.response?.data?.detail || err.message } }
    })).then((results) => { if (active) setDatasets(results) }).catch(() => { if (active) setError('Unable to load this operational dashboard.') })
    return () => { active = false }
  }, [config])

  const allRows = useMemo(() => (datasets || []).flatMap((dataset) => dataset.rows.map((row) => ({ ...row, _dataset: dataset.label, _icon: dataset.icon }))), [datasets])
  const metrics = useMemo(() => config.metrics.map((metric) => ({ ...metric, value: metric.calculate(datasets || [], allRows) })), [config.metrics, datasets, allRows])
  if (!datasets && !error) return <Spinner label={`Loading ${config.title.toLowerCase()}…`} />

  return <div className="space-y-6">
    <section className={`relative overflow-hidden rounded-[30px] bg-gradient-to-br ${config.gradient || 'from-slate-950 via-primary-950 to-primary-700'} p-6 text-white shadow-[0_24px_70px_rgba(11,44,82,.24)] sm:p-8`}>
      <div className="absolute -right-16 -top-20 h-72 w-72 rounded-full bg-white/10 blur-3xl"/>
      <div className="relative grid gap-7 xl:grid-cols-[1.25fr_.75fr] xl:items-end">
        <div><span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[.14em]"><HealthIcon name={config.icon} size={15}/> {config.eyebrow}</span><h2 className="mt-4 max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl">{config.title}</h2><p className="mt-3 max-w-3xl text-sm leading-7 text-white/75">{config.description}</p><div className="mt-5 flex flex-wrap gap-2">{config.actions.slice(0,3).map((action,index)=><Link key={action.to} to={action.to} className={`inline-flex min-h-10 items-center gap-2 rounded-xl px-4 text-sm font-bold ${index===0?'bg-white text-slate-900':'border border-white/15 bg-white/10 text-white'}`}><HealthIcon name={action.icon} size={16}/>{action.label}</Link>)}</div></div>
        <div className="rounded-2xl border border-white/15 bg-white/10 p-5 backdrop-blur"><small className="uppercase tracking-[.14em] text-white/60">Safety control list</small><div className="mt-3 space-y-2">{config.checklist.map((item,index)=><div key={item} className="flex items-center gap-3 rounded-xl bg-white/10 px-3 py-2.5 text-sm"><span className="grid h-6 w-6 place-items-center rounded-full bg-white/15 text-xs font-bold">{index+1}</span>{item}</div>)}</div></div>
      </div>
    </section>
    {error && <Alert tone="danger" title="Dashboard unavailable">{error}</Alert>}
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metrics.map((metric,index)=><Stat key={metric.label} label={metric.label} value={metric.value} icon={metric.icon} tone={['text-primary-700','text-emerald-700','text-amber-600','text-rose-600'][index%4]} caption={metric.caption}/>)}</section>
    <div className="grid gap-5 xl:grid-cols-[1.15fr_.85fr]">
      <Card title={config.queueTitle} subtitle={config.queueSubtitle} icon="activity">
        <div className="space-y-2">{allRows.filter((row)=>!done(row)).sort((a,b)=>Number(urgent(b))-Number(urgent(a))).slice(0,10).map((row)=><article key={`${row._dataset}-${row.id}`} className="grid gap-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3 sm:grid-cols-[auto_1fr_auto] sm:items-center"><span className={`grid h-10 w-10 place-items-center rounded-xl ${urgent(row)?'bg-rose-100 text-rose-700':'bg-primary-100 text-primary-700'}`}><HealthIcon name={row._icon || 'clipboard'} size={18}/></span><div className="min-w-0"><strong className="block truncate text-sm text-slate-800">{titleOf(row)}</strong><small className="block truncate text-slate-500">{row._dataset} · {row.summary || row.reason || row.patient_name || 'Role-scoped work item'}</small></div><Badge color={urgent(row)?'red':'blue'}>{statusOf(row).replaceAll('_',' ')}</Badge></article>)}{!allRows.filter((row)=>!done(row)).length&&<div className="py-10 text-center text-sm text-slate-400">No active items in the current scope.</div>}</div>
      </Card>
      <Card title="Operational workload" subtitle="Current records by responsibility" icon="chart">
        <div className="space-y-3">{(datasets||[]).map((dataset)=>{const open=dataset.rows.filter((row)=>!done(row)).length;const critical=dataset.rows.filter(urgent).length;return <div key={dataset.key} className="rounded-2xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-primary-700"><HealthIcon name={dataset.icon} size={18}/></span><div><strong className="block text-sm">{dataset.label}</strong><small className="text-slate-500">{dataset.rows.length} total records</small></div></div>{critical?<Badge color="red">{critical} urgent</Badge>:<Badge color="green">Stable</Badge>}</div><div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-primary-500" style={{width:`${dataset.rows.length?Math.max(8,open/dataset.rows.length*100):0}%`}}/></div></div>})}</div>
      </Card>
    </div>
    <section><div className="mb-3"><h3 className="text-xl font-bold text-slate-900">Professional workspaces</h3><p className="mt-1 text-sm text-slate-500">Purpose-built pages for daily work, safety controls and reporting.</p></div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{config.actions.map((action)=><Link key={action.to} to={action.to} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_30px_rgba(9,31,58,.05)] transition hover:-translate-y-1 hover:border-primary-300"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-50 text-primary-700 group-hover:bg-primary-600 group-hover:text-white"><HealthIcon name={action.icon} size={20}/></span><strong className="mt-4 block text-sm text-slate-900">{action.label}</strong><p className="mt-1 text-xs leading-5 text-slate-500">{action.description}</p><span className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-primary-700">Open <HealthIcon name="arrow" size={14}/></span></Link>)}</div></section>
  </div>
}
