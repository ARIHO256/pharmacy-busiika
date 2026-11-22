import PharmacySubstitutions from './PharmacySubstitutions'
import Operations from '../facility/Operations'
import Dashboard from './Dashboard'
import Availability from './Availability'
import Appointments from './Appointments'
import Consult from './Consult'
import Prescriptions from './Prescriptions'
import Earnings from './Earnings'
import Profile from './Profile'
import ClinicalWorkspace from './ClinicalWorkspace'
import LabReferrals from './LabReferrals'

export const nav = [
  { to: '/doctor/operations', label: 'Facility Operations', icon: 'clipboard', group: 'Care delivery', description: 'Review and manage operational workflows' },
  { to: '/doctor', label: 'Clinical Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Today, alerts and performance' },
  { to: '/doctor/availability', label: 'Availability', icon: 'clock', group: 'Scheduling', description: 'Working hours, breaks and holidays' },
  { to: '/doctor/appointments', label: 'Appointments', icon: 'calendar', group: 'Scheduling', description: 'Requests, queue and appointment history' },
  { to: '/doctor/consult', label: 'Consultations', icon: 'video', group: 'Care delivery', description: 'Chat, audio and video consultations' },
  { to: '/doctor/clinical', label: 'Clinical Workspace', icon: 'clipboard', group: 'Care delivery', description: 'Encounters, notes, diagnosis and referrals' },
  { to: '/doctor/lab-referrals', label: 'Laboratory Referrals', icon: 'flask', group: 'Care delivery', description: 'Order tests and review referred results' },
  { to: '/doctor/pharmacy-substitutions', label: 'Pharmacy Substitutions', icon: 'prescription', group: 'Care delivery' },
  { to: '/doctor/prescriptions', label: 'E-Prescriptions', icon: 'prescription', group: 'Care delivery', description: 'Create and manage prescriptions' },
  { to: '/doctor/earnings', label: 'Earnings & Payouts', icon: 'money', group: 'Finance', description: 'Revenue, commissions and withdrawals' },
  { to: '/doctor/profile', label: 'Professional Profile', icon: 'doctor', group: 'Settings', description: 'Credentials, services, fees and facilities' },
  { to: '/doctor/referrals', label: 'Referral Worklist', icon: 'clipboard', group: 'Care delivery', description: 'Track incoming referrals and record outcomes' },
]

export const routes = [
  { path: 'referrals', element: <Operations key="referrals" resource="referrals" /> },
  { path: 'operations', element: <Operations /> },
  { index: true, element: <Dashboard /> },
  { path: 'availability', element: <Availability /> },
  { path: 'appointments', element: <Appointments /> },
  { path: 'consult', element: <Consult /> },
  { path: 'clinical', element: <ClinicalWorkspace /> },
  { path: 'lab-referrals', element: <LabReferrals /> },
  { path: 'pharmacy-substitutions', element: <PharmacySubstitutions /> },
  { path: 'prescriptions', element: <Prescriptions /> },
  { path: 'earnings', element: <Earnings /> },
  { path: 'profile', element: <Profile /> },
]
