import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Table, Textarea } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

const emptyForm = {
  name: '', coverage_percent: 80, premium: 0, annual_limit: 0, deductible: 0,
  copay_percent: 0, copay_fixed: 0, waiting_period_days: 0,
  requires_preauthorization: false, network_only: false, active: true,
  description: '', exclusions: '', terms_url: '',
}

const numeric = ['coverage_percent', 'premium', 'annual_limit', 'deductible', 'copay_percent', 'copay_fixed', 'waiting_period_days']

export default function Policies() {
  const { data: policies, loading, error, reload } = useApi(() => servicesApi.policies())
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const openAdd = () => {
    setForm(emptyForm)
    setSaveError('')
    setModal({})
  }

  const openEdit = (p) => {
    setForm({ ...emptyForm, ...p })
    setSaveError('')
    setModal({ editing: p })
  }

  const set = (key) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
    setForm((current) => ({ ...current, [key]: value }))
  }

  const save = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const payload = { ...form }
      numeric.forEach((key) => { payload[key] = Number(payload[key] || 0) })
      if (modal.editing) await servicesApi.updatePolicy(modal.editing.id, payload)
      else await servicesApi.savePolicy(payload)
      setModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const deactivate = async (policy) => {
    if (!window.confirm(`Deactivate “${policy.name}”? Existing claims remain available.`)) return
    try {
      await servicesApi.updatePolicy(policy.id, { active: false })
      reload()
    } catch (err) {
      alert(errMsg(err))
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <Card
          title="Insurance products"
          subtitle="Configure premiums, deductibles, copays, benefit limits and authorization rules."
          actions={<Button onClick={openAdd}>+ Add policy</Button>}
        >
          <Table
            empty="No insurance policies are configured."
            columns={[
              {
                key: 'name', label: 'Policy', render: (p) => (
                  <div>
                    <div className="font-semibold text-slate-800">{p.name}</div>
                    <div className="text-xs text-slate-500 mt-1 max-w-xs line-clamp-2">{p.description || 'No description'}</div>
                  </div>
                ),
              },
              { key: 'coverage_percent', label: 'Coverage', render: (p) => <Badge color="blue">{p.coverage_percent}%</Badge> },
              { key: 'premium', label: 'Premium', render: (p) => money(p.premium) },
              { key: 'annual_limit', label: 'Annual limit', render: (p) => p.annual_limit ? money(p.annual_limit) : 'Unlimited' },
              {
                key: 'cost_share', label: 'Member cost share', render: (p) => (
                  <div className="text-xs text-slate-600 space-y-1">
                    <div>Deductible: {money(p.deductible)}</div>
                    <div>Copay: {p.copay_percent}% + {money(p.copay_fixed)}</div>
                  </div>
                ),
              },
              { key: 'benefits', label: 'Benefits', render: (p) => <Badge>{p.benefit_rules?.length || 0} rules</Badge> },
              { key: 'active', label: 'Status', render: (p) => <StatusBadge status={p.active ? 'active' : 'inactive'} /> },
              {
                key: 'actions', label: '', render: (p) => (
                  <div className="flex flex-wrap gap-2 justify-end">
                    <Button variant="outline" onClick={() => openEdit(p)}>Edit</Button>
                    {p.active && <Button variant="danger" onClick={() => deactivate(p)}>Deactivate</Button>}
                  </div>
                ),
              },
            ]}
            rows={policies || []}
          />
        </Card>
      </div>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit insurance policy' : 'Create insurance policy'} wide>
        <form onSubmit={save} className="space-y-5">
          <ErrorNote error={saveError} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Policy name" value={form.name} onChange={set('name')} required />
            <Input label="Monthly premium (UGX)" type="number" min="0" value={form.premium} onChange={set('premium')} required />
            <Input label="Default coverage (%)" type="number" min="0" max="100" value={form.coverage_percent} onChange={set('coverage_percent')} required />
            <Input label="Annual benefit limit (UGX, 0 = unlimited)" type="number" min="0" value={form.annual_limit} onChange={set('annual_limit')} />
            <Input label="Deductible (UGX)" type="number" min="0" value={form.deductible} onChange={set('deductible')} />
            <Input label="Copay (%)" type="number" min="0" max="100" value={form.copay_percent} onChange={set('copay_percent')} />
            <Input label="Fixed copay (UGX)" type="number" min="0" value={form.copay_fixed} onChange={set('copay_fixed')} />
            <Input label="Waiting period (days)" type="number" min="0" value={form.waiting_period_days} onChange={set('waiting_period_days')} />
            <Input label="Terms URL" type="url" value={form.terms_url} onChange={set('terms_url')} placeholder="https://…" />
          </div>
          <Textarea label="Description" rows={3} value={form.description} onChange={set('description')} />
          <Textarea label="Exclusions" rows={3} value={form.exclusions} onChange={set('exclusions')} />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 rounded-xl bg-slate-50 border border-slate-200 p-4">
            <label className="flex items-center gap-3 text-sm font-medium text-slate-700"><input type="checkbox" checked={form.requires_preauthorization} onChange={set('requires_preauthorization')} /> Preauthorization required</label>
            <label className="flex items-center gap-3 text-sm font-medium text-slate-700"><input type="checkbox" checked={form.network_only} onChange={set('network_only')} /> Network providers only</label>
            <label className="flex items-center gap-3 text-sm font-medium text-slate-700"><input type="checkbox" checked={form.active} onChange={set('active')} /> Active product</label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(null)}>Cancel</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save policy'}</Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
