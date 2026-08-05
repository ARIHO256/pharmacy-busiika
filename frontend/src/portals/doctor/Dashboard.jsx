import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { appointmentApi, chatApi, paymentApi, workforceApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import HealthIcon from '../../components/icons/HealthIcon'
import { Badge, Card, Spinner, Stat, Table } from '../../components/ui'
import { fmtMoney, statusColor } from './util'

const clinicalActions = [
  ['availability', 'clock', 'Set availability', 'Working hours, breaks and holidays'],
  ['appointments', 'calendar', 'Appointment queue', 'Confirm, reschedule and manage requests'],
  ['consult', 'video', 'Start consultation', 'Secure chat, audio and video workspace'],
  ['clinical', 'clipboard', 'Clinical workspace', 'Encounters, notes, diagnosis and referrals'],
  ['prescriptions', 'prescription', 'E-prescriptions', 'Issue and manage medication orders'],
  ['earnings', 'money', 'Earnings', 'Revenue, commissions and payouts'],
]

export default function Dashboard() {
  const { user } = useAuth()
  const [appointments, setAppointments] = useState(null)
  const [earnings, setEarnings] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [clinicQueue, setClinicQueue] = useState([])

  useEffect(() => {
    appointmentApi.list().then((response) => setAppointments(response.data || [])).catch(() => setAppointments([]))
    paymentApi.earnings().then((response) => setEarnings(response.data)).catch(() => setEarnings(null))
    chatApi.notifications().then((response) => setNotifications(Array.isArray(response.data) ? response.data : response.data?.results || [])).catch(() => {})
    workforceApi.visits({ status: 'waiting_clinician' }).then((response) => setClinicQueue(response.data || [])).catch(() => setClinicQueue([]))
  }, [])

  const data = useMemo(() => {
    if (!appointments) return null
    const today = new Date().toISOString().slice(0, 10)
    return {
      today,
      todays: appointments.filter((appointment) => appointment.date === today),
      pending: appointments.filter((appointment) => appointment.status === 'pending'),
      unread: notifications.filter((notification) => !notification.is_read).length,
    }
  }, [appointments, notifications])

  if (!data) return <Spinner label="Loading clinical workspace…" />

  const next = data.todays.find((appointment) => ['confirmed', 'pending'].includes(appointment.status)) || data.todays[0]

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-slate-900 to-violet-900 p-6 text-white shadow-[0_22px_55px_rgba(26,18,65,.2)] md:p-8">
        <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full border border-violet-200/10 shadow-[0_0_0_55px_rgba(119,86,216,.05),0_0_0_110px_rgba(119,86,216,.025)]" />
        <div className="relative grid gap-6 lg:grid-cols-[1.25fr_.75fr] lg:items-end">
          <div><span className="text-xs font-bold uppercase tracking-[0.18em] text-violet-200">Clinical operations · Today</span><h2 className="mt-3 text-3xl font-bold tracking-tight md:text-4xl">Welcome, Dr. {user?.last_name || user?.first_name || 'Doctor'}.</h2><p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">Manage the complete provider workflow from availability and appointments to consultation, documentation, prescriptions and follow-up.</p><div className="mt-5 flex flex-wrap gap-3"><Link to="clinical" className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-bold text-violet-900"><HealthIcon name="clipboard" size={17}/> Clinical workspace</Link><Link to="appointments" className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-4 text-sm font-semibold"><HealthIcon name="calendar" size={17}/> Appointment queue</Link></div></div>
          <article className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-md"><div className="flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-[0.14em] text-violet-200">Next patient</span><HealthIcon name="doctor" size={18}/></div>{next ? <div className="mt-4"><strong className="text-lg">{next.patient_name || [next.patient_first_name, next.patient_last_name].filter(Boolean).join(' ') || `Patient #${next.patient}`}</strong><p className="mt-1 text-sm text-slate-300">{next.reason || 'Consultation'} · {next.type === 'online' ? 'Online' : 'In person'}</p><div className="mt-4 flex items-center justify-between gap-3"><span className="text-sm font-semibold">{(next.start_time || '').slice(0,5)} – {(next.end_time || '').slice(0,5)}</span><Badge color={statusColor(next.status)}>{next.status}</Badge></div></div> : <div className="mt-4"><strong>No patient scheduled</strong><p className="mt-1 text-sm text-slate-300">Use availability settings to open additional care slots.</p></div>}</article>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Today's appointments" value={data.todays.length} icon="calendar" caption="Scheduled for today" />
        <Stat label="Pending requests" value={data.pending.length} icon="clock" tone="text-amber-600" caption="Awaiting your decision" />
        <Stat label="Walk-in queue" value={clinicQueue.length} icon="doctor" tone="text-emerald-600" caption="Triaged patients waiting for you" />
        <Stat label="Total earnings" value={earnings ? fmtMoney(earnings.total ?? earnings.total_earnings ?? 0) : '—'} icon="money" caption="Provider earnings recorded" />
        <Stat label="Unread notifications" value={data.unread} icon="bell" tone="text-sky-600" caption="Clinical and account updates" />
      </div>

      {clinicQueue.length > 0 && (
        <Card title="Walk-in clinic queue" subtitle="Triaged walk-in patients waiting for a clinician" icon="doctor" actions={<Link to="clinical" className="text-sm font-semibold text-primary-700 hover:underline">Open clinical workspace</Link>}>
          <Table columns={[
            { key: 'queue_number', label: 'Queue', render: (visit) => <strong>#{visit.queue_number || '—'}</strong> },
            { key: 'patient', label: 'Patient', render: (visit) => visit.patient_name || `Patient #${visit.patient}` },
            { key: 'reason', label: 'Complaint', render: (visit) => visit.reason || visit.triage?.chief_complaint || '—' },
            { key: 'priority', label: 'Priority', render: (visit) => <Badge color={visit.priority === 'emergency' ? 'red' : visit.priority === 'urgent' ? 'yellow' : 'blue'}>{visit.priority}</Badge> },
            { key: 'checked_in_at', label: 'Waiting since', render: (visit) => String(visit.checked_in_at || '').slice(11, 16) },
          ]} rows={clinicQueue.slice(0, 6)} />
        </Card>
      )}

      <Card title="Clinical workflow" subtitle="Shortcuts follow the doctor journey defined in the platform flow" icon="activity">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {clinicalActions.map(([to, icon, title, text], index) => <Link key={to} to={to} className="group flex items-center gap-3 rounded-2xl border border-slate-200 p-4 transition hover:-translate-y-0.5 hover:border-violet-200 hover:bg-violet-50/50"><span className="relative grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-700"><HealthIcon name={icon} size={20}/><i className="absolute -left-2 -top-2 grid h-5 w-5 place-items-center rounded-full bg-slate-900 text-[9px] not-italic text-white">5.{index + 3}</i></span><span className="min-w-0 flex-1"><strong className="block text-sm text-slate-800">{title}</strong><small className="mt-0.5 block text-xs leading-5 text-slate-500">{text}</small></span><HealthIcon name="chevron" size={15} className="text-slate-400"/></Link>)}
        </div>
      </Card>

      <Card title="Today's schedule" subtitle={`${data.today} · appointments and consultation status`} icon="calendar" actions={<Link to="appointments" className="text-sm font-semibold text-primary-700 hover:underline">View all</Link>}>
        <Table columns={[
          { key: 'time', label: 'Time', render: (appointment) => `${(appointment.start_time || '').slice(0, 5)} – ${(appointment.end_time || '').slice(0, 5)}` },
          { key: 'patient', label: 'Patient', render: (appointment) => appointment.patient_name || [appointment.patient_first_name, appointment.patient_last_name].filter(Boolean).join(' ') || `Patient #${appointment.patient}` },
          { key: 'type', label: 'Type', render: (appointment) => <Badge color={appointment.type === 'online' ? 'blue' : 'purple'}>{appointment.type}</Badge> },
          { key: 'reason', label: 'Reason', render: (appointment) => appointment.reason || '—' },
          { key: 'status', label: 'Status', render: (appointment) => <Badge color={statusColor(appointment.status)}>{appointment.status}</Badge> },
        ]} rows={data.todays} empty="No appointments today." />
      </Card>

      {data.pending.length > 0 && <Card title="Pending appointment requests" subtitle="Review and respond to preserve accurate availability" icon="clock"><Table columns={[
        { key: 'date', label: 'Date' },
        { key: 'time', label: 'Time', render: (appointment) => `${(appointment.start_time || '').slice(0, 5)} – ${(appointment.end_time || '').slice(0, 5)}` },
        { key: 'patient', label: 'Patient', render: (appointment) => appointment.patient_name || [appointment.patient_first_name, appointment.patient_last_name].filter(Boolean).join(' ') || `Patient #${appointment.patient}` },
        { key: 'type', label: 'Type', render: (appointment) => <Badge color={appointment.type === 'online' ? 'blue' : 'purple'}>{appointment.type}</Badge> },
        { key: 'reason', label: 'Reason', render: (appointment) => appointment.reason || '—' },
      ]} rows={data.pending.slice(0, 5)} /></Card>}
    </div>
  )
}
