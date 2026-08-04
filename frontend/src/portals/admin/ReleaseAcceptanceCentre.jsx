import { useEffect, useMemo, useState } from 'react'
import { journeyApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Badge, Button, Card, EmptyState, Input, Modal, Select, Spinner, Textarea } from '../../components/ui'
import HealthIcon from '../../components/icons/HealthIcon'

const GATES = [
  ['doctor_workflow', 'Doctor workflow acceptance'],
  ['nursing_workflow', 'Nursing and midwifery acceptance'],
  ['laboratory_workflow', 'Laboratory acceptance'],
  ['pharmacy_workflow', 'Pharmacy acceptance'],
  ['finance_workflow', 'Finance acceptance'],
  ['records_workflow', 'Medical records acceptance'],
  ['admin_workflow', 'Administrator acceptance'],
  ['privacy_legal', 'Privacy and legal approval'],
  ['clinical_safety', 'Clinical safety approval'],
  ['security', 'Security approval'],
  ['backup_restore', 'Backup and restore evidence'],
  ['disaster_recovery', 'Disaster recovery approval'],
]

const labelize = (value = '') => String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
const errorText = (error) => {
  const data = error?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (data && typeof data === 'object') return Object.entries(data).map(([key, value]) => `${labelize(key)}: ${Array.isArray(value) ? value.join(' ') : value}`).join(' ')
  return error?.message || 'Release acceptance operation failed.'
}
const tone = (status) => status === 'accepted' ? 'green' : status === 'rejected' ? 'red' : status === 'expired' ? 'orange' : 'yellow'

const emptyForm = (user, releaseVersion, environment, acceptanceType = 'doctor_workflow') => ({
  release_version: releaseVersion,
  environment,
  acceptance_type: acceptanceType,
  status: 'pending',
  reviewer_name: user?.display_name || '',
  reviewer_title: '',
  reviewer_email: user?.email || '',
  statement: '',
  expires_at: '',
  evidence: null,
})

