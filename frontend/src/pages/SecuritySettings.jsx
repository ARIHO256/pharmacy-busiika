import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { Alert, Badge, Button, Card, Input, Spinner, Table } from '../components/ui'

const date = (value) => (value ? new Date(value).toLocaleString() : '—')

export default function SecuritySettings() {
  const [data, setData] = useState(null)
  const [events, setEvents] = useState([])
  const [sessions, setSessions] = useState([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [phoneChallenge, setPhoneChallenge] = useState({ token_id: '', code: '', debug_code: '' })
  const [passwords, setPasswords] = useState({ current_password: '', new_password: '', confirm: '' })
  const [confirm, setConfirm] = useState('')

  const load = () =>
    Promise.all([authApi.security(), authApi.securityEvents(), authApi.sessions()])
      .then(([security, activity, activeSessions]) => {
        setData(security.data)
        setEvents(activity.data)
        setSessions(activeSessions.data)
      })
      .catch((requestError) => setError(requestError.response?.data?.detail || 'Could not load security settings.'))

  useEffect(() => {
    load()
  }, [])

  const requestEmail = async () => {
    setBusy(true)
    setError('')
    try {
      const { data: result } = await authApi.requestEmailVerification()
      setNotice(result.detail)
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not send verification email.')
    } finally {
      setBusy(false)
    }
  }

  const requestPhone = async () => {
    setBusy(true)
    setError('')
    try {
      const { data: result } = await authApi.requestPhoneVerification()
      setPhoneChallenge({ token_id: result.token_id, code: '', debug_code: result.debug_code || '' })
      setNotice(result.detail)
    } catch (requestError) {
      const response = requestError.response?.data
      setError(response?.phone?.join?.(' ') || response?.detail || 'Could not send the phone verification code.')
    } finally {
      setBusy(false)
    }
  }

  const verifyPhone = async () => {
    setBusy(true)
    setError('')
    try {
      const { data: result } = await authApi.verifyPhone(phoneChallenge.token_id, phoneChallenge.code)
      setNotice(result.detail)
      setPhoneChallenge({ token_id: '', code: '', debug_code: '' })
      load()
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'The verification code is invalid or expired.')
    } finally {
      setBusy(false)
    }
  }

  const toggleMfa = async () => {
    setBusy(true)
    setError('')
    try {
      const { data: result } = await authApi.updateSecurity({ mfa_enabled: !data.mfa_enabled, password: confirm })
      setNotice(result.mfa_enabled ? 'Two-step verification enabled.' : 'Two-step verification disabled.')
      setConfirm('')
      load()
    } catch (requestError) {
      setError(requestError.response?.data?.password?.join?.(' ') || requestError.response?.data?.detail || 'Could not update MFA.')
    } finally {
      setBusy(false)
    }
  }

  const changePassword = async (event) => {
    event.preventDefault()
    if (passwords.new_password !== passwords.confirm) {
      setError('New passwords do not match.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const { data: result } = await authApi.changePassword({
        current_password: passwords.current_password,
        new_password: passwords.new_password,
      })
      setNotice(result.detail)
      setPasswords({ current_password: '', new_password: '', confirm: '' })
      load()
    } catch (requestError) {
      const response = requestError.response?.data
      setError(response?.current_password?.join?.(' ') || response?.new_password?.join?.(' ') || response?.detail || 'Password change failed.')
    } finally {
      setBusy(false)
    }
  }

  const revoke = async (tokenId) => {
    setBusy(true)
    try {
      const { data: result } = await authApi.revokeSession(tokenId)
      setNotice(`${result.revoked} session${result.revoked === 1 ? '' : 's'} revoked.`)
      load()
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Could not revoke the selected session.')
    } finally {
      setBusy(false)
    }
  }

  if (!data && !error) return <Spinner />

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-6xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <span className="text-xs font-bold uppercase tracking-[.18em] text-primary-600">Identity protection</span>
            <h1 className="text-3xl font-bold text-slate-900">Security centre</h1>
            <p className="mt-1 max-w-2xl text-sm text-slate-500">Verify recovery channels, enable two-step sign-in and close sessions you no longer recognise.</p>
          </div>
          <Link className="font-semibold text-primary-700" to="/dashboard">Back to workspace</Link>
        </div>

        {notice && <Alert tone="success">{notice}</Alert>}
        {error && <Alert tone="danger">{error}</Alert>}

        <div className="grid gap-5 xl:grid-cols-3">
          <Card title="Email verification" subtitle="Required for secure recovery and sign-in alerts">
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-4">
                <div><strong className="text-slate-800">Registered email</strong><p className="text-xs text-slate-500">Verification links are single-use and time limited.</p></div>
                <Badge color={data?.email_verified ? 'green' : 'yellow'}>{data?.email_verified ? 'Verified' : 'Pending'}</Badge>
              </div>
              {!data?.email_verified && <Button onClick={requestEmail} disabled={busy}>Send verification email</Button>}
            </div>
          </Card>

          <Card title="Phone verification" subtitle="Used for urgent care and account security messages">
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-4">
                <div><strong className="text-slate-800">Mobile number</strong><p className="text-xs text-slate-500">A six-digit code is delivered through the configured SMS provider.</p></div>
                <Badge color={data?.phone_verified ? 'green' : 'yellow'}>{data?.phone_verified ? 'Verified' : 'Pending'}</Badge>
              </div>
              {!data?.phone_verified && !phoneChallenge.token_id && <Button onClick={requestPhone} disabled={busy}>Send phone code</Button>}
              {!data?.phone_verified && phoneChallenge.token_id && <div className="space-y-3"><Input label="Verification code" inputMode="numeric" maxLength={6} value={phoneChallenge.code} onChange={(event) => setPhoneChallenge({ ...phoneChallenge, code: event.target.value.replace(/\D/g, '') })} />{phoneChallenge.debug_code && <Alert tone="info">Development code: <strong>{phoneChallenge.debug_code}</strong></Alert>}<Button onClick={verifyPhone} disabled={busy || phoneChallenge.code.length !== 6}>Verify phone</Button></div>}
            </div>
          </Card>

          <Card title="Two-step verification" subtitle="Email code challenge for every password sign-in">
            <div className="space-y-4">
              <div className="flex items-center justify-between rounded-xl bg-slate-50 p-4"><strong className="text-slate-800">MFA status</strong><Badge color={data?.mfa_enabled ? 'green' : 'slate'}>{data?.mfa_enabled ? 'Enabled' : 'Disabled'}</Badge></div>
              <Input label="Confirm password" type="password" value={confirm} onChange={(event) => setConfirm(event.target.value)} />
              <Button variant={data?.mfa_enabled ? 'danger' : 'primary'} onClick={toggleMfa} disabled={busy || !confirm}>{data?.mfa_enabled ? 'Disable MFA' : 'Enable MFA'}</Button>
            </div>
          </Card>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card title="Change password" subtitle="Use at least ten characters and avoid reused passwords">
            <form className="space-y-4" onSubmit={changePassword}>
              <Input label="Current password" type="password" required value={passwords.current_password} onChange={(event) => setPasswords({ ...passwords, current_password: event.target.value })} />
              <Input label="New password" type="password" minLength={10} required value={passwords.new_password} onChange={(event) => setPasswords({ ...passwords, new_password: event.target.value })} />
              <Input label="Confirm new password" type="password" required value={passwords.confirm} onChange={(event) => setPasswords({ ...passwords, confirm: event.target.value })} />
              <Button disabled={busy}>Change password</Button>
            </form>
          </Card>

          <Card title="Active sessions" subtitle="Refresh tokens issued to signed-in browsers and devices" action={<Button size="sm" variant="danger" onClick={() => revoke('all')} disabled={busy}>Revoke all</Button>}>
            <Table rows={sessions} columns={[
              { key: 'created_at', label: 'Issued', render: (row) => date(row.created_at) },
              { key: 'expires_at', label: 'Expires', render: (row) => date(row.expires_at) },
              { key: 'revoked', label: 'Status', render: (row) => <Badge color={row.revoked ? 'slate' : 'green'}>{row.revoked ? 'Revoked' : 'Active'}</Badge> },
              { key: 'actions', label: '', render: (row) => !row.revoked && <Button size="sm" variant="ghost" onClick={() => revoke(row.id)}>Revoke</Button> },
            ]} empty="No issued sessions were found." />
          </Card>
        </div>

        <Card title="Recent security activity" subtitle="Sign-ins, lockouts, verification and credential changes">
          <Table rows={events} columns={[
            { key: 'event_type', label: 'Event', render: (row) => row.event_type.replaceAll('_', ' ') },
            { key: 'ip_address', label: 'IP address' },
            { key: 'created_at', label: 'When', render: (row) => date(row.created_at) },
            { key: 'user_agent', label: 'Device', render: (row) => <span className="line-clamp-1 max-w-sm">{row.user_agent || 'Unknown'}</span> },
          ]} empty="No security events recorded." />
        </Card>
      </div>
    </main>
  )
}
