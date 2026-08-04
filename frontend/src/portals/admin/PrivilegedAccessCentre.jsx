import { useEffect, useMemo, useState } from 'react'
import { privilegedAccessApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner, Textarea } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'
import EntitySearchSelect from '../enterprise/components/EntitySearchSelect'

const SCOPES = [
  ['patient_summary', 'Patient summary'], ['encounters', 'Clinical encounters'],
  ['medications', 'Medications'], ['allergies', 'Allergies'],
  ['laboratory', 'Laboratory'], ['imaging', 'Imaging'],
  ['admissions', 'Admissions'], ['billing', 'Billing'], ['audit', 'Audit history'],
]
const REVIEW_ROLES = new Set(['admin', 'platform_super_admin', 'compliance_admin', 'clinical_safety_admin'])
const labelize = (value = '') => String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const errorText = (error) => error?.response?.data?.detail || error?.message || 'The elevated-access operation failed.'

function countdown(expiresAt) {
  if (!expiresAt) return 'Not activated'
  const seconds = Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000)
  if (seconds <= 0) return 'Expired'
  const minutes = Math.floor(seconds / 60)
  return `${minutes}m ${seconds % 60}s remaining`
}

export default function PrivilegedAccessCentre() {
  const { activeRole } = useAuth()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [requestOpen, setRequestOpen] = useState(false)
  const [decision, setDecision] = useState(null)
  const [form, setForm] = useState({ patient: '', purpose: 'clinical_safety_review', reason: '', scopes: ['patient_summary'], read_only: true })
  const [decisionForm, setDecisionForm] = useState({ action: 'approve', notes: '', duration_minutes: 20 })

  const canReview = REVIEW_ROLES.has(activeRole)
  const activeRows = useMemo(() => rows.filter((row) => row.status === 'active' && row.is_current), [rows])

  const load = async () => {
    setLoading(true); setError('')
    try { const { data } = await privilegedAccessApi.list(); setRows(data?.results || data || []) }
    catch (err) { setError(errorText(err)) }
    finally { setLoading(false) }
  }
  useEffect(() => { load(); const timer = setInterval(load, 30000); return () => clearInterval(timer) }, [])

  const submitRequest = async (event) => {
    event.preventDefault(); setLoading(true); setError('')
    try {
      await privilegedAccessApi.request({ ...form, patient: Number(form.patient) })
      setSuccess('Patient-specific access request submitted for independent approval.')
      setRequestOpen(false)
      setForm({ patient: '', purpose: 'clinical_safety_review', reason: '', scopes: ['patient_summary'], read_only: true })
      await load()
    } catch (err) { setError(errorText(err)); setLoading(false) }
  }

  const decide = async (event) => {
    event.preventDefault(); if (!decision) return
    setLoading(true); setError('')
    try {
      await privilegedAccessApi.decide(decision.id, decisionForm)
      setSuccess(`${labelize(decisionForm.action)} recorded with a complete audit event.`)
      setDecision(null); setDecisionForm({ action: 'approve', notes: '', duration_minutes: 20 })
      await load()
    } catch (err) { setError(errorText(err)); setLoading(false) }
  }

  const toggleScope = (scope) => setForm((old) => ({ ...old, scopes: old.scopes.includes(scope) ? old.scopes.filter((item) => item !== scope) : [...old.scopes, scope] }))

  return <div className="space-y-6">
    {error ? <Alert tone="danger" title="Controlled access failed">{error}</Alert> : null}
    {success ? <Alert tone="success">{success}</Alert> : null}
    <Card title="Audited clinical access" subtitle="Administration never grants standing access to patient records. Every elevation is patient-specific, purpose-bound, time-limited and reviewed." icon="shield" actions={<Button onClick={() => setRequestOpen(true)}><HealthIcon name="plus" size={16}/> Request access</Button>}>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl bg-primary-50 p-4"><small className="font-semibold text-primary-600">Current grants</small><strong className="mt-2 block text-3xl text-primary-900">{activeRows.length}</strong></div>
        <div className="rounded-2xl bg-amber-50 p-4"><small className="font-semibold text-amber-700">Pending review</small><strong className="mt-2 block text-3xl text-amber-900">{rows.filter((row) => row.status === 'pending').length}</strong></div>
        <div className="rounded-2xl bg-slate-50 p-4"><small className="font-semibold text-slate-600">Your active role</small><strong className="mt-2 block text-lg text-slate-900">{labelize(activeRole)}</strong></div>
      </div>
      <Alert tone="info" title="Clinical access boundary">A platform administrator can manage identities, roles and services without opening clinical records. Access to a named patient requires MFA, a reason, an independent decision and automatic expiry.</Alert>
    </Card>

    <Card title="Access requests and decisions" subtitle="Refreshes automatically every 30 seconds" icon="audit">
      {loading && !rows.length ? <Spinner label="Loading access grants…"/> : !rows.length ? <EmptyState icon="shield" title="No access grants" description="No administrator has requested exceptional access to a patient record."/> : <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400"><th className="p-3">Patient</th><th className="p-3">Requester</th><th className="p-3">Purpose and scope</th><th className="p-3">Status</th><th className="p-3">Expiry</th><th className="p-3">Action</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-b border-slate-100 align-top"><td className="p-3"><strong>{row.patient_name}</strong><small className="block text-slate-400">Patient #{row.patient}</small></td><td className="p-3">{row.requester_name}<small className="block text-slate-400">{new Date(row.requested_at).toLocaleString()}</small></td><td className="p-3"><strong className="block">{labelize(row.purpose)}</strong><p className="max-w-sm text-xs text-slate-500">{row.reason}</p><div className="mt-2 flex flex-wrap gap-1">{row.scopes?.map((scope) => <Badge key={scope} color="slate">{labelize(scope)}</Badge>)}</div></td><td className="p-3"><Badge color={row.status === 'active' ? 'green' : row.status === 'pending' ? 'yellow' : row.status === 'rejected' || row.status === 'revoked' ? 'red' : 'slate'}>{labelize(row.status)}</Badge><small className="mt-1 block text-slate-400">{row.read_only ? 'Read only' : 'Write scope requested'}</small></td><td className="p-3">{countdown(row.expires_at)}</td><td className="p-3"><div className="flex flex-wrap gap-2">{row.status === 'pending' && canReview ? <><Button onClick={() => { setDecision(row); setDecisionForm({ action: 'approve', notes: '', duration_minutes: 20 }) }}>Review</Button></> : null}{row.status === 'active' ? <Button variant="danger" onClick={() => { setDecision(row); setDecisionForm({ action: 'revoke', notes: '', duration_minutes: 20 }) }}>Revoke</Button> : null}{row.status !== 'pending' && row.status !== 'active' && canReview ? <Button variant="outline" onClick={() => { setDecision(row); setDecisionForm({ action: 'review', notes: '', duration_minutes: 20 }) }}>Close review</Button> : null}</div></td></tr>)}</tbody></table></div>}
    </Card>

    <Modal open={requestOpen} onClose={() => setRequestOpen(false)} title="Request patient-specific access" wide><form onSubmit={submitRequest} className="space-y-4">
      <Alert tone="warning">MFA must be enabled. The requester cannot approve their own request. Read-only access is strongly recommended.</Alert>
      <EntitySearchSelect kind="patient" label="Patient" value={form.patient} onChange={(patient) => setForm((old) => ({ ...old, patient }))} placeholder="Search by name, phone, MRN or date of birth" required/>
      <Input label="Purpose" value={form.purpose} onChange={(event) => setForm((old) => ({ ...old, purpose: event.target.value }))} required/>
      <Textarea label="Specific reason" value={form.reason} onChange={(event) => setForm((old) => ({ ...old, reason: event.target.value }))} hint="Minimum 20 characters. This reason is permanently audited." required/>
      <fieldset><legend className="mb-2 text-sm font-semibold text-slate-700">Requested scopes</legend><div className="grid gap-2 sm:grid-cols-3">{SCOPES.map(([scope, label]) => <label key={scope} className="flex items-center gap-2 rounded-xl border border-slate-200 p-3"><input type="checkbox" checked={form.scopes.includes(scope)} onChange={() => toggleScope(scope)}/><span className="text-sm">{label}</span></label>)}</div></fieldset>
      <label className="flex items-center gap-2"><input type="checkbox" checked={form.read_only} onChange={(event) => setForm((old) => ({ ...old, read_only: event.target.checked }))}/><span className="text-sm font-semibold">Read-only access</span></label>
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setRequestOpen(false)}>Cancel</Button><Button type="submit" disabled={loading || !form.patient || form.reason.trim().length < 20}>Submit for approval</Button></div>
    </form></Modal>

    <Modal open={Boolean(decision)} onClose={() => setDecision(null)} title={`${labelize(decisionForm.action)} access request`}><form onSubmit={decide} className="space-y-4">
      {decision ? <Alert tone="warning">Patient: {decision.patient_name}. Requester: {decision.requester_name}. Decision is permanently audited.</Alert> : null}
      <Select label="Decision" value={decisionForm.action} onChange={(event) => setDecisionForm((old) => ({ ...old, action: event.target.value }))}><option value="approve">Approve</option><option value="reject">Reject</option><option value="revoke">Revoke</option><option value="review">Mark reviewed</option></Select>
      {decisionForm.action === 'approve' ? <Input label="Duration in minutes" type="number" min="5" max="60" value={decisionForm.duration_minutes} onChange={(event) => setDecisionForm((old) => ({ ...old, duration_minutes: Number(event.target.value) }))}/> : null}
      <Textarea label="Decision notes" value={decisionForm.notes} onChange={(event) => setDecisionForm((old) => ({ ...old, notes: event.target.value }))} required={decisionForm.action !== 'approve'}/>
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setDecision(null)}>Cancel</Button><Button type="submit" variant={decisionForm.action === 'reject' || decisionForm.action === 'revoke' ? 'danger' : 'primary'} disabled={loading}>Record decision</Button></div>
    </form></Modal>
  </div>
}
