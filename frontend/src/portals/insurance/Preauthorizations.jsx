import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Stat, Table, Textarea } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

const actions = [
  ['start_review', 'Start review'], ['query', 'Request information'], ['approve', 'Approve'],
  ['partial', 'Partially approve'], ['reject', 'Reject'], ['cancel', 'Cancel'],
]

export default function Preauthorizations() {
  const { data: rows, loading, error, reload } = useApi(() => servicesApi.preauthorizations())
  const { data: coverage } = useApi(() => servicesApi.myCoverage())
  const [requestOpen, setRequestOpen] = useState(false)
  const [decision, setDecision] = useState(null)
  const [form, setForm] = useState({ coverage_id: '', service_code: '', service_name: '', clinical_indication: '', diagnosis_code: '', requested_amount: '' })
  const [decisionForm, setDecisionForm] = useState({ action: 'start_review', approved_amount: '', valid_until: '', reason: '' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))
  const setDecisionValue = (key) => (event) => setDecisionForm((current) => ({ ...current, [key]: event.target.value }))

  const submitRequest = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      await servicesApi.requestPreauthorization({ ...form, requested_amount: Number(form.requested_amount || 0) })
      setRequestOpen(false)
      setForm({ coverage_id: '', service_code: '', service_name: '', clinical_indication: '', diagnosis_code: '', requested_amount: '' })
      reload()
    } catch (error) {
      setSaveError(errMsg(error))
    } finally {
      setSaving(false)
    }
  }

  const openDecision = (row) => {
    setDecision(row)
    setDecisionForm({ action: row.status === 'submitted' ? 'start_review' : 'approve', approved_amount: row.requested_amount, valid_until: '', reason: '' })
    setSaveError('')
  }

  const decide = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      await servicesApi.decidePreauthorization(decision.id, {
        ...decisionForm,
        approved_amount: Number(decisionForm.approved_amount || 0),
      })
      setDecision(null)
      reload()
    } catch (error) {
      setSaveError(errMsg(error))
    } finally {
      setSaving(false)
    }
  }

  const pending = (rows || []).filter((row) => ['submitted', 'in_review', 'query'].includes(row.status)).length
  const approved = (rows || []).filter((row) => ['approved', 'partially_approved'].includes(row.status)).length
  const value = (rows || []).filter((row) => ['approved', 'partially_approved'].includes(row.status)).reduce((sum, row) => sum + Number(row.approved_amount || 0), 0)

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Stat label="Awaiting action" value={pending} icon="file" tone="text-amber-600" />
          <Stat label="Approved requests" value={approved} icon="shield" tone="text-emerald-600" />
          <Stat label="Authorized value" value={money(value)} icon="money" tone="text-emerald-600" />
        </div>
        <Card
          title="Preauthorization work queue"
          subtitle="Review medical necessity, benefit limits and requested services before treatment."
          actions={<Button onClick={() => { setRequestOpen(true); setSaveError('') }}>+ New request</Button>}
        >
          <Table
            empty="No preauthorization requests."
            columns={[
              { key: 'authorization_number', label: 'Authorization', render: (r) => <div><div className="font-semibold text-slate-800">{r.authorization_number}</div><div className="text-xs text-slate-500">{new Date(r.created_at).toLocaleDateString()}</div></div> },
              { key: 'patient_name', label: 'Member' },
              { key: 'service_name', label: 'Service', render: (r) => <div><div className="font-medium">{r.service_name}</div><div className="text-xs text-slate-500">{r.service_code || r.diagnosis_code || '—'}</div></div> },
              { key: 'policy_name', label: 'Policy' },
              { key: 'requested_amount', label: 'Requested', render: (r) => money(r.requested_amount) },
              { key: 'approved_amount', label: 'Approved', render: (r) => money(r.approved_amount) },
              { key: 'status', label: 'Status', render: (r) => <StatusBadge status={r.status} /> },
              { key: 'valid_until', label: 'Valid until', render: (r) => r.valid_until || '—' },
              { key: 'action', label: '', render: (r) => <Button variant="outline" onClick={() => openDecision(r)}>Review</Button> },
            ]}
            rows={rows || []}
          />
        </Card>
      </div>

      <Modal open={requestOpen} onClose={() => setRequestOpen(false)} title="Submit preauthorization request" wide>
        <form onSubmit={submitRequest} className="space-y-4">
          <ErrorNote error={saveError} />
          <Select label="Member coverage" value={form.coverage_id} onChange={set('coverage_id')} required>
            <option value="">Select enrolled member</option>
            {(coverage || []).map((item) => <option key={item.id} value={item.id}>{item.patient_name} — {item.member_id} — {item.policy_name}</option>)}
          </Select>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Service name" value={form.service_name} onChange={set('service_name')} required />
            <Input label="Service code" value={form.service_code} onChange={set('service_code')} />
            <Input label="Diagnosis code" value={form.diagnosis_code} onChange={set('diagnosis_code')} />
            <Input label="Requested amount (UGX)" type="number" min="0" value={form.requested_amount} onChange={set('requested_amount')} required />
          </div>
          <Textarea label="Clinical indication" rows={4} value={form.clinical_indication} onChange={set('clinical_indication')} required />
          <div className="flex justify-end gap-2"><Button variant="outline" type="button" onClick={() => setRequestOpen(false)}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Submitting…' : 'Submit request'}</Button></div>
        </form>
      </Modal>

      <Modal open={!!decision} onClose={() => setDecision(null)} title={`Review ${decision?.authorization_number || ''}`} wide>
        {decision && <form onSubmit={decide} className="space-y-5">
          <ErrorNote error={saveError} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div><div className="text-xs text-slate-500">Member</div><div className="font-semibold">{decision.patient_name}</div></div>
            <div><div className="text-xs text-slate-500">Requested</div><div className="font-semibold">{money(decision.requested_amount)}</div></div>
            <div><div className="text-xs text-slate-500">Current status</div><StatusBadge status={decision.status} /></div>
          </div>
          <p className="text-sm text-slate-600"><strong>{decision.service_name}</strong><br />{decision.clinical_indication || 'No clinical indication supplied.'}</p>
          <Select label="Decision" value={decisionForm.action} onChange={setDecisionValue('action')}>
            {actions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Approved amount (UGX)" type="number" min="0" max={decision.requested_amount} value={decisionForm.approved_amount} onChange={setDecisionValue('approved_amount')} />
            <Input label="Valid until" type="date" value={decisionForm.valid_until} onChange={setDecisionValue('valid_until')} />
          </div>
          <Textarea label="Decision reason / request for information" rows={4} value={decisionForm.reason} onChange={setDecisionValue('reason')} />
          <div className="flex justify-end gap-2"><Button variant="outline" type="button" onClick={() => setDecision(null)}>Close</Button><Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Apply decision'}</Button></div>
        </form>}
      </Modal>
    </LoadingOrError>
  )
}
