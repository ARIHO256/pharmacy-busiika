import { useEffect, useMemo, useState } from 'react'
import { clinicalApi, governanceApi, interoperabilityApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Modal,
  SectionHeading,
  Select,
  Spinner,
  Textarea,
} from '../../components/ui'

const severityColor = {
  mild: 'green',
  moderate: 'yellow',
  severe: 'red',
  life_threatening: 'red',
  unknown: 'slate',
}

const statusColor = {
  active: 'green',
  final: 'blue',
  high: 'yellow',
  low: 'yellow',
  critical: 'red',
  abnormal: 'red',
  revoked: 'red',
  expired: 'slate',
  completed: 'blue',
}

const initialForms = {
  allergy: { substance: '', reaction: '', severity: 'unknown', notes: '' },
  condition: { display: '', onset_date: '', notes: '' },
  medication: { medication_name: '', dose: '', frequency: '', route: 'oral', notes: '' },
}

function formatDate(value) {
  if (!value) return 'Not specified'
  return new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: value.includes?.('T') ? 'short' : undefined })
}

function Metric({ label, value, tone = 'text-primary-700' }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className={`text-2xl font-bold ${tone}`}>{value}</div>
      <div className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  )
}

function ObservationCard({ item }) {
  const value = item.value_text || `${item.value_numeric ?? ''} ${item.unit || ''}`.trim()
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-semibold text-slate-800">{item.display}</div>
          <div className="mt-1 text-2xl font-bold text-primary-800">{value || '—'}</div>
        </div>
        <Badge color={statusColor[item.interpretation] || 'slate'}>{item.interpretation}</Badge>
      </div>
      <div className="mt-2 text-xs text-slate-400">Observed {formatDate(item.observed_at)}</div>
    </div>
  )
}

