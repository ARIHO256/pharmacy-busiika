import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Inventory from './Inventory'
import Orders from './Orders'
import RxOrders from './RxOrders'
import Dispensing from '../pharmacist/Dispensing'
import Suppliers from './Suppliers'
import { ProviderProfile } from './shared'
import Staff from '../facility/Staff'
import Departments from '../facility/Departments'
import AccessControl from '../operations/AccessControl'
import InventoryControl from '../operations/InventoryControl'
import Procurement from '../operations/Procurement'
import WorkforceSchedule from '../operations/WorkforceSchedule'
import Subscriptions from '../operations/Subscriptions'
import SupportCentre from '../operations/SupportCentre'
import NotificationConsole from '../operations/NotificationConsole'
import TeamSchedule from '../staff/TeamSchedule'

export const nav = [
  { to: '/pharmacy', label: 'Operations Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Orders, stock alerts and fulfilment' },
  { to: '/pharmacy/rx-orders', label: 'Prescription Queue', icon: 'prescription', group: 'Dispensing', description: 'Review and verify e-prescriptions' },
  { to: '/pharmacy/dispensing', label: 'Clinical Dispensing', icon: 'pill', group: 'Dispensing', description: 'Partial dispensing, batches, substitutions and counselling' },
  { to: '/pharmacy/orders', label: 'Orders & Delivery', icon: 'truck', group: 'Dispensing', description: 'Fulfilment, collection and dispatch' },
  { to: '/pharmacy/inventory', label: 'Medicine Inventory', icon: 'box', group: 'Inventory', description: 'Stock, batches and availability' },
  { to: '/pharmacy/suppliers', label: 'Suppliers', icon: 'building', group: 'Inventory', description: 'Supply relationships and restocking' },
  { to: '/pharmacy/staff', label: 'Staff Directory', icon: 'users', group: 'Workforce', description: 'Invite, verify and manage staff' },
  { to: '/pharmacy/departments', label: 'Departments', icon: 'building', group: 'Workforce', description: 'Units, teams and service ownership' },
  { to: '/pharmacy/schedule', label: 'Duty Roster & Leave', icon: 'calendar', group: 'Workforce', description: 'Shift coverage and leave requests' },
  { to: '/pharmacy/access', label: 'Roles & Permissions', icon: 'shield', group: 'Workforce', description: 'Granular staff access control' },
  { to: '/pharmacy/stock-control', label: 'Advanced Stock Control', icon: 'box', group: 'Operations', description: 'Batches, expiry and stock movement' },
  { to: '/pharmacy/procurement', label: 'Procurement', icon: 'file', group: 'Operations', description: 'Purchase orders and receiving' },
  { to: '/pharmacy/notifications', label: 'Notifications', icon: 'bell', group: 'Settings', description: 'Templates, announcements and broadcasts' },
  { to: '/pharmacy/subscription', label: 'Subscription', icon: 'wallet', group: 'Settings', description: 'Plan, renewal and feature limits' },
  { to: '/pharmacy/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Platform support and issue tracking' },
  { to: '/pharmacy/profile', label: 'Pharmacy Profile', icon: 'settings', group: 'Settings', description: 'Branches, licences and service settings' },

  { to: '/pharmacy/team-schedule', label: 'Team Schedule', icon: 'calendar', group: 'Professional tools', description: 'Upcoming appointments for every provider in your organization' },
  ...deepNav('pharmacy', 'pharmacy', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'inventory', element: <Inventory /> },
  { path: 'orders', element: <Orders /> },
  { path: 'rx-orders', element: <RxOrders /> },
  { path: 'dispensing', element: <Dispensing /> },
  { path: 'suppliers', element: <Suppliers /> },
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

  { path: 'team-schedule', element: <TeamSchedule /> },
  ...deepRoutes('pharmacy', 'pharmacy', { title: 'Pharmacy organization page centre' }),
]
