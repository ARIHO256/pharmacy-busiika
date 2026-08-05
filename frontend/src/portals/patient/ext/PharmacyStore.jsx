import React, { useCallback, useEffect, useState } from 'react'
import { servicesApi } from '../../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Spinner, Table } from '../../../components/ui'
import { fmtDT, statusColor, ugx } from './helpers'

export default function PharmacyStore() {
  const [tab, setTab] = useState('shop') // shop | orders
  const [medicines, setMedicines] = useState(null)
  const [pharmacies, setPharmacies] = useState([])
  const [search, setSearch] = useState('')
  const [pharmacyFilter, setPharmacyFilter] = useState('')
  const [cart, setCart] = useState([])
  const [cartOpen, setCartOpen] = useState(false)
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [delivery, setDelivery] = useState(false)
  const [address, setAddress] = useState('')
  const [placing, setPlacing] = useState(false)
  const [orders, setOrders] = useState(null)
  const [notice, setNotice] = useState(null) // {type, text}
  const [qtys, setQtys] = useState({}) // medicineId -> qty

  const loadMedicines = useCallback(async () => {
    try {
      const params = {}
      if (search) params.search = search
      if (pharmacyFilter) params.pharmacy = pharmacyFilter
      const { data } = await servicesApi.medicines(params)
      setMedicines(data)
    } catch {
      setMedicines([])
    }
  }, [search, pharmacyFilter])

  const loadCart = useCallback(async () => {
    try {
      const { data } = await servicesApi.cart()
      setCart(data)
    } catch {
      setCart([])
    }
  }, [])

  useEffect(() => {
    servicesApi.providers('pharmacies').then(({ data }) => setPharmacies(data)).catch(() => {})
    loadCart()
  }, [loadCart])

  useEffect(() => {
    const t = setTimeout(loadMedicines, 300) // debounce search
    return () => clearTimeout(t)
  }, [loadMedicines])

  const loadOrders = useCallback(async () => {
    setOrders(null)
    try {
      const { data } = await servicesApi.orders()
      setOrders(data)
    } catch {
      setOrders([])
    }
  }, [])

  useEffect(() => {
    if (tab === 'orders') loadOrders()
  }, [tab, loadOrders])

  const addToCart = async (med) => {
    const qty = Math.max(1, parseInt(qtys[med.id] || 1, 10) || 1)
    try {
      await servicesApi.addCart(med.id, qty)
      await loadCart()
      setNotice({ type: 'success', text: `${med.name} added to cart.` })
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Failed to add to cart' })
    }
  }

  const removeFromCart = async (item) => {
    try {
      await servicesApi.removeCart(item.id)
      await loadCart()
    } catch {
      /* ignore */
    }
  }

  const cartTotal = cart.reduce((sum, i) => sum + (i.medicine?.price || 0) * i.qty, 0)

  const checkout = async (e) => {
    e.preventDefault()
    setPlacing(true)
    try {
      await servicesApi.checkout({ delivery, address: delivery ? address : '' })
      setCheckoutOpen(false)
      setCartOpen(false)
      setAddress('')
      setDelivery(false)
      await loadCart()
      setNotice({ type: 'success', text: 'Order placed successfully!' })
      setTab('orders')
    } catch (err) {
      setNotice({ type: 'error', text: err?.response?.data?.detail || 'Checkout failed' })
      setCheckoutOpen(false)
    } finally {
      setPlacing(false)
    }
  }

  return (
    <div className="space-y-4">
      {notice && (
        <div
          className={`rounded-lg px-4 py-3 text-sm flex items-center justify-between ${
            notice.type === 'success'
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              : 'bg-rose-50 text-rose-700 border border-rose-200'
          }`}
        >
          <span>{notice.text}</span>
          <button className="ml-3 text-lg leading-none" onClick={() => setNotice(null)}>
            &times;
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Button variant={tab === 'shop' ? 'primary' : 'outline'} onClick={() => setTab('shop')}>
            Shop
          </Button>
          <Button variant={tab === 'orders' ? 'primary' : 'outline'} onClick={() => setTab('orders')}>
            My Orders
          </Button>
        </div>
        <Button variant="outline" onClick={() => setCartOpen(true)}>
          🛒 Cart ({cart.reduce((s, i) => s + i.qty, 0)})
        </Button>
      </div>

      {tab === 'shop' && (
        <>
          <Card>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Input
                label="Search medicines"
                placeholder="e.g. Paracetamol"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <Select
                label="Pharmacy"
                value={pharmacyFilter}
                onChange={(e) => setPharmacyFilter(e.target.value)}
              >
                <option value="">All pharmacies</option>
                {pharmacies.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.org_name}
                  </option>
                ))}
              </Select>
            </div>
          </Card>

          {medicines === null ? (
            <Spinner label="Loading medicines…" />
          ) : medicines.length === 0 ? (
            <Card>
              <div className="text-sm text-slate-400 text-center py-8">
                No medicines match your search.
              </div>
            </Card>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {medicines.map((m) => (
                <Card key={m.id}>
                  {m.image && (
                    <img
                      src={m.image}
                      alt={m.name}
                      className="w-full h-44 object-contain rounded-lg mb-3 bg-slate-50 border border-slate-100"
                    />
                  )}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-slate-800">{m.name}</h4>
                      <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">{m.description}</p>
                    </div>
                    <span className="text-sm font-bold text-primary-600 whitespace-nowrap">
                      {ugx(m.price)}
                    </span>
                  </div>
                  <div className="mt-2 text-xs">
                    {m.stock > 0 ? (
                      <Badge color="green">{m.stock} in stock</Badge>
                    ) : (
                      <Badge color="red">Out of stock</Badge>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <input
                      type="number"
                      min="1"
                      max={m.stock}
                      value={qtys[m.id] || 1}
                      onChange={(e) => setQtys({ ...qtys, [m.id]: e.target.value })}
                      aria-label={`Quantity of ${m.name}`}
                      className="w-16 px-2 py-1.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <Button
                      className="flex-1"
                      disabled={m.stock <= 0}
                      onClick={() => addToCart(m)}
                    >
                      Add to cart
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'orders' && (
        <Card title="My Orders">
          {orders === null ? (
            <Spinner label="Loading orders…" />
          ) : (
            <div className="space-y-4">
              {orders.length === 0 && (
                <div className="text-sm text-slate-400 text-center py-8">No orders yet.</div>
              )}
              {orders.map((o) => (
                <div key={o.id} className="border border-slate-200 rounded-xl p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm">
                      <span className="font-semibold text-slate-800">Order #{o.id}</span>
                      <span className="text-slate-500"> · {o.pharmacy_name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge color={statusColor(o.status)}>{o.status}</Badge>
                      <span className="font-bold text-primary-600 text-sm">{ugx(o.total)}</span>
                    </div>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {fmtDT(o.created_at)} · {o.delivery ? `Delivery to ${o.address}` : 'Pickup'}
                  </div>
                  <Table
                    empty="No items"
                    columns={[
                      { key: 'name', label: 'Item' },
                      { key: 'price', label: 'Price', render: (r) => ugx(r.price) },
                      { key: 'qty', label: 'Qty' },
                      { key: 'sub', label: 'Subtotal', render: (r) => ugx(r.price * r.qty) },
                    ]}
                    rows={o.items || []}
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* cart drawer */}
      <Modal open={cartOpen} onClose={() => setCartOpen(false)} title="Your Cart">
        {cart.length === 0 ? (
          <div className="text-sm text-slate-400 text-center py-8">Your cart is empty.</div>
        ) : (
          <div className="space-y-3">
            {cart.map((i) => (
              <div
                key={i.id}
                className="flex items-center justify-between gap-3 border-b border-slate-100 pb-3"
              >
                <div>
                  <p className="text-sm font-medium text-slate-800">{i.medicine?.name}</p>
                  <p className="text-xs text-slate-500">
                    {ugx(i.medicine?.price)} × {i.qty}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-slate-700">
                    {ugx((i.medicine?.price || 0) * i.qty)}
                  </span>
                  <Button variant="danger" className="px-2 py-1 text-xs" onClick={() => removeFromCart(i)}>
                    Remove
                  </Button>
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between pt-2">
              <span className="font-semibold text-slate-800">Total</span>
              <span className="font-bold text-primary-600">{ugx(cartTotal)}</span>
            </div>
            <div className="flex justify-end">
              <Button onClick={() => setCheckoutOpen(true)}>Checkout</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* checkout modal */}
      <Modal open={checkoutOpen} onClose={() => setCheckoutOpen(false)} title="Checkout">
        <form onSubmit={checkout} className="space-y-4">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={delivery}
              onChange={(e) => setDelivery(e.target.checked)}
              className="rounded border-slate-300 text-primary-600 focus:ring-primary-500"
            />
            Deliver to my address
          </label>
          {delivery && (
            <Input
              label="Delivery address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Street, area, city"
              required
            />
          )}
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">Total</span>
            <span className="font-bold text-primary-600">{ugx(cartTotal)}</span>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setCheckoutOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={placing || (delivery && !address.trim())}>
              {placing ? 'Placing order…' : 'Place Order'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
