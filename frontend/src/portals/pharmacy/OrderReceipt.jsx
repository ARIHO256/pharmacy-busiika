import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Input, Modal, Select, Spinner } from '../../components/ui'
import ReceiptPrint from '../cashier/ReceiptPrint'
import { errMsg, money } from './shared'

export default function OrderReceipt({ order, onClose, onRecorded, initialReceipt = null }) {
  const [receipt, setReceipt] = useState(initialReceipt)
  const [method, setMethod] = useState('cash')
  const [reference, setReference] = useState('')
  const [busy, setBusy] = useState(order.payment_recorded && !initialReceipt)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!order.payment_recorded || initialReceipt) return undefined
    let active = true
    servicesApi.orderReceipt(order.id)
      .then(({ data }) => { if (active) setReceipt(data) })
      .catch((err) => { if (active) setError(errMsg(err)) })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [order.id, order.payment_recorded, initialReceipt])

  async function save(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const { data } = await servicesApi.recordOrderPayment(order.id, { amount: order.total, method, reference })
      setReceipt(data)
    } catch (err) {
      setError(errMsg(err))
    } finally {
      setBusy(false)
    }
  }

  function close() {
    if (busy) return
    if (receipt && !order.payment_recorded) onRecorded?.()
    onClose()
  }

  return <>
    <Modal open wide={Boolean(receipt)} title={`${receipt || order.payment_recorded ? 'Receipt' : 'Record payment'} · Order #${order.id}`}
      onClose={close}>
      {error && <Alert tone="danger">{error}</Alert>}
      {receipt ? <>
        <Button className="mb-4" onClick={() => window.print()}>Print receipt</Button>
        <ReceiptPrint receipt={receipt} orderNumber={order.id} printId={null} />
      </> : order.payment_recorded ? (busy && <Spinner label="Loading receipt…" />) : (
        <form onSubmit={save} className="space-y-4">
          <p>Record the full payment of <strong>{money(order.total)}</strong> after receiving it.</p>
          <Select label="Payment received by" value={method} onChange={(event) => setMethod(event.target.value)}>
            <option value="cash">Cash</option>
            <option value="mobile_money">Mobile money</option>
            <option value="card">Card terminal</option>
            <option value="bank">Bank transfer</option>
          </Select>
          {method !== 'cash' && <Input required label="Payment reference" maxLength={120} value={reference}
            onChange={(event) => setReference(event.target.value)} />}
          <Button disabled={busy} type="submit">{busy ? 'Recording…' : 'Record payment and issue receipt'}</Button>
        </form>
      )}
    </Modal>
    {receipt && createPortal(
      <div id="print-pharmacy-receipt" className="hidden print:block">
        <ReceiptPrint receipt={receipt} orderNumber={order.id} printId={null} />
      </div>,
      document.body,
    )}
  </>
}
