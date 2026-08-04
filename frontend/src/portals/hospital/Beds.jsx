import { useMemo, useState } from 'react'
import client from '../../api/client'
import { servicesApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Modal } from '../../components/ui'
import { errMsg, ErrorNote, LoadingOrError, useApi } from '../pharmacy/shared'

export default function Beds() {
  const { data: beds, loading, error, reload } = useApi(() => servicesApi.beds())
  const [modal, setModal] = useState(false)
  const [form, setForm] = useState({ ward: '', label: '' })
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [busy, setBusy] = useState(null)

  const wards = useMemo(() => {
    const groups = {}
    for (const b of beds || []) {
      const w = b.ward || 'General'
      if (!groups[w]) groups[w] = []
      groups[w].push(b)
    }
    return Object.entries(groups).sort(([a], [z]) => a.localeCompare(z))
  }, [beds])

  const addBed = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      await servicesApi.saveBed({ ward: form.ward.trim(), label: form.label.trim() })
      setModal(false)
      setForm({ ward: '', label: '' })
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  const toggle = async (bed) => {
    setBusy(bed.id)
    try {
      await servicesApi.toggleBed(bed.id)
      reload()
    } catch (err) {
      alert(errMsg(err))
    } finally {
      setBusy(null)
    }
  }

  const remove = async (bed) => {
    if (!window.confirm(`Delete bed "${bed.label}"?`)) return
    setBusy(bed.id)
    try {
      await client.delete(`/services/beds/${bed.id}/`)
      reload()
    } catch (err) {
      alert(errMsg(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <LoadingOrError loading={loading} error={error}>
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">Bed board</h2>
          <Button
            onClick={() => {
              setSaveError('')
              setModal(true)
            }}
          >
            + Add bed
          </Button>
        </div>
        {!wards.length && (
          <Card>
            <div className="text-sm text-slate-400 text-center py-8">No beds yet — add your first ward bed.</div>
          </Card>
        )}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {wards.map(([ward, wardBeds]) => {
            const occ = wardBeds.filter((b) => b.is_occupied).length
            return (
              <Card
                key={ward}
                title={ward}
                actions={
                  <span className="text-xs text-slate-400">
                    {occ} occupied · {wardBeds.length - occ} free
                  </span>
                }
              >
                <div className="space-y-2">
                  {wardBeds.map((b) => (
                    <div
                      key={b.id}
                      className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-lg">🛏️</span>
                        <span className="text-sm font-medium text-slate-700">{b.label}</span>
                        {b.is_occupied ? <Badge color="red">occupied</Badge> : <Badge color="green">available</Badge>}
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" disabled={busy === b.id} onClick={() => toggle(b)}>
                          {b.is_occupied ? 'Mark free' : 'Mark occupied'}
                        </Button>
                        <Button variant="ghost" disabled={busy === b.id} onClick={() => remove(b)}>
                          🗑
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )
          })}
        </div>
      </div>

      <Modal open={modal} onClose={() => setModal(false)} title="Add bed">
        <form onSubmit={addBed} className="space-y-4">
          <ErrorNote error={saveError} />
          <Input
            label="Ward"
            placeholder="e.g. Maternity, ICU, General"
            value={form.ward}
            onChange={(e) => setForm({ ...form, ward: e.target.value })}
            required
          />
          <Input
            label="Bed label"
            placeholder="e.g. Bed 12"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            required
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" type="button" onClick={() => setModal(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Adding…' : 'Add bed'}
            </Button>
          </div>
        </form>
      </Modal>
    </LoadingOrError>
  )
}
