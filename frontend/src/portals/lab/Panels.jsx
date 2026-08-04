import { useMemo, useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Spinner, Table, Textarea } from '../../components/ui'
import { getError, money, statusBadge, useRemote } from '../staff/shared'

const emptyForm = { name: '', code: '', description: '', price: 0, test_ids: [] }

export default function Panels() {
  const panels = useRemote(() => servicesApi.labPanels(), [])
  const tests = useRemote(() => servicesApi.labTests(), [])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const totalTests = useMemo(
    () => (panels.data || []).reduce((sum, panel) => sum + (panel.items?.length || 0), 0),
    [panels.data],
  )

  const toggleTest = (id) => {
    setForm((current) => ({
      ...current,
      test_ids: current.test_ids.includes(id)
        ? current.test_ids.filter((value) => value !== id)
        : [...current.test_ids, id],
    }))
  }

  const save = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await servicesApi.saveLabPanel({
        name: form.name,
        code: form.code.toUpperCase(),
        description: form.description,
        price: Number(form.price),
        active: true,
        items: form.test_ids.map((test, index) => ({ test, sequence: index + 1, required: true })),
      })
      setForm(emptyForm)
      setOpen(false)
      panels.reload()
    } catch (err) {
      setError(getError(err))
    } finally {
      setBusy(false)
    }
  }

  const disable = async (panel) => {
    if (!window.confirm(`Disable ${panel.name}? Existing orders remain available.`)) return
    try {
      await servicesApi.deleteLabPanel(panel.id)
      panels.reload()
    } catch (err) {
      setError(getError(err))
    }
  }

  if (panels.loading || tests.loading) return <Spinner />
  return (
    <div className="space-y-5">
      {(error || panels.error || tests.error) && <Alert tone="danger">{error || panels.error || tests.error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><p className="text-sm text-slate-500">Active panels</p><p className="mt-2 text-3xl font-bold text-slate-900">{(panels.data || []).length}</p></Card>
        <Card><p className="text-sm text-slate-500">Tests bundled</p><p className="mt-2 text-3xl font-bold text-slate-900">{totalTests}</p></Card>
        <Card><p className="text-sm text-slate-500">Catalogue tests</p><p className="mt-2 text-3xl font-bold text-slate-900">{(tests.data || []).length}</p></Card>
      </div>
      <Card
        title="Laboratory panels and profiles"
        subtitle="Bundle related investigations into one clinically meaningful order while retaining individual results."
        actions={<Button onClick={() => setOpen(true)}>Create panel</Button>}
      >
        <Table
          rows={panels.data || []}
          empty="No test panels configured."
          columns={[
            { key: 'name', label: 'Panel', render: (row) => <strong>{row.name}<small className="block font-normal text-slate-400">{row.code}</small></strong> },
            { key: 'items', label: 'Included tests', render: (row) => <div className="flex max-w-xl flex-wrap gap-1">{(row.items || []).map((item) => <span key={item.id} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{item.test_name}</span>)}</div> },
            { key: 'price', label: 'Panel price', render: (row) => money(row.price) },
            { key: 'active', label: 'Status', render: (row) => statusBadge(row.active ? 'active' : 'inactive') },
            { key: 'actions', label: '', render: (row) => <Button variant="outline" onClick={() => disable(row)}>Disable</Button> },
          ]}
        />
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Create laboratory panel" wide>
        <form className="space-y-4" onSubmit={save}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Input required label="Panel name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Complete blood count and iron profile" />
            <Input required label="Panel code" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} placeholder="CBC-IRON" />
          </div>
          <Textarea label="Clinical description and preparation" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
          <Input required min="0" type="number" label="Panel price (UGX)" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} />
          <div>
            <p className="mb-2 text-sm font-semibold text-slate-700">Included tests</p>
            <div className="grid max-h-72 gap-2 overflow-y-auto rounded-xl border border-slate-200 p-3 sm:grid-cols-2">
              {(tests.data || []).map((test) => (
                <label key={test.id} className="flex cursor-pointer items-start gap-3 rounded-lg p-2 hover:bg-slate-50">
                  <input type="checkbox" checked={form.test_ids.includes(test.id)} onChange={() => toggleTest(test.id)} />
                  <span className="text-sm"><strong className="block text-slate-800">{test.name}</strong><small className="text-slate-400">{test.sample_type || 'Sample type not set'} · {money(test.price)}</small></span>
                </label>
              ))}
            </div>
          </div>
          {error && <Alert tone="danger">{error}</Alert>}
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={busy || !form.test_ids.length}>{busy ? 'Saving…' : 'Create panel'}</Button></div>
        </form>
      </Modal>
    </div>
  )
}
