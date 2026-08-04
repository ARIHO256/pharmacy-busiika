import { useState } from 'react'
import { billingApi, workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner, Table, Textarea } from '../../components/ui'
import { downloadBlob, getError, money, statusBadge, useRemote } from '../staff/shared'
import ReceiptPrint from './ReceiptPrint'

const emptyItem = () => ({ code: '', description: '', quantity: 1, unit_price: '', discount_amount: 0, service_type: 'other', source_id: '' })
export default function Invoices() {
  const invoices = useRemote(() => billingApi.invoices(), [])
  const [createOpen, setCreateOpen] = useState(false)
  const [paying, setPaying] = useState(null)
  const [receipt, setReceipt] = useState(null)
  const [patients, setPatients] = useState([])
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')
  const [form, setForm] = useState({ patient: '', discount_amount: 0, tax_amount: 0, currency: 'UGX', notes: '', items: [emptyItem()] })
  const [notice, setNotice] = useState('')
  const [payment, setPayment] = useState({ amount: '', method: 'cash', reference: '', notes: '' })

  const findPatients = async () => { try { const { data } = await workforceApi.patients(search); setPatients(data) } catch (err) { setError(getError(err)) } }
  const setItem = (index, key, value) => setForm({ ...form, items: form.items.map((item, i) => i === index ? { ...item, [key]: value } : item) })
  const create = async (e) => { e.preventDefault(); setError(''); try { await billingApi.createInvoice({ ...form, items: form.items.map((item) => ({ ...item, quantity: Number(item.quantity), unit_price: Number(item.unit_price), discount_amount: Number(item.discount_amount || 0) })) }); setCreateOpen(false); setForm({ patient: '', discount_amount: 0, tax_amount: 0, currency: 'UGX', notes: '', items: [emptyItem()] }); invoices.reload() } catch (err) { setError(getError(err)) } }
  const downloadInvoice = async (invoice) => { setError(''); try { downloadBlob(await billingApi.invoicePdf(invoice.id), `${invoice.number}.pdf`) } catch (err) { setError(getError(err)) } }
  const sendInvoice = async (invoice) => { setError(''); try { const { data } = await billingApi.sendInvoice(invoice.id); setNotice(data.detail || 'Invoice sent.') } catch (err) { setError(getError(err)) } }
  const recordPayment = async (e) => { e.preventDefault(); setError(''); try { const { data } = await billingApi.recordPayment(paying.id, { ...payment, amount: Number(payment.amount) }); setReceipt(data.receipt); setPaying(null); invoices.reload() } catch (err) { setError(getError(err)) } }
  if (invoices.loading) return <Spinner />
  return <div className="space-y-4">
    {error && <Alert tone="danger">{error}</Alert>}
    {notice && <Alert tone="success">{notice}</Alert>}
    <Card title="Invoices and collections" subtitle="Issue itemised invoices, record payments and generate official receipts" actions={<Button onClick={() => { setCreateOpen(true); setError('') }}>Create invoice</Button>}>
      <Table rows={invoices.data || []} empty="No invoices issued" columns={[
        { key:'number',label:'Invoice' },{key:'patient_name',label:'Patient'},{key:'amount',label:'Total',render:(i)=>money(i.amount,i.currency)},{key:'paid_amount',label:'Paid',render:(i)=>money(i.paid_amount,i.currency)},{key:'balance',label:'Balance',render:(i)=>money(i.balance,i.currency)},{key:'status',label:'Status',render:(i)=>statusBadge(i.status)},
        { key:'action',label:'',render:(i)=><div className="flex flex-wrap gap-1"><Button variant="outline" onClick={()=>downloadInvoice(i)}>PDF</Button><Button variant="outline" onClick={()=>sendInvoice(i)}>Email</Button><Button disabled={!i.balance} onClick={()=>{setPaying(i);setPayment({amount:i.balance,method:'cash',reference:'',notes:''});setError('')}}>Receive payment</Button></div> },
      ]}/>
    </Card>
    {receipt && <div className="space-y-3"><div className="flex justify-end gap-2"><Button variant="outline" onClick={() => setReceipt(null)}>Close receipt</Button><Button variant="outline" onClick={async()=>receipt.id&&downloadBlob(await billingApi.receiptPdf(receipt.id), `${receipt.number}.pdf`)}>Receipt PDF</Button><Button onClick={() => window.print()}>Print receipt</Button></div><ReceiptPrint receipt={receipt}/></div>}
    <Modal open={createOpen} onClose={() => setCreateOpen(false)} wide title="Create patient invoice"><form onSubmit={create} className="space-y-4">
      <div className="flex gap-2"><Input className="flex-1" value={search} onChange={(e)=>setSearch(e.target.value)} placeholder="Search patient by name, phone or email"/><Button type="button" variant="outline" onClick={findPatients}>Search</Button></div>
      <Select required label="Patient" value={form.patient} onChange={(e)=>setForm({...form,patient:e.target.value})}><option value="">Select patient</option>{patients.map((p)=><option key={p.id} value={p.id}>{p.name} — {p.phone}</option>)}</Select>
      <div className="space-y-3">{form.items.map((item,index)=><div key={index} className="grid gap-2 rounded-xl border border-slate-200 p-3 md:grid-cols-[1fr_90px_150px_100px_auto]"><Input required label="Service / item" value={item.description} onChange={(e)=>setItem(index,'description',e.target.value)}/><Input required label="Qty" min="1" type="number" value={item.quantity} onChange={(e)=>setItem(index,'quantity',e.target.value)}/><Input required label="Unit price" min="0" type="number" value={item.unit_price} onChange={(e)=>setItem(index,'unit_price',e.target.value)}/><Input label="Discount" min="0" type="number" value={item.discount_amount} onChange={(e)=>setItem(index,'discount_amount',e.target.value)}/><Button type="button" variant="ghost" onClick={()=>setForm({...form,items:form.items.filter((_,i)=>i!==index)})}>Remove</Button></div>)}</div>
      <Button type="button" variant="outline" onClick={()=>setForm({...form,items:[...form.items,emptyItem()]})}>Add invoice item</Button>
      <div className="grid gap-3 sm:grid-cols-3"><Input label="Invoice discount" type="number" min="0" value={form.discount_amount} onChange={(e)=>setForm({...form,discount_amount:Number(e.target.value)})}/><Input label="Tax" type="number" min="0" value={form.tax_amount} onChange={(e)=>setForm({...form,tax_amount:Number(e.target.value)})}/><Select label="Currency" value={form.currency} onChange={(e)=>setForm({...form,currency:e.target.value})}><option>UGX</option><option>USD</option><option>KES</option></Select></div>
      <Textarea label="Billing notes" value={form.notes} onChange={(e)=>setForm({...form,notes:e.target.value})}/><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setCreateOpen(false)}>Cancel</Button><Button>Issue invoice</Button></div>
    </form></Modal>
    <Modal open={!!paying} onClose={()=>setPaying(null)} title={`Receive payment — ${paying?.number || ''}`}><form onSubmit={recordPayment} className="space-y-4">
      <Alert tone="info">Outstanding balance: <strong>{money(paying?.balance,paying?.currency)}</strong></Alert><Input required type="number" min="1" max={paying?.balance} label="Amount received" value={payment.amount} onChange={(e)=>setPayment({...payment,amount:e.target.value})}/><Select label="Method" value={payment.method} onChange={(e)=>setPayment({...payment,method:e.target.value})}><option value="cash">Cash</option><option value="mobile_money">Mobile money</option><option value="card">Card</option><option value="bank">Bank transfer</option><option value="wallet">Wallet</option><option value="insurance">Insurance</option></Select><Input label="Transaction reference" value={payment.reference} onChange={(e)=>setPayment({...payment,reference:e.target.value})}/><Textarea label="Payment notes" value={payment.notes} onChange={(e)=>setPayment({...payment,notes:e.target.value})}/><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={()=>setPaying(null)}>Cancel</Button><Button>Record and issue receipt</Button></div>
    </form></Modal>
  </div>
}
