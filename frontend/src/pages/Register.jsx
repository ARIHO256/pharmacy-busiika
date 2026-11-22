import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth, ROLE_HOME } from '../auth/AuthContext'
import { Alert, Button, Input, Select, Textarea } from '../components/ui'
import HealthIcon from '../components/icons/HealthIcon'

const ROLES = [
  { value: 'patient', label: 'Patient', icon: 'heart', text: 'Book care immediately and manage your personal health journey.' },
  { value: 'doctor', label: 'Doctor / Clinician', icon: 'doctor', text: 'Submit professional credentials for admin verification before receiving bookings.' },
  { value: 'hospital', label: 'Hospital / Clinic', icon: 'hospital', text: 'Register a licensed facility and invite role-scoped staff after verification.' },
  { value: 'pharmacy', label: 'Pharmacy', icon: 'pill', text: 'Register a licensed pharmacy organization and operate medicines services.' },
  { value: 'lab', label: 'Laboratory', icon: 'flask', text: 'Register a licensed diagnostic laboratory and manage tests and results.' },
  { value: 'insurance', label: 'Health Insurance', icon: 'insurance', text: 'Register an insurer to manage policies, eligibility and claims.' },
]
const orgRoles = new Set(['hospital','pharmacy','lab','insurance'])
const initial = { email:'', password:'', first_name:'', last_name:'', phone:'', role:'patient', location:'', address:'', year_of_completion:'', university:'', cadre:'medical_officer', specialization:'', license_number:'', license_issuer:'', license_expires_on:'', license_document:null, workplace:'', consultation_fee:'', organization_type:'hospital', organization_name:'', district:'', services_description:'' }

function errorText(err) {
  const data = err.response?.data
  if (!data) return 'Registration failed. Review your details and try again.'
  if (data.detail) return data.detail
  return Object.entries(data).map(([field, messages]) => `${field.replaceAll('_',' ')}: ${Array.isArray(messages) ? messages.join(' ') : messages}`).join(' · ')
}

