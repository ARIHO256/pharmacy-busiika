import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import HealthIcon from '../components/icons/HealthIcon'

export default function FacilityHomePage() {
  const { user, loading } = useAuth()
  return <main className="min-h-screen bg-slate-50 px-5 py-10 text-slate-900">
    <div className="mx-auto max-w-xl">
      <header className="mb-8 flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-lg bg-primary-800 text-white">
          <HealthIcon name="hospital" size={20} />
        </span>
        <span className="font-semibold">MyDoctor Facility</span>
      </header>
      <section className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 sm:p-8">
        <h1 className="text-2xl font-semibold tracking-tight">Clinic and hospital care</h1>
        <p className="text-sm text-slate-600">Book appointments and manage your care with a patient account. Staff can sign in to their facility workspace.</p>
        {!loading && (user ? <Link className="inline-block rounded-md bg-primary-700 px-4 py-2 font-semibold text-white" to="/dashboard">
          Go to your workspace
        </Link> : <div className="flex flex-wrap items-center gap-4">
          <Link className="rounded-md bg-primary-700 px-4 py-2 font-semibold text-white" to="/register">Create a patient account</Link>
          <Link className="font-semibold text-primary-700 underline" to="/login">Sign in</Link>
        </div>)}
      </section>
      <p className="mt-5 text-sm"><Link className="font-semibold text-primary-700 underline" to="/onboard-facility">
        Register a clinic or hospital
      </Link></p>
    </div>
  </main>
}
