import { useEffect, useMemo, useState } from 'react'
import client from '../../api/client'
import { authApi, registryApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, Input, Select, Spinner, Stars, Table } from '../../components/ui'
import { useAuth } from '../../auth/AuthContext'
import { statusColor } from './util'

const initialProfile = {
  year_of_completion: '', university: '', cadre: '', specialty: '', workplace: '',
  experience_years: '', consultation_fee: '', bio: '', registration_number: '',
  license_issuer: '', license_issued_on: '', license_expires_on: '', offers_appointments: true,
}

function normalizeProfile(profile, doctorMode) {
  if (doctorMode) {
    return {
      year_of_completion: profile.year_of_completion ?? '', university: profile.university || '',
      cadre: profile.cadre || 'medical_officer', specialty: profile.specialization || '',
      workplace: profile.hospital || '', experience_years: profile.experience_years ?? '',
      consultation_fee: profile.fees ?? '', bio: profile.bio || '',
      registration_number: profile.license_number || '', license_issuer: profile.license_issuer || '',
      license_issued_on: profile.license_issued_on || '', license_expires_on: profile.license_expires_on || '',
      offers_appointments: true,
    }
  }
  return {
    ...initialProfile,
    year_of_completion: profile.year_of_completion ?? '', university: profile.university || '',
    cadre: profile.cadre || '', specialty: profile.specialty || '', workplace: profile.workplace || '',
    experience_years: profile.experience_years ?? '', consultation_fee: profile.consultation_fee ?? '',
    bio: profile.bio || '', registration_number: profile.registration_number || '',
    license_issuer: profile.license_issuer || '', license_issued_on: profile.license_issued_on || '',
    license_expires_on: profile.license_expires_on || '', offers_appointments: Boolean(profile.offers_appointments),
  }
}

