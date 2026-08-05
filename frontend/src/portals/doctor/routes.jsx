import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Availability from './Availability'
import Appointments from './Appointments'
import Consult from './Consult'
import Prescriptions from './Prescriptions'
import Earnings from './Earnings'
import Profile from './Profile'
import ClinicalWorkspace from './ClinicalWorkspace'
import LabReferrals from './LabReferrals'
import ClinicalRounds from '../operations/ClinicalRounds'
import Imaging from '../operations/Imaging'
import Admissions from '../operations/Admissions'
import SupportCentre from '../operations/SupportCentre'
import Referrals from './Referrals'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import MedicationSafetyWorkbench from '../enterprise/MedicationSafetyWorkbench'
import { DOCTOR_EMERGENCY, DOCTOR_INPATIENT, DOCTOR_LAB_SPECIALTY, DOCTOR_MATERNITY, DOCTOR_PHARMACY_SAFETY, DOCTOR_THEATRE } from '../enterprise/coreModules'
import TeamSchedule from '../staff/TeamSchedule'

export const nav = [
  { to: '/doctor', label: 'Clinical Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Today, alerts and performance' },
  { to: '/doctor/availability', label: 'Availability', icon: 'clock', group: 'Scheduling', description: 'Working hours, breaks and holidays' },
  { to: '/doctor/appointments', label: 'Appointments', icon: 'calendar', group: 'Scheduling', description: 'Requests, queue and appointment history' },
  { to: '/doctor/consult', label: 'Consultations', icon: 'video', group: 'Care delivery', description: 'Chat, audio and video consultations' },
  { to: '/doctor/clinical', label: 'Clinical Workspace', icon: 'clipboard', group: 'Care delivery', description: 'Encounters, notes, diagnosis and referrals' },
  { to: '/doctor/inpatients', roles: ['doctor','clinical_officer','dentist','medical_director'], label: 'Inpatient Care', icon: 'hospital', group: 'Care delivery', description: 'Admissions, ward patients and discharge planning' },
  { to: '/doctor/rounds', roles: ['doctor','clinical_officer','dentist','medical_director'], label: 'Ward Rounds', icon: 'clipboard', group: 'Care delivery', description: 'SOAP rounds and discharge readiness' },
  { to: '/doctor/imaging', roles: ['doctor','clinical_officer','dentist','medical_director'], label: 'Imaging & Radiology', icon: 'activity', group: 'Care delivery', description: 'Request imaging and review released reports' },
  { to: '/doctor/referrals', label: 'Specialist Referrals', icon: 'activity', group: 'Care delivery', description: 'Accept, coordinate and close specialist referrals' },
  { to: '/doctor/lab-referrals', label: 'Laboratory Referrals', icon: 'flask', group: 'Care delivery', description: 'Order tests and review referred results' },
  { to: '/doctor/prescriptions', roles: ['doctor','clinical_officer','dentist','medical_director'], label: 'E-Prescriptions', icon: 'prescription', group: 'Care delivery', description: 'Create and manage prescriptions' },
  { to: '/doctor/inpatient-records', label: 'Inpatient Clinical Records', icon: 'clipboard', group: 'Advanced care', description: 'Care plans, observation charts, medication schedules and transfusion records' },
  { to: '/doctor/maternity-records', label: 'Maternity Clinical Records', icon: 'users', group: 'Advanced care', description: 'Antenatal, labour, delivery, newborn and child-health records' },
  { to: '/doctor/theatre-records', label: 'Surgery & Anaesthesia', icon: 'activity', group: 'Advanced care', description: 'Pre-anaesthetic assessment, counts and implant traceability' },
  { to: '/doctor/emergency-records', label: 'Emergency & Resuscitation', icon: 'alert', group: 'Advanced care', description: 'Trauma, resuscitation and emergency observation records' },
  { to: '/doctor/special-lab', label: 'Special Laboratory Review', icon: 'flask', group: 'Advanced care', description: 'Microbiology, susceptibility and blood-bank collaboration' },
  { to: '/doctor/medication-safety', label: 'Medication Safety', icon: 'shield', group: 'Advanced care', description: 'Interactions, allergies, contraindications and adverse reactions' },
  { to: '/doctor/medication-events', label: 'Medication Safety Events', icon: 'activity', group: 'Advanced care', description: 'Document safety reviews and adverse drug reactions' },
  { to: '/doctor/earnings', label: 'Earnings & Payouts', icon: 'money', group: 'Finance', description: 'Revenue, commissions and withdrawals' },
  { to: '/doctor/support', label: 'Support Centre', icon: 'help', group: 'Settings', description: 'Clinical workflow and account support' },
  { to: '/doctor/profile', label: 'Professional Profile', icon: 'doctor', group: 'Settings', description: 'Credentials, services, fees and facilities' },

  { to: '/doctor/team-schedule', label: 'Team Schedule', icon: 'calendar', group: 'Scheduling', description: 'Upcoming appointments for every provider in your organization' },
  ...deepNav('doctor', 'doctor', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'availability', element: <Availability /> },
  { path: 'appointments', element: <Appointments /> },
  { path: 'consult', element: <Consult /> },
  { path: 'clinical', element: <ClinicalWorkspace /> },
  { path: 'lab-referrals', element: <LabReferrals /> },
  { path: 'referrals', element: <Referrals /> },
  { path: 'inpatients', element: <Admissions /> },
  { path: 'rounds', element: <ClinicalRounds /> },
  { path: 'imaging', element: <Imaging /> },
  { path: 'inpatient-records', element: <RecordWorkspace module={DOCTOR_INPATIENT} /> },
  { path: 'maternity-records', element: <RecordWorkspace module={DOCTOR_MATERNITY} /> },
  { path: 'theatre-records', element: <RecordWorkspace module={DOCTOR_THEATRE} /> },
  { path: 'emergency-records', element: <RecordWorkspace module={DOCTOR_EMERGENCY} /> },
  { path: 'special-lab', element: <RecordWorkspace module={DOCTOR_LAB_SPECIALTY} /> },
  { path: 'medication-safety', element: <MedicationSafetyWorkbench /> },
  { path: 'medication-events', element: <RecordWorkspace module={DOCTOR_PHARMACY_SAFETY} /> },
  { path: 'support', element: <SupportCentre /> },
  { path: 'prescriptions', element: <Prescriptions /> },
  { path: 'earnings', element: <Earnings /> },
  { path: 'profile', element: <Profile /> },

  { path: 'team-schedule', element: <TeamSchedule /> },
  ...deepRoutes('doctor', 'doctor', { title: 'Doctor clinical page centre' }),
]