export default function Register({ pharmacyOnly = false, pharmacyBuyer = false, accountRole }) {
  const { register } = useAuth()
  const navigate = useNavigate()
  const fixedRole = pharmacyOnly ? 'pharmacy' : accountRole
  const [form, setForm] = useState(() => ({
    ...initial, role: fixedRole || initial.role, organization_type: pharmacyOnly ? 'pharmacy' : initial.organization_type,
  }))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const selectedRole = useMemo(() => ROLES.find((role) => role.value === form.role), [form.role])
  const isDoctor = form.role === 'doctor'
  const isOrganization = orgRoles.has(form.role)
  const set = (key) => (event) => setForm({ ...form, [key]: event.target.value })

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const payload = new FormData()
      Object.entries(form).forEach(([key, value]) => {
        if (value !== '' && value !== null && value !== undefined) payload.append(key, value)
      })
      const user = await register(payload)
      navigate(pharmacyBuyer ? '/shop' : pharmacyOnly ? '/pharmacy/profile' : ROLE_HOME[user.role] || '/patient')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="healthos-auth-shell register-mode">
      <section className="healthos-auth-story">
        <Link to="/" className="healthos-auth-brand"><span><HealthIcon name="heart" size={19}/></span><div><strong>MyDoctor</strong><small>{(pharmacyOnly || pharmacyBuyer) ? 'Pharmacy' : accountRole ? 'Facility' : 'Connected Healthcare OS'}</small></div></Link>
        <div className="healthos-auth-copy">
          <span className="healthos-auth-kicker">JOIN THE HEALTH NETWORK</span>
          <h1>{pharmacyBuyer ? 'Create a buyer account.' : pharmacyOnly ? 'Register your pharmacy.' : accountRole === 'hospital' ? 'Register your facility.' : accountRole === 'patient' ? 'Create your patient account.' : 'One registration flow.'}{!accountRole && <><br/><em>{pharmacyOnly ? 'Prepare your workspace.' : 'The correct workspace for every role.'}</em></>}</h1>
          <p>{pharmacyBuyer ? 'Find medicines, order for pickup or delivery, and track your orders.' : pharmacyOnly ? 'Submit your pharmacy licence for verification. Invited staff use the link sent by their organization.' : accountRole === 'hospital' ? 'Submit the licence for your clinic or hospital. After verification, use Staff & Access to invite your team.' : accountRole === 'patient' ? 'Use a patient account to book appointments and manage your care.' : 'Patients become active immediately. Doctors and healthcare organizations enter a protected pending-verification state until an administrator validates their licence.'}</p>
          <div className="healthos-selected-role"><span><HealthIcon name={selectedRole?.icon || 'heart'} size={22}/></span><div><small>Selected workspace</small><strong>{pharmacyBuyer ? 'Buyer' : selectedRole?.label}</strong>{!pharmacyBuyer && <p>{selectedRole?.text}</p>}</div></div>
        </div>
        <div className="healthos-auth-trust"><span><HealthIcon name="shield" size={15}/> Private licence documents</span><span><HealthIcon name="lock" size={15}/> Role-scoped access</span></div>
      </section>

      <section className="healthos-auth-form-area register-form-area">
        <div className="healthos-auth-form-card register-card">
          <div className="healthos-auth-form-head"><span className="healthos-auth-form-icon"><HealthIcon name="user" size={20}/></span><div><small>CREATE ACCOUNT</small><h2>{pharmacyBuyer ? 'Buyer details' : pharmacyOnly ? 'Register your pharmacy' : accountRole === 'hospital' ? 'Facility registration' : accountRole === 'patient' ? 'Patient details' : 'Register your role'}</h2><p>{pharmacyBuyer ? 'Use contact details the pharmacy can reach for your order.' : pharmacyOnly ? 'Use the details on your registered pharmacy licence.' : accountRole === 'hospital' ? 'Use the details on your facility licence.' : accountRole === 'patient' ? 'If you’re joining a staff team, use the invitation sent by your facility.' : 'Facility staff such as nurses, receptionists and cashiers join through a secure organization invitation.'}</p></div></div>
          {!fixedRole && <div className="healthos-role-picker" role="radiogroup" aria-label="Choose account role">
            {ROLES.map((role) => <button key={role.value} type="button" className={form.role === role.value ? 'is-selected' : ''} onClick={() => setForm({ ...initial, role: role.value, email: form.email, password: form.password, first_name: form.first_name, last_name: form.last_name, phone: form.phone })} role="radio" aria-checked={form.role === role.value}><HealthIcon name={role.icon} size={18}/><span>{role.label}</span>{form.role === role.value && <HealthIcon name="check" size={15}/>}</button>)}
          </div>}
          <form onSubmit={submit} className="space-y-4" encType="multipart/form-data">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2"><Input label={isOrganization ? 'Contact first name' : 'First name'} required value={form.first_name} onChange={set('first_name')}/><Input label={isOrganization ? 'Contact last name' : 'Last name'} required value={form.last_name} onChange={set('last_name')}/></div>
            <Input label="Email address" type="email" required value={form.email} onChange={set('email')} placeholder="name@example.com"/>
            <Input label="Phone / contact number" required value={form.phone} onChange={set('phone')} placeholder="+256…"/>
            <Input label="Password" type="password" required minLength={10} value={form.password} onChange={set('password')} hint="Use at least 10 characters and avoid common or entirely numeric passwords."/>

            {form.role === 'patient' && <div className="space-y-4 rounded-2xl border border-primary-100 bg-primary-50/40 p-4"><div><strong className="text-sm text-slate-800">{pharmacyBuyer ? 'Location' : 'Patient location'}</strong>{!pharmacyBuyer && <p className="text-xs text-slate-500">Only the minimum details are required at registration. Medical history can be completed later.</p>}</div><Input label="Location / district" required={pharmacyBuyer && !form.address.trim()} value={form.location} onChange={set('location')} placeholder="Kampala, Wakiso…"/><Textarea label="Address" value={form.address} onChange={set('address')}/></div>}

            {isDoctor && <div className="space-y-4 rounded-2xl border border-violet-100 bg-violet-50/30 p-4">
              <div><strong className="text-sm text-slate-800">Professional qualification and practising licence</strong><p className="text-xs text-slate-500">All fields marked by the browser as required are needed for administrator verification.</p></div>
              <div className="grid gap-3 sm:grid-cols-2"><Input required label="Year of completion" type="number" min="1950" max="2100" value={form.year_of_completion} onChange={set('year_of_completion')}/><Input required label="University of completion" value={form.university} onChange={set('university')}/></div>
              <Select required label="Cadre" value={form.cadre} onChange={set('cadre')}><option value="medical_officer">Medical Officer</option><option value="specialist">Specialist Doctor</option><option value="consultant">Consultant</option><option value="clinical_officer">Clinical Officer</option><option value="dentist">Dentist</option><option value="other">Other regulated clinician</option></Select>
              <Input label="Speciality of practice (optional)" value={form.specialization} onChange={set('specialization')}/>
              <Input required label="Current hospital, clinic or pharmacy" value={form.workplace} onChange={set('workplace')}/>
              <div className="grid gap-3 sm:grid-cols-2"><Input required label="Practising licence number" value={form.license_number} onChange={set('license_number')}/><Input label="Issuing authority" value={form.license_issuer} onChange={set('license_issuer')}/></div>
              <div className="grid gap-3 sm:grid-cols-2"><Input label="Licence expiry date" type="date" value={form.license_expires_on} onChange={set('license_expires_on')}/><Input required label="Consultation fee (UGX)" type="number" min="0" value={form.consultation_fee} onChange={set('consultation_fee')}/></div>
              <Input required label="Practising licence photo or PDF" type="file" accept="image/jpeg,image/png,image/webp,.pdf" onChange={(e) => setForm({ ...form, license_document: e.target.files?.[0] || null })} hint="Private file; visible only to the owner and authorized verification administrators."/>
            </div>}

            {isOrganization && <div className="space-y-4 rounded-2xl border border-emerald-100 bg-emerald-50/30 p-4">
              <div><strong className="text-sm text-slate-800">Licensed organization details</strong><p className="text-xs text-slate-500">The organization remains hidden from public listings until approved.</p></div>
              {form.role === 'hospital' && <Select required label="Facility type" value={form.organization_type} onChange={set('organization_type')}><option value="hospital">Hospital</option><option value="clinic">Clinic</option></Select>}
              <Input required label="Registered organization name" value={form.organization_name} onChange={set('organization_name')}/>
              <div className="grid gap-3 sm:grid-cols-2"><Input required label="Registered licence number" value={form.license_number} onChange={set('license_number')}/><Input required label="District / location" value={form.district} onChange={set('district')}/></div>
              <Textarea required label="Physical address" value={form.address} onChange={set('address')}/>
              <Textarea required label="Description of services offered" value={form.services_description} onChange={set('services_description')}/>
              <Input required label="Registered licence photo or PDF" type="file" accept="image/jpeg,image/png,image/webp,.pdf" onChange={(e) => setForm({ ...form, license_document: e.target.files?.[0] || null })} hint="Stored privately for verification and future AI-assisted pre-screening."/>
            </div>}

            {error && <Alert tone="danger">{error}</Alert>}
            {(isDoctor || isOrganization) && <Alert tone="warning" title="Verification required">After registration you can complete your profile, but public listing, availability publishing and booking acceptance remain blocked until approval.</Alert>}
            <label className="healthos-consent-check"><input type="checkbox" required/><span>I agree to the terms, privacy notice and applicable health-data processing required to provide the service.</span></label>
            <Button type="submit" className="w-full" disabled={busy}>{busy ? 'Creating account…' : pharmacyBuyer ? 'Create buyer account' : `Create ${selectedRole?.label || ''} account`}<HealthIcon name="arrow" size={17}/></Button>
          </form>
          <p className="healthos-auth-switch">Already registered? <Link to="/login">Sign in</Link></p>
        </div>
      </section>
    </main>
  )
}
