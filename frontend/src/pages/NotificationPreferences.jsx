import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { chatApi } from '../api/endpoints'
import { Alert, Button, Card, Spinner } from '../components/ui'
import { useAuth, ROLE_HOME } from '../auth/AuthContext'

const TOGGLES = [
  ['in_app_enabled', 'In-app notifications', 'Show care, account and billing updates inside MyDoctor.'],
  ['email_enabled', 'Email delivery', 'Send eligible notifications to the verified account email.'],
  ['sms_enabled', 'SMS delivery', 'Send urgent and configured reminders by SMS when an SMS provider is connected.'],
  ['push_enabled', 'Push delivery', 'Prepare mobile or browser push delivery when a push provider is connected.'],
  ['appointment_reminders', 'Appointment reminders', 'Booking confirmation, rescheduling, cancellation and reminder messages.'],
  ['clinical_updates', 'Clinical updates', 'Released laboratory results, referrals, prescriptions and care updates.'],
  ['payment_updates', 'Billing and payment updates', 'Invoices, payment confirmation, receipts, refunds and balances.'],
  ['marketing_updates', 'Optional service updates', 'Non-clinical platform announcements and offers.'],
]

export default function NotificationPreferences() {
  const { user } = useAuth()
  const [form, setForm] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    chatApi.preferences().then(({ data }) => setForm(data)).catch(() => setError('Notification preferences could not be loaded.'))
  }, [])

  const save = async () => {
    setSaving(true); setMessage(''); setError('')
    try {
      const { data } = await chatApi.updatePreferences(form)
      setForm(data)
      setMessage('Notification preferences saved.')
    } catch (err) {
      setError(err.response?.data?.detail || 'Preferences could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  if (!form && !error) return <Spinner label="Loading notification settings…" />

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-3xl space-y-5">
        <div>
          <Link className="text-sm font-semibold text-primary-700 hover:underline" to={ROLE_HOME[user?.role] || '/dashboard'}>← Return to workspace</Link>
          <h1 className="mt-3 text-3xl font-bold text-slate-900">Notification preferences</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">Choose which channels and healthcare events may contact you. Critical security and safety notices may still be delivered when legally or operationally required.</p>
        </div>
        {message && <Alert tone="success">{message}</Alert>}
        {error && <Alert tone="danger">{error}</Alert>}
        {form && <Card title="Delivery and event controls" subtitle="Your settings are applied before email, SMS or push jobs enter the delivery queue.">
          <div className="divide-y divide-slate-100">
            {TOGGLES.map(([key, label, description]) => (
              <label key={key} className="flex cursor-pointer items-start justify-between gap-5 py-4 first:pt-0 last:pb-0">
                <span><span className="block font-semibold text-slate-800">{label}</span><span className="mt-1 block text-sm leading-5 text-slate-500">{description}</span></span>
                <input type="checkbox" className="mt-1 h-5 w-5 accent-primary-600" checked={Boolean(form[key])} onChange={(event) => setForm((old) => ({ ...old, [key]: event.target.checked }))} />
              </label>
            ))}
          </div>
          <div className="mt-6 flex justify-end"><Button disabled={saving} onClick={save}>{saving ? 'Saving…' : 'Save preferences'}</Button></div>
        </Card>}
      </div>
    </main>
  )
}
