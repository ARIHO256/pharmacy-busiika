import Operations from './Operations'
import Overview from './Overview'
import Users from './Users'
import Appointments from './Appointments'
import Finance from './Finance'
import Reviews from './Reviews'
import Audit from './Audit'
import Compliance from './Compliance'
import Registry from './Registry'

export const nav = [{ to: '/admin/operations', label: 'Operational Governance', icon: 'clipboard', group: 'Trust & governance', description: 'Review and manage operational workflows' },
  { to: '/admin', label: 'Command Centre', icon: 'dashboard', end: true, group: 'Overview', description: 'Platform health and operational metrics' },
  { to: '/admin/users', label: 'Users & Roles', icon: 'users', group: 'Identity & access', description: 'Patients, providers, staff and permissions' },
  { to: '/admin/registry', label: 'Provider Registry', icon: 'doctor', group: 'Identity & access', description: 'Verification, credentials and facilities' },
  { to: '/admin/appointments', label: 'Appointment Operations', icon: 'calendar', group: 'Care operations', description: 'Monitor appointments, no-shows and exceptions' },
  { to: '/admin/reviews', label: 'Quality & Reviews', icon: 'star', group: 'Care operations', description: 'Reviews, complaints and service quality' },
  { to: '/admin/finance', label: 'Financial Management', icon: 'money', group: 'Finance', description: 'Transactions, commissions and payouts' },
  { to: '/admin/compliance', label: 'Compliance & Privacy', icon: 'shield', group: 'Trust & governance', description: 'Consent, emergency access and policy controls' },
  { to: '/admin/audit', label: 'Audit Trail', icon: 'audit', group: 'Trust & governance', description: 'Security and clinical access history' },
]

export const routes = [{ path: 'operations', element: <Operations /> },
  { index: true, element: <Overview /> },
  { path: 'users', element: <Users /> },
  { path: 'appointments', element: <Appointments /> },
  { path: 'finance', element: <Finance /> },
  { path: 'reviews', element: <Reviews /> },
  { path: 'audit', element: <Audit /> },
  { path: 'registry', element: <Registry /> },
  { path: 'compliance', element: <Compliance /> },
]
