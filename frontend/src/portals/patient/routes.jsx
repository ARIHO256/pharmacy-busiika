import Dashboard from './Dashboard'
import FindDoctors from './FindDoctors'
import DoctorDetail from './DoctorDetail'
import Appointments from './Appointments'
import Invoices from './Invoices'
import Profile from './Profile'
import HealthRecord from './HealthRecord'
import { routesExt } from './ext/routesExt'

export const nav = [
  { to: '/patient', label: 'Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Your care summary and next actions' },
  { to: '/patient/doctors', label: 'Find Care', icon: 'search', group: 'Care journey', description: 'Search verified doctors and services' },
  { to: '/patient/appointments', label: 'Appointments', icon: 'calendar', group: 'Care journey', description: 'Book and manage appointments' },
  { to: '/patient/messages', label: 'Consultations', icon: 'video', group: 'Care journey', description: 'Secure chat, audio and video care' },
  { to: '/patient/prescriptions', label: 'Prescriptions', icon: 'prescription', group: 'Health record', description: 'View prescriptions and care instructions' },
  { to: '/patient/health-record', label: 'Health Record', icon: 'heart', group: 'Health record', description: 'Timeline, conditions, allergies and observations' },
  { to: '/patient/labs', label: 'Laboratory', icon: 'flask', group: 'Connected services', description: 'Book tests and receive results' },
  { to: '/patient/store', label: 'Pharmacy', icon: 'pill', group: 'Connected services', description: 'Send prescriptions and order medicine' },
  { to: '/patient/hospitals', label: 'Hospitals & Clinics', icon: 'hospital', group: 'Connected services', description: 'Find facilities and services' },
  { to: '/patient/insurance', label: 'Insurance', icon: 'insurance', group: 'Finance & access', description: 'Coverage, approvals and claims' },
  { to: '/patient/invoices', label: 'Payments & Invoices', icon: 'wallet', group: 'Finance & access', description: 'Payments, receipts and balances' },
  { to: '/patient/profile', label: 'Profile & Privacy', icon: 'user', group: 'Settings', description: 'Identity, medical profile and preferences' },
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'doctors', element: <FindDoctors /> },
  { path: 'doctors/:id', element: <DoctorDetail /> },
  { path: 'appointments', element: <Appointments /> },
  { path: 'health-record', element: <HealthRecord /> },
  { path: 'invoices', element: <Invoices /> },
  { path: 'profile', element: <Profile /> },
  ...routesExt,
]
