import { createPortal } from 'react-dom'
import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { displayDate, getError, money, statusBadge, useRemote } from '../staff/shared'
import ReceiptPrint from '../cashier/ReceiptPrint'

export function PharmacyAudit() {
  const [search, setSearch] = useState('')
  const rows = useRemote(() => servicesApi.pharmacyWorkspaceData('audit', { search }), [search])
  return <Card title="Pharmacy audit history">
    <Input label="Search action, worker name, email or role" value={search} onChange={(event) => setSearch(event.target.value)} />
    {rows.error ? <Alert tone="danger">{rows.error}</Alert> : rows.loading && !rows.data ? <Spinner /> :
      <Table rows={rows.data || []} empty="No audit events match." columns={[
        { key: 'created_at', label: 'When', render: (row) => displayDate(row.created_at) },
        { key: 'action', label: 'Action' }, { key: 'actor', label: 'Worker name' },
        { key: 'actor_email', label: 'Email' },
        { key: 'actor_role', label: 'Role', render: (row) => row.custom_role ? `${row.custom_role} (${row.actor_role.replaceAll('_', ' ')})` : row.actor_role.replaceAll('_', ' ') },
        { key: 'record', label: 'Record' },
      ]} />}
  </Card>
}

const creditColumns = [
  { key: 'order', label: 'Order' }, { key: 'patient', label: 'Buyer' },
  { key: 'due_at', label: 'Due date', render: (row) => displayDate(row.due_at, false) },
  { key: 'amount', label: 'Invoiced', render: (row) => money(row.amount) },
  { key: 'balance', label: 'Balance', render: (row) => money(row.balance) },
  { key: 'status', label: 'Status', render: (row) => statusBadge(row.status) },
  { key: 'payments', label: 'Statement', render: (row) => row.payments.length ? <details>
    <summary className="cursor-pointer">Payment history</summary>
    {row.payments.map((p) => <div key={p.id}>{displayDate(p.date, false)} · {money(p.amount)} · {p.status} · {p.number}</div>)}
  </details> : 'No payments' },
]

