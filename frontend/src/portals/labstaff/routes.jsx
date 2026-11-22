import Operations from '../facility/Operations'
import Dashboard from '../lab/Dashboard'
import Orders from '../lab/Orders'
import Tests from '../lab/Tests'
export const nav=[
  { to: '/lab-staff/operations', label: 'Imaging Operations', icon: 'clipboard', group: 'Diagnostics', description: 'Review and manage operational workflows' },{to:'/lab-staff',label:'Laboratory Dashboard',icon:'dashboard',end:true,group:'Overview',description:'Specimen, test and result workload'},{to:'/lab-staff/orders',label:'Test Worklist',icon:'flask',group:'Diagnostics',description:'Referred tests, specimens, processing and result release'},{to:'/lab-staff/tests',label:'Test Catalogue',icon:'clipboard',group:'Diagnostics',description:'Available tests, sample types and prices'},
  { to: '/lab-staff/imaging', label: 'Imaging Worklist', icon: 'clipboard', group: 'Diagnostics', description: 'Review imaging requests and acquisition status' },
]
export const routes=[
  { path: 'imaging', element: <Operations key="imaging" resource="imaging" /> },
  { path: 'operations', element: <Operations resource="imaging" /> },{index:true,element:<Dashboard/>},{path:'orders',element:<Orders/>},{path:'tests',element:<Tests/>}]
