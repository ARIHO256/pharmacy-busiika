import { deepNav, deepRoutes } from '../deep/routes'
import WardsBeds from '../operations/WardsBeds'
import Dashboard from './Dashboard'
import WardTasks from '../operations/WardTasks'
import ClinicalRounds from '../operations/ClinicalRounds'
import TheatreCases from '../operations/TheatreCases'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import { THEATRE_ADVANCED } from '../enterprise/coreModules'
export const nav=[{to:'/theatre',label:'Surgical Case Board',icon:'dashboard',end:true,group:'Surgery',description:'Schedule, consent, checklist, operation and recovery'},{to:'/theatre/cases',label:'Surgical Cases',icon:'hospital',group:'Surgery',description:'Theatre list and peri-operative case workflow'},{to:'/theatre/tasks',label:'Recovery & Theatre Tasks',icon:'clipboard',group:'Peri-operative care',description:'Pre-op, intra-op and recovery tasks'},{to:'/theatre/recovery',label:'Recovery Rounds',icon:'activity',group:'Peri-operative care',description:'Post-operative assessment and plan'},{to:'/theatre/capacity',label:'Theatre Capacity',icon:'bed',group:'Facility',description:'Theatre and recovery units'},{to:'/theatre/clinical-record',label:'Peri-operative Record',icon:'file',group:'Surgery',description:'Anaesthesia, intraoperative observations, counts, implants, recovery and sterilization'},
  ...deepNav('theatre', 'anaesthetist', { label: 'Complete page centre', group: 'Professional tools' }),
]
export const routes=[{index:true,element:<Dashboard/>},{path:'cases',element:<TheatreCases/>},{path:'tasks',element:<WardTasks mode="theatre"/>},{path:'recovery',element:<ClinicalRounds/>},{path:'capacity',element:<WardsBeds/>},{path:'clinical-record',element:<RecordWorkspace module={THEATRE_ADVANCED}/>},
  ...deepRoutes('theatre', 'anaesthetist', { title: 'Theatre and anaesthesia page centre' }),
]
