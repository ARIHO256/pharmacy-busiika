import * as doctor from '../doctor/routes.jsx'
import * as nurse from '../nurse/routes.jsx'
import * as reception from '../reception/routes.jsx'
import * as cashier from '../cashier/routes.jsx'
import * as facility from '../facility/routes.jsx'
import * as pharmacist from '../pharmacist/routes.jsx'
import * as insurance from '../insurance/routes.jsx'
import * as radiology from '../radiology/routes.jsx'
import * as emergency from '../emergency/routes.jsx'
import * as theatre from '../theatre/routes.jsx'

const CORE_BY_ROLE = {
  clinical_officer: { mod: doctor, base: 'doctor', label: 'Clinical practice' },
  dentist: { mod: doctor, base: 'doctor', label: 'Clinical practice' },
  physiotherapist: { mod: doctor, base: 'doctor', label: 'Clinical practice' },
  nutritionist: { mod: doctor, base: 'doctor', label: 'Clinical practice' },
  psychologist: { mod: doctor, base: 'doctor', label: 'Clinical practice' },
  medical_director: { mod: doctor, base: 'doctor', label: 'Clinical practice' },
  midwife: { mod: nurse, base: 'nurse', label: 'Nursing & maternity' },
  theatre_nurse: { mod: nurse, base: 'nurse', label: 'Nursing & theatre' },
  records_officer: { mod: reception, base: 'reception', label: 'Patient administration' },
  accountant: { mod: cashier, base: 'cashier', label: 'Billing operations' },
  finance_manager: { mod: facility, base: 'facility', label: 'Facility finance' },
  procurement_officer: { mod: facility, base: 'facility', label: 'Facility supply chain' },
  quality_officer: { mod: facility, base: 'facility', label: 'Quality operations' },
  compliance_officer: { mod: facility, base: 'facility', label: 'Compliance operations' },
  hr_officer: { mod: facility, base: 'facility', label: 'Workforce operations' },
  it_support: { mod: facility, base: 'facility', label: 'Platform operations' },
  storekeeper: { mod: pharmacist, base: 'pharmacist', label: 'Inventory operations' },
  insurance_officer: { mod: insurance, base: 'insurance', label: 'Insurance operations' },
  claims_reviewer: { mod: insurance, base: 'insurance', label: 'Claims operations' },
  radiographer: { mod: radiology, base: 'radiology', label: 'Imaging operations' },
  ambulance_dispatcher: { mod: emergency, base: 'emergency', label: 'Emergency operations' },
  paramedic: { mod: emergency, base: 'emergency', label: 'Emergency care' },
  anaesthetist: { mod: theatre, base: 'theatre', label: 'Peri-operative care' },
}

export function sharedCoreForRole(role, portalPath) {
  const config = CORE_BY_ROLE[role]
  if (!config) return { nav: [], routes: [] }
  const prefix = `/${config.base}`
  const nav = config.mod.nav
    .filter((item) => item.to?.startsWith(`${prefix}/`) && !item.to.includes('/workspace') && (!item.roles || item.roles.includes(role)))
    .map((item) => {
      const suffix = item.to.slice(prefix.length).replace(/^\//, '')
      return { ...item, to: `/${portalPath}/core/${suffix}`, group: config.label }
    })
  const routes = config.mod.routes
    .filter((route) => route.path && route.path !== 'workspaces' && !route.path.startsWith('workspace/'))
    .map((route) => ({ ...route, path: `core/${route.path}` }))
  return { nav, routes }
}
