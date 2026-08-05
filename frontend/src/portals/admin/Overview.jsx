import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, Spinner, Stat } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'
import { adminApi } from '../../api/endpoints'
import { money, BAR_COLORS, STATUS_BAR_COLORS, appointmentStatusColor } from './helpers'

function BarRow({ label, value, max, colorClass }) {
  const percentage = max > 0 ? Math.max(3, Math.round((value / max) * 100)) : 0
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-sm"><span className="capitalize text-slate-600">{label}</span><span className="font-semibold text-slate-700">{value}</span></div>
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-100"><div className={`h-full rounded-full ${colorClass}`} style={{ width: `${percentage}%` }} /></div>
    </div>
  )
}

const commandLinks = [
  ['users', 'users', 'Manage users', 'Roles, access, suspension and account operations'],
  ['registry', 'doctor', 'Verify providers', 'Credentials, licences and facility affiliations'],
  ['appointments', 'calendar', 'Monitor appointments', 'Bookings, no-shows and care exceptions'],
  ['finance', 'money', 'Financial operations', 'Transactions, commissions and payouts'],
  ['compliance', 'shield', 'Compliance centre', 'Consent, emergency access and policy review'],
  ['audit', 'audit', 'Audit trail', 'Security and clinical access evidence'],
]

export default function Overview() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.overview().then((response) => setData(response.data)).catch(() => setError('Failed to load overview.'))
  }, [])

  const usersByRole = useMemo(() => Object.entries(data?.users || {}), [data])
  const appointmentsByStatus = useMemo(() => Object.entries(data?.appointments || {}), [data])
  const organizationsByType = useMemo(() => Object.entries(data?.organizations_by_type || {}), [data])
  const totalUsers = useMemo(() => usersByRole.reduce((sum, [, count]) => sum + count, 0), [usersByRole])
  const totalAppointments = useMemo(() => appointmentsByStatus.reduce((sum, [, count]) => sum + count, 0), [appointmentsByStatus])
  const maxRole = Math.max(1, ...usersByRole.map(([, count]) => count))
  const maxStatus = Math.max(1, ...appointmentsByStatus.map(([, count]) => count))

  if (error) return <Card><p className="text-sm text-rose-600">{error}</p></Card>
  if (!data) return <Spinner label="Loading platform command centre…" />

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-slate-900 to-primary-900 p-6 text-white shadow-[0_22px_55px_rgba(6,17,31,.22)] md:p-8">
        <div className="absolute -right-14 -top-16 h-64 w-64 rounded-full border border-sky-200/10 shadow-[0_0_0_55px_rgba(59,130,208,.05),0_0_0_110px_rgba(59,130,208,.025)]" />
        <div className="relative grid gap-6 lg:grid-cols-[1.2fr_.8fr] lg:items-end">
          <div><span className="text-xs font-bold uppercase tracking-[0.18em] text-sky-200">Platform governance · Live operations</span><h2 className="mt-3 text-3xl font-bold tracking-tight md:text-4xl">HealthPilot command centre.</h2><p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">Operate the complete healthcare network across identity, appointments, finance, provider verification, quality, compliance and audit.</p><div className="mt-5 flex flex-wrap gap-3"><Link to="registry" className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-bold text-primary-900"><HealthIcon name="doctor" size={17}/> Verify providers</Link><Link to="compliance" className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-4 text-sm font-semibold"><HealthIcon name="shield" size={17}/> Compliance centre</Link></div></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur"><span className="text-xs text-slate-300">Pending verifications</span><strong className="mt-2 block text-3xl">{data.pending_verifications}</strong><small className="mt-1 block text-sky-200">Provider review queue</small></div>
            <div className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur"><span className="text-xs text-slate-300">Pending payouts</span><strong className="mt-2 block text-3xl">{data.pending_payouts}</strong><small className="mt-1 block text-sky-200">Settlement actions</small></div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Stat label="Total users" value={totalUsers.toLocaleString()} icon="users" caption="All registered platform roles" />
        <Stat label="Appointments" value={totalAppointments.toLocaleString()} icon="calendar" caption="Across all appointment states" />
        <Stat label="Revenue" value={money(data.revenue)} icon="money" caption="Recorded platform revenue" />
        <Stat label="Commissions" value={money(data.commissions)} icon="chart" tone="text-slate-700" caption="Platform commission value" />
        <Stat label="Pending verifications" value={data.pending_verifications} icon="doctor" tone="text-amber-600" caption="Credentials awaiting review" />
        <Stat label="Pending payouts" value={data.pending_payouts} icon="wallet" tone="text-amber-600" caption="Provider settlement queue" />
        <Stat label="Notification failures" value={data.failed_notification_deliveries || 0} icon="bell" tone="text-rose-600" caption="Delivery jobs requiring attention" />
      </div>

      <Card title="Operational command shortcuts" subtitle="Every control area from the admin branch of the platform flow" icon="dashboard">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {commandLinks.map(([to, icon, title, text]) => <Link key={to} to={to} className="group flex items-center gap-3 rounded-2xl border border-slate-200 p-4 transition hover:-translate-y-0.5 hover:border-primary-200 hover:bg-primary-50/50"><span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-700"><HealthIcon name={icon} size={20}/></span><span className="min-w-0 flex-1"><strong className="block text-sm text-slate-800">{title}</strong><small className="mt-0.5 block text-xs leading-5 text-slate-500">{text}</small></span><HealthIcon name="chevron" size={15} className="text-slate-400"/></Link>)}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card title="Users by role" subtitle="Distribution across the connected-care ecosystem" icon="users">
          {usersByRole.length === 0 ? <p className="py-6 text-center text-sm text-slate-400">No users yet</p> : <div className="space-y-4">{usersByRole.map(([role, count], index) => <BarRow key={role} label={role} value={count} max={maxRole} colorClass={BAR_COLORS[index % BAR_COLORS.length]} />)}</div>}
        </Card>
        <Card title="Appointments by status" subtitle="Current state of the appointment and scheduling system" icon="calendar">
          {appointmentsByStatus.length === 0 ? <p className="py-6 text-center text-sm text-slate-400">No appointments yet</p> : <div className="space-y-4">{appointmentsByStatus.map(([status, count]) => <BarRow key={status} label={status} value={count} max={maxStatus} colorClass={STATUS_BAR_COLORS[status] || (appointmentStatusColor[status] === 'green' ? 'bg-emerald-500' : 'bg-teal-500')} />)}</div>}
        </Card>
        <Card title="Organizations by type" subtitle="Hospitals, clinics, pharmacies, laboratories and insurers" icon="hospital">
          {organizationsByType.length === 0 ? <p className="py-6 text-center text-sm text-slate-400">No organizations yet</p> : <div className="space-y-4">{organizationsByType.map(([type, count], index) => <BarRow key={type} label={type.replaceAll('_', ' ')} value={count} max={Math.max(1, ...organizationsByType.map(([, value]) => value))} colorClass={BAR_COLORS[index % BAR_COLORS.length]} />)}</div>}
        </Card>
      </div>
    </div>
  )
}
