import Counter from '../pharmacy/Counter'
import ShiftClosing from '../pharmacy/ShiftClosing'
import { PharmacySafety, PharmacyTransfers } from '../pharmacy/SafetyWorkflows'
import { Procurement, Stocktake } from '../pharmacy/InventoryWorkflows'
import MedicineRegister from '../pharmacy/MedicineRegister'
import StockControl from '../pharmacy/StockControl'
import Dashboard from '../pharmacy/Dashboard'
import RxOrders from '../pharmacy/RxOrders'
import Inventory from '../pharmacy/Inventory'
import Orders from '../pharmacy/Orders'
import Suppliers from '../pharmacy/Suppliers'
export const nav=[
  { to: '/pharmacist/counter', label: 'New Sale', icon: 'cart', group: 'Sales', roles: ['pharmacy', 'pharmacist', 'cashier'] },
  { to: '/pharmacist/shifts', label: 'Cash Shifts', icon: 'money', group: 'Sales', roles: ['pharmacy', 'pharmacist', 'cashier'] },
  { to: '/pharmacist/transfers', label: 'Branch Transfers', roles: ['pharmacist'], icon: 'truck', group: 'Inventory' },
  { to: '/pharmacist/safety', label: 'Safety & Returns', roles: ['pharmacist'], icon: 'clipboard', group: 'Dispensing' },
  { to: '/pharmacist/procurement', label: 'Procurement', icon: 'building', group: 'Inventory', description: 'Purchase orders and supplier deliveries' },
  { to: '/pharmacist/stocktake', label: 'Stocktake', icon: 'clipboard', group: 'Inventory', description: 'Physical counts and stock adjustments' },
  { to: '/pharmacist/stock-control', label: 'Batch Stock & Safety', icon: 'clipboard', group: 'Inventory', description: 'Review and manage operational workflows' },{to:'/pharmacist',label:'Pharmacist Dashboard',icon:'dashboard',end:true,group:'Overview',description:'Prescription, dispensing and inventory workload'},{to:'/pharmacist/rx-orders',label:'Prescription Queue',icon:'prescription',group:'Dispensing',description:'Validate, prepare and complete prescription orders'},{to:'/pharmacist/orders',label:'Medicine Orders',icon:'cart',group:'Dispensing',description:'Review customer orders and delivery status'},{to:'/pharmacist/inventory',label:'Medicine Inventory',icon:'pill',group:'Inventory',description:'Products, stock levels, pricing and availability'},{to:'/pharmacist/suppliers',label:'Suppliers',icon:'users',group:'Inventory',description:'Supplier contacts and supplied products'},
  { to: '/pharmacist/medicine-register', label: 'Uganda Medicine Register', icon: 'pill', group: 'Inventory', description: 'Search National Drug Authority reference records' },
]
export const routes=[
  { path: 'counter', element: <Counter /> },
  { path: 'shifts', element: <ShiftClosing /> },
  { path: 'transfers', element: <PharmacyTransfers /> },
  { path: 'safety', element: <PharmacySafety /> },
  { path: 'procurement', element: <Procurement /> },
  { path: 'stocktake', element: <Stocktake /> },
  { path: 'medicine-register', element: <MedicineRegister /> }, { path: 'stock-control', element: <StockControl /> },{index:true,element:<Dashboard/>},{path:'rx-orders',element:<RxOrders/>},{path:'orders',element:<Orders/>},{path:'inventory',element:<Inventory/>},{path:'suppliers',element:<Suppliers/>}]
