import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Select, Table } from '../../components/ui'
import OrderReceipt from './OrderReceipt'
import { errMsg, LoadingOrError, money, useApi } from './shared'

const methods = [['cash', 'Cash'], ['mobile_money', 'Mobile money'], ['card', 'Card terminal'], ['bank', 'Bank transfer']]

export default function Counter() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const catalog = useApi(() => servicesApi.counterProducts(query), [query])
  const [items, setItems] = useState([])
  const [method, setMethod] = useState('cash')
  const [reference, setReference] = useState('')
  const [requestId, setRequestId] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [sale, setSale] = useState(null)
  const total = items.reduce((sum, item) => sum + item.price * Number(item.quantity), 0)
  const resetRequest = () => setRequestId(crypto.randomUUID())

  function add(product) {
    resetRequest()
    setItems((current) => [...current, { ...product, quantity: 1 }])
  }

  async function complete(event) {
    event.preventDefault()
    if (busy || !items.length) return
    setBusy(true)
    setError('')
    try {
      const { data } = await servicesApi.counterSale({
        request_id: requestId, amount: total, method, reference,
        items: items.map(({ id, quantity }) => ({ medicine: id, quantity: Number(quantity) })),
      })
      setSale(data)
      setItems([])
      setReference('')
      resetRequest()
      catalog.reload()
    } catch (failure) {
      setError(errMsg(failure))
    } finally {
      setBusy(false)
    }
  }

  return <div className="grid gap-5 xl:grid-cols-2">
    <Card title="Find medicines">
      <form className="flex items-end gap-2 pb-4" onSubmit={(event) => { event.preventDefault(); setQuery(search.trim()) }}>
        <Input label="Medicine name" type="search" className="flex-1" value={search} onChange={(event) => setSearch(event.target.value)} />
        <Button type="submit">Search</Button>
      </form>
      <LoadingOrError loading={catalog.loading} error={catalog.error}>
        <Table rows={catalog.data || []} empty="No matching medicines" columns={[
          { key: 'name', label: 'Medicine' },
          { key: 'price', label: 'Unit price', render: (row) => money(row.price) },
          { key: 'action', label: 'Availability', render: (row) => {
            if (row.sale_type === 'unclassified') return 'Classification required'
            if (row.sale_type !== 'otc') return user?.role === 'cashier' ? 'Refer to pharmacist' :
              <Link className="text-primary-700 underline" to={user?.role === 'pharmacy' ? '/pharmacy/rx-orders' : '/pharmacist/rx-orders'}>Prescription queue</Link>
            if (!row.stock) return 'No eligible stock'
            return <Button variant="outline" disabled={busy || items.some((item) => item.id === row.id)}
              onClick={() => add(row)}>Add · {row.stock} available</Button>
          } },
        ]} />
      </LoadingOrError>
    </Card>
    <Card title="Walk-in sale" subtitle="OTC sales can be completed without a customer account. Stock is allocated by earliest expiry.">
      <form className="space-y-4" onSubmit={complete}>
        {items.map((item) => <div key={item.id} className="grid items-end gap-2 border-b pb-3 sm:grid-cols-[1fr_6rem_auto]">
          <div><p className="font-semibold">{item.name}</p><p className="text-sm text-slate-600">{money(item.price)} each</p></div>
          <Input required disabled={busy} type="number" min="1" max={item.stock} label={`Quantity for ${item.name}`}
            value={item.quantity} onChange={(event) => {
              resetRequest()
              setItems((current) => current.map((row) => row.id === item.id ? { ...row, quantity: event.target.value } : row))
            }} />
          <Button type="button" variant="outline" disabled={busy} onClick={() => {
            resetRequest()
            setItems((current) => current.filter((row) => row.id !== item.id))
          }}>Remove</Button>
        </div>)}
        <p className="text-lg font-semibold">Total {money(total)}</p>
        <Select label="Payment received by" disabled={busy} value={method} onChange={(event) => {
          resetRequest()
          setMethod(event.target.value)
          setReference('')
        }}>
          {methods.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </Select>
        {method !== 'cash' && <Input required disabled={busy} label="Payment reference" maxLength={120} value={reference}
          onChange={(event) => { resetRequest(); setReference(event.target.value) }} />}
        {error && <Alert tone="danger">{error}</Alert>}
        <Button type="submit" disabled={busy || !items.length || total <= 0}>
          {busy ? 'Recording sale…' : 'Record payment and issue receipt'}
        </Button>
      </form>
    </Card>
    {sale && <OrderReceipt order={{ id: sale.order_id, payment_recorded: true }} initialReceipt={sale.receipt} onClose={() => setSale(null)} />}
  </div>
}
