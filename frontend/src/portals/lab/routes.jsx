import Dashboard from './Dashboard'
import Tests from './Tests'
import Orders from './Orders'
import { ProviderProfile } from '../pharmacy/shared'

export const nav = [
  { to: '/lab', label: 'Diagnostics Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Work queue, turnaround and critical alerts' },
  { to: '/lab/orders', label: 'Laboratory Orders', icon: 'clipboard', group: 'Diagnostics', description: 'Orders, samples, processing and results' },
  { to: '/lab/tests', label: 'Test Catalogue', icon: 'flask', group: 'Diagnostics', description: 'Tests, prices, ranges and preparation' },
  { to: '/lab/profile', label: 'Laboratory Profile', icon: 'settings', group: 'Settings', description: 'Branches, accreditation and services' },
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'tests', element: <Tests /> },
  { path: 'orders', element: <Orders /> },
  { path: 'profile', element: <ProviderProfile /> },
]
