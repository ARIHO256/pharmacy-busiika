import { useState } from 'react'
import { useAuth } from '../../auth/AuthContext'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal, Table } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, useApi } from '../pharmacy/shared'

const emptyForm = { name: '', coverage_percent: '', premium: '', description: '' }

export default function Policies() {
  const { user } = useAuth()
  const { data: policies, loading, error, reload } = useApi(() => servicesApi.policies({ provider: user.id }))
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const openAdd = () => {
    setForm(emptyForm)
    setSaveError('')
    setModal({})
  }

  const openEdit = (p) => {
    setForm({
      name: p.name,
      coverage_percent: p.coverage_percent,
      premium: p.premium,
      description: p.description || '',
    })
    setSaveError('')
    setModal({ editing: p })
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const payload = {
        name: form.name,
        coverage_percent: Number(form.coverage_percent || 0),
        premium: Number(form.premium || 0),
        description: form.description,
      }
      if (modal.editing) {
        await client.put(`/services/policies/${modal.editing.id}/`, payload)
      } else {
        await servicesApi.savePolicy(payload)
      }
      setModal(null)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const remove = async (p) => {
    if (!window.confirm(`Delete policy "${p.name}"?`)) return
    try {
      await client.delete(`/services/policies/${p.id}/`)
      reload()
    } catch (err) {
      alert(errMsg(err))
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Insurance policies" actions={<Button onClick={openAdd}>+ Add policy</Button>}>
        <Table
          empty="No policies yet — add your first one."
          columns={[
            { key: 'name', label: 'Name', render: (p) => <span className="font-medium text-slate-800">{p.name}</span> },
            {
              key: 'coverage_percent',
              label: 'Coverage',
              render: (p) => <Badge color="blue">{p.coverage_percent}%</Badge>,
            },
            { key: 'premium', label: 'Premium', render: (p) => money(p.premium) },
            {
              key: 'description',
              label: 'Description',
              render: (p) => <span className="text-slate-500 line-clamp-1 max-w-xs">{p.description || '—'}</span>,
            },
            {
              key: 'actions',
              label: '',
              render: (p) => (
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" onClick={() => openEdit(p)}>
                    Edit
                  </Button>
                  <Button variant="danger" onClick={() => remove(p)}>
                    Delete
                  </Button>
                </div>
              ),
            },
          ]}
          rows={policies || []}
        />
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit policy' : 'Add policy'}>
        <form onSubmit={save} className="space-y-4">
          <ErrorNote error={saveError} />
          <Input label="Policy name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <div className="grid grid-cols-2 gap-4">
            <Input
              label="Coverage (%)"
              type="number"
              min="0"
              max="100"
              value={form.coverage_percent}
              onChange={(e) => setForm({ ...form, coverage_percent: e.target.value })}
              required
            />
            <Input
              label="Premium (UGX)"
              type="number"
              min="0"
              value={form.premium}
              onChange={(e) => setForm({ ...form, premium: e.target.value })}
              required
            />
          </div>
          <label className="block">
            <span className="block text-sm font-medium text-slate-600 mb-1">Description</span>
            <textarea
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              rows={3}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : modal?.editing ? 'Save changes' : 'Add policy'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