export default function Profile() {
  const { setUser } = useAuth()
  const [me, setMe] = useState(null)
  const [profile, setProfile] = useState(null)
  const [userForm, setUserForm] = useState({ first_name: '', last_name: '', phone: '' })
  const [profileForm, setProfileForm] = useState(initialProfile)
  const [license, setLicense] = useState(null)
  const [certificates, setCertificates] = useState(null)
  const [photo, setPhoto] = useState(null)
  const [saving, setSaving] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [credentials, setCredentials] = useState([])
  const [credentialForm, setCredentialForm] = useState({ credential_type: 'license', identifier: '', issuer: '', title: '', issued_on: '', expires_on: '' })

  const doctorMode = me?.role === 'doctor'
  const roleLabel = useMemo(() => (me?.role || 'professional').replaceAll('_', ' '), [me])

  async function load() {
    try {
      const [meResponse, profileResponse, credentialsResponse] = await Promise.all([
        authApi.me(), client.get('/auth/me/profile/'), registryApi.credentials(),
      ])
      const user = meResponse.data
      setMe(user)
      setUserForm({ first_name: user.first_name || '', last_name: user.last_name || '', phone: user.phone || '' })
      setProfile(profileResponse.data)
      setProfileForm(normalizeProfile(profileResponse.data, user.role === 'doctor'))
      setCredentials(credentialsResponse.data || [])
    } catch {
      setError('Professional profile could not be loaded.')
    }
  }

  useEffect(() => { load() }, [])

  if (!me || !profile) return <Spinner label="Loading professional profile…" />
  const setU = (key) => (event) => setUserForm((current) => ({ ...current, [key]: event.target.value }))
  const setP = (key) => (event) => setProfileForm((current) => ({ ...current, [key]: event.target.type === 'checkbox' ? event.target.checked : event.target.value }))

  async function saveAccount(event) {
    event.preventDefault(); setSaving('account'); setMessage(''); setError('')
    try {
      const response = await authApi.updateMe(userForm)
      setUser?.(response.data); setMe(response.data); setMessage('Account details saved.')
    } catch (err) { setError(err.response?.data?.detail || 'Account details could not be saved.') }
    finally { setSaving('') }
  }

  async function saveProfile(event) {
    event.preventDefault(); setSaving('profile'); setMessage(''); setError('')
    const common = {
      year_of_completion: profileForm.year_of_completion === '' ? null : Number(profileForm.year_of_completion),
      university: profileForm.university, cadre: profileForm.cadre,
      experience_years: profileForm.experience_years === '' ? 0 : Number(profileForm.experience_years),
      bio: profileForm.bio, license_issuer: profileForm.license_issuer,
      license_issued_on: profileForm.license_issued_on || null,
      license_expires_on: profileForm.license_expires_on || null,
    }
    const payload = doctorMode
      ? { ...common, specialization: profileForm.specialty, hospital: profileForm.workplace, fees: Number(profileForm.consultation_fee || 0), license_number: profileForm.registration_number }
      : { ...common, specialty: profileForm.specialty, workplace: profileForm.workplace, consultation_fee: Number(profileForm.consultation_fee || 0), registration_number: profileForm.registration_number, offers_appointments: profileForm.offers_appointments }
    try {
      const response = await authApi.updateProfile(payload)
      setProfile(response.data); setProfileForm(normalizeProfile(response.data, doctorMode))
      setMessage('Professional profile saved. Credential changes return verification to pending review.')
    } catch (err) { setError(err.response?.data?.detail || 'Professional profile could not be saved.') }
    finally { setSaving('') }
  }

  async function uploadEvidence(event) {
    event.preventDefault()
    if (!license) return setError('Choose a practising licence document first.')
    setSaving('license'); setMessage(''); setError('')
    try {
      const form = new FormData()
      form.append(doctorMode ? 'license_number' : 'registration_number', profileForm.registration_number)
      form.append('license_issuer', profileForm.license_issuer)
      if (profileForm.license_issued_on) form.append('license_issued_on', profileForm.license_issued_on)
      if (profileForm.license_expires_on) form.append('license_expires_on', profileForm.license_expires_on)
      form.append('license_document', license)
      if (doctorMode && certificates) form.append('certificates', certificates)
      if (doctorMode) await authApi.uploadLicense(form)
      else await client.patch('/auth/me/profile/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      setLicense(null); setCertificates(null); setMessage('Credential evidence submitted for administrator review.')
      await load()
    } catch (err) { setError(err.response?.data?.detail || 'Credential evidence could not be uploaded.') }
    finally { setSaving('') }
  }

  async function uploadPhoto(event) {
    event.preventDefault()
    if (!photo) return setError('Choose a profile photo first.')
    setSaving('photo'); setMessage(''); setError('')
    try {
      const form = new FormData()
      form.append('photo', photo)
      const response = await client.patch('/auth/me/profile/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
      setProfile(response.data); setPhoto(null)
      setMessage('Profile photo updated.')
      await load()
    } catch (err) { setError(err.response?.data?.detail || 'Profile photo could not be uploaded.') }
    finally { setSaving('') }
  }

  async function submitCredential(event) {
    event.preventDefault(); setSaving('credential'); setMessage(''); setError('')
    try {
      await registryApi.createCredential({ ...credentialForm, issued_on: credentialForm.issued_on || null, expires_on: credentialForm.expires_on || null })
      const response = await registryApi.credentials(); setCredentials(response.data || [])
      setCredentialForm({ credential_type: 'license', identifier: '', issuer: '', title: '', issued_on: '', expires_on: '' })
      setMessage('Structured credential submitted for independent verification.')
    } catch (err) { setError(err.response?.data?.detail || 'Credential could not be submitted.') }
    finally { setSaving('') }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Card title="Account identity" className="xl:col-span-2">
          <form onSubmit={saveAccount} className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input label="Email" value={me.email || ''} disabled />
            <Input label="Primary role" value={roleLabel} disabled />
            <Input label="First name" value={userForm.first_name} onChange={setU('first_name')} required />
            <Input label="Last name" value={userForm.last_name} onChange={setU('last_name')} required />
            <Input label="Phone" value={userForm.phone} onChange={setU('phone')} placeholder="+256…" />
            <div className="flex items-end"><Button disabled={saving === 'account'}>{saving === 'account' ? 'Saving…' : 'Save identity'}</Button></div>
          </form>
        </Card>
        {doctorMode && (
          <Card title="Profile photo">
            <form onSubmit={uploadPhoto} className="space-y-4">
              <div className="flex items-center gap-4">
                {profile.photo_url ? (
                  <img src={profile.photo_url} alt="Current profile" className="h-20 w-20 rounded-2xl border border-slate-200 object-cover" />
                ) : (
                  <span className="grid h-20 w-20 place-items-center rounded-2xl bg-primary-50 text-2xl font-bold text-primary-700">
                    {(me.first_name || 'D')[0]}{(me.last_name || '')[0] || ''}
                  </span>
                )}
                <p className="text-sm text-slate-500">A clear headshot helps patients recognise you before a consultation.</p>
              </div>
              <input
                type="file"
                accept="image/*"
                aria-label="Profile photo file"
                onChange={(event) => setPhoto(event.target.files?.[0] || null)}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-primary-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-primary-700"
              />
              <Button disabled={saving === 'photo' || !photo}>{saving === 'photo' ? 'Uploading…' : 'Upload photo'}</Button>
            </form>
          </Card>
        )}
        <Card title="Professional standing">
          <div className="space-y-4">
            <div className="flex items-center justify-between"><span className="text-sm text-slate-500">Verification</span><Badge color={statusColor(profile.status || 'pending')}>{profile.status || 'pending'}</Badge></div>
            <div className="flex items-center justify-between"><span className="text-sm text-slate-500">Rating</span><Stars value={profile.average_rating || 0} /></div>
            <div className="flex items-center justify-between"><span className="text-sm text-slate-500">Appointments</span><Badge color={profileForm.offers_appointments ? 'green' : 'slate'}>{profileForm.offers_appointments ? 'Enabled' : 'Disabled'}</Badge></div>
            {profile.license_document_url && <a href={profile.license_document_url} target="_blank" rel="noreferrer" className="text-sm font-medium text-primary-600 hover:underline">View protected licence evidence</a>}
          </div>
        </Card>
      </div>

      {(message || error) && <Alert title={error ? 'Action required' : 'Saved'}>{error || message}</Alert>}

      <Card title={`${doctorMode ? 'Doctor' : 'Healthcare professional'} profile`}>
        <form onSubmit={saveProfile} className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <Input required label="Training institution" value={profileForm.university} onChange={setP('university')} />
          <Input required type="number" min="1950" max="2100" label="Year of completion" value={profileForm.year_of_completion} onChange={setP('year_of_completion')} />
          <Input required label="Cadre / professional title" value={profileForm.cadre} onChange={setP('cadre')} placeholder="Medical Officer, Physiotherapist…" />
          <Input label="Speciality" value={profileForm.specialty} onChange={setP('specialty')} />
          <Input required label="Current workplace" value={profileForm.workplace} onChange={setP('workplace')} />
          <Input type="number" min="0" label="Experience (years)" value={profileForm.experience_years} onChange={setP('experience_years')} />
          <Input required label="Practising licence number" value={profileForm.registration_number} onChange={setP('registration_number')} />
          <Input label="Issuing regulator" value={profileForm.license_issuer} onChange={setP('license_issuer')} />
          <Input type="date" label="Licence issued" value={profileForm.license_issued_on} onChange={setP('license_issued_on')} />
          <Input type="date" label="Licence expiry" value={profileForm.license_expires_on} onChange={setP('license_expires_on')} />
          <Input type="number" min="0" label="Consultation fee (UGX)" value={profileForm.consultation_fee} onChange={setP('consultation_fee')} />
          {!doctorMode && <label className="flex items-center gap-3 rounded-xl border border-slate-200 px-4 py-3 text-sm"><input type="checkbox" checked={profileForm.offers_appointments} onChange={setP('offers_appointments')} /><span>Publish availability after verification</span></label>}
          <label className="md:col-span-2 xl:col-span-3"><span className="mb-1 block text-sm font-medium text-slate-600">Professional biography</span><textarea rows={4} value={profileForm.bio} onChange={setP('bio')} className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" /></label>
          <div className="md:col-span-2 xl:col-span-3"><Button disabled={saving === 'profile'}>{saving === 'profile' ? 'Saving…' : 'Save professional profile'}</Button></div>
        </form>
      </Card>

      <Card title="Practising licence evidence">
        <form onSubmit={uploadEvidence} className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <label><span className="mb-1 block text-sm font-medium text-slate-600">Licence image or PDF *</span><input type="file" accept="image/*,.pdf" onChange={(event) => setLicense(event.target.files?.[0] || null)} className="text-sm" /></label>
          {doctorMode && <label><span className="mb-1 block text-sm font-medium text-slate-600">Qualification certificate</span><input type="file" accept="image/*,.pdf" onChange={(event) => setCertificates(event.target.files?.[0] || null)} className="text-sm" /></label>}
          <div className="flex items-end"><Button disabled={saving === 'license'}>{saving === 'license' ? 'Uploading…' : 'Submit for verification'}</Button></div>
        </form>
      </Card>

      <Card title="Structured credential registry">
        <form onSubmit={submitCredential} className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Select label="Credential type" value={credentialForm.credential_type} onChange={(event) => setCredentialForm((form) => ({ ...form, credential_type: event.target.value }))}><option value="license">Professional licence</option><option value="degree">Degree</option><option value="certificate">Certificate</option><option value="specialty">Speciality credential</option><option value="other">Other</option></Select>
          <Input required label="Identifier" value={credentialForm.identifier} onChange={(event) => setCredentialForm((form) => ({ ...form, identifier: event.target.value }))} />
          <Input required label="Issuer" value={credentialForm.issuer} onChange={(event) => setCredentialForm((form) => ({ ...form, issuer: event.target.value }))} />
          <Input label="Title" value={credentialForm.title} onChange={(event) => setCredentialForm((form) => ({ ...form, title: event.target.value }))} />
          <Input type="date" label="Issued on" value={credentialForm.issued_on} onChange={(event) => setCredentialForm((form) => ({ ...form, issued_on: event.target.value }))} />
          <Input type="date" label="Expires on" value={credentialForm.expires_on} onChange={(event) => setCredentialForm((form) => ({ ...form, expires_on: event.target.value }))} />
          <div className="md:col-span-3"><Button disabled={saving === 'credential'}>{saving === 'credential' ? 'Submitting…' : 'Add credential'}</Button></div>
        </form>
        <div className="mt-6"><Table rows={credentials} empty="No structured credentials submitted." columns={[{ key: 'credential_type', label: 'Type', render: (row) => <Badge color="purple">{row.credential_type}</Badge> }, { key: 'identifier', label: 'Identifier' }, { key: 'issuer', label: 'Issuer' }, { key: 'expires_on', label: 'Expires', render: (row) => row.expires_on || 'Not specified' }, { key: 'status', label: 'Status', render: (row) => <Badge color={statusColor(row.status)}>{row.status}</Badge> }]} /></div>
      </Card>
    </div>
  )
}
