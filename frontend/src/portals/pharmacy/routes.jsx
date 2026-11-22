import ManageTaxonomy from './ManageTaxonomy'
import StaffAccess from './StaffAccess'
import Counter from './Counter'
import ShiftClosing from './ShiftClosing'
import { Procurement, Stocktake } from './InventoryWorkflows'
import MedicineRegister from './MedicineRegister'
import StockControl from './StockControl'
import Dashboard from './Dashboard'
import Inventory from './Inventory'
import Orders from './Orders'
import RxOrders from './RxOrders'
import Suppliers from './Suppliers'
import { ProviderProfile } from './shared'

export const nav=[
  { to: '/pharmacy/taxonomy', label: 'Manage Taxonomy', icon: 'settings', group: 'Settings' },
  { to: '/pharmacy/staff', label: 'Staff & Access', icon: 'users', group: 'Settings' },
  { to: '/pharmacy/counter', label: 'New Sale', icon: 'cart', group: 'Sales', roles: ['pharmacy', 'pharmacist', 'cashier'] },
  { to: '/pharmacy/shifts', label: 'Cash Shifts', icon: 'money', group: 'Sales', roles: ['pharmacy', 'pharmacist', 'cashier'] },
  { to: '/pharmacy/procurement', label: 'Procurement', icon: 'building', group: 'Inventory', description: 'Purchase orders and supplier deliveries' },
  { to: '/pharmacy/stocktake', label: 'Stocktake', icon: 'clipboard', group: 'Inventory', description: 'Physical counts and stock adjustments' },
  { to: '/pharmacy/stock-control', label: 'Batch Stock & Safety', icon: 'clipboard', group: 'Inventory', description: 'Review and manage operational workflows' },
  { to: '/pharmacy', label: 'Operations Home', icon: 'dashboard', end: true, group: 'Overview', description: 'Orders, stock alerts and fulfilment' },
  { to: '/pharmacy/rx-orders', label: 'Prescription Queue', icon: 'prescription', group: 'Dispensing', description: 'Review and verify e-prescriptions' },
  { to: '/pharmacy/orders', label: 'Orders & Delivery', icon: 'truck', group: 'Dispensing', description: 'Fulfilment, collection and dispatch' },
  { to: '/pharmacy/inventory', label: 'Medicine Inventory', icon: 'box', group: 'Inventory', description: 'Stock, batches and availability' },
  { to: '/pharmacy/suppliers', label: 'Suppliers', icon: 'building', group: 'Inventory', description: 'Supply relationships and restocking' },
  { to: '/pharmacy/profile', label: 'Pharmacy Profile', icon: 'settings', group: 'Settings', description: 'Branches, licences and service settings' },
  { to: '/pharmacy/medicine-register', label: 'Uganda Medicine Register', icon: 'pill', group: 'Inventory', description: 'Search National Drug Authority reference records' },
]

export const routes=[
  { path: 'taxonomy', element: <ManageTaxonomy /> },
  { path: 'staff', element: <StaffAccess /> },
  { path: 'counter', element: <Counter /> },
  { path: 'shifts', element: <ShiftClosing /> },
  { path: 'procurement', element: <Procurement /> },
  { path: 'stocktake', element: <Stocktake /> },
  { path: 'medicine-register', element: <MedicineRegister /> }, { path: 'stock-control', element: <StockControl /> },
  { index: true, element: <Dashboard /> },
  { path: 'inventory', element: <Inventory /> },
  { path: 'orders', element: <Orders /> },
  { path: 'rx-orders', element: <RxOrders /> },
  { path: 'suppliers', element: <Suppliers /> },
  { path: 'profile', element: <ProviderProfile /> },
]
