import { useCallback, useEffect, useState } from 'react'
import { Badge } from '../../components/ui'

export function useRemote(loader, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const reload = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const response = await loader()
      setData(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Unable to load this workspace.')
    } finally {
      setLoading(false)
    }
  }, deps)
  useEffect(() => { reload() }, [reload])
  return { data, loading, error, reload, setData }
}

export function displayDate(value, withTime = true) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { dateStyle: 'medium' }).format(new Date(value))
}

export function money(value, currency = 'UGX') {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(Number(value || 0))
}

export function statusBadge(status) {
  const normalized = String(status || '').toLowerCase()
  const color = ['verified', 'paid', 'active', 'completed', 'released', 'confirmed'].includes(normalized)
    ? 'green'
    : ['pending', 'waiting_triage', 'waiting_clinician', 'partially_paid', 'processing', 'awaiting_validation'].includes(normalized)
      ? 'yellow'
      : ['suspended', 'rejected', 'cancelled', 'failed', 'revoked', 'expired'].includes(normalized)
        ? 'red'
        : 'blue'
  return <Badge color={color}>{normalized.replaceAll('_', ' ') || 'unknown'}</Badge>
}

export function getError(err) {
  const data = err.response?.data
  if (!data) return err.message || 'The request failed.'
  if (data.detail) return data.detail
  return Object.entries(data).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' · ')
}
