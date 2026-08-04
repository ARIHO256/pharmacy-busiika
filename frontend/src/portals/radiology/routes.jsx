import { deepNav, deepRoutes } from '../deep/routes'
import Imaging from '../operations/Imaging'
import Dashboard from './Dashboard'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import { RADIOLOGY_ADVANCED } from '../enterprise/coreModules'
export const nav=[{to:'/radiology',label:'Radiology Worklist',icon:'activity',end:true,group:'Diagnostics',description:'Schedule, perform, report and release imaging studies'},{to:'/radiology/reports',roles:['radiologist'],label:'Reporting Queue',icon:'file',group:'Diagnostics',description:'Findings, impressions, critical results and verification'},{to:'/radiology/advanced',label:'Structured Imaging Record',icon:'file',group:'Diagnostics',description:'Worklists, structured reports, dose records and critical alerts'},{to:'/security',label:'Security Centre',icon:'shield',group:'Settings',description:'Password, email verification and MFA'},
  ...deepNav('radiology', 'radiologist', { label: 'Complete page centre', group: 'Professional tools' }),
]
export const routes=[{index:true,element:<Dashboard/>},{path:'reports',element:<Imaging/>},{path:'advanced',element:<RecordWorkspace module={RADIOLOGY_ADVANCED}/>},
  ...deepRoutes('radiology', 'radiologist', { title: 'Radiology page centre' }),
]
