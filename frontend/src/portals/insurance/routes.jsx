import Benefits from './Benefits'
import Dashboard from './Dashboard'
import Policies from './Policies'
import Claims from './Claims'
import { ProviderProfile } from '../pharmacy/shared'

export const nav = [{ to: '/insurance/benefits', label: 'Benefits & Authorizations', icon: 'clipboard', group: 'Coverage', description: 'Review and manage operational workflows' },
  { to: '/insurance', label: 'Coverage Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Coverage, claims and settlement performance' },
  { to: '/insurance/policies', label: 'Policies & Coverage', icon: 'shield', group: 'Coverage', description: 'Plans, members, benefits and eligibility' },
  { to: '/insurance/claims', label: 'Claims & Approvals', icon: 'file', group: 'Claims', description: 'Authorisations, adjudication and decisions' },
  { to: '/insurance/profile', label: 'Insurer Profile', icon: 'settings', group: 'Settings', description: 'Organisation and network configuration' },
]

export const routes = [{ path: 'benefits', element: <Benefits /> },
  { index: true, element: <Dashboard /> },
  { path: 'policies', element: <Policies /> },
  { path: 'claims', element: <Claims /> },
  { path: 'profile', element: <ProviderProfile /> },
]
