import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { workforceApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { NewPrescription } from '../doctor/Prescriptions'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'

const destinations = [
  ['reception', 'Reception and records'], ['nursing', 'Nursing and treatment'],
  ['lab', 'Laboratory'], ['imaging', 'Imaging'], ['pharmacy', 'Facility pharmacy'],
  ['billing', 'Billing'], ['specialist', 'Specialist or referral'], ['ward', 'Ward, observation or transfer'],
]
const labels = { checkout: 'Complete visit', accept: 'Accept', return: 'Return to doctor', complete: 'Complete', cancel: 'Cancel handoff', resend: 'Send again' }
const empty = { destination: 'reception', priority: 'routine', instructions: '', prescription: '', modality: '', body_site: '', receiving_facility: '', specialty: '' }

export default function Handoffs() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const clinician = user.role === 'doctor'
  const visits = useRemote(() => clinician ? workforceApi.visits() : Promise.resolve({ data: [] }), [clinician])
  const linkedAppointment = params.get('appointment')
  const visit = params.get('visit') || (linkedAppointment && String(visits.data?.find((row) => String(row.appointment) === linkedAppointment)?.id || '')) || ''
  const summary = useRemote(() => clinician ? workforceApi.summary() : Promise.resolve({ data: null }), [clinician])
  const queue = useRemote(() => workforceApi.handoffs(visit ? { visit } : {}), [visit])
  const [form, setForm] = useState(empty)
  const referralFacilities = useRemote(() => form.destination === 'specialist'
    ? workforceApi.referralFacilities() : Promise.resolve({ data: [] }), [form.destination])
  const [signing, setSigning] = useState(false)
  const [transition, setTransition] = useState(null)
  const [outcome, setOutcome] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const rows = (queue.data || []).filter((row) => !visit || String(row.visit) === visit)
  const assigned = (visits.data || []).filter((row) => row.assigned_doctor === user.id && !['completed', 'cancelled'].includes(row.status))

  useEffect(() => {
    const timer = window.setInterval(() => { if (!document.hidden) queue.reload() }, 30000)
    return () => window.clearInterval(timer)
  }, [queue.reload])

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      if (transition) {
        if (transition.action === 'checkout') {
          await workforceApi.updateVisit(visit, { status: 'completed', checkout_note: outcome })
          visits.reload()
        } else await workforceApi.transitionHandoff(transition.row.id, { action: transition.action, outcome })
        setTransition(null)
      } else {
        const { prescription, modality, body_site, receiving_facility, specialty, ...request } = form
        await workforceApi.createHandoff({
          ...request,
          visit: Number(visit),
          ...(form.destination === 'pharmacy' && { prescription: Number(prescription) }),
          ...(form.destination === 'imaging' && { modality, body_site }),
          ...(form.destination === 'specialist' && receiving_facility && { receiving_facility: Number(receiving_facility), specialty }),
        })
        setForm(empty)
      }
      queue.reload()
    } catch (err) {
      setError(getError(err))
    } finally {
      setBusy(false)
    }
  }

  return <div className="space-y-4">
    {clinician && <Card title="Next steps">
      <Select label="Patient visit" value={visit} disabled={busy} onChange={(event) => {
        setForm(empty)
        setError('')
        setParams(event.target.value ? { visit: event.target.value } : {})
      }}>
        <option value="">All open handoffs</option>
        {visit && !assigned.some((row) => String(row.id) === visit) && <option value={visit}>Visit history</option>}
        {assigned.map((row) => <option key={row.id} value={row.id}>{row.patient_name} · {row.visit_number}</option>)}
      </Select>
      {assigned.some((row) => String(row.id) === visit) && <form className="mt-4 space-y-3" onSubmit={submit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Send to" value={form.destination} onChange={(event) => setForm({ ...form, destination: event.target.value })}>
            {destinations.filter(([key]) => key !== 'ward' || summary.data?.organization?.type === 'hospital').map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </Select>
          <Select label="Priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
            <option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option>
          </Select>
        </div>
        {form.destination === 'specialist' && <div className="grid gap-3 sm:grid-cols-2">
          <Select label="Receiving facility" value={form.receiving_facility} onChange={(event) => setForm({ ...form, receiving_facility: event.target.value })}>
            <option value="">Internal specialist review</option>
            {(referralFacilities.data || []).map((facility) => <option key={facility.id} value={facility.id}>{facility.legal_name}</option>)}
          </Select>
          {form.receiving_facility && <Input required maxLength={200} label="Specialty" value={form.specialty} onChange={(event) => setForm({ ...form, specialty: event.target.value })} />}
          {referralFacilities.error && <Alert tone="warning">{referralFacilities.error}</Alert>}
        </div>}
        {form.destination === 'imaging'  && <div className="grid gap-3 sm:grid-cols-2">
          <Select required label="Modality" value={form.modality} onChange={(event) => setForm({ ...form, modality: event.target.value })}>
            <option value="">Choose modality</option>
            {[['CR', 'X-ray'], ['DX', 'Digital radiography'], ['CT', 'CT'], ['MR', 'MRI'], ['US', 'Ultrasound'], ['NM', 'Nuclear medicine'], ['MG', 'Mammography'], ['OT', 'Other']].map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
          <Input required maxLength={120} label="Body site" value={form.body_site} onChange={(event) => setForm({ ...form, body_site: event.target.value })} />
        </div>}
        {form.destination === 'lab'  && <Link className="text-primary-700 underline" to={`/doctor/lab-referrals?visit=${visit}`}>Order a laboratory test and track its result</Link>}
        {form.destination === 'pharmacy' && <><Button type="button" variant="outline" onClick={() => setSigning(true)}>Sign prescription for this visit</Button><Input required type="number" min="1" label="Signed prescription ID" value={form.prescription} onChange={(event) => setForm({ ...form, prescription: event.target.value })} /></>}
        {form.destination !== 'lab' && <>
          <Textarea required maxLength={1000} label="Instructions for the receiving team" value={form.instructions} onChange={(event) => setForm({ ...form, instructions: event.target.value })} />
          <Button disabled={busy}>Send handoff</Button>
        </>}
      </form>}
      {visit && assigned.some((row) => String(row.id) === visit) && <Button className="mt-4" type="button" variant="outline" onClick={() => { setError(''); setOutcome(''); setTransition({ action: 'checkout', row: { patient: assigned.find((row) => String(row.id) === visit).patient_name } }) }}>Complete visit</Button>}
    </Card>}
    {!transition && error && <Alert tone="danger">{error}</Alert>}
    <Card title={visit ? 'Visit handoff history' : 'Open handoffs'} actions={<div className="flex items-center gap-3">
      {visit && <Link className="text-primary-700 underline" to="?">All open handoffs</Link>}
      <Button variant="outline" onClick={queue.reload}>Refresh</Button>
    </div>}>
      {queue.error ? <Alert tone="warning">{queue.error}</Alert> : queue.loading && !queue.data ? <Spinner /> :
        <Table rows={rows} empty="No handoffs to show" columns={[
          { key: 'patient', label: 'Patient', render: (row) => <><strong>{row.patient}</strong><div><Link className="text-primary-700 underline" to={`?visit=${row.visit}`}>{row.visit_number}</Link></div></> },
          { key: 'destination_label', label: 'Receiving team', render: (row) => <>{row.destination_label}
            {row.lab_order && user.role === 'doctor' && <div><Link className="text-primary-700 underline" to="/doctor/lab-referrals">Lab order #{row.lab_order}</Link></div>}
            {row.referral_route && user.role === 'doctor' && <div><Link className="text-primary-700 underline" to={`/doctor/referrals?record=${row.referral_route}`}>Referral #{row.referral_route}</Link></div>}
            {row.imaging_order && ['doctor', 'lab_technician'].includes(user.role) && <div><Link className="text-primary-700 underline" to={`${user.role === 'doctor' ? '/doctor/imaging' : '/lab-staff/imaging'}?record=${row.imaging_order}`}>Imaging order #{row.imaging_order}</Link></div>}
            {row.pharmacy_order && user.role === 'pharmacist' && <div><Link className="text-primary-700 underline" to="/pharmacist/rx-orders">Prescription order #{row.pharmacy_order}</Link></div>}
            {row.destination === 'billing' && user.role === 'cashier' && <div><Link className="text-primary-700 underline" to={`/cashier/invoices?visit=${row.visit}`}>Visit invoices</Link></div>}
            {row.destination === 'ward' && ['doctor', 'nurse', 'hospital', 'facility_manager'].includes(user.role) && <div><Link className="text-primary-700 underline" to={`${user.role === 'doctor' ? '/doctor/admissions' : user.role === 'nurse' ? '/nurse/ward-board' : '/facility/admissions'}?visit=${row.visit}`}>Admissions for visit #{row.visit}</Link></div>}
          </> },
          { key: 'status', label: 'Status', render: (row) => <>{statusBadge(row.status)}<div>{row.accepted_by}</div></> },
          { key: 'priority', label: 'Priority', render: (row) => statusBadge(row.priority) },
          { key: 'instructions', label: 'Details', render: (row) => <>{row.instructions}<div>{row.outcome}</div></> },
          { key: 'updated_at', label: 'Updated', render: (row) => displayDate(row.updated_at) },
          { key: 'actions', label: 'Actions', render: (row) => <div className="flex flex-wrap gap-2">{row.actions.map((action) =>
            <Button key={action} type="button" variant="outline" onClick={() => { setError(''); setOutcome(action === 'resend' ? row.instructions : ''); setTransition({ row, action }) }}>{labels[action]}</Button>
          )}</div> },
        ]}/>}
    </Card>
    <Modal open={signing} title="Sign visit prescription" onClose={() => setSigning(false)}>
      {signing && <NewPrescription visit={visit} onCreated={(row) => { setForm({ ...form, prescription: String(row.id) }); setSigning(false) }} />}
    </Modal>
    <Modal open={Boolean(transition)} title={transition ? labels[transition.action] : ''} onClose={() => { if (!busy) setTransition(null) }}>
      {transition && <form onSubmit={submit} className="space-y-3">
        {error && <Alert tone="danger">{error}</Alert>}
        <p>{transition.row.patient} · {transition.row.destination_label}</p>
        {transition.action !== 'accept' && <Textarea required maxLength={1000} label={transition.action === 'resend' ? 'Updated instructions' : transition.action === 'checkout' ? 'Care plan and follow-up instructions' : 'Outcome or reason'} value={outcome} onChange={(event) => setOutcome(event.target.value)} />}
        <Button disabled={busy}>{labels[transition.action]}</Button>
      </form>}
    </Modal>
  </div>
}
