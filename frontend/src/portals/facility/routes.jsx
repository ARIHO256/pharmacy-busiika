import ManageTaxonomy from '../pharmacy/ManageTaxonomy'
import Dashboard from './Dashboard'
import Staff from './Staff'
import Departments from './Departments'
import Queue from '../reception/Queue'
import Invoices from '../cashier/Invoices'
import Shifts from '../cashier/Shifts'
import Operations from './Operations'
export const nav=[
  { to: '/facility/pharmacy-taxonomy', label: 'Manage Taxonomy', icon: 'settings', group: 'Settings' },{to:'/facility',label:'Facility Dashboard',icon:'dashboard',end:true,group:'Overview',description:'People, care flow and operational performance'},{to:'/facility/staff',label:'Staff & Roles',icon:'users',group:'Workforce',description:'Invite, verify, suspend and assign facility staff'},{to:'/facility/departments',label:'Departments',icon:'hospital',group:'Workforce',description:'Configure clinical and operational units'},{to:'/facility/queue',label:'Patient Flow',icon:'activity',group:'Operations',description:'Monitor triage, consultation, billing and completion'},{to:'/facility/operations',label:'Operations',icon:'hospital',group:'Operations',description:'Admissions, procedures, referrals and diagnostics'},{to:'/facility/invoices',label:'Billing Oversight',icon:'money',group:'Finance',description:'Review invoices, collections and balances'},{to:'/facility/shifts',label:'Cashier Controls',icon:'audit',group:'Finance',description:'Review cash sessions and variances'}]
export const routes=[
  { path: 'pharmacy-taxonomy', element: <ManageTaxonomy /> },{index:true,element:<Dashboard/>},{path:'staff',element:<Staff/>},{path:'departments',element:<Departments/>},{path:'queue',element:<Queue/>},{path:'operations',element:<Operations/>},{path:'invoices',element:<Invoices/>},{path:'shifts',element:<Shifts readOnly/>}]
