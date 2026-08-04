import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Invoices from './Invoices'
import Shifts from './Shifts'
import FinanceControls from '../operations/FinanceControls'
import SupportCentre from '../operations/SupportCentre'
export const nav=[{to:'/cashier',label:'Billing Dashboard',icon:'dashboard',end:true,group:'Overview',description:'Collections, balances and payment activity'},{to:'/cashier/invoices',label:'Invoices & Receipts',icon:'money',group:'Billing',description:'Issue invoices, collect payments and print receipts'},{to:'/cashier/shifts',label:'Cashier Shifts',icon:'activity',group:'Controls',description:'Open, close and reconcile cashier sessions'},{to:'/cashier/controls',roles:['accountant'],label:'Refunds & Adjustments',icon:'audit',group:'Controls',description:'Financial exception approvals and audit trail'},{to:'/cashier/support',label:'Support',icon:'help',group:'Settings',description:'Billing and payment support'},
  ...deepNav('cashier', 'cashier', { label: 'Complete page centre', group: 'Professional tools' }),
]
export const routes=[{index:true,element:<Dashboard/>},{path:'invoices',element:<Invoices/>},{path:'shifts',element:<Shifts/>},{path:'controls',element:<FinanceControls/>},{path:'support',element:<SupportCentre/>},
  ...deepRoutes('cashier', 'cashier', { title: 'Cashier page centre' }),
]
