import { useEffect, useState } from 'react'
import { paymentApi } from '../../api/endpoints'
import { Badge, Button, Card, Modal, Spinner, Table } from '../../components/ui'
import { INVOICE_STATUS_COLORS, fmtUGX } from './utils'
import { downloadBlob } from '../staff/shared'

export default function Invoices() {
  const [invoices, setInvoices] = useState(null)
  const [error, setError] = useState('')
  const [receipt, setReceipt] = useState(null)
  const [receiptLoading, setReceiptLoading] = useState(false)
  const [receiptError, setReceiptError] = useState('')
  const [notice, setNotice] = useState('')

  useEffect(() => {
    paymentApi
      .invoices()
      .then((r) => setInvoices(r.data))
      .catch(() => setError('Could not load invoices.'))
  }, [])

  const openReceipt = async (inv) => {
    setReceipt({ loading: true })
    setReceiptLoading(true)
    setReceiptError('')
    try {
      const { data } = await paymentApi.receipt(inv.id)
      setReceipt(data)
    } catch {
      setReceipt(null)
      setReceiptError('Could not load the receipt for this invoice.')
    } finally {
      setReceiptLoading(false)
    }
  }


  const downloadInvoice = async (inv) => {
    setReceiptError('')
    try { downloadBlob(await paymentApi.invoicePdf(inv.id), `${inv.number}.pdf`) }
    catch { setReceiptError('Could not generate the invoice PDF.') }
  }
  const sendInvoice = async (inv) => {
    setReceiptError('')
    try { const { data } = await paymentApi.sendInvoice(inv.id); setNotice(data.detail || 'Invoice sent.') }
    catch { setReceiptError('Could not send the invoice email.') }
  }

  if (error) return <Card className="text-sm text-rose-600">{error}</Card>
  if (!invoices) return <Spinner label="Loading invoices…" />

  const columns = [
    { key: 'number', label: 'Invoice', render: (i) => <span className="font-medium text-slate-800">{i.number}</span> },
    {
      key: 'for',
      label: 'For',
      render: (i) => (
        <span className="text-slate-600">
          {i.appointment_info
            ? `${i.appointment_info.doctor_name || 'Appointment'} · ${i.appointment_info.date || ''}`
            : 'Appointment'}
        </span>
      ),
    },
    { key: 'amount', label: 'Amount', render: (i) => <span className="font-medium">{fmtUGX(i.amount)}</span> },
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
        <div className="flex flex-wrap gap-1"><Button variant="outline" className="px-3 py-1 text-xs" onClick={() => downloadInvoice(i)}>Invoice PDF</Button><Button variant="outline" className="px-3 py-1 text-xs" onClick={() => sendInvoice(i)}>Email</Button><Button variant="ghost" className="px-3 py-1 text-xs" onClick={() => openReceipt(i)}>Receipt</Button></div>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      {notice && <Card className="text-sm text-emerald-700">{notice}</Card>}
      {receiptError && <Card className="text-sm text-rose-600">{receiptError}</Card>}
      <Card title="My invoices">
        <Table columns={columns} rows={invoices} empty="No invoices yet." />
      </Card>

      <Modal open={!!receipt} onClose={() => setReceipt(null)} title="Receipt">
        {receiptLoading || receipt?.loading ? (
          <Spinner label="Loading receipt…" />
        ) : receipt ? (
          <div className="space-y-3 text-sm">
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Invoice number</span>
              <span className="font-medium text-slate-800">{receipt.invoice_number || receipt.number}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Amount</span>
              <span className="font-semibold text-primary-600">{fmtUGX(receipt.payment?.amount || receipt.amount)}</span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Status</span>
              <Badge color={INVOICE_STATUS_COLORS[receipt.payment?.status || receipt.status] || 'slate'}>{receipt.payment?.status || receipt.status}</Badge>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Patient</span>
              <span className="text-slate-800">{receipt.patient_name || receipt.patient}</span>
            </div>

            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Date</span>
              <span className="text-slate-800">{receipt.created_at ? new Date(receipt.created_at).toLocaleString() : receipt.date || '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Gateway</span>
              <span className="text-slate-800">{receipt.payment?.method || receipt.gateway || '—'}</span>
            </div>
            {receipt.id && <Button onClick={async()=>downloadBlob(await paymentApi.receiptPdf(receipt.id), `${receipt.number}.pdf`)}>Download receipt PDF</Button>}
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
