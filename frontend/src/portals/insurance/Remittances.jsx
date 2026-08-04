import { servicesApi } from '../../api/endpoints'
import { Card, Stat, Table } from '../../components/ui'
import { LoadingOrError, money, useApi } from '../pharmacy/shared'

export default function Remittances() {
  const { data: rows, loading, error } = useApi(() => servicesApi.remittances())
  const total = (rows || []).reduce((sum, row) => sum + Number(row.paid_amount || 0), 0)
  const thisMonth = (rows || []).filter((row) => {
    const date = new Date(row.paid_on)
    const now = new Date()
    return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear()
  }).reduce((sum, row) => sum + Number(row.paid_amount || 0), 0)

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Stat label="Remittance records" value={(rows || []).length} icon="file" />
          <Stat label="Total remitted" value={money(total)} icon="money" tone="text-emerald-600" />
          <Stat label="This month" value={money(thisMonth)} icon="calendar" tone="text-emerald-600" />
        </div>
        <Card title="Remittance register" subtitle="Payment references are linked to approved claims and retained for reconciliation and audit.">
          <Table
            empty="No remittances have been recorded."
            columns={[
              { key: 'paid_on', label: 'Paid on', render: (row) => new Date(row.paid_on).toLocaleDateString() },
              { key: 'remittance_number', label: 'Remittance', render: (row) => <span className="font-semibold text-slate-800">{row.remittance_number}</span> },
              { key: 'claim_number', label: 'Claim' },
              { key: 'patient_name', label: 'Patient' },
              { key: 'payment_reference', label: 'Payment reference' },
              { key: 'paid_amount', label: 'Amount', render: (row) => <span className="font-semibold text-emerald-700">{money(row.paid_amount)}</span> },
              { key: 'notes', label: 'Notes', render: (row) => row.notes || '—' },
            ]}
            rows={rows || []}
          />
        </Card>
      </div>
    </LoadingOrError>
  )
}
