import { Link } from 'react-router-dom'
import { servicesApi } from '../../api/endpoints'
import { Card, Stat, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

export default function Dashboard() {
  const { data, loading, error } = useApi(() =>
    Promise.all([
      servicesApi.policies(),
      servicesApi.claimsManage(),
      servicesApi.preauthorizations(),
      servicesApi.remittances(),
      servicesApi.eligibilityHistory(),
    ]).then(([policies, claims, preauthorizations, remittances, eligibility]) => ({
      policies: policies.data || [], claims: claims.data || [],
      preauthorizations: preauthorizations.data || [], remittances: remittances.data || [],
      eligibility: eligibility.data || [],
    })),
  )

  const policies = data?.policies || []
  const claims = data?.claims || []
  const preauthorizations = data?.preauthorizations || []
  const remittances = data?.remittances || []
  const awaiting = claims.filter((claim) => ['submitted', 'in_review', 'query'].includes(claim.status)).length
  const authorizationQueue = preauthorizations.filter((row) => ['submitted', 'in_review', 'query'].includes(row.status)).length
  const paidValue = remittances.reduce((sum, row) => sum + Number(row.paid_amount || 0), 0)
  const eligibilityRate = data?.eligibility?.length
    ? Math.round((data.eligibility.filter((row) => row.result === 'eligible').length / data.eligibility.length) * 100)
    : 0

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
          <Stat label="Active policies" value={policies.filter((policy) => policy.active).length} icon="shield" />
          <Stat label="Claims awaiting review" value={awaiting} icon="file" tone="text-amber-600" />
          <Stat label="Preauthorization queue" value={authorizationQueue} icon="clipboard" tone="text-amber-600" />
          <Stat label="Eligibility success" value={`${eligibilityRate}%`} icon="activity" tone="text-emerald-600" />
          <Stat label="Remitted value" value={money(paidValue)} icon="money" tone="text-emerald-600" />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
          <Card title="Recent claims" className="xl:col-span-2" actions={<Link to="claims" className="text-sm text-primary-600 hover:underline">Open work queue</Link>}>
            <Table
              empty="No claims yet"
              columns={[
                { key: 'claim_number', label: 'Claim', render: (claim) => <span className="font-semibold">{claim.claim_number || `#${claim.id}`}</span> },
                { key: 'patient_name', label: 'Patient' },
                { key: 'amount', label: 'Requested', render: (claim) => money(claim.amount) },
                { key: 'approved_amount', label: 'Approved', render: (claim) => money(claim.approved_amount) },
                { key: 'created_at', label: 'Submitted', render: (claim) => fmtDate(claim.created_at) },
                { key: 'status', label: 'Status', render: (claim) => <StatusBadge status={claim.status} /> },
              ]}
              rows={claims.slice(0, 7)}
            />
          </Card>

          <Card title="Operational shortcuts">
            <div className="space-y-3">
              {[
                ['/insurance/eligibility', 'Run eligibility check', 'Validate a member before service delivery'],
                ['/insurance/preauthorizations', 'Review preauthorizations', 'Approve, query or reject requests'],
                ['/insurance/benefits', 'Configure benefit rules', 'Limits, copays and exclusions'],
                ['/insurance/remittances', 'Reconcile remittances', 'Claim settlement and payment references'],
              ].map(([to, title, description]) => (
                <Link key={to} to={to} className="block rounded-xl border border-slate-200 p-4 hover:border-primary-300 hover:bg-primary-50 transition-colors">
                  <div className="font-semibold text-slate-800">{title}</div>
                  <div className="text-xs text-slate-500 mt-1">{description}</div>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </LoadingOrError>
  )
}
