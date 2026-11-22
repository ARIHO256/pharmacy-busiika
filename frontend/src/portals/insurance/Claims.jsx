import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Button, Card, Table } from '../../components/ui'
import { errMsg, fmtDate, LoadingOrError, money, StatusBadge, useApi } from '../pharmacy/shared'

export default function Claims() {
  const { data: claims, loading, error, reload } = useApi(() => servicesApi.claimsManage())
  const [deciding, setDeciding] = useState(null)

  const decide = async (claim, action) => {
    if (action === 'reject' && !window.confirm(`Reject claim #${claim.id} (${claim.invoice_number})?`)) return
    setDeciding(claim.id)
    try {
      await servicesApi.decideClaim(claim.id, action)
      reload()
    } catch (e) {
      alert(errMsg(e))
    } finally {
      setDeciding(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Insurance claims">
        <Table
          empty="No claims yet"
          columns={[
            { key: 'id', label: 'Claim', render: (c) => <span className="font-medium text-slate-800">#{c.id}</span> },
            { key: 'patient_name', label: 'Patient' },
            { key: 'invoice_number', label: 'Invoice' },
            { key: 'policy_name', label: 'Policy', render: (c) => c.policy_name || '—' },
            { key: 'amount', label: 'Amount', render: (c) => money(c.amount) },
            { key: 'created_at', label: 'Submitted', render: (c) => fmtDate(c.created_at) },
            { key: 'status', label: 'Status', render: (c) => <StatusBadge status={c.status} /> },
            {
              key: 'actions',
              label: 'Decision',
              render: (c) =>
                c.status === 'submitted' ? (
                  <div className="flex gap-2">
                    <Button disabled={deciding === c.id} onClick={() => decide(c, 'approve')}>
                      Approve
                    </Button>
                    <Button variant="danger" disabled={deciding === c.id} onClick={() => decide(c, 'reject')}>
                      Reject
                    </Button>
                  </div>
                ) : (
                  <span className="text-slate-300 text-xs">—</span>
                ),
            },
          ]}
          rows={claims || []}
        />
      </Card>
    </LoadingOrError>
  )
}
