import OrderIssues from '../../pharmacy/OrderIssues'
import OrderReceipt from '../../pharmacy/OrderReceipt'
import React, { useCallback, useEffect, useState } from 'react'
import { servicesApi } from '../../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Select, Spinner, Table } from '../../../components/ui'
import { fmtDT, statusColor, ugx } from './helpers'

export default function PharmacyStore({ buyer = false }) {
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
  const [helpOrder, setHelpOrder] = useState(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [savedAddress, setSavedAddress] = useState('')
  const [addressDraft, setAddressDraft] = useState('')
  const [addressError, setAddressError] = useState('')
  const [addressSaving, setAddressSaving] = useState(false)
  const [receiptOrder, setReceiptOrder] = useState(null)
  const [notice, setNotice] = useState(null) // {type, text}
  const [qtys, setQtys] = useState({}) // medicineId -> qty

  useEffect(() => {
    if (!buyer) return
    servicesApi.pharmacyWorkspaceData('buyer-address').then(({ data }) => setSavedAddress(data.address)).catch(() => {})
  }, [buyer])

  async function saveAddress(event) {
    event.preventDefault()
    setAddressSaving(true)
    setAddressError('')
    try {
      const { data } = await servicesApi.saveBuyerAddress(addressDraft)
      setSavedAddress(data.address)
      setAccountOpen(false)
    } catch {
      setAddressError('Could not save the delivery address.')
    } finally {
      setAddressSaving(false)
    }
  }

  const loadMedicines = useCallback(async () => {
    try {
      const params = buyer ? { wholesale: 1 } : {}
      if (search) params.search = search
      if (pharmacyFilter) params.pharmacy = pharmacyFilter
      const { data } = await servicesApi.medicines(params)
      setMedicines(data)
    } catch {
      setMedicines([])
    }
  }, [search, pharmacyFilter, buyer])

  const loadCart = useCallback(async () => {
    try {
      const { data } = await servicesApi.cart(buyer)
      setCart(data)
    } catch {
      setCart([])
    }
  }, [buyer])

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
    const qty = Number(qtys[med.id] ?? med.wholesale_minimum ?? 1)
    try {
      await servicesApi.addCart(med.id, qty, buyer)
      await loadCart()
      loadMedicines()
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

  const unitPrice = (medicine) => medicine?.wholesale_unit_price ?? medicine?.price ?? 0
  const cartTotal = cart.reduce((sum, i) => sum + unitPrice(i.medicine) * i.qty, 0)
  const invalidWholesaleCart = buyer && cart.some((i) =>
    !i.medicine?.wholesale_minimum || !i.medicine?.wholesale_unit_price || i.qty < i.medicine.wholesale_minimum)

  const checkout = async (e) => {
    e.preventDefault()
    if (placing) return
    setPlacing(true)
    try {
      await servicesApi.checkout({ delivery, address: delivery ? address.trim() : '' }, buyer)
      setCheckoutOpen(false)
      setCartOpen(false)
      setAddress('')
      setDelivery(false)
      await loadCart()
      loadMedicines()
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
          {buyer && <Button variant="outline" onClick={() => { setAddressDraft(savedAddress); setAddressError(''); setAccountOpen(true) }}>Buyer account</Button>}
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
                    {p.org_name}{p.parent_facility_name ? ` · ${p.parent_facility_name} (${p.parent_facility_type})` : ''}
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
                      className="w-full h-32 object-cover rounded-lg mb-3"
                    />
                  )}
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <h4 className="font-semibold text-slate-800">{m.name}</h4>
                      <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">{m.description}</p>
                    </div>
                    <span className="text-sm font-bold text-primary-600 whitespace-nowrap">
                      {ugx(unitPrice(m))}
                    </span>
                  </div>
                  <div className="mt-2 text-xs">
                    {m.wholesale_minimum && <p className="mb-1 text-slate-600">Minimum {m.wholesale_minimum} units · price per unit</p>}
                    {m.stock > 0 ? (
                      <Badge color="green">{m.stock} in stock</Badge>
                    ) : (
                      <Badge color="red">Out of stock</Badge>
                    )}
                  </div>
                  <div className="mt-3 flex items-center gap-2">
                    <input
                      type="number"
                      min={m.wholesale_minimum ?? 1}
                      max={m.stock}
                      aria-label={`Quantity for ${m.name}`}
                      value={qtys[m.id] ?? m.wholesale_minimum ?? 1}
                      onChange={(e) => setQtys({ ...qtys, [m.id]: e.target.value })}
                      className="w-16 px-2 py-1.5 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                    <Button
                      className="flex-1"
                      disabled={!m.available_online || Number(qtys[m.id] ?? m.wholesale_minimum ?? 1) < (m.wholesale_minimum ?? 1) || Number(qtys[m.id] ?? m.wholesale_minimum ?? 1) > m.stock}
                      onClick={() => addToCart(m)}
                    >
                      {m.available_online ? 'Add to cart' : ['prescription', 'controlled'].includes(m.sale_type) ? 'Prescription required' : 'Unavailable online'}
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'orders' && (
        <Card title="My Orders" actions={<Button variant="outline" onClick={loadOrders}>Refresh orders</Button>}>
          {orders === null ? (
            <Spinner label="Loading orders…" />
          ) : (
            <div className="space-y-4">
              {orders.length === 0 && (
                <div className="text-sm text-slate-400 text-center py-8">No orders yet.</div>
              )}
              {orders.map((o) => {
                const pharmacy = pharmacies.find((entry) => entry.id === o.pharmacy)
                return (
                <div key={o.id} className="border border-slate-200 rounded-xl p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm">
                      <span className="font-semibold text-slate-800">Order #{o.id}</span>
                      <span className="text-slate-500"> · {o.pharmacy_contact?.legal_name || pharmacy?.org_name || o.pharmacy_name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge color={statusColor(o.status)}>{({ ready: 'Ready for pickup', dispatched: 'Out for delivery', delivered: o.delivery ? 'Delivered' : 'Collected' })[o.status] || o.status}</Badge>
                      <span className="font-bold text-primary-600 text-sm">{ugx(o.total)}</span>
                    </div>
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {fmtDT(o.created_at)} · {o.delivery ? `Delivery to ${o.address}` : (o.pharmacy_contact?.address || pharmacy?.address) ? `Pickup at ${o.pharmacy_contact?.address || pharmacy.address}` : 'Pickup'}
                    {o.handed_over_at && ` · Handover recorded ${fmtDT(o.handed_over_at)}`}
                  </div>
                  {o.pickup_instructions && <p className="text-sm">{o.pickup_instructions}</p>}
                  {o.pharmacy_contact?.phone && <p className="text-sm">Pharmacy phone <a className="underline" href={`tel:${o.pharmacy_contact.phone.replace(/[^+0-9]/g, '')}`}>{o.pharmacy_contact.phone}</a></p>}
                  {o.credit && <p className="text-sm">Balance {ugx(o.credit.balance)} · Due {new Date(o.credit.due_at).toLocaleDateString()}</p>}
                  {o.billing_status === 'refunded' && <p className="text-sm font-semibold">Refunded</p>}
                  {buyer && <Button variant="outline" className="mt-2" onClick={() => setHelpOrder(o)}>Order help</Button>}
                  {o.payment_recorded && <Button variant="outline" className="mt-2"
                    onClick={() => setReceiptOrder(o)}>Print receipt</Button>}
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
                )
              })}
            </div>
          )}
        </Card>
      )}

      {receiptOrder && <OrderReceipt order={receiptOrder} onClose={() => setReceiptOrder(null)} />}

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
                    {ugx(unitPrice(i.medicine))} × {i.qty}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-slate-700">
                    {ugx(unitPrice(i.medicine) * i.qty)}
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
            {invalidWholesaleCart && <p className="text-sm text-rose-700">Remove items that are unavailable for wholesale or below the minimum, then add them again from the shop.</p>}
            <div className="flex justify-end">
              <Button disabled={invalidWholesaleCart} onClick={() => setCheckoutOpen(true)}>Checkout</Button>
            </div>
          </div>
        )}
      </Modal>

      {helpOrder && <OrderIssues order={helpOrder} buyer onClose={() => setHelpOrder(null)} />}
      {accountOpen && <Modal open title="Buyer account" onClose={() => { if (!addressSaving) setAccountOpen(false) }}>
        <form onSubmit={saveAddress} className="space-y-3">
          <Input label="Saved delivery address" maxLength={255} value={addressDraft} onChange={(event) => setAddressDraft(event.target.value)} />
          {addressError && <p className="text-sm text-rose-700">{addressError}</p>}
          <Button disabled={addressSaving}>Save delivery address</Button>
        </form>
      </Modal>}
      {/* checkout modal */}
      <Modal open={checkoutOpen} onClose={() => setCheckoutOpen(false)} title="Checkout">
        <form onSubmit={checkout} className="space-y-4">
          <p className="text-sm text-slate-600">Pay the pharmacy at pickup or on delivery.</p>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={delivery}
              onChange={(e) => { setDelivery(e.target.checked); if (e.target.checked && !address) setAddress(savedAddress) }}
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
              maxLength={255}
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
