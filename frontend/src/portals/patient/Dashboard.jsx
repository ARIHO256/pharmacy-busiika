import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { appointmentApi, chatApi, paymentApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import HealthIcon from '../../components/icons/HealthIcon'
import { Badge, Card, Spinner, Stat } from '../../components/ui'
import { APPT_STATUS_COLORS, fmtTime, todayISO } from './utils'

const careActions = [
  { to: 'doctors', icon: 'search', title: 'Find care', text: 'Search verified doctors and services', tone: 'blue' },
  { to: 'appointments', icon: 'calendar', title: 'Book appointment', text: 'Choose online or in-person care', tone: 'green' },
  { to: 'messages', icon: 'video', title: 'Consultation', text: 'Open secure chat, audio or video', tone: 'violet' },
  { to: 'health-record', icon: 'heart', title: 'Health record', text: 'Timeline, conditions and consent', tone: 'orange' },
]

const connectedServices = [
  ['store', 'pill', 'Pharmacy', 'Send prescriptions and order medicine'],
  ['labs', 'flask', 'Laboratory', 'Book tests and receive structured results'],
  ['hospitals', 'hospital', 'Hospitals', 'Find facilities, services and bookings'],
  ['insurance', 'insurance', 'Insurance', 'Coverage, approvals and claims'],
  ['prescriptions', 'prescription', 'Prescriptions', 'Medication instructions and refill history'],
  ['invoices', 'wallet', 'Payments', 'Invoices, receipts and balances'],
]

export default function Dashboard() {
  const { user } = useAuth()
  const [appointments, setAppointments] = useState(null)
  const [invoices, setInvoices] = useState(null)
  const [notifications, setNotifications] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    const normalizeList = (data) => (Array.isArray(data) ? data : data?.results || [])
    Promise.all([
      appointmentApi.list().then((response) => response.data),
      paymentApi.invoices().then((response) => response.data),
      chatApi.notifications().then((response) => response.data),
    ])
      .then(([appointmentData, invoiceData, notificationData]) => {
        setAppointments(normalizeList(appointmentData))
        setInvoices(normalizeList(invoiceData))
        setNotifications(normalizeList(notificationData))
      })
      .catch(() => setError('Could not load your dashboard. Please try again.'))
  }, [])

  const dashboardData = useMemo(() => {
    if (!appointments || !invoices) return null
    const today = todayISO()
    const upcoming = appointments
      .filter((appointment) => ['pending', 'confirmed'].includes(appointment.status) && appointment.date >= today)
      .sort((a, b) => `${a.date}T${a.start_time}`.localeCompare(`${b.date}T${b.start_time}`))
    return {
      upcoming,
      pendingInvoices: invoices.filter((invoice) => invoice.status === 'pending'),
      unread: notifications.filter((notification) => !notification.is_read),
    }
  }, [appointments, invoices, notifications])

  if (error) return <Card className="text-sm text-rose-600">{error}</Card>
  if (!dashboardData) return <Spinner label="Loading your care workspace…" />

  const next = dashboardData.upcoming[0]
  const firstName = user?.first_name || 'there'

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-primary-900 to-primary-700 p-6 text-white shadow-[0_22px_55px_rgba(10,45,102,.22)] md:p-8">
        <div className="absolute -right-16 -top-20 h-64 w-64 rounded-full border border-cyan-200/10 shadow-[0_0_0_55px_rgba(40,197,228,.04),0_0_0_110px_rgba(40,197,228,.025)]" />
        <div className="relative grid gap-6 lg:grid-cols-[1.25fr_.75fr] lg:items-end">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">Your care command centre</span>
            <h2 className="mt-3 text-3xl font-bold tracking-tight md:text-4xl">Good day, {firstName}.</h2>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">Continue your healthcare journey from discovery and booking through consultation, prescriptions, diagnostics and follow-up.</p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Link to="doctors" className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-bold text-primary-800 shadow-lg"><HealthIcon name="search" size={17} /> Find a doctor</Link>
              <Link to="health-record" className="inline-flex min-h-11 items-center gap-2 rounded-xl border border-white/20 bg-white/5 px-4 text-sm font-semibold text-white backdrop-blur"><HealthIcon name="heart" size={17} /> Open health record</Link>
            </div>
          </div>
          <article className="rounded-2xl border border-white/20 bg-white/10 p-4 backdrop-blur-md">
            <div className="flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-[0.14em] text-cyan-200">Next appointment</span><HealthIcon name="calendar" size={18} /></div>
            {next ? (
              <div className="mt-4">
                <strong className="text-lg">Dr. {next.doctor_name}</strong>
                <p className="mt-1 text-sm text-slate-300">{next.doctor_specialization || 'General care'} · {next.type === 'online' ? 'Online consultation' : 'In-person visit'}</p>
                <div className="mt-4 flex items-center justify-between gap-3"><span className="text-sm font-semibold">{next.date} · {fmtTime(next.start_time)}</span><Badge color={APPT_STATUS_COLORS[next.status] || 'slate'}>{next.status}</Badge></div>
              </div>
            ) : (
              <div className="mt-4"><strong>No appointment scheduled</strong><p className="mt-1 text-sm text-slate-300">Find a provider and choose a convenient care slot.</p></div>
            )}
          </article>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat label="Upcoming appointments" value={dashboardData.upcoming.length} icon="calendar" caption="Confirmed and pending care" />
        <Stat label="Pending invoices" value={dashboardData.pendingInvoices.length} icon="wallet" tone="text-amber-600" caption="Payments requiring attention" />
        <Stat label="Unread notifications" value={dashboardData.unread.length} icon="bell" tone="text-sky-600" caption="Care and account updates" />
      </div>

      <section>
        <div className="mb-3 flex items-end justify-between gap-3"><div><span className="text-xs font-bold uppercase tracking-[0.15em] text-primary-600">Patient flow</span><h3 className="mt-1 text-xl font-bold text-slate-900">Continue your care journey</h3></div></div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {careActions.map((action) => (
            <Link key={action.to} to={action.to} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_30px_rgba(9,31,58,.05)] transition hover:-translate-y-1 hover:border-primary-200 hover:shadow-[0_18px_38px_rgba(9,31,58,.1)]">
              <span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-50 text-primary-700 transition group-hover:bg-primary-100"><HealthIcon name={action.icon} size={21} /></span>
              <strong className="mt-4 block text-sm text-slate-900">{action.title}</strong><span className="mt-1 block text-xs leading-5 text-slate-500">{action.text}</span><span className="mt-4 inline-flex items-center gap-1 text-xs font-bold text-primary-700">Open <HealthIcon name="arrow" size={14} /></span>
            </Link>
          ))}
        </div>
      </section>

      <Card title="Next appointments" subtitle="Your confirmed and pending care schedule" icon="calendar" actions={<Link to="appointments" className="text-sm font-semibold text-primary-700 hover:underline">View all</Link>}>
        {dashboardData.upcoming.length === 0 ? (
          <div className="py-8 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-primary-50 text-primary-700"><HealthIcon name="calendar" size={22} /></span><p className="mt-3 text-sm text-slate-500">No upcoming appointments.</p><Link to="doctors" className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-primary-700">Find a doctor <HealthIcon name="arrow" size={15} /></Link></div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {dashboardData.upcoming.slice(0, 5).map((appointment) => (
              <li key={appointment.id} className="flex flex-col justify-between gap-3 py-3 sm:flex-row sm:items-center">
                <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-primary-50 text-primary-700"><HealthIcon name="doctor" size={19} /></span><div><div className="font-semibold text-slate-800">Dr. {appointment.doctor_name}</div><div className="text-xs text-slate-500">{appointment.doctor_specialization || 'General'} · {appointment.type === 'online' ? 'Online' : 'In person'}</div></div></div>
                <div className="flex items-center gap-3 sm:text-right"><div><div className="text-sm font-medium text-slate-700">{appointment.date} · {fmtTime(appointment.start_time)}</div><Badge color={APPT_STATUS_COLORS[appointment.status] || 'slate'}>{appointment.status}</Badge></div></div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title="Connected healthcare services" subtitle="Move from consultation into diagnostics, medicines, facilities and coverage" icon="globe">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {connectedServices.map(([to, icon, title, text]) => (
            <Link key={to} to={to} className="flex items-center gap-3 rounded-2xl border border-slate-200 p-4 transition hover:border-primary-200 hover:bg-primary-50/50"><span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-100 text-primary-700"><HealthIcon name={icon} size={19} /></span><span className="min-w-0 flex-1"><strong className="block text-sm text-slate-800">{title}</strong><small className="mt-0.5 block text-xs leading-5 text-slate-500">{text}</small></span><HealthIcon name="chevron" size={15} className="text-slate-400" /></Link>
          ))}
        </div>
      </Card>
    </div>
  )
}
