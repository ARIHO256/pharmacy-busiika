import { useCallback, useEffect, useState } from 'react'
import { authApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, Input, Modal, Select, Spinner, Table } from '../../components/ui'

const emptyForm = {
  first_name: '', last_name: '', dob: '', gender: '', relationship: 'child', blood_group: '',
  allergies: '', medical_history: '', emergency_contact: '', location: '', address: '', notes: '',
}

export default function Dependents() {
  const [rows, setRows] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [open, setOpen] = useState(false)
  const [authority, setAuthority] = useState(null)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(() => {
    authApi.dependents().then((r) => setRows(r.data)).catch(() => setError('Could not load family and caregiver access.'))
  }, [])
  useEffect(() => load(), [load])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true); setError(''); setNotice('')
    try {
      const payload = new FormData()
      Object.entries(form).forEach(([key, value]) => value !== '' && payload.append(key, value))
      if (authority) payload.append('authority_document', authority)
      const { data } = await authApi.addDependent(payload)
      setOpen(false); setForm(emptyForm); setAuthority(null)
      setNotice(data.status === 'pending'
        ? 'Dependent created. Adult caregiver authority is pending administrator verification.'
        : 'Dependent created and ready for appointments, records and billing.')
      load()
    } catch (err) {
      const data = err.response?.data
      setError(data?.detail || Object.values(data || {}).flat().join(' ') || 'Could not create the dependent profile.')
    } finally { setBusy(false) }
  }

  const revoke = async (row) => {
    if (!window.confirm(`Revoke caregiver access for ${row.patient_name}? Historical records will be preserved.`)) return
    setBusy(true); setError('')
    try { await authApi.revokeDependent(row.id); setNotice('Caregiver access revoked.'); load() }
    catch (err) { setError(err.response?.data?.detail || 'Could not revoke access.') }
    finally { setBusy(false) }
  }

  if (!rows) return <Spinner label="Loading family profiles…" />
  return <div className="space-y-5">
    {notice && <Alert tone="success">{notice}</Alert>}
    {error && <Alert tone="danger">{error}</Alert>}
    <Card>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.16em] text-primary-600">Family care</p>
          <h2 className="mt-1 text-xl font-semibold text-slate-900">Dependents and caregiver authority</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Create a separate clinical identity for a child or dependent. Their appointments, prescriptions, invoices and medical records remain distinct from yours while approved caregiver permissions are enforced by the API.</p>
        </div>
        <Button onClick={() => { setForm(emptyForm); setAuthority(null); setOpen(true) }}>Add dependent</Button>
      </div>
    </Card>
    <Card title="Managed patient profiles" subtitle="Only active relationships can be used for bookings, billing and record access.">
      <Table rows={rows} empty="No dependents have been added." columns={[
        { key: 'patient', label: 'Patient', render: (r) => <div><div className="font-semibold text-slate-800">{r.patient_name}</div><div className="text-xs text-slate-400">DOB {r.dob || 'not recorded'} · {r.gender || 'not specified'}</div></div> },
        { key: 'relationship', label: 'Relationship', render: (r) => String(r.relationship || '').replaceAll('_', ' ') },
        { key: 'status', label: 'Authority', render: (r) => <Badge color={r.status === 'active' ? 'green' : r.status === 'pending' ? 'amber' : 'slate'}>{r.status}</Badge> },
        { key: 'permissions', label: 'Permissions', render: (r) => <div className="flex max-w-sm flex-wrap gap-1 text-xs">{r.can_book && <Badge>Bookings</Badge>}{r.can_view_records && <Badge>Records</Badge>}{r.can_manage_billing && <Badge>Billing</Badge>}{r.can_receive_notifications && <Badge>Alerts</Badge>}</div> },
        { key: 'actions', label: '', render: (r) => r.status !== 'revoked' ? <Button variant="outline" className="px-3 py-1 text-xs" disabled={busy} onClick={() => revoke(r)}>Revoke</Button> : null },
      ]}/>
    </Card>
    <Modal open={open} onClose={() => setOpen(false)} title="Add a dependent patient" wide>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2"><Input required label="First name" value={form.first_name} onChange={(e) => setForm({...form, first_name:e.target.value})}/><Input required label="Last name" value={form.last_name} onChange={(e) => setForm({...form, last_name:e.target.value})}/></div>
        <div className="grid gap-3 sm:grid-cols-3"><Input required type="date" label="Date of birth" value={form.dob} onChange={(e) => setForm({...form, dob:e.target.value})}/><Select label="Gender" value={form.gender} onChange={(e) => setForm({...form, gender:e.target.value})}><option value="">Not specified</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option><option value="prefer_not_to_say">Prefer not to say</option></Select><Select required label="Relationship" value={form.relationship} onChange={(e) => setForm({...form, relationship:e.target.value})}><option value="child">Child / dependent</option><option value="parent">Parent</option><option value="guardian">Legal guardian</option><option value="spouse">Spouse</option><option value="sibling">Sibling</option><option value="caregiver">Caregiver</option><option value="legal_representative">Legal representative</option><option value="other">Other</option></Select></div>
        <div className="grid gap-3 sm:grid-cols-2"><Input label="Blood group" value={form.blood_group} onChange={(e) => setForm({...form, blood_group:e.target.value})}/><Input label="Emergency contact" value={form.emergency_contact} onChange={(e) => setForm({...form, emergency_contact:e.target.value})}/></div>
        <div className="grid gap-3 sm:grid-cols-2"><Input label="Location" value={form.location} onChange={(e) => setForm({...form, location:e.target.value})}/><Input label="Address" value={form.address} onChange={(e) => setForm({...form, address:e.target.value})}/></div>
        <label className="block"><span className="mb-1 block text-sm font-medium text-slate-600">Known allergies</span><textarea rows={2} className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" value={form.allergies} onChange={(e) => setForm({...form, allergies:e.target.value})}/></label>
        <label className="block"><span className="mb-1 block text-sm font-medium text-slate-600">Medical history</span><textarea rows={2} className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm" value={form.medical_history} onChange={(e) => setForm({...form, medical_history:e.target.value})}/></label>
        <label className="block"><span className="mb-1 block text-sm font-medium text-slate-600">Authority evidence <span className="font-normal text-slate-400">(recommended for adults)</span></span><input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" className="w-full rounded-xl border border-slate-300 p-2 text-sm" onChange={(e) => setAuthority(e.target.files?.[0] || null)}/></label>
        <p className="rounded-xl bg-amber-50 p-3 text-xs leading-5 text-amber-800">Child profiles become active immediately. Access to an adult dependent requires authority evidence or administrator approval.</p>
        <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={busy}>{busy ? 'Creating…' : 'Create patient profile'}</Button></div>
      </form>
    </Modal>
  </div>
}
