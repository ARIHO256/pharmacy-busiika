import Dashboard from './Dashboard'
import Invoices from './Invoices'
import Shifts from './Shifts'
export const nav=[{to:'/cashier',label:'Billing Dashboard',icon:'dashboard',end:true,group:'Overview',description:'Collections, balances and payment activity'},{to:'/cashier/invoices',label:'Invoices & Receipts',icon:'money',group:'Billing',description:'Issue invoices, collect payments and print receipts'},{to:'/cashier/shifts',label:'Cashier Shifts',icon:'activity',group:'Controls',description:'Open, close and reconcile cashier sessions'}]
export const routes=[{index:true,element:<Dashboard/>},{path:'invoices',element:<Invoices/>},{path:'shifts',element:<Shifts/>}]
