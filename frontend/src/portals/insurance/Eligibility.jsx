import { useEffect, useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Select, Stat, Table } from '../../components/ui'
import { errMsg, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

export default function Eligibility() {
  const { data: history, loading, error, reload } = useApi(() => servicesApi.eligibilityHistory())
  const { data: insurers } = useApi(() => servicesApi.providers('insurers'))
  const [form, setForm] = useState({ provider_id: '', member_id: '', service_code: '', service_category: '', estimated_amount: '' })
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!form.provider_id && insurers?.length) setForm((current) => ({ ...current, provider_id: String(insurers[0].id) }))
  }, [insurers, form.provider_id])

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))

  const check = async (event) => {
    event.preventDefault()
    setChecking(true)
    setResult(null)
    try {
      const { data } = await servicesApi.verifyCoverage({ ...form, estimated_amount: Number(form.estimated_amount || 0) })
      setResult(data)
      reload()
    } catch (error) {
      setResult({ error: errMsg(error) })
    } finally {
      setChecking(false)
    }
  }

  const eligible = (history || []).filter((item) => item.result === 'eligible').length
  const preauth = (history || []).filter((item) => item.requires_preauthorization).length

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Stat label="Eligibility checks" value={(history || []).length} icon="shield" />
          <Stat label="Eligible" value={eligible} icon="activity" tone="text-emerald-600" />
          <Stat label="Preauthorization required" value={preauth} icon="file" tone="text-amber-600" />
        </div>

        <Card title="Real-time eligibility check" subtitle="Validate membership, benefit rules, waiting periods, annual limits, deductibles and copays before service delivery.">
          <form onSubmit={check} className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4 items-end">
            <Select label="Insurer" value={form.provider_id} onChange={set('provider_id')} required>
              <option value="">Select insurer</option>
              {(insurers || []).map((item) => <option key={item.id} value={item.id}>{item.org_name}</option>)}
            </Select>
            <Input label="Member ID" value={form.member_id} onChange={set('member_id')} placeholder="SH-0001026" required />
            <Input label="Service code" value={form.service_code} onChange={set('service_code')} placeholder="CONSULT" />
            <Input label="Service category" value={form.service_category} onChange={set('service_category')} placeholder="consultation" />
            <div className="space-y-2">
              <Input label="Estimated amount (UGX)" type="number" min="0" value={form.estimated_amount} onChange={set('estimated_amount')} />
              <Button type="submit" disabled={checking} className="w-full">{checking ? 'Checking…' : 'Check eligibility'}</Button>
            </div>
          </form>

          {result && (
            <div className={`mt-5 rounded-2xl border p-5 ${result.error || !result.valid ? 'border-rose-200 bg-rose-50' : 'border-emerald-200 bg-emerald-50'}`}>
              {result.error ? <p className="text-sm text-rose-700">{result.error}</p> : (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-3"><StatusBadge status={result.result} /><span className="font-semibold text-slate-800">{result.policy || result.policy_name || 'Coverage decision'}</span></div>
                  <p className="text-sm text-slate-600">{result.reason}</p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div><div className="text-xs text-slate-500">Coverage</div><div className="font-semibold">{result.coverage_percent || 0}%</div></div>
                    <div><div className="text-xs text-slate-500">Covered amount</div><div className="font-semibold">{money(result.covered_amount)}</div></div>
                    <div><div className="text-xs text-slate-500">Patient responsibility</div><div className="font-semibold">{money(result.patient_responsibility)}</div></div>
                    <div><div className="text-xs text-slate-500">Preauthorization</div><Badge color={result.requires_preauthorization ? 'yellow' : 'green'}>{result.requires_preauthorization ? 'Required' : 'Not required'}</Badge></div>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>

        <Card title="Eligibility decision history" subtitle="Every decision stores the rule snapshot used at the time of care.">
          <Table
            empty="No eligibility checks have been recorded."
            columns={[
              { key: 'checked_at', label: 'Checked', render: (row) => new Date(row.checked_at).toLocaleString() },
              { key: 'member_id', label: 'Member' },
              { key: 'patient_name', label: 'Patient', render: (row) => row.patient_name || 'Not matched' },
              { key: 'service_category', label: 'Service', render: (row) => <div><div className="capitalize">{row.service_category || 'General'}</div><div className="text-xs text-slate-500">{row.service_code || '—'}</div></div> },
              { key: 'estimated_amount', label: 'Estimate', render: (row) => money(row.estimated_amount) },
              { key: 'covered_amount', label: 'Covered', render: (row) => money(row.covered_amount) },
              { key: 'result', label: 'Decision', render: (row) => <StatusBadge status={row.result} /> },
              { key: 'requires_preauthorization', label: 'Preauth', render: (row) => row.requires_preauthorization ? <Badge color="yellow">Required</Badge> : <Badge color="green">No</Badge> },
            ]}
            rows={history || []}
          />
        </Card>
      </div>
    </LoadingOrError>
  )
}
