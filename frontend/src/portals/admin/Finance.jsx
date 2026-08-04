import { useEffect, useMemo, useState } from 'react'
import { Badge, Card, Spinner, Stat, Table } from '../../components/ui'
import { adminApi } from '../../api/endpoints'
import { fmtDateTime, invoiceStatusColor, money } from './helpers'

export default function Finance() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi
      .finance()
      .then((res) => setData(res.data))
      .catch(() => setError('Failed to load finance data.'))
  }, [])

  const payoutCounts = useMemo(() => {
    const counts = { pending: 0, paid: 0 }
    for (const p of data?.payouts || []) counts[p.status] = (counts[p.status] || 0) + 1
    return counts
  }, [data])

  if (error) return <Card><p className="text-sm text-rose-600">{error}</p></Card>
  if (!data) return <Spinner label="Loading finance…" />

  const invoiceColumns = [
    { key: 'number', label: 'Invoice #' },
    { key: 'patient', label: 'Patient', render: (i) => i.patient || '—' },
    { key: 'doctor', label: 'Doctor', render: (i) => i.doctor || '—' },
    { key: 'amount', label: 'Amount', render: (i) => money(i.amount) },
    {
      key: 'status',
      label: 'Status',
      render: (i) => <Badge color={invoiceStatusColor[i.status] || 'slate'}>{i.status}</Badge>,
    },
    { key: 'paid_at', label: 'Paid At', render: (i) => fmtDateTime(i.paid_at) },
  ]

  const payoutColumns = [
    { key: 'doctor', label: 'Doctor', render: (p) => p.doctor || '—' },
    { key: 'amount', label: 'Amount', render: (p) => money(p.amount) },
    {
      key: 'status',
      label: 'Status',
      render: (p) => (
        <Badge color={p.status === 'paid' ? 'green' : 'yellow'}>{p.status}</Badge>
      ),
    },
    { key: 'created_at', label: 'Created', render: (p) => fmtDateTime(p.created_at) },
  ]

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Stat label="Revenue (paid invoices)" value={money(data.revenue)} icon="💰" />
        <Stat label="Commissions Total" value={money(data.commissions_total)} icon="🏦" tone="text-slate-700" />
        <Stat label="Pending Payouts" value={payoutCounts.pending || 0} icon="⏳" tone="text-amber-600" />
        <Stat label="Paid Payouts" value={payoutCounts.paid || 0} icon="✅" tone="text-emerald-600" />
      </div>

      <Card title={`Invoices (${data.invoices.length})`}>
        <Table columns={invoiceColumns} rows={data.invoices} empty="No invoices yet" />
      </Card>

      <Card title={`Payouts (${data.payouts.length})`}>
        <Table columns={payoutColumns} rows={data.payouts} empty="No payouts yet" />
      </Card>
    </div>
  )
}
