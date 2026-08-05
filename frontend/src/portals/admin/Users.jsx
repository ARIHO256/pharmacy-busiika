import { useCallback, useEffect, useState } from 'react'
import { Alert, Badge, Button, Card, Select, Spinner, Table } from '../../components/ui'
import { Link } from 'react-router-dom'
import { adminApi } from '../../api/endpoints'
import { fmtDate, profileStatusColor, roleColor, ROLES } from './helpers'

const REGULATED_ROLES = ['doctor', 'nurse', 'pharmacist', 'lab_technician']
const ORGANIZATION_ROLES = ['pharmacy', 'lab', 'hospital', 'insurance']
const VERIFIABLE_ROLES = [...REGULATED_ROLES, ...ORGANIZATION_ROLES]

function askReason(action, user) {
  if (action === 'verify' || action === 'activate' || action === 'reactivate') return ''
  return window.prompt(`Record the reason to ${action} ${user.email}. This will be written to the audit log.`, '')
}

export default function Users() {
  const [users, setUsers] = useState(null)
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(null)

  const load = useCallback(() => {
    setError('')
    const params = {}
    if (role) params.role = role
    if (status) params.status = status
    adminApi.users(params).then((res) => setUsers(res.data)).catch(() => {
      setUsers([])
      setError('Failed to load users.')
    })
  }, [role, status])

  useEffect(() => { setUsers(null); load() }, [load])

  const act = async (user, action) => {
    const reason = askReason(action, user)
    if (reason === null) return
    if (['reject', 'suspend'].includes(action) && !reason.trim()) {
      setError(`A reason is required to ${action} an account.`)
      return
    }
    setBusy(`${user.id}:${action}`)
    setError('')
    try {
      await adminApi.setStatus(user.id, { action, reason })
      await load()
    } catch (e) {
      setError(e?.response?.data?.detail || `Failed to ${action} ${user.email}.`)
    } finally {
      setBusy(null)
    }
  }

  const columns = [
    {
      key: 'identity', label: 'User', render: (u) => (
        <div>
          <div className="font-semibold text-slate-800">
            <Link to={`/admin/users/${u.id}`} className="hover:underline">{u.name || 'Unnamed user'}</Link>
          </div>
          <div className="text-xs text-slate-500">{u.email}</div>
        </div>
      ),
    },
    { key: 'role', label: 'Role', render: (u) => <Badge color={roleColor[u.role] || 'slate'}>{u.role.replaceAll('_', ' ')}</Badge> },
    { key: 'status', label: 'Profile status', render: (u) => u.status ? <Badge color={profileStatusColor[u.status] || 'slate'}>{u.status}</Badge> : <span className="text-slate-300">—</span> },
    { key: 'is_verified', label: 'Verified', render: (u) => u.is_verified ? <Badge color="green">yes</Badge> : <Badge color="slate">no</Badge> },
    { key: 'is_active', label: 'Access', render: (u) => u.is_active ? <Badge color="green">active</Badge> : <Badge color="red">blocked</Badge> },
    { key: 'date_joined', label: 'Joined', render: (u) => fmtDate(u.date_joined) },
    {
      key: 'actions', label: 'Actions', render: (u) => {
        const verifiable = VERIFIABLE_ROLES.includes(u.role)
        return (
          <div className="flex min-w-[220px] flex-wrap gap-2">
            {verifiable && u.status !== 'verified' && u.status !== 'revoked' && (
              <Button className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => act(u, 'verify')}>
                {busy === `${u.id}:verify` ? '…' : 'Verify'}
              </Button>
            )}
            {verifiable && u.status === 'pending' && (
              <Button variant="outline" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => act(u, 'reject')}>Reject</Button>
            )}
            {u.is_active ? (
              <Button variant="danger" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => act(u, 'suspend')}>
                {busy === `${u.id}:suspend` ? '…' : 'Suspend'}
              </Button>
            ) : (
              <Button variant="outline" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => act(u, 'reactivate')}>
                {busy === `${u.id}:reactivate` ? '…' : 'Reactivate'}
              </Button>
            )}
          </div>
        )
      },
    },
  ]

  return (
    <div className="space-y-4">
      <Card title="User, staff and provider administration">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Select label="Role" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">All roles</option>
            {ROLES.map((r) => <option key={r} value={r}>{r.replaceAll('_', ' ')}</option>)}
          </Select>
          <Select label="Profile status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {['pending', 'verified', 'rejected', 'suspended', 'expired', 'revoked'].map((item) => <option key={item}>{item}</option>)}
          </Select>
        </div>
      </Card>
      {error && <Alert tone="danger">{error}</Alert>}
      <Card title={`Users${users ? ` (${users.length})` : ''}`}>
        {users === null ? <Spinner label="Loading users…" /> : <Table columns={columns} rows={users} empty="No users match the filters" />}
      </Card>
    </div>
  )
}
