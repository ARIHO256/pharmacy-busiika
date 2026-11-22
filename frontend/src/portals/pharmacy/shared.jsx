// Shared helpers for the four provider portals (pharmacy/lab/hospital/insurance).
import { useCallback, useEffect, useState } from 'react'
import { Alert, Textarea, Badge, Button, Card, Input, Spinner } from '../../components/ui'
import client from '../../api/client'

export const money = (n) => `UGX ${Number(n || 0).toLocaleString()}`

export const fmtDate = (s) => (s ? new Date(s).toLocaleString() : '—')

const statusColors = {
  new: 'yellow',
  pending: 'yellow',
  booked: 'yellow',
  submitted: 'yellow',
  confirmed: 'blue',
  prepared: 'blue',
  processing: 'blue',
  sample_collected: 'blue',
  delivered: 'green',
  completed: 'green',
  approved: 'green',
  verified: 'green',
  cancelled: 'red',
  rejected: 'red',
  suspended: 'red',
}

export function StatusBadge({ status }) {
  return (
    <Badge color={statusColors[status] || 'slate'}>
      {String(status || '—').replace(/_/g, ' ')}
    </Badge>
  )
}

export function useApi(fn, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fn()
      setData(res.data)
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to load data.')
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => {
    load()
  }, [load])
  return { data, loading, error, reload: load, setData }
}

export const errMsg = (e) =>
  e?.response?.data?.detail ||
  (typeof e?.response?.data === 'string' ? e.response.data : null) ||
  'Something went wrong. Please try again.'

export function ErrorNote({ error }) {
  if (!error) return null
  return (
    <div className="mb-4 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-sm px-4 py-2.5">
      {error}
    </div>
  )
}

export function LoadingOrError({ loading, error, children }) {
  if (loading) return <Spinner />
  if (error) return <ErrorNote error={error} />
  return children
}

// Identical org profile page used by all provider portals.
export function ProviderProfile() {
  const { data, loading, error, reload } = useApi(() => client.get('/auth/me/profile/'))
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    if (data && !form) {
      setForm({
        org_name: data.org_name || '',
        license_number: data.license_number || '',
        address: data.address || '',
        district: data.district || '',
        services_description: data.services_description || '',
      })
    }
  }, [data, form])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    setSaved(false)
    setSaveError('')
    try {
      await client.patch('/auth/me/profile/', form)
      setSaved(true)
      reload()
    } catch (err) {
      setSaveError(errMsg(err))
    } finally {
      setSaving(false)
    }
  }

  if (error) return <ErrorNote error={error} />
  if (loading || !form) return <Spinner label="Loading organization profile…" />

  return (
    <>
      <div className="max-w-2xl space-y-6">
        <Card
          title="Verification status"
          actions={<StatusBadge status={data?.status || 'pending'} />}
        >
          <p className="text-sm text-slate-500">
            {data?.status === 'verified'
              ? 'Your organization is verified and visible to patients.'
              : data?.status === 'suspended'
                ? 'Your organization has been suspended. Contact the platform administrator.'
                : 'Your organization is pending verification by the platform administrator.'}
          </p>
        </Card>
        <Card title="Organization profile">
          <form onSubmit={save} className="space-y-4">
            <ErrorNote error={saveError} />
            {saved && (
              <div className="rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm px-4 py-2.5">
                Profile saved.
              </div>
            )}
            <Input label="Organization name" value={form.org_name} onChange={set('org_name')} required />
            <Input label="License number" value={form.license_number} onChange={set('license_number')} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Input label="District or region" value={form.district} onChange={set('district')} />
              <Input label="Street address" value={form.address} onChange={set('address')} />
            </div>
            <Textarea label="Services description" value={form.services_description} onChange={set('services_description')} />
            {data.verification_notes && <Alert tone="warning" title="Verification feedback">{data.verification_notes}</Alert>}
            <div className="pt-1">
              <Button type="submit" disabled={saving}>
                {saving ? 'Saving…' : 'Save profile'}
              </Button>
            </div>
          </form>
        </Card>
      </div>
    </>
  )
}
