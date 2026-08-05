import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { Alert, Button, Input } from '../components/ui'
import HealthIcon from '../components/icons/HealthIcon'

export default function ForgotPassword(){
  const [email,setEmail]=useState(''); const [busy,setBusy]=useState(false); const [message,setMessage]=useState(''); const [error,setError]=useState('')
  const submit=async(e)=>{e.preventDefault();setBusy(true);setError('');try{const {data}=await authApi.forgotPassword(email);setMessage(data.detail)}catch(err){setError(err.response?.data?.detail||'Could not start password recovery.')}finally{setBusy(false)}}
  return <main className="min-h-screen bg-slate-50 px-4 py-16"><section className="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-7 shadow-xl"><Link to="/" className="mb-7 flex items-center gap-2 font-bold text-primary-700"><span className="grid h-9 w-9 place-items-center rounded-xl bg-primary-50"><HealthIcon name="heart" size={18}/></span>HealthPilot</Link><span className="text-xs font-bold uppercase tracking-[.18em] text-primary-600">Account recovery</span><h1 className="mt-2 text-3xl font-bold text-slate-900">Reset your password</h1><p className="mt-2 text-sm leading-6 text-slate-500">Enter your registered email. We will send a private, time-limited recovery link.</p><form className="mt-6 space-y-4" onSubmit={submit}><Input label="Email address" type="email" required value={email} onChange={e=>setEmail(e.target.value)}/>{message&&<Alert tone="success">{message}</Alert>}{error&&<Alert tone="danger">{error}</Alert>}<Button className="w-full" disabled={busy}>{busy?'Sending…':'Send reset link'}</Button></form><Link to="/login" className="mt-5 flex items-center justify-center text-sm font-semibold text-primary-700">Return to sign in</Link></section></main>
}