export default function HealthRecord() {
  const { user } = useAuth()
  const [summary, setSummary] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [consents, setConsents] = useState([])
  const [tab, setTab] = useState('summary')
  const [recordType, setRecordType] = useState(null)
  const [form, setForm] = useState(initialForms.allergy)
  const [consentOpen, setConsentOpen] = useState(false)
  const [consentForm, setConsentForm] = useState({
    consent_type: 'data_sharing',
    purpose: 'treatment',
    recipient_class: 'authorised_provider',
    data_categories: ['patient_summary', 'allergies', 'medications', 'conditions'],
    valid_until: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function load() {
    setError('')
    try {
      const [summaryRes, timelineRes, consentRes] = await Promise.all([
        clinicalApi.summary(),
        clinicalApi.timeline(),
        governanceApi.consents(),
      ])
      setSummary(summaryRes.data)
      setTimeline(timelineRes.data || [])
      setConsents(consentRes.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Your health record could not be loaded.')
      setSummary({ allergies: [], conditions: [], medications: [], latest_observations: [], active_care_plans: [], open_referrals: [] })
    }
  }

  useEffect(() => { load() }, [])

  const activeConsents = useMemo(() => consents.filter((c) => c.is_current), [consents])

  function openRecord(type) {
    setRecordType(type)
    setForm({ ...initialForms[type] })
    setError('')
  }

  async function submitRecord(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (recordType === 'allergy') await clinicalApi.addAllergy(form)
      if (recordType === 'condition') await clinicalApi.addCondition(form)
      if (recordType === 'medication') await clinicalApi.addMedication(form)
      setRecordType(null)
      setNotice('Your health record was updated. Clinician verification remains visible separately.')
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'The health record could not be updated.')
    } finally {
      setSaving(false)
    }
  }

  async function grantConsent(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const payload = {
        ...consentForm,
        valid_until: consentForm.valid_until ? new Date(consentForm.valid_until).toISOString() : null,
      }
      await governanceApi.grantConsent(payload)
      setConsentOpen(false)
      setNotice('Consent was recorded and will be enforced during clinical access decisions.')
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Consent could not be recorded.')
    } finally {
      setSaving(false)
    }
  }

  async function revokeConsent(consent) {
    const reason = window.prompt('Reason for revoking this consent (optional):', '')
    if (reason === null) return
    try {
      await governanceApi.revokeConsent(consent.id, reason)
      setNotice('Consent revoked. Previous lawful accesses remain in the audit trail.')
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Consent could not be revoked.')
    }
  }

  async function exportPatientSummary() {
    if (!user?.id) return
    setSaving(true)
    setError('')
    try {
      const response = await interoperabilityApi.patientSummary(user.id)
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/fhir+json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `mydoctor-patient-summary-${user.id}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setNotice('A standards-aligned draft FHIR patient summary was exported. It is not yet a certified national implementation package.')
    } catch (err) {
      setError(err.response?.data?.detail || 'The patient summary could not be exported.')
    } finally {
      setSaving(false)
    }
  }

  if (!summary) return <Spinner label="Loading your longitudinal health record…" />

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Longitudinal record"
        title="My Health Record"
        description="A structured, time-based view of your allergies, conditions, medicines, observations, care plans, referrals and privacy permissions."
        actions={<div className="flex flex-wrap gap-2"><Button variant="outline" disabled={saving} onClick={exportPatientSummary}>Export FHIR summary</Button><Button onClick={() => openRecord('allergy')}>Add health information</Button></div>}
      />

      {error && <Alert tone="danger" title="Action needed">{error}</Alert>}
      {notice && <Alert tone="success">{notice}</Alert>}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Metric label="Active allergies" value={summary.allergies?.length || 0} tone="text-rose-600" />
        <Metric label="Active conditions" value={summary.conditions?.length || 0} />
        <Metric label="Current medicines" value={summary.medications?.length || 0} tone="text-violet-700" />
        <Metric label="Active consents" value={activeConsents.length} tone="text-emerald-700" />
      </div>

      <div className="flex gap-2 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5">
        {[
          ['summary', 'Clinical summary'],
          ['timeline', 'Health timeline'],
          ['care', 'Care plans & referrals'],
          ['privacy', 'Privacy & consent'],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`whitespace-nowrap rounded-lg px-4 py-2 text-sm font-medium ${tab === key ? 'bg-primary-700 text-white' : 'text-slate-600 hover:bg-slate-50'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'summary' && (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-3">
            <Card
              title="Allergies and sensitivities"
              actions={<Button variant="ghost" onClick={() => openRecord('allergy')}>+ Add</Button>}
            >
              {!summary.allergies?.length ? (
                <EmptyState icon="⚕" title="No structured allergies" description="Add known allergies even when they were reported outside MyDoctor." />
              ) : (
                <div className="space-y-3">
                  {summary.allergies.map((item) => (
                    <div key={item.id} className="rounded-lg border border-rose-100 bg-rose-50/60 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="font-semibold text-slate-800">{item.substance}</div>
                        <Badge color={severityColor[item.severity]}>{item.severity.replaceAll('_', ' ')}</Badge>
                      </div>
                      <div className="mt-1 text-sm text-slate-600">{item.reaction || 'Reaction not recorded'}</div>
                      <div className="mt-2 text-xs text-slate-400">{item.verification.replaceAll('_', ' ')}</div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Conditions" actions={<Button variant="ghost" onClick={() => openRecord('condition')}>+ Add</Button>}>
              {!summary.conditions?.length ? (
                <EmptyState icon="♡" title="No active conditions" description="Conditions entered by you are clearly marked as patient reported until verified." />
              ) : (
                <div className="space-y-3">
                  {summary.conditions.map((item) => (
                    <div key={item.id} className="border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium text-slate-800">{item.display}</div>
                        <Badge color="blue">{item.clinical_status}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-slate-500">{item.verification.replaceAll('_', ' ')}</div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card title="Current medications" actions={<Button variant="ghost" onClick={() => openRecord('medication')}>+ Add</Button>}>
              {!summary.medications?.length ? (
                <EmptyState icon="💊" title="No current medicines" description="Keep this list current to support safer prescribing." />
              ) : (
                <div className="space-y-3">
                  {summary.medications.map((item) => (
                    <div key={item.id} className="rounded-lg bg-violet-50 p-3">
                      <div className="font-semibold text-slate-800">{item.medication_name}</div>
                      <div className="mt-1 text-sm text-slate-600">{[item.dose, item.frequency, item.route].filter(Boolean).join(' · ') || 'Directions not recorded'}</div>
                      <div className="mt-2 text-xs text-slate-400">{item.source.replaceAll('_', ' ')}</div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card title="Latest observations">
            {!summary.latest_observations?.length ? (
              <EmptyState icon="⌁" title="No observations recorded" description="Vital signs, laboratory values and device readings will appear here." />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {summary.latest_observations.map((item) => <ObservationCard key={item.id} item={item} />)}
              </div>
            )}
          </Card>
        </div>
      )}

      {tab === 'timeline' && (
        <Card title="Health timeline">
          {!timeline.length ? (
            <EmptyState icon="◷" title="No timeline events yet" description="Final consultations, results, referrals and prescriptions will be placed here chronologically." />
          ) : (
            <div className="relative space-y-0 before:absolute before:bottom-4 before:left-[11px] before:top-4 before:w-px before:bg-slate-200">
              {timeline.map((event) => (
                <div key={event.id} className="relative flex gap-4 py-4">
                  <div className="relative z-10 mt-1.5 h-6 w-6 shrink-0 rounded-full border-4 border-white bg-primary-600 shadow" />
                  <div className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <div className="font-semibold text-slate-800">{event.title}</div>
                        {event.subtitle && <div className="mt-1 text-sm text-slate-500">{event.subtitle}</div>}
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge color={statusColor[event.status] || 'slate'}>{event.status}</Badge>
                        <span className="text-xs text-slate-400">{formatDate(event.occurred_at)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {tab === 'care' && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card title="Active care plans">
            {!summary.active_care_plans?.length ? (
              <EmptyState icon="✓" title="No active care plan" description="Clinicians can create measurable goals and activities during a consultation." />
            ) : summary.active_care_plans.map((plan) => (
              <div key={plan.id} className="mb-3 rounded-xl border border-slate-200 p-4 last:mb-0">
                <div className="flex items-center justify-between"><div className="font-semibold">{plan.title}</div><Badge color="green">{plan.status}</Badge></div>
                <p className="mt-2 text-sm text-slate-600">{plan.description}</p>
                {!!plan.goals?.length && <div className="mt-3 text-xs text-slate-500">{plan.goals.length} tracked goal(s)</div>}
              </div>
            ))}
          </Card>
          <Card title="Open referrals">
            {!summary.open_referrals?.length ? (
              <EmptyState icon="↗" title="No open referrals" description="Referrals remain visible until accepted, completed or cancelled." />
            ) : summary.open_referrals.map((referral) => (
              <div key={referral.id} className="mb-3 rounded-xl border border-primary-100 bg-primary-50/60 p-4 last:mb-0">
                <div className="flex items-center justify-between"><div className="font-semibold">{referral.target_specialty}</div><Badge color={referral.priority === 'emergency' ? 'red' : referral.priority === 'urgent' ? 'yellow' : 'blue'}>{referral.priority}</Badge></div>
                <p className="mt-2 text-sm text-slate-600">{referral.reason}</p>
                <div className="mt-3 text-xs text-slate-500">Status: {referral.status.replaceAll('_', ' ')}</div>
              </div>
            ))}
          </Card>
        </div>
      )}

      {tab === 'privacy' && (
        <div className="space-y-5">
          <Alert title="Your consent is executable">
            MyDoctor uses these records in access decisions. Revoking consent stops future non-emergency access, while previous lawful access remains traceable in the audit history.
          </Alert>
          <Card title="Consent register" actions={<Button onClick={() => setConsentOpen(true)}>Grant consent</Button>}>
            {!consents.length ? (
              <EmptyState icon="🔐" title="No consent records" description="Appointment bookings automatically create a narrow treatment consent for the selected provider." />
            ) : (
              <div className="space-y-3">
                {consents.map((consent) => (
                  <div key={consent.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="font-semibold text-slate-800">{consent.consent_type.replaceAll('_', ' ')}</div>
                      <div className="mt-1 text-sm text-slate-500">For {consent.purpose.replaceAll('_', ' ')} · {consent.granted_to_name}</div>
                      <div className="mt-1 text-xs text-slate-400">Granted {formatDate(consent.granted_at)} · Source: {consent.source.replaceAll('_', ' ')}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge color={statusColor[consent.status] || 'blue'}>{consent.status}</Badge>
                      {consent.is_current && <Button variant="outline" onClick={() => revokeConsent(consent)}>Revoke</Button>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      <Modal open={!!recordType} onClose={() => setRecordType(null)} title={`Add ${recordType || ''}`}>
        <form onSubmit={submitRecord} className="space-y-4">
          {recordType === 'allergy' && (
            <>
              <Input required label="Substance or medicine" value={form.substance} onChange={(e) => setForm({ ...form, substance: e.target.value })} placeholder="e.g. Penicillin" />
              <Input label="Reaction" value={form.reaction} onChange={(e) => setForm({ ...form, reaction: e.target.value })} placeholder="e.g. Rash, swelling" />
              <Select label="Severity" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })}>
                <option value="unknown">Unknown</option><option value="mild">Mild</option><option value="moderate">Moderate</option><option value="severe">Severe</option><option value="life_threatening">Life threatening</option>
              </Select>
            </>
          )}
          {recordType === 'condition' && (
            <>
              <Input required label="Condition" value={form.display} onChange={(e) => setForm({ ...form, display: e.target.value })} placeholder="e.g. Hypertension" />
              <Input type="date" label="Onset date" value={form.onset_date} onChange={(e) => setForm({ ...form, onset_date: e.target.value })} />
            </>
          )}
          {recordType === 'medication' && (
            <>
              <Input required label="Medicine" value={form.medication_name} onChange={(e) => setForm({ ...form, medication_name: e.target.value })} />
              <div className="grid grid-cols-2 gap-3"><Input label="Dose" value={form.dose} onChange={(e) => setForm({ ...form, dose: e.target.value })} /><Input label="Frequency" value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })} /></div>
              <Input label="Route" value={form.route} onChange={(e) => setForm({ ...form, route: e.target.value })} />
            </>
          )}
          <Textarea label="Notes" value={form.notes || ''} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <Alert tone="warning">Information entered by a patient remains marked as patient reported until a clinician verifies it.</Alert>
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setRecordType(null)}>Cancel</Button><Button disabled={saving}>{saving ? 'Saving…' : 'Save record'}</Button></div>
        </form>
      </Modal>

      <Modal open={consentOpen} onClose={() => setConsentOpen(false)} title="Grant health-data consent">
        <form onSubmit={grantConsent} className="space-y-4">
          <Select label="Consent type" value={consentForm.consent_type} onChange={(e) => setConsentForm({ ...consentForm, consent_type: e.target.value })}>
            <option value="treatment">Treatment</option><option value="telemedicine">Telemedicine</option><option value="data_sharing">Clinical data sharing</option><option value="pharmacy">Pharmacy fulfilment</option><option value="laboratory">Laboratory services</option><option value="insurance">Insurance processing</option><option value="research">Research</option>
          </Select>
          <Select label="Purpose" value={consentForm.purpose} onChange={(e) => setConsentForm({ ...consentForm, purpose: e.target.value })}>
            <option value="treatment">Treatment</option><option value="payment">Payment</option><option value="healthcare_operations">Healthcare operations</option><option value="research">Research</option>
          </Select>
          <Input label="Recipient class" value={consentForm.recipient_class} onChange={(e) => setConsentForm({ ...consentForm, recipient_class: e.target.value })} />
          <Input type="datetime-local" label="Optional expiry" value={consentForm.valid_until} onChange={(e) => setConsentForm({ ...consentForm, valid_until: e.target.value })} />
          <Textarea label="Data categories (comma separated)" value={consentForm.data_categories.join(', ')} onChange={(e) => setConsentForm({ ...consentForm, data_categories: e.target.value.split(',').map((v) => v.trim()).filter(Boolean) })} />
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setConsentOpen(false)}>Cancel</Button><Button disabled={saving}>{saving ? 'Recording…' : 'Grant consent'}</Button></div>
        </form>
      </Modal>
    </div>
  )
}
