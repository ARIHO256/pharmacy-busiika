import ManageTaxonomy from '../pharmacy/ManageTaxonomy'
import Dashboard from './Dashboard'
import Services from './Services'
import Bookings from './Bookings'
import Beds from './Beds'
import { ProviderProfile } from '../pharmacy/shared'

export const nav = [
  { to: '/hospital/pharmacy-taxonomy', label: 'Manage Taxonomy', icon: 'settings', group: 'Settings' },
  { to: '/hospital', label: 'Facility Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Capacity, bookings and service performance' },
  { to: '/hospital/bookings', label: 'Bookings & Queue', icon: 'calendar', group: 'Care operations', description: 'Appointments and patient arrival flow' },
  { to: '/hospital/services', label: 'Services & Departments', icon: 'hospital', group: 'Care operations', description: 'Departments, clinicians, prices and hours' },
  { to: '/hospital/beds', label: 'Beds & Capacity', icon: 'bed', group: 'Facility operations', description: 'Bed inventory and availability' },
  { to: '/hospital/profile', label: 'Facility Profile', icon: 'settings', group: 'Settings', description: 'Locations, licences and organisation settings' },
]

export const routes = [
  { path: 'pharmacy-taxonomy', element: <ManageTaxonomy /> },
  { index: true, element: <Dashboard /> },
  { path: 'services', element: <Services /> },
  { path: 'bookings', element: <Bookings /> },
  { path: 'beds', element: <Beds /> },
  { path: 'profile', element: <ProviderProfile /> },
]
