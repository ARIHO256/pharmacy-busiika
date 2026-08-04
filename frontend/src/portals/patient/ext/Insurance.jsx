import React, { useCallback, useEffect, useState } from 'react'
import client from '../../../api/client'
import { paymentApi, servicesApi } from '../../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../../components/ui'
import { fmtDT, statusColor, ugx } from './helpers'

export default function Insurance() {
  const [tab, setTab] = useState('policies') // policies | coverage | preauthorizations | claims
  const [insurers, setInsurers] = useState([])
  const [policies, setPolicies] = useState(null)
  const [providerFilter, setProviderFilter] = useState('')

  // verify coverage tool
  const [verifyMemberId, setVerifyMemberId] = useState('')
  const [verifyProvider, setVerifyProvider] = useState('')
  const [verifyResult, setVerifyResult] = useState(null)
  const [verifying, setVerifying] = useState(false)

  // my coverage
  const [coverage, setCoverage] = useState(null)
  const [addOpen, setAddOpen] = useState(false)
  const [addProvider, setAddProvider] = useState('')
  const [addPolicy, setAddPolicy] = useState('')
  const [addMemberId, setAddMemberId] = useState('')
  const [providerPolicies, setProviderPolicies] = useState([])
  const [saving, setSaving] = useState(false)

  // claims
  const [claims, setClaims] = useState(null)
  const [claimOpen, setClaimOpen] = useState(false)
  const [claimProvider, setClaimProvider] = useState('')
  const [claimPolicy, setClaimPolicy] = useState('')
  const [claimInvoice, setClaimInvoice] = useState('')
  const [claimAmount, setClaimAmount] = useState('')
  const [claimPolicies, setClaimPolicies] = useState([])
  const [paidInvoices, setPaidInvoices] = useState([])
  const [submitting, setSubmitting] = useState(false)

  // preauthorization
  const [preauthorizations, setPreauthorizations] = useState(null)
  const [preauthOpen, setPreauthOpen] = useState(false)
  const [preauthCoverage, setPreauthCoverage] = useState('')
  const [preauthService, setPreauthService] = useState('')
  const [preauthCode, setPreauthCode] = useState('')
  const [preauthDiagnosis, setPreauthDiagnosis] = useState('')
  const [preauthIndication, setPreauthIndication] = useState('')
  const [preauthAmount, setPreauthAmount] = useState('')

  const [notice, setNotice] = useState(null)

  useEffect(() => {
    servicesApi
      .providers('insurers')
      .then(({ data }) => setInsurers(data))
      .catch(() => {})
  }, [])

  const loadPolicies = useCallback(async () => {
    setPolicies(null)
    try {
      const params = providerFilter ? { provider: providerFilter } : {}
      const { data } = await servicesApi.policies(params)
      setPolicies(data)
    } catch {
      setPolicies([])
    }
  }, [providerFilter])

  useEffect(() => {
    if (tab === 'policies') loadPolicies()
  }, [tab, loadPolicies])

  const loadCoverage = useCallback(async () => {
    setCoverage(null)
    try {
      const { data } = await servicesApi.myCoverage()
      setCoverage(data)
    } catch {
      setCoverage([])
    }
  }, [])

  const loadClaims = useCallback(async () => {
    setClaims(null)
    try {
      const { data } = await servicesApi.myClaims()
      setClaims(data)
    } catch {
      setClaims([])
    }
  }, [])

  const loadPreauthorizations = useCallback(async () => {
    setPreauthorizations(null)
    try {
      const { data } = await servicesApi.preauthorizations()
      setPreauthorizations(data)
    } catch {
      setPreauthorizations([])
    }
  }, [])

  useEffect(() => {
    if (tab === 'coverage') loadCoverage()
    if (tab === 'preauthorizations') {
      loadCoverage()
      loadPreauthorizations()
    }
    if (tab === 'claims') loadClaims()
  }, [tab, loadCoverage, loadClaims, loadPreauthorizations])

  const insurerName = (id) => insurers.find((i) => i.id === id)?.org_name || `Insurer #${id}`

  const verify = async (e) => {
    e.preventDefault()
    setVerifying(true)
    setVerifyResult(null)
    try {
      const { data } = await servicesApi.verifyCoverage({
        member_id: verifyMemberId,
        provider_id: verifyProvider,
      })
      setVerifyResult(data)
    } catch (err) {
      setVerifyResult({ error: err?.response?.data?.detail || 'Verification failed' })
    } finally {
      setVerifying(false)
    }
  }

  const openAddCoverage = async () => {
    setAddOpen(true)
    setAddProvider('')
    setAddPolicy('')
    setAddMemberId('')
    setProviderPolicies([])
  }

  useEffect(() => {
    if (!addProvider) {
      setProviderPolicies([])
      return
    }
    servicesApi
      .policies({ provider: addProvider })
      .then(({ data }) => setProviderPolicies(data))
      .catch(() => setProviderPolicies([]))
  }, [addProvider])

  const saveCoverage = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await client.post('/services/coverage/', {
        provider_id: addProvider,
        policy_id: addPolicy,
        member_id: addMemberId,
      })
      setNotice({ type: 'success', text: 'Coverage added successfully.' })
      setAddOpen(false)
      loadCoverage()
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Failed to add coverage' })
      setAddOpen(false)
    } finally {
      setSaving(false)
    }
  }

  const openClaim = async () => {
    setClaimOpen(true)
    setClaimProvider('')
    setClaimPolicy('')
    setClaimInvoice('')
    setClaimAmount('')
    setClaimPolicies([])
    try {
      const { data } = await paymentApi.invoices()
      setPaidInvoices(data.filter((i) => i.status === 'paid'))
    } catch {
      setPaidInvoices([])
    }
  }

  useEffect(() => {
    if (!claimProvider) {
      setClaimPolicies([])
      return
    }
    servicesApi
      .policies({ provider: claimProvider })
      .then(({ data }) => setClaimPolicies(data))
      .catch(() => setClaimPolicies([]))
  }, [claimProvider])

  const submitClaim = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await servicesApi.submitClaim({
        provider_id: claimProvider,
        policy_id: claimPolicy,
        invoice_id: claimInvoice || null,
        amount: parseInt(claimAmount, 10),
      })
      setNotice({ type: 'success', text: 'Claim submitted successfully.' })
      setClaimOpen(false)
      loadClaims()
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Failed to submit claim' })
      setClaimOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  const openPreauthorization = () => {
    if (coverage === null) loadCoverage()
    setPreauthCoverage('')
    setPreauthService('')
    setPreauthCode('')
    setPreauthDiagnosis('')
    setPreauthIndication('')
    setPreauthAmount('')
    setPreauthOpen(true)
  }

  const submitPreauthorization = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await servicesApi.requestPreauthorization({
        coverage_id: preauthCoverage,
        service_name: preauthService,
        service_code: preauthCode,
        diagnosis_code: preauthDiagnosis,
        clinical_indication: preauthIndication,
        requested_amount: Number(preauthAmount || 0),
      })
      setNotice({ type: 'success', text: 'Preauthorization request submitted.' })
      setPreauthOpen(false)
      loadPreauthorizations()
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Failed to submit preauthorization' })
      setPreauthOpen(false)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      {notice && (
        <div
          className={`rounded-lg px-4 py-3 text-sm flex items-center justify-between ${
            notice.type === 'success'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-rose-50 text-rose-700 border border-rose-200'
          }`}
        >
          <span>{notice.text}</span>
          <button className="ml-3 text-lg leading-none" onClick={() => setNotice(null)}>
            &times;
          </button>
        </div>
      )}

      <div className="flex gap-2">
        <Button
          variant={tab === 'policies' ? 'primary' : 'outline'}
          onClick={() => setTab('policies')}
        >
          Browse Policies
        </Button>
        <Button
          variant={tab === 'coverage' ? 'primary' : 'outline'}
          onClick={() => setTab('coverage')}
        >
          My Coverage
        </Button>
        <Button
          variant={tab === 'preauthorizations' ? 'primary' : 'outline'}
          onClick={() => setTab('preauthorizations')}
        >
          Preauthorizations
        </Button>
        <Button variant={tab === 'claims' ? 'primary' : 'outline'} onClick={() => setTab('claims')}>
          My Claims
        </Button>
      </div>

      {tab === 'policies' && (
        <>
          <Card>
            <Select
              label="Insurance provider"
              value={providerFilter}
              onChange={(e) => setProviderFilter(e.target.value)}
            >
              <option value="">All providers</option>
              {insurers.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.org_name}
                </option>
              ))}
            </Select>
          </Card>
          {policies === null ? (
            <Spinner label="Loading policies…" />
          ) : policies.length === 0 ? (
            <Card>
              <div className="text-sm text-slate-400 text-center py-8">No policies found.</div>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {policies.map((p) => (
                <Card key={p.id}>
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-slate-800">{p.name}</h4>
                      <p className="text-xs text-slate-500 mt-0.5">{insurerName(p.provider)}</p>
                    </div>
                    <Badge color="green">{p.coverage_percent}% covered</Badge>
                  </div>
                  {p.description && (
                    <p className="text-xs text-slate-500 line-clamp-3 mt-2">{p.description}</p>
                  )}
                  <p className="mt-3 text-sm">
                    <span className="text-slate-500">Premium: </span>
                    <span className="font-bold text-primary-600">{ugx(p.premium)}</span>
                  </p>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500">
                    <span>Deductible: {ugx(p.deductible)}</span>
                    <span>Copay: {p.copay_percent}%</span>
                    <span>Annual limit: {p.annual_limit ? ugx(p.annual_limit) : 'Unlimited'}</span>
                    <span>{p.requires_preauthorization ? 'Preauthorization applies' : 'Rule-based authorization'}</span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'coverage' && (
        <div className="space-y-4">
          <Card title="Verify Coverage">
            <form onSubmit={verify} className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
              <Input
                label="Member ID"
                value={verifyMemberId}
                onChange={(e) => setVerifyMemberId(e.target.value)}
                placeholder="e.g. MEM-12345"
                required
              />
              <Select
                label="Provider"
                value={verifyProvider}
                onChange={(e) => setVerifyProvider(e.target.value)}
                required
              >
                <option value="">Select provider…</option>
                {insurers.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.org_name}
                  </option>
                ))}
              </Select>
              <Button type="submit" disabled={verifying}>
                {verifying ? 'Verifying…' : 'Verify'}
              </Button>
            </form>
            {verifyResult && (
              <div
                className={`mt-4 rounded-lg px-4 py-3 text-sm border ${
                  verifyResult.error
                    ? 'bg-rose-50 text-rose-700 border-rose-200'
                    : verifyResult.valid
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}
              >
                {verifyResult.error ? (
                  verifyResult.error
                ) : verifyResult.valid ? (
                  <span className="flex items-center gap-2">
                    <Badge color="green">Valid</Badge>
                    Policy <strong>{verifyResult.policy}</strong> —{' '}
                    {verifyResult.coverage_percent}% coverage
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Badge color="yellow">Not found</Badge>
                    No active coverage for this member ID at the selected provider.
                  </span>
                )}
              </div>
            )}
          </Card>

          <Card
            title="My Coverage"
            actions={<Button onClick={openAddCoverage}>Add Coverage</Button>}
          >
            {coverage === null ? (
              <Spinner label="Loading coverage…" />
            ) : (
              <Table
                empty="No coverage added yet."
                columns={[
                  { key: 'provider_name', label: 'Provider' },
                  { key: 'policy_name', label: 'Policy' },
                  {
                    key: 'coverage_percent',
                    label: 'Coverage',
                    render: (r) => `${r.coverage_percent}%`,
                  },
                  { key: 'member_id', label: 'Member ID' },
                  { key: 'effective_from', label: 'Effective', render: (r) => r.effective_from || '—' },
                  { key: 'expires_on', label: 'Expires', render: (r) => r.expires_on || 'No expiry' },
                  {
                    key: 'active',
                    label: 'Status',
                    render: (r) => (
                      <Badge color={r.active ? 'green' : 'red'}>
                        {r.active ? 'Active' : 'Inactive'}
                      </Badge>
                    ),
                  },
                ]}
                rows={coverage}
              />
            )}
          </Card>
        </div>
      )}

      {tab === 'preauthorizations' && (
        <Card title="My Preauthorizations" actions={<Button onClick={openPreauthorization}>Request Authorization</Button>}>
          {preauthorizations === null ? <Spinner label="Loading preauthorizations…" /> : (
            <Table
              empty="No preauthorization requests yet."
              columns={[
                { key: 'authorization_number', label: 'Authorization', render: (r) => r.authorization_number || `#${r.id}` },
                { key: 'service_name', label: 'Service' },
                { key: 'policy_name', label: 'Policy' },
                { key: 'requested_amount', label: 'Requested', render: (r) => ugx(r.requested_amount) },
                { key: 'approved_amount', label: 'Approved', render: (r) => ugx(r.approved_amount) },
                { key: 'status', label: 'Status', render: (r) => <Badge color={statusColor(r.status)}>{String(r.status).replace(/_/g, ' ')}</Badge> },
                { key: 'valid_until', label: 'Valid until', render: (r) => r.valid_until || '—' },
                { key: 'decision_reason', label: 'Decision', render: (r) => r.decision_reason || 'Awaiting review' },
              ]}
              rows={preauthorizations}
            />
          )}
        </Card>
      )}

      {tab === 'claims' && (
        <Card
          title="My Claims"
          actions={<Button onClick={openClaim}>Submit Claim</Button>}
        >
          {claims === null ? (
            <Spinner label="Loading claims…" />
          ) : (
            <Table
              empty="No claims submitted yet."
              columns={[
                { key: 'claim_number', label: 'Claim', render: (r) => r.claim_number || `#${r.id}` },
                {
                  key: 'provider',
                  label: 'Provider',
                  render: (r) => insurerName(r.provider),
                },
                { key: 'policy_name', label: 'Policy' },
                {
                  key: 'invoice_number',
                  label: 'Invoice',
                  render: (r) => r.invoice_number || '—',
                },
                { key: 'amount', label: 'Amount', render: (r) => ugx(r.amount) },
                { key: 'approved_amount', label: 'Approved', render: (r) => ugx(r.approved_amount) },
                { key: 'patient_responsibility', label: 'My share', render: (r) => ugx(r.patient_responsibility) },
                {
                  key: 'status',
                  label: 'Status',
                  render: (r) => <Badge color={statusColor(r.status)}>{r.status}</Badge>,
                },
                { key: 'created_at', label: 'Submitted', render: (r) => fmtDT(r.created_at) },
              ]}
              rows={claims}
            />
          )}
        </Card>
      )}

      {/* add coverage modal */}
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add Coverage">
        <form onSubmit={saveCoverage} className="space-y-4">
          <Select
            label="Insurance provider"
            value={addProvider}
            onChange={(e) => {
              setAddProvider(e.target.value)
              setAddPolicy('')
            }}
            required
          >
            <option value="">Select provider…</option>
            {insurers.map((i) => (
              <option key={i.id} value={i.id}>
                {i.org_name}
              </option>
            ))}
          </Select>
          <Select
            label="Policy"
            value={addPolicy}
            onChange={(e) => setAddPolicy(e.target.value)}
            required
            disabled={!addProvider}
          >
            <option value="">
              {addProvider ? 'Select policy…' : 'Choose a provider first'}
            </option>
            {providerPolicies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.coverage_percent}% covered
              </option>
            ))}
          </Select>
          <Input
            label="Member ID"
            value={addMemberId}
            onChange={(e) => setAddMemberId(e.target.value)}
            placeholder="Your membership number"
            required
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving || !addProvider || !addPolicy || !addMemberId}>
              {saving ? 'Saving…' : 'Save Coverage'}
            </Button>
          </div>
        </form>
      </Modal>

      <Modal open={preauthOpen} onClose={() => setPreauthOpen(false)} title="Request Preauthorization" wide>
        <form onSubmit={submitPreauthorization} className="space-y-4">
          <Select label="Coverage" value={preauthCoverage} onChange={(e) => setPreauthCoverage(e.target.value)} required>
            <option value="">Select active coverage…</option>
            {(coverage || []).filter((item) => item.is_current).map((item) => (
              <option key={item.id} value={item.id}>{item.provider_name} — {item.policy_name} — {item.member_id}</option>
            ))}
          </Select>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input label="Service or procedure" value={preauthService} onChange={(e) => setPreauthService(e.target.value)} required />
            <Input label="Service code" value={preauthCode} onChange={(e) => setPreauthCode(e.target.value)} />
            <Input label="Diagnosis code" value={preauthDiagnosis} onChange={(e) => setPreauthDiagnosis(e.target.value)} />
            <Input label="Requested amount (UGX)" type="number" min="1" value={preauthAmount} onChange={(e) => setPreauthAmount(e.target.value)} required />
          </div>
          <Textarea label="Clinical indication" rows={4} value={preauthIndication} onChange={(e) => setPreauthIndication(e.target.value)} required />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setPreauthOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={submitting || !preauthCoverage || !preauthService || !preauthAmount}>{submitting ? 'Submitting…' : 'Submit Request'}</Button>
          </div>
        </form>
      </Modal>

      {/* submit claim modal */}
      <Modal open={claimOpen} onClose={() => setClaimOpen(false)} title="Submit Claim">
        <form onSubmit={submitClaim} className="space-y-4">
          <Select
            label="Insurance provider"
            value={claimProvider}
            onChange={(e) => {
              setClaimProvider(e.target.value)
              setClaimPolicy('')
            }}
            required
          >
            <option value="">Select provider…</option>
            {insurers.map((i) => (
              <option key={i.id} value={i.id}>
                {i.org_name}
              </option>
            ))}
          </Select>
          <Select
            label="Policy"
            value={claimPolicy}
            onChange={(e) => setClaimPolicy(e.target.value)}
            required
            disabled={!claimProvider}
          >
            <option value="">
              {claimProvider ? 'Select policy…' : 'Choose a provider first'}
            </option>
            {claimPolicies.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.coverage_percent}% covered
              </option>
            ))}
          </Select>
          <Select
            label="Paid invoice (optional)"
            value={claimInvoice}
            onChange={(e) => setClaimInvoice(e.target.value)}
          >
            <option value="">No invoice attached</option>
            {paidInvoices.map((inv) => (
              <option key={inv.id} value={inv.id}>
                {inv.number} — {ugx(inv.amount)}
              </option>
            ))}
          </Select>
          <Input
            label="Claim amount (UGX)"
            type="number"
            min="1"
            value={claimAmount}
            onChange={(e) => setClaimAmount(e.target.value)}
            required
          />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setClaimOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting || !claimProvider || !claimPolicy || !claimAmount}
            >
              {submitting ? 'Submitting…' : 'Submit Claim'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
