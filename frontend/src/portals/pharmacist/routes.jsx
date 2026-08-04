import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import RxOrders from '../pharmacy/RxOrders'
import Inventory from '../pharmacy/Inventory'
import Orders from '../pharmacy/Orders'
import Suppliers from '../pharmacy/Suppliers'
import Dispensing from './Dispensing'
import InventoryControl from '../operations/InventoryControl'
import Procurement from '../operations/Procurement'
import SupportCentre from '../operations/SupportCentre'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import MedicationSafetyWorkbench from '../enterprise/MedicationSafetyWorkbench'
import { PHARMACY_CONTROL, PHARMACY_SAFETY } from '../enterprise/coreModules'

export const nav = [
  { to: '/pharmacist', label: 'Pharmacist Dashboard', icon: 'dashboard', end: true, group: 'Overview', description: 'Prescription, dispensing and inventory workload' },
  { to: '/pharmacist/dispensing', roles: ['pharmacist'], label: 'Clinical Dispensing', icon: 'pill', group: 'Dispensing', description: 'Review, partial fulfilment, batch traceability and counselling' },
  { to: '/pharmacist/rx-orders', roles: ['pharmacist'], label: 'Prescription Queue', icon: 'prescription', group: 'Dispensing', description: 'Validate and prepare prescription orders' },
  { to: '/pharmacist/orders', roles: ['pharmacist'], label: 'Medicine Orders', icon: 'cart', group: 'Dispensing', description: 'Review customer orders and delivery status' },
  { to: '/pharmacist/inventory', label: 'Medicine Inventory', icon: 'pill', group: 'Inventory', description: 'Products, stock levels, pricing and availability' },
  { to: '/pharmacist/suppliers', label: 'Suppliers', icon: 'users', group: 'Inventory', description: 'Supplier contacts and supplied products' },
  { to: '/pharmacist/batches', label: 'Batch & Expiry Control', icon: 'activity', group: 'Inventory', description: 'Batch receiving, FEFO, recalls and movement ledger' },
  { to: '/pharmacist/procurement', label: 'Procurement', icon: 'file', group: 'Inventory', description: 'Purchase orders and stock replenishment' },
  { to: '/pharmacist/medication-safety', roles: ['pharmacist'], label: 'Medication Safety Engine', icon: 'shield', group: 'Clinical pharmacy', description: 'Interactions, allergies, contraindications and dosing guidance' },
  { to: '/pharmacist/safety-events', roles: ['pharmacist'], label: 'Medication Safety Records', icon: 'activity', group: 'Clinical pharmacy', description: 'Adverse reactions, safety reviews and dispensing labels' },
  { to: '/pharmacist/controlled-stock', label: 'Controlled Stock Governance', icon: 'audit', group: 'Inventory', description: 'Controlled medicines, cold chain, counts and recalls' },
  { to: '/pharmacist/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Prescription and inventory support' },

  ...deepNav('pharmacist', 'pharmacist', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'dispensing', element: <Dispensing /> },
  { path: 'rx-orders', element: <RxOrders /> },
  { path: 'orders', element: <Orders /> },
  { path: 'inventory', element: <Inventory /> },
  { path: 'suppliers', element: <Suppliers /> },
  { path: 'batches', element: <InventoryControl /> },
  { path: 'procurement', element: <Procurement /> },
  { path: 'medication-safety', element: <MedicationSafetyWorkbench /> },
  { path: 'safety-events', element: <RecordWorkspace module={PHARMACY_SAFETY} /> },
  { path: 'controlled-stock', element: <RecordWorkspace module={PHARMACY_CONTROL} /> },
  { path: 'support', element: <SupportCentre /> },

  ...deepRoutes('pharmacist', 'pharmacist', { title: 'Pharmacy professional page centre' }),
]
