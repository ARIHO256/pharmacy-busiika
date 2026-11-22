import { useEffect, useRef, useState } from 'react'
import { paymentApi } from '../../api/endpoints'
import { Badge, Button, Card, Modal, Spinner, Table } from '../../components/ui'
import { INVOICE_STATUS_COLORS } from './utils'
import { money } from '../staff/shared'

export default function Invoices() {
  const [invoices, setInvoices] = useState(null)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const [receiptLoading, setReceiptLoading] = useState(false)
  const receiptRequest = useRef(0)
  const [receiptError, setReceiptError] = useState('')

  useEffect(() => {
    paymentApi
      .invoices()
      .then((r) => setInvoices(r.data))
      .catch(() => setError('Could not load invoices.'))
  }, [])

  const openReceipt = async (inv) => {
    const request = ++receiptRequest.current
    setReceipt({ loading: true })
    setReceiptLoading(true)
    setReceiptError('')
    try {
      const { data } = await paymentApi.receipt(inv.id)
      if (request === receiptRequest.current) setReceipt(data)
    } catch {
      if (request !== receiptRequest.current) return
      setReceipt(null)
      setReceiptError('Could not load the receipt for this invoice.')
    } finally {
      if (request === receiptRequest.current) setReceiptLoading(false)
    }
  }

  if (error) return <Card className="text-sm text-rose-600">{error}</Card>
  if (!invoices) return <Spinner label="Loading invoices…" />

  const columns = [
    { key: 'number', label: 'Invoice', render: (i) => <span className="font-medium text-slate-800">{i.number}</span> },
    {
      key: 'for',
      label: 'For',
      render: (i) => <span className="text-slate-600">{i.appointment_info || 'Appointment'}</span>,
    },
    { key: 'amount', label: 'Amount', render: (i) => <span className="font-medium">{money(i.amount, i.currency)}</span> },
    {
      key: 'status',
      label: 'Status',
      render: (i) => <Badge color={INVOICE_STATUS_COLORS[i.status] || 'slate'}>{i.status}</Badge>,
    },
    { key: 'created_at', label: 'Issued', render: (i) => String(i.created_at || '').slice(0, 10) },
    {
      key: 'actions',
      label: '',
      render: (i) => (
        <Button variant="outline" className="px-3 py-1 text-xs" onClick={() => openReceipt(i)}>
          Receipt
        </Button>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      {receiptError && <Card className="text-sm text-rose-600">{receiptError}</Card>}
      <Card title="My invoices">
        <Table columns={columns} rows={invoices} empty="No invoices yet." />
      </Card>

      <Modal open={!!receipt} onClose={() => { receiptRequest.current += 1; setReceipt(null) }} title="Receipt">
        {receiptLoading || receipt?.loading ? (
          <Spinner label="Loading receipt…" />
        ) : receipt ? (
          <div className="space-y-3 text-sm">
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Invoice number</span>
              <span className="font-medium text-slate-800">{receipt.number}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Amount</span>
              <span className="font-semibold text-primary-600">{money(receipt.payment?.amount ?? receipt.amount, receipt.currency)}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Status</span>
              <Badge color={INVOICE_STATUS_COLORS[receipt.status] || 'slate'}>{receipt.payment?.status || receipt.status || '—'}</Badge>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Patient</span>
              <span className="text-slate-800">{receipt.patient_name || receipt.patient || '—'}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Doctor</span>
              <span className="text-slate-800">{receipt.doctor || '—'}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Date</span>
              <span className="text-slate-800">{receipt.date || receipt.created_at?.slice(0, 10) || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Gateway</span>
              <span className="text-slate-800">{receipt.gateway || '—'}</span>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
