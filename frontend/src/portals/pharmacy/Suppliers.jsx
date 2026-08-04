import { useState } from 'react'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Button, Card, Input, Modal, Table } from '../../components/ui'
import { errMsg, ErrorNote, fmtDate, LoadingOrError, money, useApi } from './shared'

const emptyForm = { suppliername: '', contact: '', email: '', address: '', products: [] }
const emptyProduct = { name: '', qty: '', price: '' }

export default function Suppliers() {
  const { data: suppliers, loading, error, reload } = useApi(() => servicesApi.suppliers())
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const openAdd = () => {
    setForm(emptyForm)
    setSaveError('')
    setModal({})
  }

  const openEdit = (s) => {
    setForm({
      suppliername: s.suppliername || '',
      contact: s.contact || '',
      email: s.email || '',
      address: s.address || '',
      products: (s.products || []).map((p) => ({ name: p.name, qty: p.qty, price: p.price })),
    })
    setSaveError('')
    setModal({ editing: s })
  }

  const setProduct = (i, k, v) =>
    setForm((f) => ({ ...f, products: f.products.map((p, j) => (j === i ? { ...p, [k]: v } : p)) }))

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const payload = {
        suppliername: form.suppliername,
        contact: form.contact,
        email: form.email,
        address: form.address,
        products: form.products
          .filter((p) => p.name.trim())
          .map((p) => ({ name: p.name.trim(), qty: Number(p.qty || 0), price: Number(p.price || 0) })),
      }
      if (modal.editing) {
        await client.put(`/services/suppliers/${modal.editing.id}/`, payload)
      } else {
        await servicesApi.saveSupplier(payload)
      }
      setModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (s) => {
    if (!window.confirm(`Delete supplier "${s.suppliername}"?`)) return
    try {
      await servicesApi.deleteSupplier(s.id)
      reload()
    } catch (err) {
      alert(errMsg(err))
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Suppliers" actions={<Button onClick={openAdd}>+ Add supplier</Button>}>
        <Table
          empty="No suppliers yet"
          columns={[
            {
              key: 'suppliername',
              label: 'Supplier',
              render: (s) => <span className="font-medium text-slate-800">{s.suppliername}</span>,
            },
            { key: 'contact', label: 'Contact', render: (s) => s.contact || '—' },
            { key: 'email', label: 'Email', render: (s) => s.email || '—' },
            { key: 'address', label: 'Address', render: (s) => s.address || '—' },
            { key: 'supply_date', label: 'Since', render: (s) => fmtDate(s.supply_date) },
            {
              key: 'products',
              label: 'Products',
              render: (s) =>
                s.products?.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {s.products.map((p) => (
                      <span
                        key={p.id}
                        className="inline-block bg-slate-100 text-slate-600 rounded-full px-2.5 py-0.5 text-xs"
                        title={`${money(p.price)} each`}
                      >
                        {p.name} × {p.qty}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-slate-300">—</span>
                ),
            },
            {
              key: 'actions',
              label: '',
              render: (s) => (
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => openEdit(s)}>
                    Edit
                  </Button>
                  <Button variant="danger" onClick={() => remove(s)}>
                    Delete
                  </Button>
                </div>
              ),
            },
          ]}
          rows={suppliers || []}
        />
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit supplier' : 'Add supplier'} wide>
        <form onSubmit={save} className="space-y-4">
          <ErrorNote error={saveError} />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Input
              label="Supplier name"
              value={form.suppliername}
              onChange={(e) => setForm({ ...form, suppliername: e.target.value })}
              required
            />
            <Input label="Contact" value={form.contact} onChange={(e) => setForm({ ...form, contact: e.target.value })} />
            <Input
              label="Email"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            <Input label="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-slate-600">Products supplied</span>
              <Button
                variant="outline"
                type="button"
                onClick={() => setForm((f) => ({ ...f, products: [...f.products, { ...emptyProduct }] }))}
              >
                + Add product
              </Button>
            </div>
            {!form.products.length && <p className="text-xs text-slate-400">No products listed for this supplier.</p>}
            <div className="space-y-2">
              {form.products.map((p, i) => (
                <div key={i} className="grid grid-cols-[1fr_90px_120px_36px] gap-2 items-center">
                  <Input placeholder="Product name" value={p.name} onChange={(e) => setProduct(i, 'name', e.target.value)} />
                  <Input
                    placeholder="Qty"
                    type="number"
                    min="0"
                    value={p.qty}
                    onChange={(e) => setProduct(i, 'qty', e.target.value)}
                  />
                  <Input
                    placeholder="Price (UGX)"
                    type="number"
                    min="0"
                    value={p.price}
                    onChange={(e) => setProduct(i, 'price', e.target.value)}
                  />
                  <button
                    type="button"
                    className="text-slate-400 hover:text-rose-600 text-lg"
                    onClick={() => setForm((f) => ({ ...f, products: f.products.filter((_, j) => j !== i) }))}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : modal?.editing ? 'Save changes' : 'Add supplier'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
