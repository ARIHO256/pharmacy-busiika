import { Link } from 'react-router-dom'
import { servicesApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Card, Stat, Table } from '../../components/ui'
import { fmtDate, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

export default function Dashboard() {
  const { user } = useAuth()
  const { data, loading, error } = useApi(() =>
    Promise.all([servicesApi.policies({ provider: user.id }), servicesApi.claimsManage()]).then(([policies, claims]) => ({
      policies: policies.data || [],
      claims: claims.data || [],
    })),
  )

  const policies = data?.policies || []
  const claims = data?.claims || []
  const submitted = claims.filter((c) => c.status === 'submitted').length
  const approvedValue = claims
    .filter((c) => c.status === 'approved')
    .reduce((s, c) => s + Number(c.amount || 0), 0)

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Stat label="Active policies" value={policies.length} icon="🛡️" />
          <Stat label="Claims awaiting review" value={submitted} icon="📑" />
          <Stat label="Approved claims" value={claims.filter((c) => c.status === 'approved').length} icon="✅" tone="text-emerald-600" />
          <Stat label="Approved value" value={money(approvedValue)} icon="💰" tone="text-emerald-600" />
        </div>
        <Card
          title="Recent claims"
          actions={
            <Link to="claims" className="text-sm text-primary-600 hover:underline">
              View all
            </Link>
          }
        >
          <Table
            empty="No claims yet"
            columns={[
              { key: 'patient_name', label: 'Patient' },
              { key: 'invoice_number', label: 'Invoice' },
              { key: 'amount', label: 'Amount', render: (c) => money(c.amount) },
              { key: 'created_at', label: 'Submitted', render: (c) => fmtDate(c.created_at) },
              { key: 'status', label: 'Status', render: (c) => <StatusBadge status={c.status} /> },
            ]}
            rows={claims.slice(0, 5)}
          />
        </Card>
      </div>
    </LoadingOrError>
  )
}
