import { Link, Navigate, useLocation } from 'react-router-dom'
import { operationsApi, workforceApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Spinner } from '../../components/ui'
import PortalLayout from '../../layouts/PortalLayout'
import { useRemote } from '../staff/shared'
import { facilityNavigation } from './routes'

export default function FacilityWorkspace() {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const isOwner = user.role === 'hospital'
  const workspace = useRemote(() => workforceApi.summary(), [user.id])
  const atProfile = pathname.replace(/\/+$/, '') === '/facility/profile'

  if (workspace.loading) return <Spinner label="Loading facility…" />
  const organization = workspace.data?.organization
  const verified = organization?.status === 'verified'
  if (isOwner && !verified) {
    if (!atProfile) return <Navigate to="/facility/profile" replace />
    return <PortalLayout nav={facilityNavigation(null, user.role)} title="Facility profile" role="hospital" home="/facility/profile" />
  }
  if (workspace.error || !verified || !['clinic', 'hospital'].includes(organization.type)) {
    return <div className="mx-auto max-w-lg space-y-4 p-6">
      <Alert tone="warning">This account needs an active assignment at a verified clinic or hospital.</Alert>
      <Link className="text-primary-700 underline" to="/">Return to MyDoctor Facility</Link>
    </div>
  }

  const nav = facilityNavigation(organization.type, user.role, organization.has_pharmacy)
  const current = pathname.replace(/\/+$/, '').toLowerCase()
  if (!nav.some((item) => item.to === current)) return <Navigate to="/facility" replace />
  return <PortalLayout title="MyDoctor Facility" nav={nav} role={user.role} home="/facility"
    workspaceName={organization.name} outletContext={workspace.data} />
}

export function LegacyHospitalPath() {
  const location = useLocation()
  return <Navigate replace to={{
    pathname: location.pathname.replace(/^\/hospital(?=\/|$)/i, '/facility'),
    search: location.search,
    hash: location.hash,
  }} />
}


const wardPaths = new Set(['/nurse/ward-board', '/nurse/scheduled-doses'])

export function NursingWorkspace({ nav, title }) {
  const { user } = useAuth()
  const { pathname } = useLocation()
  const workspace = useRemote(() => operationsApi.context(), [user.id])
  if (workspace.loading) return <Spinner label="Loading nursing workspace…" />
  const hasHospital = workspace.data?.organizations.some((organization) => organization.type === 'hospital')
  const available = hasHospital ? nav : nav.filter((item) => !wardPaths.has(item.to))
  if (!hasHospital && wardPaths.has(pathname.toLowerCase().replace(/\/+$/, ''))) return <Navigate to="/nurse" replace />
  return <PortalLayout nav={available} title={title} role="nurse" outletContext={{ hasHospital }} />
}
