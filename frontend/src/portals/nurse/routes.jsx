import Operations from '../facility/Operations'
import Dashboard from './Dashboard'
import Triage from './Triage'
import Notes from './Notes'
import Handover from './Handover'
import Medications from './Medications'

export const nav = [
  { to: '/nurse/operations', label: 'Facility Operations', icon: 'clipboard', group: 'Patient care', description: 'Review and manage operational workflows' },
  { to: '/nurse', label: 'Nursing Dashboard', icon: 'dashboard', end: true, group: 'Overview', description: 'Patient flow, urgency and current care workload' },
  { to: '/nurse/triage', label: 'Triage Queue', icon: 'activity', group: 'Patient care', description: 'Record vital signs, complaints and urgency' },
  { to: '/nurse/handover', label: 'Shift Handover', icon: 'clipboard', group: 'Patient care', description: 'Record patient status and next actions at shift change' },
  { to: '/nurse/notes', label: 'Nursing Notes', icon: 'clipboard', group: 'Patient care', description: 'Assessments, progress, procedures and handovers' },
  { to: '/nurse/medications', label: 'Medication Rounds', icon: 'pill', group: 'Medication safety', description: 'Record administered, held, refused and missed doses' },
  { to: '/nurse/ward-board', label: 'Ward Admissions', icon: 'clipboard', group: 'Patient care', description: 'Review admissions and coordinate transfers' },
  { to: '/nurse/scheduled-doses', label: 'Scheduled Doses', icon: 'clipboard', group: 'Medication safety', description: 'Review due doses and record administration outcomes' },
]
export const routes = [
  { path: 'ward-board', element: <Operations key="admissions" resource="admissions" /> },
  { path: 'scheduled-doses', element: <Operations key="medication-schedules" resource="medication-schedules" /> },
  { path: 'operations', element: <Operations /> },
  { index: true, element: <Dashboard /> },
  { path: 'triage', element: <Triage /> },
  { path: 'handover', element: <Handover /> },
  { path: 'notes', element: <Notes /> },
  { path: 'medications', element: <Medications /> },
]
