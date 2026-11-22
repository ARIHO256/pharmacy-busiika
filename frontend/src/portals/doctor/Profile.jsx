import { useEffect, useState } from 'react'
import client from '../../api/client'
import { authApi, registryApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, Input, Select, Spinner, Stars, Table } from '../../components/ui'
import { statusColor } from './util'
import { useAuth } from '../../auth/AuthContext'

export default function Profile() {
  const { setUser } = useAuth()
  const [me, setMe] = useState(null)
  const [profile, setProfile] = useState(null)
  const [userForm, setUserForm] = useState({ first_name: '', last_name: '', phone: '' })
  const [profileForm, setProfileForm] = useState({ year_of_completion: '', university: '', cadre: 'medical_officer', specialization: '', hospital: '', experience_years: '', fees: '', bio: '', license_number: '', license_issuer: '', license_expires_on: '' })
  const [savingUser, setSavingUser] = useState(false)
  const [savingProfile, setSavingProfile] = useState(false)
  const [userMsg, setUserMsg] = useState('')
  const [profileMsg, setProfileMsg] = useState('')
  const [license, setLicense] = useState(null)
  const [certificates, setCertificates] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [uploadErr, setUploadErr] = useState('')
  const [credentials, setCredentials] = useState([])
  const [credentialForm, setCredentialForm] = useState({
    credential_type: 'license',
    identifier: '',
    issuer: '',
    title: '',
    issued_on: '',
    expires_on: '',
  })
  const [savingCredential, setSavingCredential] = useState(false)
  const [credentialMsg, setCredentialMsg] = useState('')

  useEffect(() => {
    authApi.me().then((r) => {
      setMe(r.data)
      setUserForm({
        first_name: r.data.first_name || '',
        last_name: r.data.last_name || '',
        phone: r.data.phone || '',
      })
    }).catch(() => setMe({}))
    client.get('/auth/me/profile/').then((r) => {
      setProfile(r.data)
      setProfileForm({
        year_of_completion: r.data.year_of_completion ?? '',
        university: r.data.university || '',
        cadre: r.data.cadre || 'medical_officer',
        specialization: r.data.specialization || '',
        hospital: r.data.hospital || '',
        experience_years: r.data.experience_years ?? '',
        fees: r.data.fees ?? '',
        bio: r.data.bio || '',
        license_number: r.data.license_number || '',
        license_issuer: r.data.license_issuer || '',
        license_expires_on: r.data.license_expires_on || '',
      })
    }).catch(() => setProfile({}))
    registryApi.credentials().then((r) => setCredentials(r.data || [])).catch(() => setCredentials([]))
  }, [])

  if (!me || !profile) return <Spinner label="Loading profile…" />

  const setU = (k) => (e) => setUserForm((f) => ({ ...f, [k]: e.target.value }))
  const setP = (k) => (e) => setProfileForm((f) => ({ ...f, [k]: e.target.value }))

  async function saveUser(e) {
    e.preventDefault()
    setSavingUser(true)
    setUserMsg('')
    try {
      const r = await authApi.updateMe(userForm)
      setUser?.(r.data)
      setUserMsg('Account details saved.')
    } catch {
      setUserMsg('Could not save account details.')
    } finally {
      setSavingUser(false)
    }
  }

  async function saveProfile(e) {
    e.preventDefault()
    setSavingProfile(true)
    setProfileMsg('')
    try {
      const payload = {
        ...profileForm,
        year_of_completion: profileForm.year_of_completion === '' ? null : Number(profileForm.year_of_completion),
        experience_years: profileForm.experience_years === '' ? 0 : Number(profileForm.experience_years),
        fees: profileForm.fees === '' ? 0 : Number(profileForm.fees),
        license_expires_on: profileForm.license_expires_on || null,
      }
      const r = await client.patch('/auth/me/profile/', payload)
      setProfile(r.data)
      setProfileMsg('Professional profile saved.')
    } catch (err) {
      setProfileMsg(err.response?.data?.detail || 'Could not save profile.')
    } finally {
      setSavingProfile(false)
    }
  }

  async function uploadLicense(e) {
    e.preventDefault()
    if (!license) return setUploadErr('Choose a license document first')
    setUploading(true)
    setUploadMsg('')
    setUploadErr('')
    try {
      const fd = new FormData()
      fd.append('license_document', license)
      fd.append('license_number', profileForm.license_number)
      if (profileForm.license_issuer) fd.append('license_issuer', profileForm.license_issuer)
      if (profileForm.license_expires_on) fd.append('license_expires_on', profileForm.license_expires_on)
      if (certificates) fd.append('certificates', certificates)
      await authApi.uploadLicense(fd)
      setUploadMsg('Documents uploaded. Verification is pending review.')
      setLicense(null)
      setCertificates(null)
    } catch (err) {
      setUploadErr(err.response?.data?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function submitCredential(e) {
    e.preventDefault()
    setSavingCredential(true)
    setCredentialMsg('')
    try {
      const payload = {
        ...credentialForm,
        issued_on: credentialForm.issued_on || null,
        expires_on: credentialForm.expires_on || null,
      }
      await registryApi.createCredential(payload)
      const response = await registryApi.credentials()
      setCredentials(response.data || [])
      setCredentialForm({ credential_type: 'license', identifier: '', issuer: '', title: '', issued_on: '', expires_on: '' })
      setCredentialMsg('Credential submitted for independent administrator verification.')
    } catch (err) {
      const data = err.response?.data
      setCredentialMsg(data?.detail || (data ? JSON.stringify(data) : 'Credential could not be submitted.'))
    } finally {
      setSavingCredential(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* Account */}
      <Card title="Account details">
        <form onSubmit={saveUser} className="space-y-4">
          <Input label="Email" value={me.email || ''} disabled />
          <div className="grid grid-cols-2 gap-3">
            <Input label="First name" value={userForm.first_name} onChange={setU('first_name')} />
            <Input label="Last name" value={userForm.last_name} onChange={setU('last_name')} />
          </div>
          <Input label="Phone" value={userForm.phone} onChange={setU('phone')} placeholder="+256…" />
          {userMsg && <p className="text-sm text-slate-500">{userMsg}</p>}
          <Button type="submit" disabled={savingUser}>{savingUser ? 'Saving…' : 'Save account'}</Button>
        </form>
      </Card>

      {/* Verification status */}
      <Card title="Verification">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Status</span>
            <Badge color={statusColor(profile.status || 'pending')}>{profile.status || 'pending'}</Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-500">Average rating</span>
            <Stars value={profile.average_rating || 0} />
          </div>
          {profile.license_document_url && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-500">License on file</span>
              <a href={profile.license_document_url} target="_blank" rel="noopener noreferrer" className="text-sm text-primary-600 hover:underline">
                View document
              </a>
            </div>
          )}
        </div>

        <form onSubmit={uploadLicense} className="mt-5 border-t border-slate-100 pt-4 space-y-3">
          <span className="block text-sm font-medium text-slate-600">Upload / replace license</span>
          <label className="block">
            <span className="block text-xs text-slate-500 mb-1">License document *</span>
            <input type="file" accept="image/*,.pdf" onChange={(e) => setLicense(e.target.files?.[0] || null)} className="text-sm text-slate-600" />
          </label>
          <label className="block">
            <span className="block text-xs text-slate-500 mb-1">Certificates (optional)</span>
            <input type="file" accept="image/*,.pdf" onChange={(e) => setCertificates(e.target.files?.[0] || null)} className="text-sm text-slate-600" />
          </label>
          {uploadMsg && <p className="text-sm text-emerald-600">{uploadMsg}</p>}
          {uploadErr && <p className="text-sm text-rose-600">{uploadErr}</p>}
          <Button type="submit" disabled={uploading}>{uploading ? 'Uploading…' : 'Upload'}</Button>
        </form>
      </Card>

      <Card title="Professional credentials" className="lg:col-span-2">
        <Alert title="Registry-backed verification">
          Credentials are stored separately from your portal profile so their identifiers, issuer, validity period and verification history remain auditable.
        </Alert>
        <form onSubmit={submitCredential} className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <Select label="Credential type" value={credentialForm.credential_type} onChange={(e) => setCredentialForm((f) => ({ ...f, credential_type: e.target.value }))}>
            <option value="license">Professional licence</option>
            <option value="degree">Degree</option>
            <option value="certificate">Certificate</option>
            <option value="specialty">Specialty credential</option>
            <option value="other">Other</option>
          </Select>
          <Input required label="Identifier" value={credentialForm.identifier} onChange={(e) => setCredentialForm((f) => ({ ...f, identifier: e.target.value }))} placeholder="e.g. MDC-12345" />
          <Input required label="Issuer" value={credentialForm.issuer} onChange={(e) => setCredentialForm((f) => ({ ...f, issuer: e.target.value }))} placeholder="Licensing council or university" />
          <Input label="Title" value={credentialForm.title} onChange={(e) => setCredentialForm((f) => ({ ...f, title: e.target.value }))} placeholder="Medical practitioner licence" />
          <Input type="date" label="Issued on" value={credentialForm.issued_on} onChange={(e) => setCredentialForm((f) => ({ ...f, issued_on: e.target.value }))} />
          <Input type="date" label="Expires on" value={credentialForm.expires_on} onChange={(e) => setCredentialForm((f) => ({ ...f, expires_on: e.target.value }))} />
          <div className="md:col-span-3 flex flex-wrap items-center gap-3">
            <Button disabled={savingCredential}>{savingCredential ? 'Submitting…' : 'Submit credential'}</Button>
            {credentialMsg && <span className="text-sm text-slate-500">{credentialMsg}</span>}
          </div>
        </form>

        <div className="mt-6">
          <Table
            rows={credentials}
            empty="No structured credentials submitted yet."
            columns={[
              { key: 'credential_type', label: 'Type', render: (row) => <Badge color="purple">{row.credential_type}</Badge> },
              { key: 'identifier', label: 'Identifier' },
              { key: 'issuer', label: 'Issuer' },
              { key: 'expires_on', label: 'Expires', render: (row) => row.expires_on || 'Not specified' },
              { key: 'status', label: 'Status', render: (row) => <Badge color={statusColor(row.status)}>{row.status}</Badge> },
            ]}
          />
        </div>
      </Card>

      {/* Professional profile */}
      <Card title="Professional profile" className="lg:col-span-2">
        <form onSubmit={saveProfile} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input required label="University of completion" value={profileForm.university} onChange={setP('university')} placeholder="Medical training institution" />
          <Input required label="Year of completion" type="number" min="1950" max="2100" value={profileForm.year_of_completion} onChange={setP('year_of_completion')} />
          <Select required label="Cadre" value={profileForm.cadre} onChange={setP('cadre')}>
            <option value="medical_officer">Medical Officer</option>
            <option value="specialist">Specialist Doctor</option>
            <option value="consultant">Consultant</option>
            <option value="clinical_officer">Clinical Officer</option>
            <option value="dentist">Dentist</option>
            <option value="other">Other</option>
          </Select>
          <Input label="Specialization" value={profileForm.specialization} onChange={setP('specialization')} placeholder="General Medicine" />
          <Input required label="Hospital / Clinic / Pharmacy" value={profileForm.hospital} onChange={setP('hospital')} placeholder="Current workplace" />
          <Input label="Years of experience" type="number" min="0" value={profileForm.experience_years} onChange={setP('experience_years')} />
          <Input required label="Practising licence number" value={profileForm.license_number} onChange={setP('license_number')} placeholder="e.g. MDC-12345" />
          <Input label="Licence issuing authority" value={profileForm.license_issuer} onChange={setP('license_issuer')} placeholder="Professional council" />
          <Input label="Licence expiry" type="date" value={profileForm.license_expires_on} onChange={setP('license_expires_on')} />
          <Input required label="Consultation fee (UGX)" type="number" min="0" value={profileForm.fees} onChange={setP('fees')} placeholder="30000" />
          <label className="block md:col-span-2">
            <span className="block text-sm font-medium text-slate-600 mb-1">Bio</span>
            <textarea
              value={profileForm.bio}
              onChange={setP('bio')}
              rows={4}
              className="w-full px-3 py-2 rounded-lg border border-slate-300 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Short professional summary shown to patients…"
            />
          </label>
          <div className="md:col-span-2 flex items-center gap-3">
            <Button type="submit" disabled={savingProfile}>{savingProfile ? 'Saving…' : 'Save profile'}</Button>
            {profileMsg && <span className="text-sm text-slate-500">{profileMsg}</span>}
          </div>
        </form>
      </Card>
    </div>
  )
}
