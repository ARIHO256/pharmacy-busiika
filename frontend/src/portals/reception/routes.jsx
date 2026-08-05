import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Patients from './Patients'
import CheckIn from './CheckIn'
import Queue from './Queue'
import TeamSchedule from '../staff/TeamSchedule'

export const nav = [
  { to: '/reception', label: 'Front Desk Dashboard', icon: 'dashboard', end: true, group: 'Overview', description: 'Daily arrivals, queues and facility flow' },
  { to: '/reception/patients', label: 'Patient Directory', icon: 'users', group: 'Registration', description: 'Search and register walk-in patients' },
  { to: '/reception/check-in', label: 'Patient Check-in', icon: 'calendar', group: 'Registration', description: 'Create visits and assign queue numbers' },
  { to: '/reception/queue', label: 'Patient Flow Board', icon: 'activity', group: 'Operations', description: 'Track triage, clinician, billing and completion stages' },

  { to: '/reception/team-schedule', label: 'Team Schedule', icon: 'calendar', group: 'Front desk', description: 'Upcoming appointments for every provider in your organization' },
  ...deepNav('reception', 'receptionist', { label: 'Complete page centre', group: 'Professional tools' }),
]
export const routes = [{ index: true, element: <Dashboard /> }, { path: 'patients', element: <Patients /> }, { path: 'check-in', element: <CheckIn /> }, { path: 'queue', element: <Queue /> },
  { path: 'team-schedule', element: <TeamSchedule /> },
  ...deepRoutes('reception', 'receptionist', { title: 'Front desk page centre' }),
]
