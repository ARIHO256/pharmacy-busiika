import { useEffect, useMemo, useState } from 'react'
import client from '../../api/client'
import { interoperabilityApi, registryApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, EmptyState, SectionHeading, Spinner, Stat, Table } from '../../components/ui'

const statusColor = {
  pending: 'yellow', verified: 'green', rejected: 'red', suspended: 'red',
  revoked: 'red', expired: 'slate', inactive: 'slate', published: 'green', failed: 'red',
}

async function openProtectedFile(url) {
  const response = await client.get(url.replace(/^.*\/api\//, '/'), { responseType: 'blob' })
  const objectUrl = URL.createObjectURL(response.data)
  window.open(objectUrl, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

function reasonFor(status, noun) {
  if (status === 'verified') return window.prompt(`Optional verification note for this ${noun}:`, '')
  return window.prompt(`Reason for marking this ${noun} as ${status}. This is required and audited:`, '')
}

export default function Registry() {
  const [organizations, setOrganizations] = useState(null)
  const [credentials, setCredentials] = useState(null)
  const [outbox, setOutbox] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  async function load() {
    setError('')
    try {
      const [organizationRes, credentialRes, outboxRes] = await Promise.all([
        registryApi.myOrganizations(), registryApi.credentials(), interoperabilityApi.outbox({ limit: 100 }),
      ])
      setOrganizations(organizationRes.data || [])
      setCredentials(credentialRes.data || [])
      setOutbox(outboxRes.data || [])
    } catch (err) {
      setError(err.response?.data?.detail || 'The provider registry could not be loaded.')
      setOrganizations([]); setCredentials([]); setOutbox([])
    }
  }

  useEffect(() => { load() }, [])

  const metrics = useMemo(() => ({
    verifiedOrganizations: organizations?.filter((item) => item.status === 'verified').length || 0,
    pendingOrganizations: organizations?.filter((item) => item.status === 'pending').length || 0,
    pendingCredentials: credentials?.filter((item) => item.status === 'pending').length || 0,
    failedEvents: outbox?.filter((item) => item.status === 'failed').length || 0,
  }), [organizations, credentials, outbox])

  async function setOrganizationStatus(organization, status) {
    const reason = reasonFor(status, 'organization')
    if (reason === null || (status !== 'verified' && !reason.trim())) return
    setBusy(`organization:${organization.public_id}:${status}`); setError('')
    try { await registryApi.setOrganizationStatus(organization.public_id, status, reason); await load() }
    catch (err) { setError(err.response?.data?.detail || 'The organization status could not be changed.') }
    finally { setBusy('') }
  }

  async function setCredentialStatus(credential, status) {
    const reason = reasonFor(status, 'credential')
    if (reason === null || (status !== 'verified' && !reason.trim())) return
    setBusy(`credential:${credential.id}:${status}`); setError('')
    try { await registryApi.verifyCredential(credential.id, status, reason); await load() }
    catch (err) { setError(err.response?.data?.detail || 'The credential status could not be changed.') }
    finally { setBusy('') }
  }

  async function viewDocument(url) {
    if (!url) return
    try { await openProtectedFile(url) }
    catch (err) { setError(err.response?.data?.detail || 'The protected document could not be opened.') }
  }

  if (organizations === null || credentials === null || outbox === null) return <Spinner label="Loading provider registries…" />

  const organizationColumns = [
    { key: 'legal_name', label: 'Organization', render: (row) => <div><div className="font-semibold text-slate-800">{row.trading_name || row.legal_name}</div><div className="text-xs text-slate-400">{row.owner_email || 'No owner'} · {row.contact_email || 'No contact email'}</div><div className="mt-1 max-w-md text-xs text-slate-500">{row.services_description || 'No service description supplied.'}</div></div> },
    { key: 'organization_type', label: 'Type', render: (row) => <Badge color="blue">{row.organization_type}</Badge> },
    { key: 'license_number', label: 'Licence', render: (row) => <div><div>{row.license_number || '—'}</div>{row.license_document_url && <button className="mt-1 text-xs font-semibold text-teal-700 hover:underline" onClick={() => viewDocument(row.license_document_url)}>View protected document</button>}</div> },
    { key: 'district', label: 'District', render: (row) => row.district || '—' },
    { key: 'status', label: 'Status', render: (row) => <Badge color={statusColor[row.status] || 'slate'}>{row.status}</Badge> },
    { key: 'actions', label: 'Actions', render: (row) => <div className="flex flex-wrap gap-2">
      {row.status !== 'verified' && <Button className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setOrganizationStatus(row, 'verified')}>Verify</Button>}
      {row.status === 'pending' && <Button variant="outline" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setOrganizationStatus(row, 'rejected')}>Reject</Button>}
      {row.status === 'verified' && <Button variant="danger" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setOrganizationStatus(row, 'suspended')}>Suspend</Button>}
      {['suspended', 'rejected', 'inactive'].includes(row.status) && <Button variant="outline" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setOrganizationStatus(row, 'verified')}>Reactivate</Button>}
    </div> },
  ]

  const credentialColumns = [
    { key: 'practitioner_name', label: 'Practitioner' },
    { key: 'credential_type', label: 'Type', render: (row) => <Badge color="purple">{row.credential_type}</Badge> },
    { key: 'identifier', label: 'Identifier', render: (row) => <div><div>{row.identifier}</div>{row.document_url && <button className="mt-1 text-xs font-semibold text-teal-700 hover:underline" onClick={() => viewDocument(row.document_url)}>View protected document</button>}</div> },
    { key: 'issuer', label: 'Issuer' },
    { key: 'expires_on', label: 'Expires', render: (row) => row.expires_on || 'Not specified' },
    { key: 'status', label: 'Status', render: (row) => <Badge color={statusColor[row.status] || 'slate'}>{row.status}</Badge> },
    { key: 'actions', label: 'Actions', render: (row) => <div className="flex flex-wrap gap-2">
      {row.status !== 'verified' && row.status !== 'revoked' && <Button className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setCredentialStatus(row, 'verified')}>Verify</Button>}
      {row.status === 'pending' && <Button variant="danger" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setCredentialStatus(row, 'rejected')}>Reject</Button>}
      {row.status === 'verified' && <Button variant="danger" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setCredentialStatus(row, 'revoked')}>Revoke</Button>}
      {row.status === 'verified' && <Button variant="outline" className="px-3 py-1 text-xs" disabled={!!busy} onClick={() => setCredentialStatus(row, 'expired')}>Mark expired</Button>}
    </div> },
  ]

  return <div className="space-y-6">
    <SectionHeading eyebrow="Trusted provider network" title="Provider & Facility Registry" description="Inspect protected licence evidence, manage verification decisions and monitor the event pipeline. Every decision records its actor, reason and time." />
    {error && <Alert tone="danger">{error}</Alert>}
    {!!metrics.failedEvents && <Alert tone="warning" title="Integration delivery needs attention">{metrics.failedEvents} outbox event(s) are marked failed. The event record remains available for safe replay.</Alert>}
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <Stat label="Verified organizations" value={metrics.verifiedOrganizations} icon="🏥" tone="text-emerald-700" />
      <Stat label="Organizations pending" value={metrics.pendingOrganizations} icon="⏳" tone="text-amber-600" />
      <Stat label="Credentials pending" value={metrics.pendingCredentials} icon="🪪" tone="text-violet-700" />
      <Stat label="Failed outbox events" value={metrics.failedEvents} icon="↻" tone="text-rose-600" />
    </div>
    <Card title={`Organizations (${organizations.length})`}><Table columns={organizationColumns} rows={organizations} empty="No registered healthcare organizations." /></Card>
    <Card title={`Practitioner credentials (${credentials.length})`}><Table columns={credentialColumns} rows={credentials} empty="No practitioner credentials have been submitted." /></Card>
    <Card title="Recent integration outbox">{!outbox.length ? <EmptyState icon="↻" title="No domain events yet" description="Clinical, consent, booking and financial events will be recorded here before delivery to external systems." /> : <div className="space-y-2">{outbox.slice(0, 12).map((event) => <div key={event.id} className="flex flex-col gap-2 rounded-xl border border-slate-200 p-3 sm:flex-row sm:items-center sm:justify-between"><div><div className="font-medium text-slate-800">{event.event_type}</div><div className="mt-1 text-xs text-slate-400">{event.aggregate_type} {event.aggregate_id} · v{event.event_version}</div></div><Badge color={statusColor[event.status] || 'yellow'}>{event.status}</Badge></div>)}</div>}</Card>
  </div>
}
