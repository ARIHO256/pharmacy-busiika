import { useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Select, Table } from '../../components/ui'
import { displayDate, getError, statusBadge, useRemote } from '../staff/shared'
import { LoadingOrError } from './shared'

const roles = { pharmacist: 'Pharmacist', storekeeper: 'Storekeeper', cashier: 'Sales cashier' }
const empty = { first_name: '', last_name: '', email: '', role: 'pharmacist' }

function invitationLink(invitation) {
  const path = new URL(invitation.invitation_url, window.location.origin).pathname
  return new URL(path, window.location.origin).href
}

export default function StaffAccess() {
  const staff = useRemote(() => workforceApi.staff(), [])
  const [invite, setInvite] = useState(false)
  const [form, setForm] = useState(empty)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [link, setLink] = useState('')
  const change = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }))

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const { data } = await workforceApi.inviteStaff(form)
      setLink(invitationLink(data))
      setInvite(false)
      setForm(empty)
      staff.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(false)
    }
  }

  async function toggle(row) {
    setBusy(true)
    setError('')
    try {
      await workforceApi.setStaffStatus(row.id, row.status === 'active' ? 'suspended' : 'active')
      staff.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(false)
    }
  }

  return <LoadingOrError loading={staff.loading} error={staff.error}>
    <div className="space-y-5">
      {!invite && error && <Alert tone="danger">{error}</Alert>}
      <Card title="Pharmacy team" actions={<Button onClick={() => { setError(''); setInvite(true) }}>Invite staff member</Button>}>
        <Table rows={staff.data?.staff || []} empty="No staff members yet" columns={[
          { key: 'user_name', label: 'Staff member' },
          { key: 'role', label: 'Role', render: (row) => roles[row.role] || row.role.replaceAll('_', ' ') },
          { key: 'verification_status', label: 'Verification', render: (row) => statusBadge(row.verification_status) },
          { key: 'status', label: 'Access', render: (row) => statusBadge(row.status) },
          { key: 'action', label: 'Manage', render: (row) => <Button variant="outline" disabled={busy}
            onClick={() => toggle(row)}>{row.status === 'active' ? 'Suspend access' : 'Reactivate access'}</Button> },
        ]} />
      </Card>
      <Card title="Pending invitations">
        <Table rows={staff.data?.invitations || []} empty="No pending invitations" columns={[
          { key: 'email', label: 'Email' },
          { key: 'role', label: 'Role', render: (row) => roles[row.role] || row.role },
          { key: 'expires_at', label: 'Expires', render: (row) => displayDate(row.expires_at) },
          { key: 'link', label: 'Invitation', render: (row) => <Button variant="outline"
            onClick={() => setLink(invitationLink(row))}>View link</Button> },
        ]} />
      </Card>
    </div>
    {invite && <Modal open title="Invite pharmacy staff" onClose={() => { if (!busy) setInvite(false) }}>
      <form className="space-y-3" onSubmit={submit}>
        <Input label="First name" value={form.first_name} onChange={change('first_name')} />
        <Input label="Last name" value={form.last_name} onChange={change('last_name')} />
        <Input required type="email" label="Staff email" value={form.email} onChange={change('email')} />
        <Select label="Role" value={form.role} onChange={change('role')}>
          {Object.entries(roles).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </Select>
        {form.role === 'pharmacist' && <p className="text-sm text-slate-600">The pharmacist submits their licence when accepting the invitation.</p>}
        {error && <Alert tone="danger">{error}</Alert>}
        <Button disabled={busy} type="submit">Create invitation</Button>
      </form>
    </Modal>}
    {link && <Modal open title="Staff invitation link" onClose={() => setLink('')}>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">Share this link with the staff member you invited.</p>
        <Input label="Invitation URL" readOnly value={link} onFocus={(event) => event.target.select()} />
        <Button onClick={() => setLink('')}>Done</Button>
      </div>
    </Modal>}
  </LoadingOrError>
}
