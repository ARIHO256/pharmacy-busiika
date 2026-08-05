import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import { NURSE_EMERGENCY, NURSE_INPATIENT, NURSE_MATERNITY, NURSE_THEATRE } from '../enterprise/coreModules'
import Triage from './Triage'
import Notes from './Notes'
import Medications from './Medications'
import Admissions from '../operations/Admissions'
import WardTasks from '../operations/WardTasks'
import WardsBeds from '../operations/WardsBeds'
import SupportCentre from '../operations/SupportCentre'
import MaternityCare from '../operations/MaternityCare'
import WorkforceSchedule from '../operations/WorkforceSchedule'
import TheatreCases from '../operations/TheatreCases'
import TeamSchedule from '../staff/TeamSchedule'

export const nav = [
  { to: '/nurse', label: 'Nursing Dashboard', icon: 'dashboard', end: true, group: 'Overview', description: 'Patient flow, urgency and current care workload' },
  { to: '/nurse/inpatients', label: 'Inpatient Board', icon: 'hospital', group: 'Patient care', description: 'Ward patients, beds and discharge state' },
  { to: '/nurse/ward-tasks', label: 'Ward Tasks', icon: 'clipboard', group: 'Patient care', description: 'Observations, procedures, mobilisation and handover' },
  { to: '/nurse/bed-board', label: 'Bed Board', icon: 'bed', group: 'Patient care', description: 'Bed availability, cleaning and maintenance state' },
  { to: '/nurse/triage', label: 'Triage Queue', icon: 'activity', group: 'Patient care', description: 'Record vital signs, complaints and urgency' },
  { to: '/nurse/notes', label: 'Nursing Notes', icon: 'clipboard', group: 'Patient care', description: 'Assessments, progress, procedures and handovers' },
  { to: '/nurse/medications', label: 'Medication Rounds', icon: 'pill', group: 'Medication safety', description: 'Record administered, held, refused and missed doses' },
  { to: '/nurse/maternity', roles: ['nurse','midwife'], label: 'Maternity & Newborn', icon: 'users', group: 'Specialist care', description: 'Antenatal, labour, delivery and postnatal workflow' },
  { to: '/nurse/theatre', roles: ['nurse','theatre_nurse'], label: 'Theatre Cases', icon: 'activity', group: 'Specialist care', description: 'Surgical checklist, recovery and theatre nursing workflow' },
  { to: '/nurse/advanced-inpatient', label: 'Advanced Inpatient Records', icon: 'clipboard', group: 'Patient safety', description: 'Care plans, fluid balance, observations, risks, handover and transfusion' },
  { to: '/nurse/maternity-records', roles: ['nurse','midwife'], label: 'Maternity Clinical Record', icon: 'users', group: 'Specialist care', description: 'Partographs, newborn assessment, immunization and growth monitoring' },
  { to: '/nurse/emergency-records', label: 'Emergency Records', icon: 'alert', group: 'Patient safety', description: 'Pre-hospital, trauma, resuscitation and observation documentation' },
  { to: '/nurse/theatre-records', roles: ['nurse','theatre_nurse'], label: 'Recovery Records', icon: 'activity', group: 'Specialist care', description: 'Post-anaesthetic recovery and structured handover' },
  { to: '/nurse/schedule', label: 'My Duty Roster', icon: 'calendar', group: 'Workforce', description: 'Shifts, confirmations and leave requests' },
  { to: '/nurse/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Report workflow or account issues' },

  { to: '/nurse/team-schedule', label: 'Team Schedule', icon: 'calendar', group: 'Patient care', description: 'Upcoming appointments for every provider in your organization' },
  ...deepNav('nurse', 'nurse', { label: 'Complete page centre', group: 'Professional tools' }),
]
export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'triage', element: <Triage /> },
  { path: 'notes', element: <Notes /> },
  { path: 'medications', element: <Medications /> },
  { path: 'inpatients', element: <Admissions /> },
  { path: 'ward-tasks', element: <WardTasks /> },
  { path: 'bed-board', element: <WardsBeds /> },
  { path: 'maternity', element: <MaternityCare /> },
  { path: 'theatre', element: <TheatreCases /> },
  { path: 'advanced-inpatient', element: <RecordWorkspace module={NURSE_INPATIENT} /> },
  { path: 'maternity-records', element: <RecordWorkspace module={NURSE_MATERNITY} /> },
  { path: 'emergency-records', element: <RecordWorkspace module={NURSE_EMERGENCY} /> },
  { path: 'theatre-records', element: <RecordWorkspace module={NURSE_THEATRE} /> },
  { path: 'schedule', element: <WorkforceSchedule /> },
  { path: 'support', element: <SupportCentre /> },

  { path: 'team-schedule', element: <TeamSchedule /> },
  ...deepRoutes('nurse', 'nurse', { title: 'Nursing page centre' }),
]
