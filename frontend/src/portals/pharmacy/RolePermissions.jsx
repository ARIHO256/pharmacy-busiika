import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Spinner } from '../../components/ui'
import { getError, useRemote } from '../staff/shared'

export const pharmacyRoleLabels = { pharmacist: 'Pharmacist', storekeeper: 'Storekeeper', cashier: 'Sales cashier' }

export default function RolePermissions() {
  const remote = useRemote(() => servicesApi.pharmacyRolePermissions(), [])
  const [role, setRole] = useState('pharmacist')
  const [draft, setDraft] = useState(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [creation, setCreation] = useState({ name: '', base_role: 'pharmacist', all: false })
  const [creationError, setCreationError] = useState('')
  const custom = remote.data?.custom_roles?.find((item) => role === `custom:${item.id}`)
  const settings = custom || remote.data?.roles?.[role]

  if (remote.loading) return <Spinner label="Loading role permissions…" />
  if (!settings) return <Alert tone="danger">{remote.error || 'Only pharmacy owners can manage role permissions.'}</Alert>

  const granted = new Set(draft || settings.enabled)
  const available = new Set(settings.available)

  function toggle(key) {
    if (granted.has(key)) granted.delete(key)
    else granted.add(key)
    setDraft([...granted])
    setMessage('')
  }

  async function create(event) {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setCreationError('')
    try {
      const { name, base_role, all } = creation
      const { data } = await servicesApi.createPharmacyRole({
        name, base_role, permissions: all ? remote.data.roles[base_role].available : [],
      })
      remote.setData((current) => ({ ...current, custom_roles: [...current.custom_roles, data] }))
      setRole(`custom:${data.id}`)
      setDraft(null)
      setError('')
      setMessage(`${data.name} is ready to assign to staff.`)
      setCreating(false)
    } catch (failure) {
      setCreationError(getError(failure))
    } finally {
      setSaving(false)
    }
  }

  async function save() {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const { data } = await servicesApi.savePharmacyRolePermissions({ ...(custom ? { custom_role: custom.id } : { role }), permissions: [...granted] })
      remote.setData((current) => ({
        ...current,
        ...(custom
          ? { custom_roles: current.custom_roles.map((item) => item.id === data.id ? data : item) }
          : { roles: { ...current.roles, [role]: { ...current.roles[role], enabled: data.enabled } } }),
      }))
      setDraft(null)
      setMessage('Permissions saved. Staff can refresh to update their navigation.')
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setSaving(false)
    }
  }

  return <Card title="Role permissions" subtitle="Choose pages and actions for each staff role in your pharmacy."
    actions={<Button type="button" disabled={saving} onClick={() => {
      setCreation({ name: '', base_role: 'pharmacist', all: false })
      setCreationError('')
      setCreating(true)
    }}>Add role</Button>}>
    <div className="space-y-5">
      <Select label="Staff role" value={role} disabled={saving} onChange={(event) => {
        setRole(event.target.value)
        setDraft(null)
        setError('')
        setMessage('')
      }}>
        {Object.keys(remote.data.roles).map((key) => <option key={key} value={key}>{pharmacyRoleLabels[key]}</option>)}
        {remote.data.custom_roles.map((item) => <option key={item.id} value={`custom:${item.id}`}>{item.name}</option>)}
      </Select>
      {custom && <p className="text-sm text-slate-600">Staff type {pharmacyRoleLabels[custom.base_role]}</p>}
      <div className="grid gap-3 md:grid-cols-2">
        {remote.data.groups.filter((group) => available.has(group.key)).map((group) => (
          <fieldset key={group.key} className="space-y-2 rounded-lg border border-slate-200 p-3">
            <label className="flex items-center gap-2 text-sm font-semibold">
              <input type="checkbox" checked={granted.has(group.key)} disabled={saving}
                onChange={() => toggle(group.key)} />
              {group.label}
            </label>
            {Object.entries(group.actions).filter(([key]) => available.has(key)).map(([key, label]) => (
              <label key={key} className="ml-5 flex items-center gap-2 text-sm">
                <input type="checkbox" checked={granted.has(group.key) && granted.has(key)}
                  disabled={saving || !granted.has(group.key)} onChange={() => toggle(key)} />
                {label}
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      {error && <Alert tone="danger">{error}</Alert>}
      {message && <Alert tone="success">{message}</Alert>}
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={saving || !draft} onClick={save}>{saving ? 'Saving…' : 'Save permissions'}</Button>
        <Button type="button" variant="outline" disabled={saving} onClick={() => setDraft(settings.available)}>{custom ? 'Select all available permissions' : 'Reset to role defaults'}</Button>
      </div>
    </div>
    <Modal open={creating} title="Add pharmacy role" onClose={() => { if (!saving) setCreating(false) }}>
      <form onSubmit={create} className="space-y-4">
        <Input required maxLength={80} label="Role name" value={creation.name}
          onChange={(event) => setCreation({ ...creation, name: event.target.value })} />
        <Select label="Staff type" value={creation.base_role}
          onChange={(event) => setCreation({ ...creation, base_role: event.target.value })}>
          {Object.entries(pharmacyRoleLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </Select>
        <p className="text-sm text-slate-600">Staff type determines which permissions are available and whether licence verification is required.</p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={creation.all}
            onChange={(event) => setCreation({ ...creation, all: event.target.checked })} />
          Grant all available permissions
        </label>
        {creationError && <Alert tone="danger">{creationError}</Alert>}
        <Button disabled={saving} type="submit">{saving ? 'Creating…' : 'Create role'}</Button>
      </form>
    </Modal>
  </Card>
}
