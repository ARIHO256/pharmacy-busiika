import { useState } from 'react'
import { workforceApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Table, Textarea } from '../../components/ui'
import { getError } from '../staff/shared'

export default function Patients() {
  const [search, setSearch] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [created, setCreated] = useState(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', phone: '', location: '', address: '' })
  const runSearch = async (e) => { e?.preventDefault(); setLoading(true); setError(''); try { const { data } = await workforceApi.patients(search); setRows(data) } catch (err) { setError(getError(err)) } finally { setLoading(false) } }
  const create = async (e) => { e.preventDefault(); setError(''); try { const { data } = await workforceApi.registerPatient(form); setCreated(data); setOpen(false); setRows((old) => [data, ...old]) } catch (err) { setError(getError(err)) } }
  return <div className="space-y-4">
    {created && <Alert tone="success" title="Patient registered">Account created for {created.name}. Temporary password: <strong>{created.temporary_password}</strong>. Share it securely and ask the patient to change it immediately.</Alert>}
    {error && <Alert tone="danger">{error}</Alert>}
    <Card title="Patient directory" subtitle="Search before creating a record to prevent duplicates" actions={<Button onClick={() => { setOpen(true); setError('') }}>Register walk-in patient</Button>}>
      <form onSubmit={runSearch} className="mb-5 flex gap-2"><Input className="flex-1" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name, phone or email"/><Button disabled={loading}>{loading ? 'Searching…' : 'Search'}</Button></form>
      <Table rows={rows} empty="Search for a patient by name, phone or email" columns={[{ key: 'name', label: 'Patient' }, { key: 'email', label: 'Email' }, { key: 'phone', label: 'Phone' }, { key: 'location', label: 'Location' }]}/>
    </Card>
    <Modal open={open} onClose={() => setOpen(false)} title="Register walk-in patient"><form onSubmit={create} className="space-y-4">
      <div className="grid grid-cols-2 gap-3"><Input required label="First name" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })}/><Input required label="Last name" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })}/></div>
      <Input required label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}/><Input required label="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}/>
      <Input label="Location / district" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })}/><Textarea label="Address" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}/>
      <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button>Create patient</Button></div>
    </form></Modal>
  </div>
}
