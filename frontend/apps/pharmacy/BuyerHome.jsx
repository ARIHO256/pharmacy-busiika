import { Link } from 'react-router-dom'
import { useAuth } from '../../src/auth/AuthContext'
import { Button } from '../../src/components/ui'
import HealthIcon from '../../src/components/icons/HealthIcon'

export default function BuyerHome({ shop = false, children }) {
  const { user, logout } = useAuth()
  return <main className="min-h-screen bg-slate-50 text-slate-900">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-4">
        <Link to="/" className="flex items-center gap-2 font-semibold"><HealthIcon name="pill" size={20} />MyDoctor Pharmacy</Link>
        <nav className="flex items-center gap-4 text-sm font-semibold">
          {user ? <>
            <Link to="/dashboard">{user.role === 'patient' ? 'Shop' : 'Staff workspace'}</Link>
            <Button variant="outline" onClick={logout}>Sign out</Button>
          </> : <Link to="/login">Sign in</Link>}
        </nav>
      </div>
    </header>
    <div className="mx-auto max-w-6xl px-5 py-8">
      {shop ? <><h1 className="mb-5 text-2xl font-semibold">Wholesale medicines</h1>{children}</> :
        <section className="max-w-xl py-12">
          <h1 className="text-4xl font-semibold tracking-tight">Buy medicines wholesale from verified pharmacies</h1>
          <p className="mt-4 text-slate-600">Shop over-the-counter medicines in bulk and arrange pickup or delivery with the pharmacy.</p>
          <div className="mt-6 flex flex-wrap gap-4">
            <Link to={user ? '/dashboard' : '/register'} className="rounded-lg bg-emerald-800 px-4 py-3 text-sm font-semibold text-white">
              {user ? 'Open workspace' : 'Create a buyer account'}
            </Link>
            {!user && <Link to="/onboard-pharmacy" className="self-center text-sm font-semibold text-emerald-900 underline">Register a pharmacy</Link>}
          </div>
        </section>}
    </div>
  </main>
}
