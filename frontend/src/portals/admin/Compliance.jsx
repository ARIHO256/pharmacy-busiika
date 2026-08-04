import { useEffect, useState } from 'react'
import { governanceApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, EmptyState, SectionHeading, Spinner, Stat, Table, Textarea, Modal } from '../../components/ui'

export default function Compliance() {
  const [overview, setOverview] = useState(null)
  const [events, setEvents] = useState([])
  const [breakGlass, setBreakGlass] = useState([])
  const [error, setError] = useState('')
  const [reviewing, setReviewing] = useState(null)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    setError('')
    try {
      const [overviewRes, auditRes, breakRes] = await Promise.all([
        governanceApi.complianceOverview(),
        governanceApi.auditEvents({ limit: 250 }),
        governanceApi.breakGlass(),
      ])
      setOverview(overviewRes.data)
      setEvents(auditRes.data || [])
      setBreakGlass(breakRes.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'Compliance data could not be loaded.')
      setOverview({ consents: {}, active_break_glass: 0, unreviewed_break_glass: 0, audit_events_24h: 0, denied_access_24h: 0 })
    }
  }

  useEffect(() => { load() }, [])

  async function review(action) {
    setSaving(true)
    try {
      await governanceApi.reviewBreakGlass(reviewing.id, { action, notes })
      setReviewing(null)
      setNotes('')
      await load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Review could not be completed.')
    } finally {
      setSaving(false)
    }
  }

  if (!overview) return <Spinner label="Loading compliance controls…" />

  const decisionColor = { allow: 'green', deny: 'red', 'n/a': 'slate' }
  const statusColor = { active: 'red', ended: 'yellow', reviewed: 'green', rejected: 'red' }

  const auditColumns = [
    { key: 'time', label: 'Time', render: (row) => <span className="whitespace-nowrap text-xs text-slate-500">{new Date(row.created_at).toLocaleString()}</span> },
    { key: 'action', label: 'Action', render: (row) => <div><div className="font-medium text-slate-800">{row.action}</div><div className="text-xs text-slate-400">{row.resource_type} {row.resource_id}</div></div> },
    { key: 'actor', label: 'Actor', render: (row) => row.actor_name || 'System' },
    { key: 'patient', label: 'Patient', render: (row) => row.patient_name || '—' },
    { key: 'purpose', label: 'Purpose', render: (row) => row.purpose || '—' },
    { key: 'decision', label: 'Decision', render: (row) => <Badge color={decisionColor[row.decision]}>{row.decision}</Badge> },
  ]

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Trust and governance"
        title="Privacy, Consent & Compliance"
        description="Monitor executable consent, patient-record access, denied requests and time-bound emergency access. Audit records are append-only."
      />

      {error && <Alert tone="danger">{error}</Alert>}
      {!!overview.unreviewed_break_glass && <Alert tone="warning" title="Emergency access review required">{overview.unreviewed_break_glass} break-glass access request(s) require compliance review.</Alert>}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Audit events (24h)" value={overview.audit_events_24h} icon="🧾" tone="text-primary-700" />
        <Stat label="Denied access (24h)" value={overview.denied_access_24h} icon="⛔" tone="text-rose-600" />
        <Stat label="Active emergency access" value={overview.active_break_glass} icon="🚨" tone="text-amber-600" />
        <Stat label="Active consents" value={overview.consents?.active || 0} icon="🔐" tone="text-emerald-600" />
      </div>

      <Card title="Break-glass emergency access">
        {!breakGlass.length ? (
          <EmptyState icon="✓" title="No emergency access requests" description="Emergency accesses will appear here for retrospective review." />
        ) : (
          <div className="space-y-3">
            {breakGlass.map((item) => (
              <div key={item.id} className="flex flex-col gap-3 rounded-xl border border-slate-200 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="flex items-center gap-2"><span className="font-semibold text-slate-800">{item.requester_name} → {item.patient_name}</span><Badge color={statusColor[item.status] || 'slate'}>{item.status}</Badge></div>
                  <p className="mt-2 text-sm text-slate-600">{item.reason}</p>
                  <div className="mt-2 text-xs text-slate-400">Started {new Date(item.started_at).toLocaleString()} · Expires {new Date(item.expires_at).toLocaleString()}</div>
                </div>
                {['active', 'ended'].includes(item.status) && <Button variant="outline" onClick={() => { setReviewing(item); setNotes('') }}>Review</Button>}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card title="Security and clinical access audit">
        <Table columns={auditColumns} rows={events} empty="No governance audit events yet." />
      </Card>

      <Modal open={!!reviewing} onClose={() => setReviewing(null)} title="Review emergency access">
        {reviewing && (
          <div className="space-y-4">
            <Alert tone="warning">Confirm whether emergency access was justified. Rejection does not erase the event; it records a compliance finding.</Alert>
            <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{reviewing.reason}</div>
            <Textarea label="Review notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
            <div className="flex justify-end gap-2"><Button variant="danger" disabled={saving} onClick={() => review('reject')}>Reject access</Button><Button disabled={saving} onClick={() => review('approve')}>Approve as justified</Button></div>
          </div>
        )}
      </Modal>
    </div>
  )
}
