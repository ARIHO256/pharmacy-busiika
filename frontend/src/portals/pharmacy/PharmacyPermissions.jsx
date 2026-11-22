import { createContext, useContext } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { servicesApi, workforceApi } from '../../api/endpoints'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Button, Spinner } from '../../components/ui'
import PortalLayout from '../../layouts/PortalLayout'
import { useRemote } from '../staff/shared'

const Policy = createContext(null)

export function usePharmacyPermissions() {
  const enabled = useContext(Policy)
  return (permission) => !permission || enabled === null || enabled.has(permission)
}

const navKey = (item) => item.permissionKey || (item.end ? 'overview' : item.to.split('/').at(-1))

export function PharmacyStaffLayout({ nav, home, ...layout }) {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const remote = useRemote(() => user?.role === 'admin' ? Promise.resolve({ data: null }) : servicesApi.pharmacyRolePermissions(), [user?.id])
  const facility = useRemote(() => user?.role === 'pharmacist' && nav.some((item) => navKey(item) === 'handoffs')
    ? workforceApi.handoffs() : Promise.resolve({ data: null }), [user?.id, nav.some((item) => navKey(item) === 'handoffs')])
  if (user?.role === 'admin') return <PortalLayout {...layout} nav={nav} />
  if (remote.loading || facility.loading) return <Spinner label="Loading pharmacy permissions…" />
  const handoffPage = Array.isArray(facility.data) && nav.find((item) => navKey(item) === 'handoffs')
  if (remote.error && handoffPage) return <PortalLayout {...layout} nav={[handoffPage]} home={handoffPage.to} />
  if (remote.error) return <div className="mx-auto max-w-lg space-y-4 p-6">
    <Alert tone="danger">{remote.error}</Alert>
    <Button onClick={logout}>Sign out</Button>
  </div>

  const granted = new Set(remote.data.enabled)
  if (handoffPage) granted.add('handoffs')
  const pages = nav.filter((item) => granted.has(navKey(item)) && (!item.roles || item.roles.includes(user.role)))
  if (!pages.length) return <div className="mx-auto max-w-lg space-y-4 p-6">
    <Alert>Your pharmacy owner hasn’t enabled any pages for this role.</Alert>
    <Button onClick={logout}>Sign out</Button>
  </div>
  const start = pages.find((item) => item.to === home)?.to || pages[0].to
  const current = pathname.replace(/\/+$/, '').toLowerCase()
  if (!pages.some((item) => item.to === current)) return <Navigate to={start} replace />

  return <Policy.Provider value={granted}>
    <PortalLayout {...layout} nav={pages} home={start} />
  </Policy.Provider>
}
