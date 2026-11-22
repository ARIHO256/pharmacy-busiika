import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth, ROLE_HOME } from '../auth/AuthContext'
import { Button, Input } from '../components/ui'
import HealthIcon from '../components/icons/HealthIcon'

const promises = [
  ['calendar', 'Appointments', 'Book and manage care from one timeline'],
  ['video', 'Telemedicine', 'Secure chat, audio and video consultations'],
  ['heart', 'Health record', 'Your longitudinal record, consent and history'],
]

export default function Login({ product, destination = (user) => ROLE_HOME[user.role] || "/patient" }) {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const user = await login(form.email, form.password)
      navigate(destination(user), { replace: Boolean(product) })
    } catch {
      setError('Invalid email or password')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="healthos-auth-shell">
      <section className="healthos-auth-story">
        <Link to="/" className="healthos-auth-brand"><span><HealthIcon name="heart" size={19}/></span><div><strong>MyDoctor</strong><small>{product ? 'Pharmacy' : 'Connected Healthcare OS'}</small></div></Link>
        <div className="healthos-auth-copy">
          <span className="healthos-auth-kicker">{product?.kicker || 'Patients · Doctors · Connected care'}</span>
          <h1>{product?.headline[0] || 'Every care journey.'}<br/><em>{product?.headline[1] || 'One secure workspace.'}</em></h1>
          <p>{product?.description || 'Sign in to appointments, consultations, prescriptions, diagnostics, payments and your complete health record.'}</p>
          <div className="healthos-auth-promises">
            {(product?.features || promises).map(([icon, title, text]) => (
              <article key={title}><span><HealthIcon name={icon} size={18}/></span><div><strong>{title}</strong><small>{text}</small></div></article>
            ))}
          </div>
        </div>
        <div className="healthos-auth-trust"><span><i/> Platform operational</span><span><HealthIcon name="shield" size={15}/> Privacy by design</span></div>
      </section>

      <section className="healthos-auth-form-area">
        <div className="healthos-auth-form-card">
          <div className="healthos-auth-form-head">
            <span className="healthos-auth-form-icon"><HealthIcon name="lock" size={20}/></span>
            <div><small>SECURE ACCESS</small><h2>Welcome back</h2><p>Enter your credentials to open your role-based workspace.</p></div>
          </div>
          <form onSubmit={submit} className="space-y-4">
            <Input label="Email address" type="email" autoComplete="email" required value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="name@example.com" />
            <Input label="Password" type="password" autoComplete="current-password" required value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="Enter your password" />
            {!product && <div className="healthos-auth-options"><label><input type="checkbox"/> Keep me signed in</label><button type="button">Forgot password?</button></div>}
            {error && <div className="healthos-auth-error"><HealthIcon name="alert" size={17}/>{error}</div>}
            <Button type="submit" className="w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in securely'}<HealthIcon name="arrow" size={17}/></Button>
          </form>
          <div className="healthos-auth-divider"><span>{product ? 'New pharmacy owner?' : 'New to MyDoctor?'}</span></div>
          <Link to="/register" className="healthos-auth-secondary">{product ? 'Register your pharmacy' : 'Create an account'} <HealthIcon name="arrow" size={16}/></Link>
          <p className="healthos-auth-legal">By continuing, you agree to the platform terms, privacy notice and appropriate healthcare-data use.</p>
        </div>
      </section>
    </main>
  )
}
