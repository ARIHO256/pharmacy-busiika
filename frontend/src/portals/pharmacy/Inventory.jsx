import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Button, Card, Input, Modal, Table } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, useApi } from './shared'

const emptyForm = { name: '', description: '', price: '', stock: '', image: null }

export default function Inventory() {
  const { user } = useAuth()
  const { data: meds, loading, error, reload } = useApi(() => servicesApi.medicines({ pharmacy: user.id }))
  const [modal, setModal] = useState(null) // {editing?: med}
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [deleting, setDeleting] = useState(null)

  const openAdd = () => {
    setForm(emptyForm)
    setSaveError('')
    setModal({})
  }

  const openEdit = (med) => {
    setForm({ name: med.name, description: med.description || '', price: med.price, stock: med.stock, image: null })
    setSaveError('')
    setModal({ editing: med })
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const fd = new FormData()
      fd.append('name', form.name)
      fd.append('description', form.description)
      fd.append('price', form.price)
      fd.append('stock', form.stock)
      if (form.image) fd.append('image', form.image)
      if (modal.editing) {
        await client.put(`/services/medicines/${modal.editing.id}/`, fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      } else {
        await client.post('/services/medicines/', fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      }
      setModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (med) => {
    if (!window.confirm(`Delete "${med.name}" from inventory?`)) return
    setDeleting(med.id)
    try {
      await servicesApi.deleteMedicine(med.id)
      reload()
    } catch (err) {
      alert(errMsg(err))
    } finally {
      setDeleting(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Medicine inventory" actions={<Button onClick={openAdd}>+ Add medicine</Button>}>
        <Table
          empty="No medicines yet — add your first one."
          columns={[
            {
              key: 'image',
              label: '',
              render: (m) =>
                m.image ? (
                  <img src={m.image} alt={m.name} className="w-10 h-10 rounded-lg object-cover border border-slate-200" />
                ) : (
                  <div className="w-10 h-10 rounded-lg bg-slate-100 flex items-center justify-center text-slate-400">💊</div>
                ),
            },
            { key: 'name', label: 'Name', render: (m) => <span className="font-medium text-slate-800">{m.name}</span> },
            {
              key: 'description',
              label: 'Description',
              render: (m) => <span className="text-slate-500 line-clamp-1 max-w-xs">{m.description || '—'}</span>,
            },
            { key: 'price', label: 'Price', render: (m) => money(m.price) },
            {
              key: 'stock',
              label: 'Stock',
              render: (m) => (
                <span className={m.stock > 0 ? 'text-slate-700' : 'text-rose-600 font-medium'}>
                  {m.stock > 0 ? m.stock : 'Out of stock'}
                </span>
              ),
            },
            {
              key: 'actions',
              label: '',
              render: (m) => (
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => openEdit(m)}>
                    Edit
                  </Button>
                  <Button variant="danger" disabled={deleting === m.id} onClick={() => remove(m)}>
                    {deleting === m.id ? '…' : 'Delete'}
                  </Button>
                </div>
              ),
            },
          ]}
          rows={meds || []}
        />
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit medicine' : 'Add medicine'}>
        <form onSubmit={save} className="space-y-4">
          <ErrorNote error={saveError} />
          <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <label className="block">
            <span className="block text-sm font-medium text-slate-600 mb-1">Description</span>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Price (UGX)"
              type="number"
              min="0"
              value={form.price}
              onChange={(e) => setForm({ ...form, price: e.target.value })}
              required
            />
            <Input
              label="Stock"
              type="number"
              min="0"
              value={form.stock}
              onChange={(e) => setForm({ ...form, stock: e.target.value })}
              required
            />
          </div>
          <Input
            label="Image (optional)"
            type="file"
            accept="image/*"
            onChange={(e) => setForm({ ...form, image: e.target.files?.[0] || null })}
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : modal?.editing ? 'Save changes' : 'Add medicine'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
