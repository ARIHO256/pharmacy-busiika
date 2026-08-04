// Patient portal extension routes — messages, prescriptions, connected services.
// The lead agent merges these into portals/patient/routes.jsx.
import React from 'react'
import Messages from './Messages'
import Prescriptions from './Prescriptions'
import PharmacyStore from './PharmacyStore'
import LabTests from './LabTests'
import Hospitals from './Hospitals'
import Insurance from './Insurance'

export const navExt = [
  { to: 'messages', label: 'Messages', icon: '💬' },
  { to: 'prescriptions', label: 'Prescriptions', icon: '📋' },
  { to: 'store', label: 'Pharmacy', icon: '💊' },
  { to: 'labs', label: 'Lab Tests', icon: '🧪' },
  { to: 'hospitals', label: 'Hospitals', icon: '🏥' },
  { to: 'insurance', label: 'Insurance', icon: '🛡️' },
]

export const routesExt = [
  { path: 'messages', element: <Messages /> },
  { path: 'prescriptions', element: <Prescriptions /> },
  { path: 'store', element: <PharmacyStore /> },
  { path: 'labs', element: <LabTests /> },
  { path: 'hospitals', element: <Hospitals /> },
  { path: 'insurance', element: <Insurance /> },
]
