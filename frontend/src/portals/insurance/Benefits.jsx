import { useEffect, useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Table, Textarea } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

const emptyRule = {
  service_code: '', service_category: '', description: '', coverage_percent: '',
  annual_limit: 0, per_visit_limit: 0, copay_percent: '', copay_fixed: 0,
  waiting_period_days: 0, requires_preauthorization: false, excluded: false, active: true,
}

export default function Benefits() {
  const { data: policies, loading, error } = useApi(() => servicesApi.policies())
  const [policyId, setPolicyId] = useState('')
  const [rules, setRules] = useState([])
  const [loadingRules, setLoadingRules] = useState(false)
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyRule)
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!policyId && policies?.length) setPolicyId(String(policies[0].id))
  }, [policies, policyId])

  const loadRules = async () => {
    if (!policyId) return setRules([])
    setLoadingRules(true)
    try {
      const { data } = await servicesApi.policyBenefits(policyId)
      setRules(data || [])
    } catch (err) {
      alert(errMsg(err))
      setRules([])
    } finally {
      setLoadingRules(false)
    }
  }

  useEffect(() => { loadRules() }, [policyId]) // eslint-disable-line react-hooks/exhaustive-deps

  const set = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm((current) => ({ ...current, [key]: value }))
  }

  const openRule = (rule = null) => {
    setForm(rule ? { ...emptyRule, ...rule } : emptyRule)
    setSaveError('')
    setModal(rule ? { editing: rule } : {})
  }

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError('')
    const payload = {
      ...form,
      coverage_percent: form.coverage_percent === '' ? null : Number(form.coverage_percent),
      copay_percent: form.copay_percent === '' ? null : Number(form.copay_percent),
      annual_limit: Number(form.annual_limit || 0),
      per_visit_limit: Number(form.per_visit_limit || 0),
      copay_fixed: Number(form.copay_fixed || 0),
      waiting_period_days: Number(form.waiting_period_days || 0),
    }
    try {
      if (modal.editing) await servicesApi.updatePolicyBenefit(modal.editing.id, payload)
      else await servicesApi.savePolicyBenefit(policyId, payload)
      setModal(null)
      loadRules()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const deactivate = async (rule) => {
    if (!window.confirm(`Deactivate the ${rule.service_category} benefit?`)) return
    try {
      await servicesApi.deletePolicyBenefit(rule.id)
      loadRules()
    } catch (err) {
      alert(errMsg(err))
    }
  }

  const selected = policies?.find((policy) => String(policy.id) === String(policyId))

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <Card title="Benefit rule engine" subtitle="Define covered service categories, limits, cost sharing, exclusions and preauthorization triggers.">
          <div className="flex flex-col md:flex-row md:items-end gap-4">
            <div className="flex-1 max-w-xl">
              <Select label="Policy" value={policyId} onChange={(event) => setPolicyId(event.target.value)}>
                {(policies || []).map((policy) => <option key={policy.id} value={policy.id}>{policy.name}</option>)}
              </Select>
            </div>
            <Button onClick={() => openRule()} disabled={!policyId}>+ Add benefit rule</Button>
          </div>
          {selected && (
            <div className="mt-5 grid grid-cols-2 lg:grid-cols-4 gap-3">
              <div className="rounded-xl border border-slate-200 p-3"><div className="text-xs text-slate-500">Default coverage</div><div className="text-lg font-semibold">{selected.coverage_percent}%</div></div>
              <div className="rounded-xl border border-slate-200 p-3"><div className="text-xs text-slate-500">Annual limit</div><div className="text-lg font-semibold">{selected.annual_limit ? money(selected.annual_limit) : 'Unlimited'}</div></div>
              <div className="rounded-xl border border-slate-200 p-3"><div className="text-xs text-slate-500">Default copay</div><div className="text-lg font-semibold">{selected.copay_percent}%</div></div>
              <div className="rounded-xl border border-slate-200 p-3"><div className="text-xs text-slate-500">Authorization</div><div className="text-lg font-semibold">{selected.requires_preauthorization ? 'Required' : 'Rule based'}</div></div>
            </div>
          )}
        </Card>

        <Card title="Configured benefits" actions={loadingRules ? <Badge color="blue">Loading…</Badge> : <Badge>{rules.length} rules</Badge>}>
          <Table
            empty="No benefit rules are configured for this policy."
            columns={[
              { key: 'service_category', label: 'Service', render: (r) => <div><div className="font-semibold text-slate-800 capitalize">{r.service_category}</div><div className="text-xs text-slate-500">{r.service_code || 'All services in category'}</div></div> },
              { key: 'coverage_percent', label: 'Coverage', render: (r) => r.excluded ? <Badge color="red">Excluded</Badge> : <Badge color="blue">{r.coverage_percent ?? selected?.coverage_percent ?? 0}%</Badge> },
              { key: 'per_visit_limit', label: 'Per visit', render: (r) => r.per_visit_limit ? money(r.per_visit_limit) : 'No limit' },
              { key: 'annual_limit', label: 'Annual', render: (r) => r.annual_limit ? money(r.annual_limit) : 'Policy limit' },
              { key: 'cost_share', label: 'Cost share', render: (r) => <span className="text-xs">{r.copay_percent ?? selected?.copay_percent ?? 0}% + {money(r.copay_fixed)}</span> },
              { key: 'requires_preauthorization', label: 'Preauth', render: (r) => <StatusBadge status={r.requires_preauthorization ? 'required' : 'not_required'} /> },
              { key: 'active', label: 'Status', render: (r) => <StatusBadge status={r.active ? 'active' : 'inactive'} /> },
              { key: 'actions', label: '', render: (r) => <div className="flex gap-2 justify-end"><Button variant="outline" onClick={() => openRule(r)}>Edit</Button>{r.active && <Button variant="danger" onClick={() => deactivate(r)}>Deactivate</Button>}</div> },
            ]}
            rows={rules}
          />
        </Card>
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit benefit rule' : 'Add benefit rule'} wide>
        <form onSubmit={save} className="space-y-5">
          <ErrorNote error={saveError} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Service category" value={form.service_category} onChange={set('service_category')} placeholder="consultation, laboratory, inpatient…" required />
            <Input label="Service code" value={form.service_code} onChange={set('service_code')} placeholder="Optional exact code" />
            <Input label="Coverage override (%)" type="number" min="0" max="100" value={form.coverage_percent} onChange={set('coverage_percent')} placeholder="Use policy default" />
            <Input label="Per-visit limit (UGX)" type="number" min="0" value={form.per_visit_limit} onChange={set('per_visit_limit')} />
            <Input label="Annual limit (UGX)" type="number" min="0" value={form.annual_limit} onChange={set('annual_limit')} />
            <Input label="Copay override (%)" type="number" min="0" max="100" value={form.copay_percent} onChange={set('copay_percent')} placeholder="Use policy default" />
            <Input label="Fixed copay (UGX)" type="number" min="0" value={form.copay_fixed} onChange={set('copay_fixed')} />
            <Input label="Waiting period (days)" type="number" min="0" value={form.waiting_period_days} onChange={set('waiting_period_days')} />
          </div>
          <Textarea label="Rule description" rows={3} value={form.description} onChange={set('description')} />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 rounded-xl bg-slate-50 border border-slate-200 p-4">
            <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={form.requires_preauthorization} onChange={set('requires_preauthorization')} /> Preauthorization</label>
            <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={form.excluded} onChange={set('excluded')} /> Excluded service</label>
            <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={form.active} onChange={set('active')} /> Active rule</label>
          </div>
          <div className="flex justify-end gap-2"><Button variant="outline" type="button" onClick={() => setModal(null)}>Cancel</Button><Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save benefit'}</Button></div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
