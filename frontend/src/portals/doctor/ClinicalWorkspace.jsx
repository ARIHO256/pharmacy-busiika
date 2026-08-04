import { useEffect, useMemo, useState } from 'react'
import { appointmentApi, authApi, clinicalApi, governanceApi } from '../../api/endpoints'
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

const emptyEncounter = {
  chief_complaint: '',
  history_of_present_illness: '',
  examination: '',
  assessment: '',
  treatment_plan: '',
  safety_net_advice: '',
  telemedicine_limitations: '',
  follow_up_date: '',
}

function patientName(appointment) {
  return appointment.patient_name || `Patient #${appointment.patient}`
}

function Obs({ item }) {
  const value = item.value_text || `${item.value_numeric ?? ''} ${item.unit || ''}`.trim()
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">{item.display}</div>
      <div className="mt-1 text-lg font-bold text-slate-800">{value || '—'}</div>
      <Badge color={item.interpretation === 'critical' ? 'red' : item.interpretation === 'normal' ? 'green' : 'yellow'}>{item.interpretation}</Badge>
    </div>
  )
}

export default function ClinicalWorkspace() {
  const [appointments, setAppointments] = useState(null)
  const [active, setActive] = useState(null)
  const [summary, setSummary] = useState(null)
  const [consents, setConsents] = useState([])
  const [encounter, setEncounter] = useState(null)
  const [form, setForm] = useState(emptyEncounter)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [vitalsOpen, setVitalsOpen] = useState(false)
  const [vital, setVital] = useState({ display: 'Blood pressure', code: 'blood-pressure', value_text: '', unit: 'mmHg', interpretation: 'unknown' })
  const [referralOpen, setReferralOpen] = useState(false)
  const [referralProviders, setReferralProviders] = useState([])
  const [referral, setReferral] = useState({ target_provider: '', target_specialty: '', target_facility: '', reason: '', clinical_summary: '', priority: 'routine' })
  const [emergencyOpen, setEmergencyOpen] = useState(false)
  const [emergencyReason, setEmergencyReason] = useState('')
  const [amendmentOpen, setAmendmentOpen] = useState(false)
  const [amendmentReason, setAmendmentReason] = useState('')
  const [amendMode, setAmendMode] = useState(false)

  async function loadAppointments() {
    try {
      const response = await appointmentApi.list()
      const list = (response.data || []).filter((a) => ['confirmed', 'completed'].includes(a.status))
      setAppointments(list)
      if (!active && list.length) setActive(list[0])
    } catch {
      setAppointments([])
    }
  }

  useEffect(() => { loadAppointments(); authApi.doctors().then((r) => setReferralProviders(r.data || [])).catch(() => setReferralProviders([])) }, [])

  useEffect(() => {
    if (!active) return
    let cancelled = false
    setSummary(null)
    setError('')
    Promise.all([
      clinicalApi.summary(active.patient),
      clinicalApi.encounters(active.patient),
      governanceApi.patientConsents(active.patient),
    ]).then(([summaryRes, encounterRes, consentRes]) => {
      if (cancelled) return
      setSummary(summaryRes.data)
      setConsents(consentRes.data || [])
      const found = (encounterRes.data || []).find((e) => e.appointment === active.id) || null
      setEncounter(found)
      setAmendMode(false)
      setAmendmentReason('')
      setForm(found ? {
        chief_complaint: found.chief_complaint || active.reason || '',
        history_of_present_illness: found.history_of_present_illness || '',
        examination: found.examination || '',
        assessment: found.assessment || '',
        treatment_plan: found.treatment_plan || '',
        safety_net_advice: found.safety_net_advice || '',
        telemedicine_limitations: found.telemedicine_limitations || '',
        follow_up_date: found.follow_up_date || '',
      } : { ...emptyEncounter, chief_complaint: active.reason || '' })
    }).catch((err) => {
      if (cancelled) return
      setSummary({ denied: true, allergies: [], conditions: [], medications: [], latest_observations: [] })
      setConsents([])
      setError(err.response?.data?.detail || 'The patient record is not available.')
    })
    return () => { cancelled = true }
  }, [active?.id])

  const activeConsent = useMemo(() => consents.some((c) => c.is_current && ['treatment', 'telemedicine', 'data_sharing'].includes(c.consent_type)), [consents])
  const final = ['final', 'amended'].includes(encounter?.status)
  const noteLocked = final && !amendMode

  async function saveEncounter(e) {
    e?.preventDefault()
    if (!active) return
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const response = encounter
        ? await clinicalApi.updateEncounter(encounter.id, form)
        : await clinicalApi.saveEncounter({ appointment: active.id, ...form })
      setEncounter(response.data)
      setNotice('Draft clinical note saved with provenance and audit history.')
    } catch (err) {
      setError(err.response?.data?.detail || 'The clinical note could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function finalize() {
    if (!encounter) {
      setError('Save the encounter before finalizing it.')
      return
    }
    if (!window.confirm('Finalize and sign this clinical note? Final notes cannot be silently overwritten.')) return
    setSaving(true)
    try {
      const response = await clinicalApi.finalizeEncounter(encounter.id)
      setEncounter(response.data)
      setNotice('Clinical note finalized and signed. Any later correction must be an amendment.')
      await loadAppointments()
    } catch (err) {
      setError(err.response?.data?.detail || 'The clinical note could not be finalized.')
    } finally {
      setSaving(false)
    }
  }

  function beginAmendment(e) {
    e.preventDefault()
    if (amendmentReason.trim().length < 10) {
      setError('Provide a specific amendment reason of at least 10 characters.')
      return
    }
    setAmendmentOpen(false)
    setAmendMode(true)
    setError('')
    setNotice('Amendment mode is active. Update the required fields and save a new signed version.')
  }

  async function saveAmendment() {
    if (!encounter || !amendMode) return
    setSaving(true)
    setError('')
    try {
      const response = await clinicalApi.amendEncounter(encounter.id, {
        reason: amendmentReason,
        ...form,
      })
      setEncounter(response.data)
      setAmendMode(false)
      setAmendmentReason('')
      setNotice(`Amendment version ${response.data.version} was signed without deleting the previous version.`)
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.non_field_errors?.[0] || 'The amendment could not be saved.')
    } finally {
      setSaving(false)
    }
  }

  async function saveVital(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await clinicalApi.addObservation({
        ...vital,
        category: 'vital_signs',
        encounter: encounter?.id || null,
      }, active.patient)
      setVitalsOpen(false)
      const response = await clinicalApi.summary(active.patient)
      setSummary(response.data)
      setNotice('Observation recorded in the longitudinal patient record.')
    } catch (err) {
      setError(err.response?.data?.detail || 'Observation could not be recorded.')
    } finally {
      setSaving(false)
    }
  }

  async function createReferral(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await clinicalApi.addReferral({ ...referral, encounter: encounter?.id || null }, active.patient)
      setReferralOpen(false)
      setNotice('Referral created and added to the patient timeline.')
      setReferral({ target_provider: '', target_specialty: '', target_facility: '', reason: '', clinical_summary: '', priority: 'routine' })
    } catch (err) {
      setError(err.response?.data?.detail || 'Referral could not be created.')
    } finally {
      setSaving(false)
    }
  }

  async function startEmergency(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await governanceApi.startBreakGlass({ patient: active.patient, appointment: active.id, reason: emergencyReason })
      setEmergencyOpen(false)
      setNotice('Emergency access is active for 30 minutes and has been escalated for compliance review.')
      const response = await clinicalApi.summary(active.patient)
      setSummary(response.data)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Emergency access could not be started.')
    } finally {
      setSaving(false)
    }
  }

  if (!appointments) return <Spinner label="Loading clinical workspace…" />

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Clinical care"
        title="Clinical Workspace"
        description="Document the encounter, review consent-aware patient history, capture observations, create referrals and sign the final record."
      />

      {error && (
        <Alert tone="danger" title="Clinical access or validation issue">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <span>{error}</span>
            {active && <Button variant="danger" onClick={() => setEmergencyOpen(true)}>Request emergency access</Button>}
          </div>
        </Alert>
      )}
      {notice && <Alert tone="success">{notice}</Alert>}

      {!appointments.length ? (
        <Card><EmptyState icon="🩺" title="No eligible appointments" description="Confirmed and recently completed appointments appear here for clinical documentation." /></Card>
      ) : (
        <div className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)]">
          <Card title="Care queue" className="h-fit [&>div:last-child]:!p-2">
            <div className="space-y-1">
              {appointments.map((item) => (
                <button
                  key={item.id}
                  onClick={() => { setActive(item); setNotice('') }}
                  className={`w-full rounded-lg p-3 text-left transition ${active?.id === item.id ? 'bg-primary-50 ring-1 ring-primary-200' : 'hover:bg-slate-50'}`}
                >
                  <div className="font-semibold text-slate-800">{patientName(item)}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.date} · {String(item.start_time).slice(0, 5)}</div>
                  <div className="mt-2 flex items-center justify-between"><Badge color={item.status === 'confirmed' ? 'green' : 'blue'}>{item.status}</Badge><span className="text-xs text-slate-400">#{item.id}</span></div>
                </button>
              ))}
            </div>
          </Card>

          <div className="min-w-0 space-y-5">
            <Card>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-xs font-bold uppercase tracking-[0.14em] text-primary-600">Patient context</div>
                  <h3 className="mt-1 text-xl font-bold text-slate-900">{patientName(active)}</h3>
                  <div className="mt-1 text-sm text-slate-500">{active.type === 'online' ? 'Telemedicine' : 'In-person'} appointment · {active.reason || 'Reason not recorded'}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge color={activeConsent ? 'green' : 'yellow'}>{activeConsent ? 'Active consent' : 'Consent review needed'}</Badge>
                  {encounter && <Badge color={final ? 'blue' : 'yellow'}>{encounter.status}</Badge>}
                  <Button variant="outline" onClick={() => setVitalsOpen(true)}>Record observation</Button>
                  <Button variant="outline" onClick={() => setReferralOpen(true)}>Create referral</Button>
                </div>
              </div>
            </Card>

            <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
              <div className="space-y-5">
                {!summary ? <Card><Spinner label="Loading patient summary…" /></Card> : (
                  <>
                    <Card title="Safety summary">
                      <div className="space-y-4">
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-rose-600">Allergies</div>
                          {!summary.allergies?.length ? <div className="mt-2 text-sm text-slate-400">None recorded</div> : summary.allergies.map((a) => <div key={a.id} className="mt-2 rounded-lg bg-rose-50 p-2.5 text-sm"><strong>{a.substance}</strong>{a.reaction ? ` — ${a.reaction}` : ''}</div>)}
                        </div>
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-primary-700">Conditions</div>
                          {!summary.conditions?.length ? <div className="mt-2 text-sm text-slate-400">None recorded</div> : summary.conditions.map((c) => <div key={c.id} className="mt-2 text-sm text-slate-700">• {c.display}</div>)}
                        </div>
                        <div>
                          <div className="text-xs font-semibold uppercase tracking-wide text-violet-700">Current medicines</div>
                          {!summary.medications?.length ? <div className="mt-2 text-sm text-slate-400">None recorded</div> : summary.medications.map((m) => <div key={m.id} className="mt-2 text-sm text-slate-700">• {m.medication_name} {m.dose}</div>)}
                        </div>
                      </div>
                    </Card>
                    <Card title="Latest observations">
                      {!summary.latest_observations?.length ? <div className="text-sm text-slate-400">No observations</div> : <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">{summary.latest_observations.slice(0, 6).map((item) => <Obs key={item.id} item={item} />)}</div>}
                    </Card>
                  </>
                )}
              </div>

              <Card title="Clinical encounter note" actions={encounter?.signed_at ? <span className="text-xs text-slate-400">Signed {new Date(encounter.signed_at).toLocaleString()}</span> : null}>
                <form onSubmit={saveEncounter} className="space-y-4">
                  <Textarea disabled={noteLocked} label="Chief complaint" value={form.chief_complaint} onChange={(e) => setForm({ ...form, chief_complaint: e.target.value })} />
                  <Textarea disabled={noteLocked} label="History of present illness" value={form.history_of_present_illness} onChange={(e) => setForm({ ...form, history_of_present_illness: e.target.value })} />
                  <Textarea disabled={noteLocked} label="Examination and observations" value={form.examination} onChange={(e) => setForm({ ...form, examination: e.target.value })} />
                  <Textarea disabled={noteLocked} required label="Assessment / diagnosis" value={form.assessment} onChange={(e) => setForm({ ...form, assessment: e.target.value })} />
                  <Textarea disabled={noteLocked} required label="Treatment plan" value={form.treatment_plan} onChange={(e) => setForm({ ...form, treatment_plan: e.target.value })} />
                  <Textarea disabled={noteLocked} label="Safety-net advice" value={form.safety_net_advice} onChange={(e) => setForm({ ...form, safety_net_advice: e.target.value })} />
                  {active.type === 'online' && <Textarea disabled={noteLocked} label="Limitations of remote examination" value={form.telemedicine_limitations} onChange={(e) => setForm({ ...form, telemedicine_limitations: e.target.value })} />}
                  <Input disabled={noteLocked} type="date" label="Follow-up date" value={form.follow_up_date} onChange={(e) => setForm({ ...form, follow_up_date: e.target.value })} />
                  {final && !amendMode ? (
                    <Alert tone="info" title={`Signed record · version ${encounter.version}`}>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <span>This note is immutable. A correction creates a new signed version while preserving the earlier one.</span>
                        <Button type="button" variant="outline" onClick={() => setAmendmentOpen(true)}>Create amendment</Button>
                      </div>
                    </Alert>
                  ) : amendMode ? (
                    <div className="space-y-3">
                      <Alert tone="warning" title="Amendment mode">Reason: {amendmentReason}</Alert>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button type="button" variant="outline" onClick={() => { setAmendMode(false); setAmendmentReason('') }} disabled={saving}>Cancel amendment</Button>
                        <Button type="button" onClick={saveAmendment} disabled={saving}>{saving ? 'Signing…' : 'Save signed amendment'}</Button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-wrap justify-end gap-2"><Button type="submit" variant="outline" disabled={saving}>{saving ? 'Saving…' : 'Save draft'}</Button><Button type="button" onClick={finalize} disabled={saving || !encounter}>Finalize & sign</Button></div>
                  )}
                </form>
              </Card>
            </div>
          </div>
        </div>
      )}

      <Modal open={vitalsOpen} onClose={() => setVitalsOpen(false)} title="Record clinical observation">
        <form onSubmit={saveVital} className="space-y-4">
          <Select label="Observation" value={vital.code} onChange={(e) => {
            const selected = {
              'blood-pressure': ['Blood pressure', 'mmHg'],
              'heart-rate': ['Heart rate', 'bpm'],
              'temperature': ['Body temperature', '°C'],
              'oxygen-saturation': ['Oxygen saturation', '%'],
              'weight': ['Weight', 'kg'],
            }[e.target.value]
            setVital({ ...vital, code: e.target.value, display: selected[0], unit: selected[1] })
          }}>
            <option value="blood-pressure">Blood pressure</option><option value="heart-rate">Heart rate</option><option value="temperature">Temperature</option><option value="oxygen-saturation">Oxygen saturation</option><option value="weight">Weight</option>
          </Select>
          <Input required label={`Value (${vital.unit})`} value={vital.value_text} onChange={(e) => setVital({ ...vital, value_text: e.target.value })} placeholder={vital.code === 'blood-pressure' ? '120/80' : ''} />
          <Select label="Interpretation" value={vital.interpretation} onChange={(e) => setVital({ ...vital, interpretation: e.target.value })}><option value="unknown">Not assessed</option><option value="normal">Normal</option><option value="high">High</option><option value="low">Low</option><option value="abnormal">Abnormal</option><option value="critical">Critical</option></Select>
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setVitalsOpen(false)}>Cancel</Button><Button disabled={saving}>Record</Button></div>
        </form>
      </Modal>

      <Modal open={referralOpen} onClose={() => setReferralOpen(false)} title="Create referral">
        <form onSubmit={createReferral} className="space-y-4">
          <Select label="Receiving clinician" value={referral.target_provider} onChange={(e) => { const clinician = referralProviders.find((row) => String(row.id) === e.target.value); setReferral({ ...referral, target_provider: e.target.value, target_specialty: clinician?.specialization || referral.target_specialty, target_facility: clinician?.hospital || referral.target_facility }) }}>
            <option value="">Open referral / receiving facility to assign</option>
            {referralProviders.map((clinician) => <option key={clinician.id} value={clinician.id}>Dr. {clinician.first_name} {clinician.last_name} · {clinician.specialization || 'General practice'}</option>)}
          </Select>
          <Input required label="Target specialty" value={referral.target_specialty} onChange={(e) => setReferral({ ...referral, target_specialty: e.target.value })} placeholder="e.g. Neurology" />
          <Input label="Target facility" value={referral.target_facility} onChange={(e) => setReferral({ ...referral, target_facility: e.target.value })} />
          <Select label="Priority" value={referral.priority} onChange={(e) => setReferral({ ...referral, priority: e.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="emergency">Emergency</option></Select>
          <Textarea required label="Reason for referral" value={referral.reason} onChange={(e) => setReferral({ ...referral, reason: e.target.value })} />
          <Textarea label="Clinical summary" value={referral.clinical_summary} onChange={(e) => setReferral({ ...referral, clinical_summary: e.target.value })} />
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setReferralOpen(false)}>Cancel</Button><Button disabled={saving}>Create referral</Button></div>
        </form>
      </Modal>


      <Modal open={amendmentOpen} onClose={() => setAmendmentOpen(false)} title="Create traceable amendment">
        <form onSubmit={beginAmendment} className="space-y-4">
          <Alert tone="warning" title="The signed version will remain available">Describe why the correction is necessary. The platform will create a new version and retain both snapshots in the audit history.</Alert>
          <Textarea required minLength={10} label="Amendment reason" value={amendmentReason} onChange={(e) => setAmendmentReason(e.target.value)} placeholder="e.g. Corrected the assessment after reviewing the laboratory result" />
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setAmendmentOpen(false)}>Cancel</Button><Button>Continue to amendment</Button></div>
        </form>
      </Modal>

      <Modal open={emergencyOpen} onClose={() => setEmergencyOpen(false)} title="Break-glass emergency access">
        <form onSubmit={startEmergency} className="space-y-4">
          <Alert tone="danger" title="High-severity audited action">Use only when immediate patient safety requires access and normal consent is unavailable. Access expires after 30 minutes and is reviewed by compliance staff.</Alert>
          <Textarea required minLength={15} label="Specific emergency reason" value={emergencyReason} onChange={(e) => setEmergencyReason(e.target.value)} />
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setEmergencyOpen(false)}>Cancel</Button><Button variant="danger" disabled={saving}>Start emergency access</Button></div>
        </form>
      </Modal>
    </div>
  )
}
