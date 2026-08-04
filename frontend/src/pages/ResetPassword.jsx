import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { authApi } from '../api/endpoints'
import { Alert, Button, Input } from '../components/ui'
export default function ResetPassword(){
 const {tokenId,token}=useParams(); const [form,setForm]=useState({password:'',confirm:''}); const [busy,setBusy]=useState(false); const [message,setMessage]=useState(''); const [error,setError]=useState('')
 const submit=async(e)=>{e.preventDefault();if(form.password!==form.confirm){setError('Passwords do not match.');return}setBusy(true);setError('');try{const {data}=await authApi.resetPassword(tokenId,token,form.password);setMessage(data.detail)}catch(err){const d=err.response?.data;setError(d?.detail||d?.password?.join(' ')||'The reset link is invalid or expired.')}finally{setBusy(false)}}
 return <main className="min-h-screen bg-slate-50 px-4 py-16"><section className="mx-auto max-w-md rounded-3xl border border-slate-200 bg-white p-7 shadow-xl"><h1 className="text-3xl font-bold text-slate-900">Choose a new password</h1><p className="mt-2 text-sm text-slate-500">Use at least 10 characters and avoid common passwords.</p><form className="mt-6 space-y-4" onSubmit={submit}><Input label="New password" type="password" required minLength={10} value={form.password} onChange={e=>setForm({...form,password:e.target.value})}/><Input label="Confirm password" type="password" required value={form.confirm} onChange={e=>setForm({...form,confirm:e.target.value})}/>{message&&<Alert tone="success">{message} <Link className="font-bold underline" to="/login">Sign in</Link></Alert>}{error&&<Alert tone="danger">{error}</Alert>}<Button className="w-full" disabled={busy}>{busy?'Updating…':'Update password'}</Button></form></section></main>
}
