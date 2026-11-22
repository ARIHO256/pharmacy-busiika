import { useState } from 'react'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Button, Card, Input, Modal, Table } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, money, useApi } from '../pharmacy/shared'

const emptyForm = { name: '', price: '' }

export default function Services() {
  const { data: services, loading, error, reload } = useApi(() => servicesApi.hospitalServices())
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
    setForm({ name: s.name, price: s.price })
    setSaveError('')
    setModal({ editing: s })
  }

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      const payload = { name: form.name, price: Number(form.price || 0) }
      if (modal.editing) {
        await client.put(`/services/hospital-services/${modal.editing.id}/`, payload)
      } else {
        await servicesApi.saveHospitalService(payload)
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
    if (!window.confirm(`Delete service "${s.name}"?`)) return
    try {
      await client.delete(`/services/hospital-services/${s.id}/`)
      reload()
    } catch (err) {
      alert(errMsg(err))
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <Card title="Facility services" actions={<Button onClick={openAdd}>+ Add service</Button>}>
        <Table
          empty="No services yet — add your first one."
          columns={[
            { key: 'name', label: 'Name', render: (s) => <span className="font-medium text-slate-800">{s.name}</span> },
            { key: 'price', label: 'Price', render: (s) => money(s.price) },
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
          rows={services || []}
        />
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.editing ? 'Edit service' : 'Add service'}>
        <form onSubmit={save} className="space-y-4">
          <ErrorNote error={saveError} />
          <Input
            label="Service name"
            placeholder="e.g. General consultation, X-Ray"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            required
          />
          <Input
            label="Price (UGX)"
            type="number"
            min="0"
            value={form.price}
            onChange={(e) => setForm({ ...form, price: e.target.value })}
            required
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : modal?.editing ? 'Save changes' : 'Add service'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
