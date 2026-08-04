import { useMemo, useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Stat, Table, Textarea } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

const decisionActions = [
  ['start_review', 'Start review'],
  ['query', 'Request information'],
  ['approve', 'Approve in full'],
  ['partial', 'Partially approve'],
  ['reject', 'Reject'],
  ['cancel', 'Cancel'],
  ['mark_paid', 'Record remittance'],
]

export default function Claims() {
  const [filters, setFilters] = useState({ status: '', search: '' })
  const { data: claims, loading, error, reload } = useApi(() => servicesApi.claimsManage(filters), [filters.status, filters.search])
  const [selected, setSelected] = useState(null)
  const [form, setForm] = useState({ action: 'start_review', approved_amount: '', reason: '', paid_amount: '', payment_reference: '', remittance_number: '', paid_on: '' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const stats = useMemo(() => {
    const list = claims || []
    return {
      awaiting: list.filter((claim) => ['submitted', 'in_review', 'query'].includes(claim.status)).length,
      approved: list.filter((claim) => ['approved', 'partially_approved', 'paid'].includes(claim.status)).reduce((sum, claim) => sum + Number(claim.approved_amount || 0), 0),
      paid: list.filter((claim) => claim.status === 'paid').reduce((sum, claim) => sum + Number(claim.approved_amount || 0), 0),
      total: list.length,
    }
  }, [claims])

  const openReview = (claim) => {
    setSelected(claim)
    const action = claim.status === 'submitted' ? 'start_review' : ['approved', 'partially_approved'].includes(claim.status) ? 'mark_paid' : 'approve'
    setForm({
      action,
      approved_amount: claim.approved_amount || claim.amount,
      reason: claim.decision_reason || '',
      paid_amount: claim.approved_amount || '',
      payment_reference: '',
      remittance_number: '',
      paid_on: '',
    })
    setSaveError('')
  }

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))

  const apply = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError('')
    const payload = {
      action: form.action,
      reason: form.reason,
      approved_amount: Number(form.approved_amount || 0),
    }
    if (form.action === 'mark_paid') {
      Object.assign(payload, {
        paid_amount: Number(form.paid_amount || 0),
        payment_reference: form.payment_reference,
        remittance_number: form.remittance_number,
        paid_on: form.paid_on || undefined,
      })
    }
    try {
      await servicesApi.decideClaim(selected.id, payload)
      setSelected(null)
      reload()
    } catch (error) {
      setSaveError(errMsg(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <Stat label="Claims in view" value={stats.total} icon="file" />
          <Stat label="Awaiting adjudication" value={stats.awaiting} icon="activity" tone="text-amber-600" />
          <Stat label="Approved value" value={money(stats.approved)} icon="shield" tone="text-emerald-600" />
          <Stat label="Paid value" value={money(stats.paid)} icon="money" tone="text-emerald-600" />
        </div>

        <Card title="Claims adjudication" subtitle="Review claim lines, clinical context, authorization and financial responsibility.">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            <Select label="Status" value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
              <option value="">All statuses</option>
              {['submitted', 'in_review', 'query', 'partially_approved', 'approved', 'rejected', 'paid', 'cancelled'].map((status) => <option key={status} value={status}>{status.replace(/_/g, ' ')}</option>)}
            </Select>
            <div className="md:col-span-2"><Input label="Search claim number or patient" value={filters.search} onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))} placeholder="CLM-… or member name" /></div>
          </div>
          <Table
            empty="No claims match the current filters."
            columns={[
              { key: 'claim_number', label: 'Claim', render: (c) => <div><div className="font-semibold text-slate-800">{c.claim_number || `#${c.id}`}</div><div className="text-xs text-slate-500">{new Date(c.created_at).toLocaleDateString()}</div></div> },
              { key: 'patient_name', label: 'Patient' },
              { key: 'invoice_number', label: 'Invoice', render: (c) => c.invoice_number || 'Direct claim' },
              { key: 'policy_name', label: 'Policy' },
              { key: 'amount', label: 'Requested', render: (c) => money(c.amount) },
              { key: 'approved_amount', label: 'Approved', render: (c) => money(c.approved_amount) },
              { key: 'patient_responsibility', label: 'Patient share', render: (c) => money(c.patient_responsibility) },
              { key: 'status', label: 'Status', render: (c) => <StatusBadge status={c.status} /> },
              { key: 'actions', label: '', render: (c) => <Button variant="outline" onClick={() => openReview(c)}>Open</Button> },
            ]}
            rows={claims || []}
          />
        </Card>
      </div>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={selected?.claim_number || 'Claim review'} wide>
        {selected && <form onSubmit={apply} className="space-y-5">
          <ErrorNote error={saveError} />
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div><div className="text-xs text-slate-500">Patient</div><div className="font-semibold">{selected.patient_name}</div></div>
            <div><div className="text-xs text-slate-500">Policy</div><div className="font-semibold">{selected.policy_name}</div></div>
            <div><div className="text-xs text-slate-500">Requested</div><div className="font-semibold">{money(selected.amount)}</div></div>
            <div><div className="text-xs text-slate-500">Status</div><StatusBadge status={selected.status} /></div>
          </div>

          {(selected.diagnosis_code || selected.clinical_summary) && <div className="rounded-xl border border-slate-200 p-4"><div className="text-xs uppercase tracking-wide font-semibold text-slate-500">Clinical context</div><p className="text-sm text-slate-700 mt-2">{selected.diagnosis_code && <Badge color="blue">{selected.diagnosis_code}</Badge>} {selected.clinical_summary}</p></div>}

          <div>
            <div className="text-sm font-semibold text-slate-800 mb-2">Claim line items</div>
            <Table
              empty="No claim line items."
              columns={[
                { key: 'description', label: 'Service' },
                { key: 'service_code', label: 'Code', render: (item) => item.service_code || '—' },
                { key: 'requested_amount', label: 'Requested', render: (item) => money(item.requested_amount) },
                { key: 'approved_amount', label: 'Approved', render: (item) => money(item.approved_amount) },
                { key: 'status', label: 'Decision', render: (item) => <StatusBadge status={item.status} /> },
              ]}
              rows={selected.items || []}
            />
          </div>

          <Select label="Workflow action" value={form.action} onChange={set('action')}>
            {decisionActions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>

          {form.action === 'mark_paid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="Amount remitted (UGX)" type="number" min="1" max={selected.approved_amount} value={form.paid_amount} onChange={set('paid_amount')} required />
              <Input label="Payment reference" value={form.payment_reference} onChange={set('payment_reference')} required />
              <Input label="Remittance number" value={form.remittance_number} onChange={set('remittance_number')} placeholder="Generated if blank" />
              <Input label="Paid on" type="date" value={form.paid_on} onChange={set('paid_on')} />
            </div>
          ) : (
            <Input label="Approved amount (UGX)" type="number" min="0" max={selected.amount} value={form.approved_amount} onChange={set('approved_amount')} />
          )}

          <Textarea label={form.action === 'query' ? 'Information required' : 'Decision reason / notes'} rows={4} value={form.reason} onChange={set('reason')} />

          {selected.remittances?.length > 0 && <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4"><div className="font-semibold text-emerald-800 mb-2">Recorded remittances</div>{selected.remittances.map((remittance) => <div key={remittance.id} className="text-sm text-emerald-700 flex justify-between gap-4"><span>{remittance.remittance_number} · {remittance.payment_reference}</span><span>{money(remittance.paid_amount)}</span></div>)}</div>}

          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setSelected(null)}>Close</Button><Button type="submit" disabled={saving}>{saving ? 'Applying…' : 'Apply action'}</Button></div>
        </form>}
      </Modal>
    </LoadingOrError>
  )
}
