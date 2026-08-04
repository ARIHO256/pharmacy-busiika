import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Tests from './Tests'
import Orders from './Orders'
import Panels from './Panels'
import SpecimenTracking from './SpecimenTracking'
import { ProviderProfile } from '../pharmacy/shared'
import Staff from '../facility/Staff'
import Departments from '../facility/Departments'
import AccessControl from '../operations/AccessControl'
import InventoryControl from '../operations/InventoryControl'
import Procurement from '../operations/Procurement'
import WorkforceSchedule from '../operations/WorkforceSchedule'
import Subscriptions from '../operations/Subscriptions'
import SupportCentre from '../operations/SupportCentre'
import NotificationConsole from '../operations/NotificationConsole'

export const nav = [
  { to: '/lab', label: 'Diagnostics Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Work queue, turnaround and critical alerts' },
  { to: '/lab/orders', label: 'Laboratory Orders', icon: 'clipboard', group: 'Diagnostics', description: 'Orders, samples, processing and results' },
  { to: '/lab/specimens', label: 'Specimen Tracking', icon: 'activity', group: 'Diagnostics', description: 'Barcode custody, handover, rejection, storage and disposal' },
  { to: '/lab/panels', label: 'Test Panels', icon: 'flask', group: 'Diagnostics', description: 'Bundle tests into profiles and clinical panels' },
  { to: '/lab/tests', label: 'Test Catalogue', icon: 'flask', group: 'Diagnostics', description: 'Tests, prices, ranges and preparation' },
  { to: '/lab/staff', label: 'Staff Directory', icon: 'users', group: 'Workforce', description: 'Invite, verify and manage staff' },
  { to: '/lab/departments', label: 'Departments', icon: 'building', group: 'Workforce', description: 'Units, teams and service ownership' },
  { to: '/lab/schedule', label: 'Duty Roster & Leave', icon: 'calendar', group: 'Workforce', description: 'Shift coverage and leave requests' },
  { to: '/lab/access', label: 'Roles & Permissions', icon: 'shield', group: 'Workforce', description: 'Granular staff access control' },
  { to: '/lab/stock-control', label: 'Advanced Stock Control', icon: 'box', group: 'Operations', description: 'Batches, expiry and stock movement' },
  { to: '/lab/procurement', label: 'Procurement', icon: 'file', group: 'Operations', description: 'Purchase orders and receiving' },
  { to: '/lab/notifications', label: 'Notifications', icon: 'bell', group: 'Settings', description: 'Templates, announcements and broadcasts' },
  { to: '/lab/subscription', label: 'Subscription', icon: 'wallet', group: 'Settings', description: 'Plan, renewal and feature limits' },
  { to: '/lab/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Platform support and issue tracking' },
  { to: '/lab/profile', label: 'Laboratory Profile', icon: 'settings', group: 'Settings', description: 'Branches, accreditation and services' },

  ...deepNav('lab', 'lab', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'tests', element: <Tests /> },
  { path: 'orders', element: <Orders /> },
  { path: 'specimens', element: <SpecimenTracking /> },
  { path: 'panels', element: <Panels /> },
  { path: 'staff', element: <Staff /> },
  { path: 'departments', element: <Departments /> },
  { path: 'schedule', element: <WorkforceSchedule /> },
  { path: 'access', element: <AccessControl /> },
  { path: 'stock-control', element: <InventoryControl /> },
  { path: 'procurement', element: <Procurement /> },
  { path: 'notifications', element: <NotificationConsole /> },
  { path: 'subscription', element: <Subscriptions /> },
  { path: 'support', element: <SupportCentre /> },
  { path: 'profile', element: <ProviderProfile /> },

  ...deepRoutes('lab', 'lab', { title: 'Laboratory organization page centre' }),
]
