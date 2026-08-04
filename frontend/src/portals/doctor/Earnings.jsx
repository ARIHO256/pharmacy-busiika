import { useCallback, useEffect, useState } from 'react'
import { paymentApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Spinner, Stat, Table } from '../../components/ui'
import { fmtMoney, statusColor } from './util'

export default function Earnings() {
  const [data, setData] = useState(null)
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    paymentApi.earnings().then((r) => setData(r.data)).catch(() => setData({}))
  }, [])
  useEffect(() => { load() }, [load])

  if (!data) return <Spinner label="Loading earnings…" />

  const total = data.total ?? data.total_earnings ?? 0
  const pending = data.pending ?? data.available ?? data.pending_available ?? 0
  const payouts = data.payouts || []
  const paidOut = data.paid_out ?? payouts.filter((p) => p.status === 'paid').reduce((s, p) => s + Number(p.amount || 0), 0)

  async function withdraw(e) {
    e.preventDefault()
    setMsg('')
    setError('')
    const amt = Number(amount)
    if (!amt || amt <= 0) return setError('Enter a valid amount')
    if (amt > Number(pending)) return setError(`Amount exceeds your available balance of ${fmtMoney(pending)}`)
    setBusy(true)
    try {
      await paymentApi.withdraw(amt)
      setMsg(`Withdrawal of ${fmtMoney(amt)} requested.`)
      setAmount('')
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Withdrawal failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Stat label="Total earnings" value={fmtMoney(total)} icon="💰" />
        <Stat label="Available to withdraw" value={fmtMoney(pending)} icon="🏦" tone="text-emerald-600" />
        <Stat label="Paid out" value={fmtMoney(paidOut)} icon="✅" tone="text-sky-600" />
      </div>

      <Card title="Request withdrawal">
        <form onSubmit={withdraw} className="flex flex-col sm:flex-row gap-3 sm:items-end max-w-lg">
          <Input
            label={`Amount (max ${fmtMoney(pending)})`}
            type="number"
            min="1"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="e.g. 50000"
            className="flex-1"
          />
          <Button type="submit" disabled={busy || !Number(pending)}>
            {busy ? 'Processing…' : 'Withdraw'}
          </Button>
        </form>
        {msg && <p className="mt-3 text-sm text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-lg px-4 py-2.5">{msg}</p>}
        {error && <p className="mt-3 text-sm text-rose-600 bg-rose-50 border border-rose-100 rounded-lg px-4 py-2.5">{error}</p>}
      </Card>

      <Card title="Payout history">
        <Table
          columns={[
            { key: 'id', label: 'Payout #', render: (p) => `PO-${p.id}` },
            { key: 'amount', label: 'Amount', render: (p) => fmtMoney(p.amount) },
            { key: 'status', label: 'Status', render: (p) => <Badge color={statusColor(p.status)}>{p.status}</Badge> },
            { key: 'created_at', label: 'Requested', render: (p) => (p.created_at || '').slice(0, 10) },
          ]}
          rows={payouts}
          empty="No payouts yet."
        />
      </Card>
    </div>
  )
}
