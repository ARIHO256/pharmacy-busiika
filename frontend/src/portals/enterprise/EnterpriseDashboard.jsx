import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { enterpriseApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, Spinner, Stat } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'
import { useAuth } from '../../auth/AuthContext'
import { dashboardConfig } from './roleDashboardConfig'

function tone(index) {
  return ['text-primary-700', 'text-emerald-700', 'text-violet-700', 'text-rose-700'][index % 4]
}

export default function EnterpriseDashboard({ portal }) {
  const { activeContext, activeRole } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const role = activeRole || activeContext?.role_code
  const config = dashboardConfig(role, portal)

  useEffect(() => {
    setData(null)
    enterpriseApi.roleDashboard().then(({ data: result }) => setData(result)).catch((err) => setError(err.response?.data?.detail || 'Unable to load the role dashboard.'))
  }, [role])

  const quickModules = useMemo(() => {
    const ordered = [...portal.modules]
    return ordered.sort((a, b) => {
      const ai = config.primary.indexOf(a.id)
      const bi = config.primary.indexOf(b.id)
      return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi)
    }).slice(0, 6)
  }, [config.primary, portal.modules])

  if (!data && !error) return <Spinner label={`Loading ${portal.title.toLowerCase()}…`} />

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[30px] border border-primary-200 bg-gradient-to-br from-slate-950 via-primary-950 to-primary-700 p-6 text-white shadow-[0_24px_70px_rgba(11,44,82,.24)] sm:p-8">
        <div className="absolute -right-20 -top-24 h-72 w-72 rounded-full bg-sky-400/20 blur-3xl" />
        <div className="absolute -bottom-24 left-1/3 h-64 w-64 rounded-full bg-violet-400/10 blur-3xl" />
        <div className="relative grid gap-7 xl:grid-cols-[1.35fr_.85fr] xl:items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-[.15em]"><HealthIcon name={portal.icon} size={15}/> {portal.eyebrow}</div>
            <h2 className="mt-4 max-w-3xl text-3xl font-bold tracking-tight sm:text-4xl">{config.banner}</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-primary-100 sm:text-base">{data?.headline || config.focus}</p>
            <div className="mt-5 flex flex-wrap gap-2 text-xs"><span className="rounded-full bg-white/10 px-3 py-1.5 capitalize">{role?.replaceAll('_', ' ')}</span>{activeContext?.organization_name && <span className="rounded-full bg-white/10 px-3 py-1.5">{activeContext.organization_name}</span>}{activeContext?.department_name && <span className="rounded-full bg-white/10 px-3 py-1.5">{activeContext.department_name}</span>}</div>
          </div>
          <div className="rounded-2xl border border-white/15 bg-white/10 p-5 backdrop-blur">
            <div className="flex items-center justify-between"><div><small className="text-primary-200">Today’s control list</small><strong className="mt-1 block text-lg">Start with the highest-risk work</strong></div><span className="grid h-11 w-11 place-items-center rounded-2xl bg-white/10"><HealthIcon name="clipboard" size={21}/></span></div>
            <div className="mt-4 space-y-2">{config.checklist.map((item, index) => <div key={item} className="flex items-center gap-3 rounded-xl bg-white/10 px-3 py-2.5 text-sm"><span className="grid h-6 w-6 place-items-center rounded-full bg-white/15 text-xs font-bold">{index + 1}</span><span>{item}</span></div>)}</div>
          </div>
        </div>
      </section>

      {error && <Alert tone="danger" title="Dashboard unavailable">{error}</Alert>}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {(data?.metrics || []).map((metric, index) => <Stat key={metric.label} label={metric.label} value={metric.value} icon={metric.icon} tone={tone(index)} caption={metric.critical ? `${metric.critical} critical item${metric.critical === 1 ? '' : 's'}` : 'Current role and organization scope'} />)}
      </section>

      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <Card title="Priority work queues" subtitle="Tailored to your role, organization and active department" icon="activity">
          <div className="space-y-3">{(data?.queues || []).map((queue) => {
            const module = portal.modules.find((item) => item.recordTypes?.includes(queue.record_type))
            return <Link key={queue.record_type} to={module?.id || portal.modules[0]?.id || '.'} className="grid gap-3 rounded-2xl border border-slate-200 p-4 transition hover:border-primary-300 hover:bg-primary-50/40 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center"><div><strong className="text-sm text-slate-900">{queue.label}</strong><p className="mt-1 text-xs text-slate-500">Open workflow queue</p></div><Badge color="blue">{queue.total} open</Badge><Badge color={queue.critical ? 'red' : 'slate'}>{queue.critical} critical</Badge><Badge color={queue.overdue ? 'orange' : 'green'}>{queue.overdue} overdue</Badge></Link>
          })}{!(data?.queues || []).length && <div className="py-10 text-center text-sm text-slate-400">No open queues in this role context.</div>}</div>
        </Card>
        <Card title="Operational pulse" subtitle="Work requiring attention now" icon="alert">
          <div className="grid grid-cols-2 gap-3"><div className="rounded-2xl bg-slate-950 p-4 text-white"><small className="text-slate-300">Open work</small><strong className="mt-2 block text-3xl">{data?.open_total || 0}</strong></div><div className="rounded-2xl bg-rose-600 p-4 text-white"><small className="text-rose-100">Critical</small><strong className="mt-2 block text-3xl">{data?.critical_total || 0}</strong></div><div className="rounded-2xl bg-amber-500 p-4 text-white"><small className="text-amber-50">Overdue</small><strong className="mt-2 block text-3xl">{data?.overdue_total || 0}</strong></div><div className="rounded-2xl bg-primary-700 p-4 text-white"><small className="text-primary-100">Assigned to you</small><strong className="mt-2 block text-3xl">{data?.assigned_total || 0}</strong></div></div>
        </Card>
      </div>

      <section>
        <div className="mb-4"><h3 className="text-xl font-bold text-slate-900">Professional workspaces</h3><p className="mt-1 text-sm text-slate-500">Purpose-built modules for your role, with patient context, audit history and workflow controls.</p></div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{quickModules.map((module) => <Link key={module.id} to={module.id} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_30px_rgba(9,31,58,.055)] transition hover:-translate-y-1 hover:border-primary-300 hover:shadow-[0_20px_45px_rgba(9,31,58,.1)]"><div className="flex items-start justify-between gap-4"><span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary-50 text-primary-700 transition group-hover:bg-primary-600 group-hover:text-white"><HealthIcon name={module.icon} size={22}/></span><Badge color="blue">{module.kind === 'records' ? `${module.recordTypes.length} workflow${module.recordTypes.length === 1 ? '' : 's'}` : 'Management'}</Badge></div><h4 className="mt-4 font-bold text-slate-900">{module.label}</h4><p className="mt-2 text-sm leading-6 text-slate-500">{module.description}</p><div className="mt-4 flex items-center gap-2 text-sm font-semibold text-primary-700">Open workspace <HealthIcon name="arrow" size={15}/></div></Link>)}</div>
      </section>

      <Card title="Recent role activity" subtitle="Latest records visible in your active context" icon="audit">
        <div className="grid gap-3 lg:grid-cols-2">{(data?.recent || []).slice(0, 8).map((row) => <div key={row.id} className="flex items-start justify-between gap-4 rounded-xl border border-slate-100 bg-slate-50/70 p-3"><div className="min-w-0"><strong className="block truncate text-sm text-slate-800">{row.title}</strong><span className="mt-1 block text-xs text-slate-500">{row.reference} · {row.patient_name || row.record_type?.replaceAll('_', ' ')}</span></div><Badge color={row.priority === 'critical' ? 'red' : row.status === 'completed' ? 'green' : 'blue'}>{row.status?.replaceAll('_', ' ')}</Badge></div>)}{!(data?.recent || []).length && <div className="col-span-full py-8 text-center text-sm text-slate-400">No recent activity in this role context.</div>}</div>
      </Card>
    </div>
  )
}
