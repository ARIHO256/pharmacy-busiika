import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from '../../src/auth/AuthContext'
import { Button, Card, Spinner } from '../../src/components/ui'
import PortalLayout from '../../src/layouts/PortalLayout'
import AcceptInvitation from '../../src/pages/AcceptInvitation'
import Login from '../../src/pages/Login'
import NotificationPreferences from '../../src/pages/NotificationPreferences'
import Register from '../../src/pages/Register'
import * as pharmacy from '../../src/portals/pharmacy/routes'
import * as pharmacist from '../../src/portals/pharmacist/routes'

const staffRoles = ['pharmacist', 'storekeeper', 'cashier']
const pharmacyRoles = ['pharmacy', ...staffRoles]
const salesPages = new Set(['counter', 'orders', 'shifts'])
const stockPages = new Set(['inventory', 'procurement', 'stocktake', 'stock-control', 'suppliers', 'medicine-register'])
const pharmacyLogin = {
  kicker: 'Pharmacy owners and staff',
  headline: ['Manage your pharmacy.', 'From stock to receipt.'],
  description: 'Sign in to your pharmacy to review prescriptions, manage batch stock, and handle medicine orders.',
  features: [
    ['prescription', 'Prescriptions', 'Review and dispense from traceable batches'],
    ['box', 'Stock', 'Manage purchasing, expiry dates, and stock counts'],
    ['money', 'Orders and receipts', 'Record payments received and print receipts'],
  ],
}

function pharmacyHome(user) {
  if (user.role === 'cashier') return '/pharmacist/counter'
  if (user.role === 'storekeeper') return '/pharmacist/inventory'
  if (user.role === 'pharmacist') return '/pharmacist/rx-orders'
  return user.is_verified ? '/pharmacy' : '/pharmacy/profile'
}

function AccountNotice({ verification = false }) {
  const { logout, user } = useAuth()
  const platform = import.meta.env.VITE_PLATFORM_URL
  return <main className="min-h-screen bg-slate-50 px-4 py-16">
    <div className="mx-auto max-w-lg">
      <Card title={verification ? 'Pharmacist verification' : 'This account uses a different workspace'}>
        <p className="text-sm text-slate-600">{verification
          ? 'A verified pharmacist account is required to access dispensing and stock workflows. Contact the person who invited you for help with your verification.'
          : `${user.email} is signed in. MyDoctor Pharmacy is for pharmacy owners and invited pharmacy staff.`}</p>
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Button onClick={logout}>Sign out</Button>
          {!verification && platform && <a className="text-sm font-semibold text-primary-700" href={platform}>Open MyDoctor HealthOS</a>}
        </div>
      </Card>
    </div>
  </main>
}

function PharmacyAccess({ allowed = pharmacyRoles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) return <Spinner label="Loading pharmacy workspace…" />
  if (!user) return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  if (!pharmacyRoles.includes(user.role)) return <AccountNotice />
  if (user.role === 'pharmacist' && !user.is_verified) return <AccountNotice verification />
  if (!allowed.includes(user.role)) return <Navigate to={pharmacyHome(user)} replace />
  return children
}

function WorkspaceHome() {
  const { user } = useAuth()
  return <Navigate to={pharmacyHome(user)} replace />
}

function PharmacyLogin() {
  const { user, loading } = useAuth()
  const { state } = useLocation()
  if (loading) return <Spinner />
  if (user) return <Navigate to="/dashboard" replace />
  return <Login product={pharmacyLogin} destination={(account) => {
    const prefix = account.role === 'pharmacy' ? '/pharmacy' : '/pharmacist'
    const from = state?.from
    return pharmacyRoles.includes(account.role) && typeof from === 'string' && from.startsWith(prefix + '/')
      ? from
      : '/dashboard'
  }} />
}

function orderedNavigation(nav) {
  const priority = ['end', 'counter', 'rx-orders', 'orders', 'shifts', 'inventory', 'stock-control', 'stocktake', 'transfers',
    'procurement', 'suppliers', 'safety', 'medicine-register', 'staff', 'taxonomy', 'profile']
  return nav.map((item) => {
    const page = item.end ? 'end' : item.to.split('/').at(-1)
    const group = {
      'rx-orders': 'Dispensing', orders: 'Sales', procurement: 'Purchasing', suppliers: 'Purchasing',
      safety: 'Safety', 'medicine-register': 'Inventory',
    }[page] || item.group
    return { ...item, group, label: page === 'orders' ? 'Orders & Receipts' : item.label, index: priority.indexOf(page) }
  }).sort((first, second) => first.index - second.index)
}

const ownerNav = orderedNavigation(pharmacy.nav)
const staffNav = orderedNavigation(pharmacist.nav)

function PharmacyShell({ staff }) {
  const { user } = useAuth()
  const location = useLocation()
  const stockOnly = user.role === 'storekeeper'
  const salesOnly = user.role === 'cashier'
  const page = location.pathname.split('/')[2]
  if (!staff && !user.is_verified && page !== 'profile') return <Navigate to="/pharmacy/profile" replace />
  if (salesOnly && !salesPages.has(page)) return <Navigate to='/pharmacist/counter' replace />
  if (stockOnly && !stockPages.has(page)) return <Navigate to="/pharmacist/inventory" replace />
  let nav = staff ? staffNav : ownerNav
  if (salesOnly) nav = nav.filter((item) => salesPages.has(item.to.split('/').at(-1)))
  if (stockOnly) nav = nav.filter((item) => stockPages.has(item.to.split('/').at(-1)))
  if (!staff && !user.is_verified) nav = nav.filter((item) => item.to === '/pharmacy/profile')
  return <PortalLayout nav={nav} role={staff ? 'pharmacist' : 'pharmacy'}
    title="MyDoctor Pharmacy" productLabel="Pharmacy" home={pharmacyHome(user)} />
}

function workspace(path, allowed, module) {
  return <Route path={path} element={<PharmacyAccess allowed={allowed}><PharmacyShell staff={path === 'pharmacist'} /></PharmacyAccess>}>
    {module.routes.map((route) => <Route key={route.path || 'index'} {...route} />)}
    <Route path="*" element={<WorkspaceHome />} />
  </Route>
}

export default function PharmacyApp() {
  return <Routes>
    <Route path="/" element={<PharmacyAccess><WorkspaceHome /></PharmacyAccess>} />
    <Route path="/dashboard" element={<PharmacyAccess><WorkspaceHome /></PharmacyAccess>} />
    <Route path="/login" element={<PharmacyLogin />} />
    <Route path="/register" element={<Register pharmacyOnly />} />
    <Route path="/accept-invitation/:token" element={<AcceptInvitation allowedRoles={pharmacyRoles} />} />
    <Route path="/notification-settings" element={<PharmacyAccess><NotificationPreferences /></PharmacyAccess>} />
    {workspace('pharmacy', ['pharmacy'], pharmacy)}
    {workspace('pharmacist', staffRoles, pharmacist)}
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes>
}
