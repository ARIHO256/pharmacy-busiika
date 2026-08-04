import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Policies from './Policies'
import Benefits from './Benefits'
import Eligibility from './Eligibility'
import Preauthorizations from './Preauthorizations'
import Claims from './Claims'
import Remittances from './Remittances'
import { ProviderProfile } from '../pharmacy/shared'
import Staff from '../facility/Staff'
import Departments from '../facility/Departments'
import AccessControl from '../operations/AccessControl'
import WorkforceSchedule from '../operations/WorkforceSchedule'
import Subscriptions from '../operations/Subscriptions'
import SupportCentre from '../operations/SupportCentre'
import NotificationConsole from '../operations/NotificationConsole'

export const nav = [
  { to: '/insurance', label: 'Coverage Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Coverage, claims and settlement performance' },
  { to: '/insurance/policies', label: 'Policies & Coverage', icon: 'shield', group: 'Coverage', description: 'Plans, members, benefits and eligibility' },
  { to: '/insurance/benefits', label: 'Benefit Rules', icon: 'settings', group: 'Coverage', description: 'Service limits, copays, exclusions and authorization rules' },
  { to: '/insurance/eligibility', label: 'Eligibility Checks', icon: 'activity', group: 'Coverage', description: 'Validate membership and estimate patient responsibility' },
  { to: '/insurance/preauthorizations', label: 'Preauthorizations', icon: 'clipboard', group: 'Claims', description: 'Medical necessity review before treatment' },
  { to: '/insurance/claims', label: 'Claims & Approvals', icon: 'file', group: 'Claims', description: 'Authorisations, adjudication and decisions' },
  { to: '/insurance/remittances', label: 'Remittances', icon: 'money', group: 'Claims', description: 'Claim settlement and reconciliation register' },
  { to: '/insurance/staff', label: 'Staff Directory', icon: 'users', group: 'Workforce', description: 'Invite, verify and manage staff' },
  { to: '/insurance/departments', label: 'Departments', icon: 'building', group: 'Workforce', description: 'Units, teams and service ownership' },
  { to: '/insurance/schedule', label: 'Duty Roster & Leave', icon: 'calendar', group: 'Workforce', description: 'Shift coverage and leave requests' },
  { to: '/insurance/access', label: 'Roles & Permissions', icon: 'shield', group: 'Workforce', description: 'Granular staff access control' },
  { to: '/insurance/notifications', label: 'Notifications', icon: 'bell', group: 'Settings', description: 'Templates, announcements and broadcasts' },
  { to: '/insurance/subscription', label: 'Subscription', icon: 'wallet', group: 'Settings', description: 'Plan, renewal and feature limits' },
  { to: '/insurance/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Platform support and issue tracking' },
  { to: '/insurance/profile', label: 'Insurer Profile', icon: 'settings', group: 'Settings', description: 'Organisation and network configuration' },

  ...deepNav('insurance', 'insurance', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'policies', element: <Policies /> },
  { path: 'benefits', element: <Benefits /> },
  { path: 'eligibility', element: <Eligibility /> },
  { path: 'preauthorizations', element: <Preauthorizations /> },
  { path: 'claims', element: <Claims /> },
  { path: 'remittances', element: <Remittances /> },
  { path: 'staff', element: <Staff /> },
  { path: 'departments', element: <Departments /> },
  { path: 'schedule', element: <WorkforceSchedule /> },
  { path: 'access', element: <AccessControl /> },
  { path: 'notifications', element: <NotificationConsole /> },
  { path: 'subscription', element: <Subscriptions /> },
  { path: 'support', element: <SupportCentre /> },
  { path: 'profile', element: <ProviderProfile /> },

  ...deepRoutes('insurance', 'insurance', { title: 'Insurance page centre' }),
]
