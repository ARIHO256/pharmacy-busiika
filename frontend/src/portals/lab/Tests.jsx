import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Button, Card, Input, Modal, Table } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, useApi } from '../pharmacy/shared'

const emptyForm = { name: '', description: '', price: '', sample_type: '' }

export default function Tests() {
  const { user } = useAuth()
  const { data: tests, loading, error, reload } = useApi(() => servicesApi.labTests({ lab: user.id }))
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const openAdd = () => {
    setForm(emptyForm)
    setSaveError('')
    setModal({})
  }

  const openEdit = (t) => {
    setForm({ name: t.name, description: t.description || '', price: t.price, sample_type: t.sample_type || '' })
    setSaveError('')
    setModal({ editing: t })
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const payload = { ...form, price: Number(form.price || 0) }
      if (modal.editing) {
        await client.put(`/services/lab-tests/${modal.editing.id}/`, payload)
      } else {
        await servicesApi.saveLabTest(payload)
      }
      setModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (t) => {
    if (!window.confirm(`Delete test "${t.name}"?`)) return
    try {
      await client.delete(`/services/lab-tests/${t.id}/`)
      reload()
    } catch (err) {
      alert(errMsg(err))
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Lab tests catalog" actions={<Button onClick={openAdd}>+ Add test</Button>}>
        <Table
          empty="No tests yet — add your first one."
          columns={[
            { key: 'name', label: 'Name', render: (t) => <span className="font-medium text-slate-800">{t.name}</span> },
            {
              key: 'description',
              label: 'Description',
              render: (t) => <span className="text-slate-500 line-clamp-1 max-w-xs">{t.description || '—'}</span>,
            },
            { key: 'sample_type', label: 'Sample type', render: (t) => t.sample_type || '—' },
            { key: 'price', label: 'Price', render: (t) => money(t.price) },
            {
              key: 'actions',
              label: '',
              render: (t) => (
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => openEdit(t)}>
                    Edit
                  </Button>
                  <Button variant="danger" onClick={() => remove(t)}>
                    Delete
                  </Button>
                </div>
              ),
            },
          ]}
          rows={tests || []}
        />
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit test' : 'Add test'}>
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
              label="Sample type"
              placeholder="e.g. Blood, Urine"
              value={form.sample_type}
              onChange={(e) => setForm({ ...form, sample_type: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : modal?.editing ? 'Save changes' : 'Add test'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
