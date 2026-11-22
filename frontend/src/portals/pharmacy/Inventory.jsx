import { usePharmacyPermissions } from './PharmacyPermissions'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext'
import MedicineTaxonomyFields from './MedicineTaxonomyFields'
import { Formulary } from './InventoryWorkflows'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Button, Card, Input, Modal, Select, Table } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, useApi } from './shared'

const saleTypes = {
  unclassified: 'Unclassified',
  otc: 'Over the counter',
  prescription: 'Prescription only',
  controlled: 'Controlled',
}
const emptyForm = { family: '', category: '', taxonomy_node: '', product_attributes: {}, sale_type: 'unclassified', name: '', description: '', price: '', units_per_pack: 1, unit_label: 'unit', reorder_level: 0, wholesale_minimum: '', wholesale_unit_price: '', stock: '', image: null }

export default function Inventory() {
  const [tab, setTab] = useState('inventory')
  return <div className="space-y-4">
    <div className="flex flex-wrap gap-2" aria-label="Medicine inventory views">
      <Button variant={tab === 'inventory' ? 'primary' : 'outline'} aria-pressed={tab === 'inventory'} onClick={() => setTab('inventory')}>Inventory</Button>
      <Button variant={tab === 'formulary' ? 'primary' : 'outline'} aria-pressed={tab === 'formulary'} onClick={() => setTab('formulary')}>Formulary</Button>
    </div>
    {tab === 'inventory' ? <InventoryList /> : <Formulary />}
  </div>
}

function InventoryList() {
  const allows = usePharmacyPermissions()
  const { user } = useAuth()
  const canManageSaved = user?.role === 'pharmacy'
  const canClassify = user?.role !== 'storekeeper'
  const { data: meds, loading, error, reload } = useApi(() => servicesApi.medicines())
  const taxonomy = useApi(() => servicesApi.medicineTaxonomy())
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
    setForm({ ...emptyForm, taxonomy_node: med.taxonomy_node || '', product_attributes: med.product_attributes || {}, sale_type: med.sale_type, name: med.name, description: med.description || '', price: med.price, units_per_pack: med.units_per_pack, unit_label: med.unit_label, reorder_level: med.reorder_level, wholesale_minimum: med.wholesale_minimum ?? '', wholesale_unit_price: med.wholesale_unit_price ?? '', stock: med.stock, image: null })
    setSaveError('')
    setModal({ editing: med })
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const fd = new FormData()
      if (canClassify) {
        fd.append('sale_type', form.sale_type)
        fd.append('wholesale_minimum', form.wholesale_minimum)
        fd.append('wholesale_unit_price', form.wholesale_unit_price)
      }
      if (!taxonomy.error && !taxonomy.loading && taxonomy.data?.length) {
        fd.append('taxonomy_node', form.taxonomy_node)
        fd.append('product_attributes', JSON.stringify(form.product_attributes))
      }
      fd.append('name', form.name)
      fd.append('description', form.description)
      fd.append('price', form.price)
      for (const key of ['units_per_pack', 'unit_label', 'reorder_level']) fd.append(key, form[key])
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
      <Card title="Medicine inventory" actions={<div className="flex flex-wrap items-center gap-3">
        {user?.role === 'pharmacy' && <Link to="/pharmacy/taxonomy" className="text-sm font-semibold text-primary-700">Manage taxonomy</Link>}
        {allows('catalogue_edit') && <Button onClick={openAdd}>+ Add medicine</Button>}
      </div>}>
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
            { key: 'taxonomy_node', label: 'Catalogue', render: (medicine) =>
              taxonomy.data?.find((node) => node.node_id === medicine.taxonomy_node)?.name || '—' },
            { key: 'sale_type', label: 'Sale classification', render: (m) => saleTypes[m.sale_type] },
            { key: 'price', label: 'Price', render: (m) => money(m.price) },
            { key: 'wholesale_minimum', label: 'Wholesale', render: (m) => m.wholesale_minimum ? `${m.wholesale_minimum}+ at ${money(m.wholesale_unit_price)} each` : '—' },
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
              render: (m) => canManageSaved && (
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
          {canClassify && <Select label="Sale classification" value={form.sale_type} onChange={(event) => setForm({ ...form, sale_type: event.target.value })}>
            {Object.entries(saleTypes).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>}
          <MedicineTaxonomyFields catalog={taxonomy} selection={form}
            setSelection={(selection) => setForm((current) => ({ ...current, ...selection }))} />
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
          <fieldset className="grid gap-3 sm:grid-cols-3">
            <legend className="mb-2 text-sm font-semibold">Pack sizes and stock</legend>
            <Input label="Base unit (e.g. tablet)" required maxLength={32} value={form.unit_label}
              onChange={(e) => setForm({ ...form, unit_label: e.target.value })} />
            <Input label="Units in one pack" required type="number" min="1" max="1000000" value={form.units_per_pack}
              onChange={(e) => setForm({ ...form, units_per_pack: e.target.value })} />
            <Input label="Reorder at this quantity" required type="number" min="0" value={form.reorder_level}
              onChange={(e) => setForm({ ...form, reorder_level: e.target.value })} />
            <p className="text-sm text-slate-600 sm:col-span-3">Enter retail and wholesale prices per base unit. For a wholesale pack minimum, enter the equivalent number of base units.</p>
          </fieldset>
          {canClassify && form.sale_type === 'otc' && <fieldset className="grid gap-3 sm:grid-cols-2">
            <legend className="mb-2 text-sm font-semibold">Wholesale ordering</legend>
            <Input label="Minimum units per order" type="number" min="2" max="1000000" required={Boolean(form.wholesale_unit_price)}
              value={form.wholesale_minimum} onChange={(e) => setForm({ ...form, wholesale_minimum: e.target.value })} />
            <Input label="Wholesale unit price (UGX)" type="number" min="1" required={Boolean(form.wholesale_minimum)}
              value={form.wholesale_unit_price} onChange={(e) => setForm({ ...form, wholesale_unit_price: e.target.value })} />
            <p className="text-sm text-slate-600 sm:col-span-2">Leave both fields blank to keep this product out of the wholesale shop.</p>
          </fieldset>}
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