export function PharmacyFinance({ refund = false }) {
  const page = refund ? 'refunds' : 'credit'
  const [voiding, setVoiding] = useState(false)
  const [patient, setPatient] = useState('')
  const data = useRemote(() => servicesApi.pharmacyWorkspaceData(page, patient && !refund ? { patient } : {}), [page, patient])
  const [form, setForm] = useState({ order: '', reason: '', reference: '', due_date: '' })
  const [payment, setPayment] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmation, setConfirmation] = useState('')
  const change = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const { data: response } = await servicesApi.savePharmacyWorkspace(
        payment ? `credit/${payment.id}/payments` : page,
        payment ? { amount: Number(payment.amount), method: payment.method, reference: payment.reference, request_id: payment.request_id } :
          refund ? { order: Number(form.order), reason: form.reason, reference: form.reference, action: voiding ? 'void' : 'refund' } :
            { order: Number(form.order), due_date: form.due_date },
      )
      if (payment) setReceipt(response)
      setConfirmation(refund ? voiding ? 'Order voided.' : 'Refund recorded.' : payment ? 'Payment recorded.' : 'Credit invoice issued.')
      setPayment(null)
      setForm({ order: '', reason: '', reference: '', due_date: '' })
      data.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(false)
    }
  }

  return <div className="space-y-4">
    {!payment && error && <Alert tone="danger">{error}</Alert>}
    {confirmation && <Alert tone="success">{confirmation}</Alert>}
    {data.error && <Alert tone="danger">{data.error}</Alert>}
    <Card title={refund ? 'Refunds and voids'  : 'Issue a credit invoice'} subtitle={refund
      ? 'Record funds already returned. Handed-over medicines remain outside saleable stock and follow the returns workflow.'
      : 'Select an unpaid buyer order and enter its due date.'}>
      <form onSubmit={submit} className="space-y-3">
        {refund && <Select label="Action" value={voiding ? 'void' : 'refund'} onChange={(event) => {
          setVoiding(event.target.value === 'void')
          setForm({ ...form, order: '', reference: '' })
        }}>
          <option value="refund">Record a full refund</option>
          <option value="void">Void an unpaid order</option>
        </Select>}
        <Select required label="Order" value={form.order} onChange={change('order')}>
          <option value="">Select order</option>
          {((voiding ? data.data?.voidable : data.data?.eligible) || []).map((row) => <option key={row.id} value={row.id}>
            #{row.id} · {row.patient || row.status} · {money(row.amount ?? row.total)}
          </option>)}
        </Select>
        {refund ? <>
          <Textarea label={voiding ? 'Void reason' : 'Refund reason'} required maxLength={1000} value={form.reason} onChange={change('reason')} />
          {!voiding && <Input label="Refund payment reference" required maxLength={120} value={form.reference} onChange={change('reference')} />}
        </> : <Input label="Due date" required type="date" value={form.due_date} onChange={change('due_date')} />}
        <Button disabled={busy || !form.order}>{refund ? voiding ? 'Void order' : 'Record full refund' : 'Issue credit invoice'}</Button>
      </form>
    </Card>
    <Card title={refund ? 'Refund history' : 'Accounts receivable'}>
      {!refund && <Select label="Buyer statement" value={patient} onChange={(event) => setPatient(event.target.value)}>
        <option value="">All buyers</option>
        {Array.from(new Map((data.data?.accounts || []).map((row) => [row.patient_id, row.patient]))).map(([id, name]) =>
          <option key={id} value={id}>{name}</option>)}
      </Select>}
      <Table rows={(refund ? data.data?.records : data.data?.accounts) || []} empty={data.loading ? 'Loading records…' : 'No records yet.'} columns={refund ? [
        { key: 'order_id', label: 'Order' }, { key: 'amount', label: 'Refunded', render: (row) => money(row.amount) },
        { key: 'reference', label: 'Reference' }, { key: 'reason', label: 'Reason' },
        { key: 'created_at', label: 'Date', render: (row) => displayDate(row.created_at) },
      ] : [...creditColumns, { key: 'action', label: 'Collect', render: (row) =>
        row.balance > 0 && ['pending', 'partially_paid'].includes(row.status) &&
        <Button variant="outline" onClick={() => { setError(''); setPayment({ ...row, amount: row.balance, method: 'cash', reference: '', request_id: crypto.randomUUID() }) }}>Record payment</Button>,
      }]} />
    </Card>
    {payment && <Modal open title={`Record payment · order #${payment.order}`} onClose={() => { if (!busy) setPayment(null) }}>
      <form onSubmit={submit} className="space-y-3">
        <Input label="Amount received" type="number" min="1" max={payment.balance} required value={payment.amount}
          onChange={(e) => setPayment({ ...payment, amount: e.target.value })} />
        <Select label="Payment method" value={payment.method} onChange={(e) => setPayment({ ...payment, method: e.target.value })}>
          <option value="cash">Cash</option><option value="mobile_money">Mobile money</option>
          <option value="bank">Bank transfer</option><option value="card">Card terminal</option>
        </Select>
        <Input label="Payment reference" required={payment.method !== 'cash'} maxLength={120} value={payment.reference}
          onChange={(e) => setPayment({ ...payment, reference: e.target.value })} />
        {error && <Alert tone="danger">{error}</Alert>}
        <Button disabled={busy}>Record payment</Button>
      </form>
    </Modal>}
    {receipt && <Modal open title="Payment receipt" onClose={() => setReceipt(null)}>
      <Button onClick={() => window.print()}>Print receipt</Button>
      <ReceiptPrint receipt={receipt} printId={null} />
    </Modal>}
    {receipt && createPortal(<div id="print-pharmacy-receipt" className="hidden print:block"><ReceiptPrint receipt={receipt} printId={null} /></div>, document.body)}
  </div>
}
