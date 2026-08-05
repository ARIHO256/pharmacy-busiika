import { Link } from 'react-router-dom'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import HealthIcon from '../components/icons/HealthIcon'
import ReleaseAcceptanceCentre from '../portals/admin/ReleaseAcceptanceCentre'

export default function ReleaseAcceptancePage() {
  const { user, activeRole } = useAuth()
  const role = activeRole || user?.role
  return <div className="min-h-screen bg-slate-50">
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-4 py-4 sm:px-8">
        <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-2xl bg-primary-700 text-white"><HealthIcon name="verified" size={22}/></span><div><strong className="block text-slate-950">HealthPilot Release Governance</strong><small className="text-slate-500">Qualified, evidence-backed production acceptance</small></div></div>
        <Link to={ROLE_HOME[role] || '/dashboard'} className="inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><HealthIcon name="chevron" size={15}/> Return to workspace</Link>
      </div>
    </header>
    <main className="mx-auto max-w-[1500px] px-4 py-8 sm:px-8"><ReleaseAcceptanceCentre /></main>
  </div>
}
