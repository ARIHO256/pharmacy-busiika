import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Table } from '../../components/ui'
import { getError, useRemote } from '../staff/shared'
import { LoadingOrError } from './shared'

const levels = { 2: 'Product family', 3: 'Category', 4: 'Subcategory' }
const blankNode = { level: 2, parent: '', name: '', copyFrom: '', fields: [] }

function TaxonomyForm({ nodes, editing, onSave, onClose }) {
  const [form, setForm] = useState(editing ? { ...blankNode, name: editing.name } : blankNode)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const change = (changes) => setForm((current) => ({ ...current, ...changes }))
  const changeField = (index, changes) => setForm((current) => ({
    ...current,
    fields: current.fields.map((field, position) => position === index ? { ...field, ...changes } : field),
  }))

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    try {
      const values = { name: form.name }
      if (!editing) {
        values.level = form.level
        if (form.parent) values.parent = form.parent
        if (form.copyFrom) values.copy_from = form.copyFrom
        else if (form.fields.length) values.fields = form.fields
      }
      await onSave(values)
    } catch (failure) {
      setError(getError(failure))
      setBusy(false)
    }
  }

  return <Modal open title={editing ? 'Rename taxonomy node' : 'Add taxonomy node'} onClose={() => { if (!busy) onClose() }}>
    <form onSubmit={submit} className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      <Input required maxLength={200} label="Name" value={form.name} onChange={(event) => change({ name: event.target.value })} />
      {!editing && <>
        <Select label="Node type" value={form.level}
          onChange={(event) => change({ level: Number(event.target.value), parent: '', copyFrom: '', fields: [] })}>
          {Object.entries(levels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </Select>
        {form.level > 2 && <Select required label="Parent node" value={form.parent} onChange={(event) => change({ parent: event.target.value })}>
          <option value="">Select a parent</option>
          {nodes.filter((node) => node.level === form.level - 1 && !node.archived).map((node) => (
            <option key={node.node_id} value={node.node_id}>{node.path}</option>
          ))}
        </Select>}
        {form.level === 4 && <>
          <Select label="Product field template" value={form.copyFrom} onChange={(event) => change({ copyFrom: event.target.value, fields: [] })}>
            <option value="">Define fields manually</option>
            {nodes.filter((node) => node.level === 4 && node.attribute_fields.length).map((node) => (
              <option key={node.node_id} value={node.node_id}>{node.path}</option>
            ))}
          </Select>
          {!form.copyFrom && <div className="space-y-3">
            {form.fields.map((field, index) => <div className="flex flex-wrap items-end gap-2" key={index}>
              <Input required maxLength={80} label="Field label" value={field.label}
                onChange={(event) => changeField(index, { label: event.target.value })} />
              <Select label="Field type" value={field.type} onChange={(event) => changeField(index, { type: event.target.value })}>
                <option value="text">Text</option>
                <option value="integer">Whole number</option>
              </Select>
              <Button type="button" variant="outline" onClick={() => change({ fields: form.fields.filter((_, position) => position !== index) })}>Remove</Button>
            </div>)}
            <Button type="button" variant="outline" disabled={form.fields.length >= 20}
              onClick={() => change({ fields: [...form.fields, { label: '', type: 'text' }] })}>Add product field</Button>
          </div>}
        </>}
      </>}
      <Button type="submit" disabled={busy}>{busy ? 'Saving…' : editing ? 'Save name' : 'Add node'}</Button>
    </form>
  </Modal>
}

export default function ManageTaxonomy() {
  const [organization, setOrganization] = useState(undefined)
  const remote = useRemote(() => servicesApi.manageMedicineTaxonomy(organization), [organization])
  const [modal, setModal] = useState(null)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const data = remote.data
  const rawNodes = data?.nodes || []
  const names = new Map(rawNodes.map((node) => [node.node_id, node]))
  const nodes = rawNodes.map((node) => {
    const parent = names.get(node.parent)
    const family = names.get(parent?.parent)
    return { ...node, path: [family?.name, parent?.name, node.name].filter(Boolean).join(' → ') }
  })

  async function save(values) {
    if (modal.editing) await servicesApi.updateMedicineTaxonomyNode(data.organization, modal.editing.node_id, values)
    else await servicesApi.addMedicineTaxonomyNode(data.organization, values)
    setModal(null)
    remote.reload()
  }

  async function archive(node) {
    if (busy) return
    setError('')
    setBusy(node.node_id)
    try {
      await servicesApi.updateMedicineTaxonomyNode(data.organization, node.node_id, { archived: !node.directly_archived })
      remote.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(null)
    }
  }

  return <LoadingOrError loading={remote.loading} error={remote.error}>
    <div className="space-y-4">
      <Select label="Pharmacy" value={data?.organization ?? ''} onChange={(event) => { setError(''); setOrganization(event.target.value) }}>
        {data?.organizations.map((choice) => <option key={choice.id} value={choice.id}>{choice.name}</option>)}
      </Select>
      {error && <Alert tone="danger">{error}</Alert>}
      <Card title="Manage taxonomy" subtitle="Changes apply to this pharmacy. Archiving a node hides it and its descendants from new selections."
        actions={<Button onClick={() => setModal({})}>Add node</Button>}>
        <Table rows={nodes.map((node) => ({ ...node, id: node.node_id }))} empty="No catalogue nodes" columns={[
          { key: 'path', label: 'Taxonomy path' },
          { key: 'level', label: 'Type', render: (node) => levels[node.level] },
          { key: 'status', label: 'Status', render: (node) => node.directly_archived ? 'Archived' : node.archived ? 'Parent archived' : 'Active' },
          { key: 'actions', label: 'Actions', render: (node) => <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setModal({ editing: node })}>Rename</Button>
            {(!node.archived || node.directly_archived) && <Button variant="outline" disabled={Boolean(busy)} onClick={() => archive(node)}>
              {node.directly_archived ? 'Restore' : 'Archive'}
            </Button>}
          </div> },
        ]} />
      </Card>
    </div>
    {modal && <TaxonomyForm nodes={nodes} editing={modal.editing} onSave={save} onClose={() => setModal(null)} />}
  </LoadingOrError>
}