export default function ReleaseAcceptanceCentre() {
  const { user, activeRole } = useAuth()
  const [releaseVersion, setReleaseVersion] = useState(import.meta.env.VITE_RELEASE_VERSION || '2026.08')
  const [environment, setEnvironment] = useState('production')
  const [readiness, setReadiness] = useState(null)
  const [records, setRecords] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(() => emptyForm(user, releaseVersion, environment))

  const byType = useMemo(() => Object.fromEntries(records.map((row) => [row.acceptance_type, row])), [records])
  const accepted = readiness?.gates?.filter((gate) => gate.accepted).length || 0

  const load = async () => {
    if (!releaseVersion.trim()) return
    setLoading(true); setError('')
    try {
      const [readyResponse, recordsResponse] = await Promise.all([
        journeyApi.productionReadiness({ release_version: releaseVersion.trim(), environment }),
        journeyApi.releaseAcceptances({ release_version: releaseVersion.trim(), environment }),
      ])
      setReadiness(readyResponse.data)
      setRecords(recordsResponse.data?.results || recordsResponse.data || [])
    } catch (err) { setError(errorText(err)) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const openGate = (acceptanceType) => {
    const existing = byType[acceptanceType]
    setEditing(existing || { acceptance_type: acceptanceType })
    setForm(existing ? {
      release_version: existing.release_version,
      environment: existing.environment,
      acceptance_type: existing.acceptance_type,
      status: existing.status,
      reviewer_name: existing.reviewer_name || user?.display_name || '',
      reviewer_title: existing.reviewer_title || '',
      reviewer_email: existing.reviewer_email || user?.email || '',
      statement: existing.statement || '',
      expires_at: existing.expires_at ? String(existing.expires_at).slice(0, 16) : '',
      evidence: null,
    } : emptyForm(user, releaseVersion, environment, acceptanceType))
  }

  const submit = async (event) => {
    event.preventDefault(); setLoading(true); setError(''); setSuccess('')
    try {
      const payload = new FormData()
      Object.entries(form).forEach(([key, value]) => {
        if (key === 'evidence') { if (value) payload.append(key, value); return }
        if (value !== '' && value !== null && value !== undefined) payload.append(key, value)
      })
      const existing = byType[form.acceptance_type]
      if (existing) await journeyApi.updateReleaseAcceptance(existing.id, payload)
      else await journeyApi.createReleaseAcceptance(payload)
      setSuccess(`${GATES.find(([code]) => code === form.acceptance_type)?.[1] || 'Acceptance gate'} was recorded with an audit trail.`)
      setEditing(null)
      await load()
    } catch (err) { setError(errorText(err)); setLoading(false) }
  }

  return <div className="space-y-6" data-testid="release-acceptance-centre">
    {error ? <Alert tone="danger" title="Release gate failed">{error}</Alert> : null}
    {success ? <Alert tone="success">{success}</Alert> : null}

    <Card title="Production release acceptance" subtitle="Technical checks do not replace qualified human and operational sign-off." icon="verified">
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
        <Input label="Release version" value={releaseVersion} onChange={(event) => setReleaseVersion(event.target.value)} placeholder="2026.08"/>
        <Select label="Environment" value={environment} onChange={(event) => setEnvironment(event.target.value)}><option value="production">Production</option><option value="staging">Staging</option><option value="sandbox">Sandbox</option></Select>
        <div className="flex items-end"><Button onClick={load} disabled={loading || !releaseVersion.trim()}><HealthIcon name="refresh" size={16}/> Refresh evidence</Button></div>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl bg-primary-50 p-4"><small className="font-semibold text-primary-700">Accepted gates</small><strong className="mt-2 block text-3xl text-primary-950">{accepted}/{GATES.length}</strong></div>
        <div className={`rounded-2xl p-4 ${readiness?.ready_for_promotion ? 'bg-emerald-50' : 'bg-amber-50'}`}><small className={`font-semibold ${readiness?.ready_for_promotion ? 'text-emerald-700' : 'text-amber-700'}`}>Promotion status</small><strong className="mt-2 block text-xl text-slate-950">{readiness?.ready_for_promotion ? 'Ready' : 'Blocked'}</strong></div>
        <div className="rounded-2xl bg-slate-50 p-4"><small className="font-semibold text-slate-600">Active reviewer role</small><strong className="mt-2 block text-lg text-slate-900">{labelize(activeRole)}</strong></div>
      </div>
      <Alert tone={readiness?.ready_for_promotion ? 'success' : 'warning'} title={readiness?.ready_for_promotion ? 'Formal gates complete' : 'Promotion remains blocked'} className="mt-5">{readiness?.message || 'Select a release version to load its acceptance evidence.'}</Alert>
    </Card>

    <Card title="Required acceptance evidence" subtitle="Only qualified roles can sign each gate. Accepted evidence is hashed and audited." icon="audit">
      {loading && !readiness ? <Spinner label="Loading release gates…"/> : !readiness ? <EmptyState icon="verified" title="No release selected" description="Enter a release version to inspect its production acceptance gates."/> : <div className="grid gap-3 lg:grid-cols-2">{(readiness.gates || []).map((gate) => {
        const row = byType[gate.acceptance_type]
        return <article key={gate.acceptance_type} className="rounded-2xl border border-slate-200 p-4" data-testid={`acceptance-${gate.acceptance_type}`}>
          <div className="flex items-start justify-between gap-4"><div><h3 className="font-semibold text-slate-900">{gate.label}</h3><p className="mt-1 text-xs text-slate-500">{row?.reviewer_name ? `Reviewed by ${row.reviewer_name}` : 'No qualified evidence recorded yet.'}</p></div><Badge color={tone(gate.status)}>{labelize(gate.status)}</Badge></div>
          <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-2"><span>Signed: {gate.signed_at ? new Date(gate.signed_at).toLocaleString() : 'Not signed'}</span><span className="truncate">Hash: {gate.evidence_hash || 'No evidence hash'}</span></div>
          <div className="mt-4 flex justify-end"><Button variant="outline" onClick={() => openGate(gate.acceptance_type)}>{row ? 'Review gate' : 'Record evidence'}</Button></div>
        </article>
      })}</div>}
    </Card>

    <Modal open={Boolean(editing)} onClose={() => setEditing(null)} title="Record release acceptance" wide><form onSubmit={submit} className="space-y-4">
      <Alert tone="warning" title="Human evidence cannot be generated by the application">Upload the actual signed test report, clinical approval, legal opinion, security report, backup exercise, or disaster-recovery evidence. Do not mark a gate accepted until the reviewer has completed the work.</Alert>
      <div className="grid gap-4 sm:grid-cols-2"><Input label="Release version" value={form.release_version} readOnly/><Input label="Environment" value={form.environment} readOnly/></div>
      <Select label="Acceptance gate" value={form.acceptance_type} disabled>{GATES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</Select>
      <div className="grid gap-4 sm:grid-cols-2"><Input label="Reviewer name" value={form.reviewer_name} onChange={(event) => setForm((old) => ({ ...old, reviewer_name: event.target.value }))} required/><Input label="Reviewer title" value={form.reviewer_title} onChange={(event) => setForm((old) => ({ ...old, reviewer_title: event.target.value }))}/><Input label="Reviewer email" type="email" value={form.reviewer_email} onChange={(event) => setForm((old) => ({ ...old, reviewer_email: event.target.value }))}/><Select label="Decision" value={form.status} onChange={(event) => setForm((old) => ({ ...old, status: event.target.value }))}><option value="pending">Pending</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option><option value="expired">Expired</option></Select></div>
      <Textarea label="Acceptance statement" value={form.statement} onChange={(event) => setForm((old) => ({ ...old, statement: event.target.value }))} placeholder="Describe the scope tested, evidence reviewed, limitations, and final decision." required/>
      <div className="grid gap-4 sm:grid-cols-2"><Input label="Evidence file" type="file" onChange={(event) => setForm((old) => ({ ...old, evidence: event.target.files?.[0] || null }))} required={form.status === 'accepted' && !byType[form.acceptance_type]?.evidence}/><Input label="Expires at" type="datetime-local" value={form.expires_at} onChange={(event) => setForm((old) => ({ ...old, expires_at: event.target.value }))}/></div>
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setEditing(null)}>Cancel</Button><Button type="submit" disabled={loading || form.statement.trim().length < 20}>{byType[form.acceptance_type] ? 'Update gate' : 'Record gate'}</Button></div>
    </form></Modal>
  </div>
}
