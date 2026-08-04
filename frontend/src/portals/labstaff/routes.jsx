import { deepNav, deepRoutes } from '../deep/routes'
import Dashboard from './Dashboard'
import Orders from '../lab/Orders'
import SpecimenTracking from '../lab/SpecimenTracking'
import Tests from '../lab/Tests'
import InventoryControl from '../operations/InventoryControl'
import SupportCentre from '../operations/SupportCentre'
import RecordWorkspace from '../enterprise/RecordWorkspace'
import { LAB_QUALITY, LAB_SPECIMEN, LAB_SPECIALTY } from '../enterprise/coreModules'

export const nav = [
  { to: '/lab-staff', label: 'Laboratory Dashboard', icon: 'dashboard', end: true, group: 'Overview', description: 'Specimen, test and result workload' },
  { to: '/lab-staff/orders', label: 'Test Worklist', icon: 'flask', group: 'Diagnostics', description: 'Referred tests, processing, validation and result release' },
  { to: '/lab-staff/specimens', label: 'Specimen Custody', icon: 'activity', group: 'Diagnostics', description: 'Barcode, collection, transfer, rejection, storage and disposal' },
  { to: '/lab-staff/tests', label: 'Test Catalogue', icon: 'clipboard', group: 'Diagnostics', description: 'Available tests, sample types and prices' },
  { to: '/lab-staff/reagents', label: 'Reagents & Supplies', icon: 'pill', group: 'Laboratory operations', description: 'Reagent batches, expiry and stock movements' },
  { to: '/lab-staff/quality', label: 'Quality & Calibration', icon: 'shield', group: 'Laboratory operations', description: 'QC, equipment calibration, analyser imports and reference ranges' },
  { to: '/lab-staff/advanced-specimens', label: 'Aliquots & Storage', icon: 'flask', group: 'Diagnostics', description: 'Advanced sample custody, storage and disposal records' },
  { to: '/lab-staff/specialty', label: 'Microbiology & Blood Bank', icon: 'activity', group: 'Diagnostics', description: 'Culture, susceptibility and blood-bank workflows' },
  { to: '/lab-staff/support', label: 'Support', icon: 'help', group: 'Settings', description: 'Diagnostic workflow support' },

  ...deepNav('lab-staff', 'lab_technician', { label: 'Complete page centre', group: 'Professional tools' }),
]

export const routes = [
  { index: true, element: <Dashboard /> },
  { path: 'orders', element: <Orders /> },
  { path: 'specimens', element: <SpecimenTracking /> },
  { path: 'tests', element: <Tests /> },
  { path: 'reagents', element: <InventoryControl /> },
  { path: 'quality', element: <RecordWorkspace module={LAB_QUALITY} /> },
  { path: 'advanced-specimens', element: <RecordWorkspace module={LAB_SPECIMEN} /> },
  { path: 'specialty', element: <RecordWorkspace module={LAB_SPECIALTY} /> },
  { path: 'support', element: <SupportCentre /> },

  ...deepRoutes('lab-staff', 'lab_technician', { title: 'Laboratory professional page centre' }),
]
