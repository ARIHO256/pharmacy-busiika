import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Spinner, Badge, Button, Alert } from '../../components/ui'
import { platformAdminApi, adminApi } from '../../api/endpoints'
import { fmtDate, profileStatusColor, roleColor } from './helpers'

export default function AdminUserProfile() {
    const { id } = useParams()
    const navigate = useNavigate()
    const [user, setUser] = useState(null)
    const [contexts, setContexts] = useState(null)
    const [error, setError] = useState('')
    const [busy, setBusy] = useState(null)

    function askReason(action) {
        if (action === 'verify' || action === 'activate' || action === 'deactivate') return ''
        return window.prompt(`Record the reason to ${action} this account. This will be written to the audit log.`, '')
    }

    const load = useCallback(async () => {
        setError('')
        setUser(null)
        setContexts(null)
        try {
            const res = await platformAdminApi.user(id)
            // API returns { user: {...}, contexts: [...], ... }
            setUser(res.data.user)
            setContexts(res.data.contexts || [])
        } catch (e) {
            setError('Failed to load user profile.')
            setUser(null)
            setContexts([])
        }
    }, [id])

    useEffect(() => { load() }, [load])

    const act = async (action, payload = {}) => {
        if (!user) return
        const reason = askReason(action)
        if (reason === null) return
        if (['unverify', 'deactivate'].includes(action) && !reason.trim()) {
            setError(`A reason is required to ${action} an account.`)
            return
        }
        setBusy(action)
        setError('')
        try {
            // use platform admin actions when available
            await platformAdminApi.userAction(id, { action, reason, ...payload })
            await load()
        } catch (e) {
            setError(e?.response?.data?.detail || `Failed to ${action} user.`)
        } finally {
            setBusy(null)
        }
    }

    if (!user) return <Card>{error ? <Alert tone="danger">{error}</Alert> : <Spinner label="Loading profile…" />}</Card>

    return (
        <div className="space-y-4">
            {error && <Alert tone="danger">{error}</Alert>}
            <Card title="User profile">
                <div className="grid gap-4 md:grid-cols-3">
                    <div>
                        <div className="text-sm text-slate-500">Name</div>
                        <div className="font-semibold text-slate-800 text-lg">{user.name || 'Unnamed user'}</div>
                        <div className="text-xs text-slate-500 mt-1">{user.email}</div>
                        <div className="text-xs text-slate-500 mt-1">{user.phone || ''}</div>
                        <div className="mt-3">
                            <Badge color={roleColor[user.registration_role] || 'slate'}>{(user.registration_role || user.active_role || '').replaceAll('_', ' ')}</Badge>
                            <span className="ml-2">{user.is_verified ? <Badge color="green">verified</Badge> : <Badge color="slate">not verified</Badge>}</span>
                            <div className="mt-2 text-xs text-slate-500">MFA: {user.mfa_enabled ? 'enabled' : 'disabled'} • Email: {user.email_verified ? 'yes' : 'no'} • Phone: {user.phone_verified ? 'yes' : 'no'}</div>
                        </div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-500">Profile status</div>
                        <div className="mt-2"><Badge color={profileStatusColor[user.status] || 'slate'}>{user.status || '—'}</Badge></div>
                        <div className="text-sm text-slate-500 mt-4">Access</div>
                        <div className="mt-2">{user.is_active ? <Badge color="green">active</Badge> : <Badge color="red">blocked</Badge>}</div>
                    </div>
                    <div>
                        <div className="text-sm text-slate-500">Joined</div>
                        <div className="mt-2">{fmtDate(user.date_joined)}</div>
                        <div className="text-sm text-slate-500 mt-4">Actions</div>
                        <div className="flex flex-wrap gap-2 mt-2">
                            {user.is_active ? (
                                <Button variant="danger" disabled={!!busy} onClick={() => act('deactivate')}>Deactivate</Button>
                            ) : (
                                <Button variant="outline" disabled={!!busy} onClick={() => act('activate')}>Reactivate</Button>
                            )}
                            {user.is_verified ? (
                                <Button className="px-3 py-1 text-sm" disabled={!!busy} onClick={() => act('unverify')}>Remove verification</Button>
                            ) : (
                                <Button className="px-3 py-1 text-sm" disabled={!!busy} onClick={() => act('verify')}>Verify</Button>
                            )}
                            {user.status === 'pending' && <Button variant="outline" disabled={!!busy} onClick={() => act('unverify')}>Reject</Button>}
                            <Button variant="outline" onClick={() => navigate(-1)}>Back</Button>
                        </div>
                    </div>
                </div>
            </Card>

            <Card title="Assigned contexts">
                {contexts === null ? <Spinner label="Loading…" /> : (
                    contexts.length === 0 ? <div className="text-sm text-slate-500">No role contexts found for this user.</div> : (
                        <div className="space-y-2">
                            {contexts.map((c) => (
                                <div key={c.id} className="flex items-center justify-between border rounded p-3">
                                    <div>
                                        <div className="font-medium">{c.title || c.role_code}</div>
                                        <div className="text-xs text-slate-500">{c.organization_name || ''} • {c.location_name || ''}</div>
                                        <div className="text-xs text-slate-400">{c.starts_on ? `From ${fmtDate(c.starts_on)}` : ''} {c.ends_on ? `until ${fmtDate(c.ends_on)}` : ''}</div>
                                    </div>
                                    <div className="text-sm text-slate-500">{c.active ? <Badge color="green">active</Badge> : <Badge color="slate">inactive</Badge>}</div>
                                </div>
                            ))}
                        </div>
                    )
                )}
            </Card>
        </div>
    )
}
