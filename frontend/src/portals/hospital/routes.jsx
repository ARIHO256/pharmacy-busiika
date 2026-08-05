import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Services from './Services'
import Bookings from './Bookings'
import Beds from './Beds'
import { ProviderProfile } from '../pharmacy/shared'
import Admissions from '../operations/Admissions'
import WardsBeds from '../operations/WardsBeds'
import InventoryControl from '../operations/InventoryControl'
import Procurement from '../operations/Procurement'
import AccessControl from '../operations/AccessControl'
import Subscriptions from '../operations/Subscriptions'
import SupportCentre from '../operations/SupportCentre'
import Staff from '../facility/Staff'
import Departments from '../facility/Departments'
import Invoices from '../cashier/Invoices'
import WorkforceSchedule from '../operations/WorkforceSchedule'
import EmergencyBoard from '../operations/EmergencyBoard'
import TheatreCases from '../operations/TheatreCases'
import MaternityCare from '../operations/MaternityCare'
import QualityCompliance from '../operations/QualityCompliance'
import EnterpriseAnalytics from '../operations/EnterpriseAnalytics'
import NotificationConsole from '../operations/NotificationConsole'
import TeamSchedule from '../staff/TeamSchedule'

export const nav = [
  { to: '/hospital', label: 'Facility Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Capacity, bookings and service performance' },
  { to: '/hospital/bookings', label: 'Bookings & Queue', icon: 'calendar', group: 'Care operations', description: 'Appointments and patient arrival flow' },
  { to: '/hospital/services', label: 'Services & Departments', icon: 'hospital', group: 'Care operations', description: 'Departments, clinicians, prices and hours' },
  { to: '/hospital/beds', label: 'Beds & Capacity', icon: 'bed', group: 'Facility operations', description: 'Bed inventory and availability' },
  { to: '/hospital/admissions', label: 'Admissions & Discharge', icon: 'hospital', group: 'Care operations', description: 'Inpatient admission, transfer and discharge' },
  { to: '/hospital/ward-management', label: 'Ward Management', icon: 'bed', group: 'Facility operations', description: 'Wards, rooms, bed pricing and turnover' },
  { to: '/hospital/inventory', label: 'Inventory', icon: 'pill', group: 'Supply chain', description: 'Batches, expiry, cold-chain and stock movement' },
  { to: '/hospital/procurement', label: 'Procurement', icon: 'file', group: 'Supply chain', description: 'Purchase orders and approvals' },
  { to: '/hospital/staff-access', label: 'Staff Roles & Access', icon: 'shield', group: 'Workforce', description: 'Custom roles and granular permissions' },
  { to: '/hospital/staff', label: 'Staff Directory', icon: 'users', group: 'Workforce', description: 'Invite, assign and manage organization staff' },
  { to: '/hospital/departments', label: 'Departments', icon: 'building', group: 'Workforce', description: 'Clinical and operational department structure' },
  { to: '/hospital/schedule', label: 'Duty Roster & Leave', icon: 'calendar', group: 'Workforce', description: 'Shift coverage and leave approvals' },
  { to: '/hospital/invoices', label: 'Invoices & Collections', icon: 'money', group: 'Finance', description: 'Issue invoices, collect payments and print receipts' },
  { to: '/hospital/emergency', label: 'Emergency & Ambulance', icon: 'activity', group: 'Clinical operations', description: 'Emergency cases and ambulance dispatch' },
  { to: '/hospital/theatre', label: 'Theatre Operations', icon: 'hospital', group: 'Clinical operations', description: 'Surgical list, safety and recovery' },
  { to: '/hospital/maternity', label: 'Maternity Care', icon: 'users', group: 'Clinical operations', description: 'Antenatal, delivery and newborn care' },
  { to: '/hospital/quality', label: 'Quality & Privacy', icon: 'shield', group: 'Governance', description: 'Incidents, corrective actions and privacy requests' },
  { to: '/hospital/analytics', label: 'Analytics & Reports', icon: 'chart', group: 'Governance', description: 'Operational and financial performance' },
  { to: '/hospital/notifications', label: 'Notifications', icon: 'bell', group: 'Settings', description: 'Templates, broadcasts and announcements' },
  { to: '/hospital/subscription', label: 'Subscription', icon: 'wallet', group: 'Settings', description: 'Organization plan and renewal' },
  { to: '/hospital/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Platform support and issue tracking' },
  { to: '/hospital/profile', label: 'Facility Profile', icon: 'settings', group: 'Settings', description: 'Locations, licences and organisation settings' },

  { to: '/hospital/team-schedule', label: 'Team Schedule', icon: 'calendar', group: 'Operations', description: 'Upcoming appointments for every provider in your organization' },
  ...deepNav('hospital', 'hospital', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'services', element: <Services /> },
  { path: 'bookings', element: <Bookings /> },
  { path: 'beds', element: <Beds /> },
  { path: 'admissions', element: <Admissions /> },
  { path: 'ward-management', element: <WardsBeds /> },
  { path: 'inventory', element: <InventoryControl /> },
  { path: 'procurement', element: <Procurement /> },
  { path: 'staff-access', element: <AccessControl /> },
  { path: 'staff', element: <Staff /> },
  { path: 'departments', element: <Departments /> },
  { path: 'schedule', element: <WorkforceSchedule /> },
  { path: 'invoices', element: <Invoices /> },
  { path: 'emergency', element: <EmergencyBoard /> },
  { path: 'theatre', element: <TheatreCases /> },
  { path: 'maternity', element: <MaternityCare /> },
  { path: 'quality', element: <QualityCompliance /> },
  { path: 'analytics', element: <EnterpriseAnalytics /> },
  { path: 'notifications', element: <NotificationConsole /> },
  { path: 'subscription', element: <Subscriptions /> },
  { path: 'support', element: <SupportCentre /> },
  { path: 'profile', element: <ProviderProfile /> },

  { path: 'team-schedule', element: <TeamSchedule /> },
  ...deepRoutes('hospital', 'hospital', { title: 'Hospital operations page centre' }),
]
