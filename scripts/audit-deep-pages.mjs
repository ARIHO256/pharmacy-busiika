#!/usr/bin/env node
import fs from 'node:fs'
import { PAGE_CATALOG } from '../frontend/src/portals/deep/pageCatalog.js'

const expectedRoles = [
  'patient','doctor','clinical_officer','dentist','physiotherapist','nutritionist','psychologist','medical_director',
  'nurse','midwife','theatre_nurse','receptionist','records_officer','cashier','accountant','finance_manager',
  'pharmacist','storekeeper','lab_technician','radiologist','radiographer','anaesthetist','paramedic','ambulance_dispatcher',
  'facility_manager','procurement_officer','quality_officer','compliance_officer','hr_officer','it_support',
  'insurance','insurance_officer','claims_reviewer','hospital','pharmacy','lab','admin',
]
const missingRoles = expectedRoles.filter((role) => !PAGE_CATALOG[role]?.length)
if (missingRoles.length) throw new Error(`Missing deep page catalogues: ${missingRoles.join(', ')}`)

const requiredSlugs = [
  'appointment-detail','virtual-waiting-room','diagnostic-viewer','consent-centre','dependent-dashboard',
  'my-patients','results-inbox','critical-results','order-entry','medical-certificates','on-call-schedule',
  'assigned-patients','emar','fluid-balance','early-warning','nursing-handover',
  'appointment-calendar','provider-schedules','patient-arrival-board','queue-ticket','call-centre',
  'master-patient-index','merge-wizard','record-release','legal-holds','data-export',
  'patient-account','split-payment','bank-reconciliation','general-ledger','income-statement','budget-management',
  'prescription-workspace','controlled-drug-register','stock-count','goods-received','cold-chain-chart',
  'collection-worklist','barcode-scanner','validation-queue','critical-escalation','blood-bank','quality-control',
  'imaging-calendar','modality-worklist','pacs-viewer','reporting-editor','radiation-dose',
  'dispatch-map','call-intake','trauma-chart','resuscitation-timeline','mass-casualty',
  'theatre-calendar','pre-anaesthetic','anaesthesia-chart','instrument-count','recovery-observation','sterilization',
  'antenatal-dashboard','visual-partograph','birth-record','newborn-assessment','immunization-calendar','growth-chart',
  'multi-branch-dashboard','visual-bed-map','bed-turnover','staff-onboarding','infection-control','regulatory-reporting',
  'member-directory','plan-designer','preauthorization-workbench','claim-line-adjudication','fraud-investigation','loss-ratio',
  'user-detail','role-matrix','verification-case','notification-monitor','dead-letter','backup-restore','maintenance-mode',
]
const allSlugs = new Set(Object.values(PAGE_CATALOG).flat().map((page) => page.slug))
const missingSlugs = requiredSlugs.filter((slug) => !allSlugs.has(slug))
if (missingSlugs.length) throw new Error(`Missing required deep pages: ${missingSlugs.join(', ')}`)

const routeFiles = [
  'patient','doctor','nurse','reception','cashier','facility','pharmacist','labstaff','radiology','emergency','theatre','insurance','admin','hospital','pharmacy','lab',
]
for (const portal of routeFiles) {
  const source = fs.readFileSync(new URL(`../frontend/src/portals/${portal}/routes.jsx`, import.meta.url), 'utf8')
  if (!source.includes('deepNav(') || !source.includes('deepRoutes(')) throw new Error(`${portal} does not expose its complete page centre`)
}
const enterpriseRoutes = fs.readFileSync(new URL('../frontend/src/portals/enterprise/routes.jsx', import.meta.url), 'utf8')
if (!enterpriseRoutes.includes('deepNav(portal.path, role') || !enterpriseRoutes.includes('deepRoutes(portal.path, role')) throw new Error('Enterprise role portals are not connected to role-specific deep pages')

const pageCount = [...new Map(Object.values(PAGE_CATALOG).flat().map((page) => [page.slug, page])).values()].length
const rolePageLinks = Object.values(PAGE_CATALOG).reduce((sum, pages) => sum + pages.length, 0)
console.log(`Deep page catalogue: ${pageCount} unique pages, ${rolePageLinks} role-page links, ${expectedRoles.length} roles passed`)
