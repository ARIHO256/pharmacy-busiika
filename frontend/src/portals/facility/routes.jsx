import Handoffs from './Handoffs'
import ManageTaxonomy from '../pharmacy/ManageTaxonomy'
import Dashboard from './Dashboard'
import Staff from './Staff'
import Departments from './Departments'
import Queue from '../reception/Queue'
import Invoices from '../cashier/Invoices'
import Shifts from '../cashier/Shifts'
import Operations from './Operations'
import Services from '../hospital/Services'
import Bookings from '../hospital/Bookings'
import Beds from '../hospital/Beds'
import { ProviderProfile } from '../pharmacy/shared'

const shared = [
  { path: '', label: 'Overview', icon: 'dashboard', group: 'Overview', element: <Dashboard /> },
  { path: 'bookings', label: 'Bookings', icon: 'calendar', group: 'Patient care', element: <Bookings /> },
  { path: 'queue', label: 'Patient Flow', icon: 'activity', group: 'Patient care', element: <Queue /> },
  { path: 'services', label: 'Facility Services', icon: 'hospital', group: 'Patient care', element: <Services /> },
  { path: 'operations', label: 'Referrals & Diagnostics', icon: 'clipboard', group: 'Patient care',
    manager: true, element: <Operations key="diagnostics" resources={['referrals', 'imaging', 'offline-nodes']} facilityOnly /> },
  { path: 'handoffs', label: 'Patient Handoffs', icon: 'clipboard', group: 'Patient care', element: <Handoffs /> },
  { path: 'admissions', label: 'Admissions', icon: 'clipboard', group: 'Inpatient & Theatre',
    hospital: true, element: <Operations key="admissions" resource="admissions" facilityOnly /> },
  { path: 'beds', label: 'Wards & Beds', icon: 'bed', group: 'Inpatient & Theatre', hospital: true, element: <Beds /> },
  { path: 'medications', label: 'Medication Schedules', icon: 'pill', group: 'Inpatient & Theatre',
    hospital: true, manager: true, element: <Operations key="medications" resource="medication-schedules" facilityOnly /> },
  { path: 'theatre', label: 'Theatre', icon: 'calendar', group: 'Inpatient & Theatre',
    hospital: true, element: <Operations key="theatre" resource="procedures" facilityOnly /> },
  { path: 'invoices', label: 'Billing Oversight', icon: 'money', group: 'Billing', element: <Invoices /> },
  { path: 'shifts', label: 'Cashier Shifts', icon: 'audit', group: 'Billing', element: <Shifts readOnly /> },
  { path: 'staff', label: 'Staff & Access', icon: 'users', group: 'Administration', element: <Staff /> },
  { path: 'departments', label: 'Departments', icon: 'hospital', group: 'Administration', element: <Departments /> },
  { path: 'pharmacy-taxonomy', label: 'Pharmacy Taxonomy', icon: 'settings', group: 'Administration', pharmacy: true, element: <ManageTaxonomy /> },
  { path: 'profile', label: 'Facility Profile', icon: 'settings', group: 'Administration', owner: true, element: <ProviderProfile /> },
]

export const routes = shared.map(({ path, element }) => path ? { path, element } : { index: true, element })

export function facilityNavigation(type, role, hasPharmacy) {
  return shared.filter((item) => {
    if (!type) return item.owner
    if (item.hospital && type !== 'hospital') return false
    if (item.pharmacy && !hasPharmacy) return false
    if (item.manager && role !== 'facility_manager') return false
    return !item.owner || role === 'hospital'
  }).map(({ path, label, icon, group }) => ({
    to: path ? `/facility/${path}` : '/facility',
    end: !path,
    label, icon, group,
  }))
}
