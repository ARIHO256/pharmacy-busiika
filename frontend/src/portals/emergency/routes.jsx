import { deepNav, deepRoutes } from '../deep/routes'
import EmergencyBoard from '../operations/EmergencyBoard'
import Dashboard from './Dashboard'
import Triage from '../nurse/Triage'
import Admissions from '../operations/Admissions'
import WardTasks from '../operations/WardTasks'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import { EMERGENCY_ADVANCED } from '../enterprise/coreModules'
export const nav=[{to:'/emergency',label:'Emergency & Ambulance Board',icon:'activity',end:true,group:'Emergency',description:'Live casualty, acuity, treatment and dispatch operations'},{to:'/emergency/triage',roles:['paramedic'],label:'Emergency Triage',icon:'alert',group:'Emergency',description:'Vital signs, acuity and escalation'},{to:'/emergency/admissions',roles:['paramedic'],label:'Observation & Admissions',icon:'hospital',group:'Care delivery',description:'Emergency observation beds and inpatient admission'},{to:'/emergency/tasks',roles:['paramedic'],label:'Emergency Tasks',icon:'clipboard',group:'Care delivery',description:'STAT procedures, observations and handover'},{to:'/emergency/clinical-record',label:'Structured Emergency Record',icon:'file',group:'Emergency',description:'Pre-hospital, trauma, resuscitation, observation and mass-casualty records'},
  ...deepNav('emergency', 'paramedic', { label: 'Complete page centre', group: 'Professional tools' }),
]
export const routes=[{index:true,element:<Dashboard/>},{path:'triage',element:<Triage/>},{path:'admissions',element:<Admissions/>},{path:'tasks',element:<WardTasks/>},{path:'clinical-record',element:<RecordWorkspace module={EMERGENCY_ADVANCED}/>},
  ...deepRoutes('emergency', 'paramedic', { title: 'Emergency and ambulance page centre' }),
]
