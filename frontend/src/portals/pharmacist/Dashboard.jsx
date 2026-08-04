import { enterpriseApi, operationsApi, servicesApi } from '../../api/endpoints'
import RoleOperationsDashboard from '../deep/RoleOperationsDashboard'

const config = {
  eyebrow:'Clinical pharmacy', title:'Pharmacist dispensing and medicine-safety command centre', icon:'pill', gradient:'from-slate-950 via-emerald-950 to-emerald-700', description:'Prioritise prescription review, dispensing, medicine-safety interventions, controlled stock and expiring inventory without mixing organization administration into the clinical pharmacist experience.',
  sources:[
    {key:'prescriptions',label:'Prescription queue',icon:'prescription',load:()=>servicesApi.pharmacyOrders()},
    {key:'inventory',label:'Medicine inventory',icon:'pill',load:()=>operationsApi.inventoryItems()},
    {key:'safety',label:'Medication safety',icon:'shield',load:()=>enterpriseApi.records({record_type:'medication_safety_check'})},
    {key:'controlled',label:'Controlled stock',icon:'audit',load:()=>enterpriseApi.records({record_type:'controlled_drug_entry'})},
  ],
  metrics:[
    {label:'Prescriptions awaiting review',icon:'prescription',caption:'Clinical review before dispensing',calculate:(d)=>d.find(x=>x.key==='prescriptions')?.rows.filter(x=>!['completed','dispensed','cancelled'].includes(x.status)).length||0},
    {label:'Low-stock products',icon:'alert',caption:'At or below reorder level',calculate:(d)=>d.find(x=>x.key==='inventory')?.rows.filter(x=>Number(x.quantity_on_hand??x.quantity??0)<=Number(x.reorder_level??0)).length||0},
    {label:'Safety alerts',icon:'shield',caption:'Interactions and contraindications',calculate:(d)=>d.find(x=>x.key==='safety')?.rows.filter(x=>x.priority==='critical'||x.status!=='completed').length||0},
    {label:'Controlled entries',icon:'audit',caption:'Controlled medicine activity',calculate:(d)=>d.find(x=>x.key==='controlled')?.rows.length||0},
  ],
  checklist:['Confirm patient, prescriber and prescription authenticity','Review allergy, interaction and dose alerts','Use FEFO batch selection and preserve traceability','Counsel the patient and document the dispensing outcome'], queueTitle:'Clinical dispensing priorities', queueSubtitle:'Prescriptions, safety reviews and stock exceptions requiring action',
  actions:[
    {to:'dispensing',label:'Clinical dispensing',icon:'pill',description:'Review, select batches, dispense and counsel.'},{to:'rx-orders',label:'Prescription queue',icon:'prescription',description:'Validate and prepare incoming prescriptions.'},{to:'medication-safety',label:'Safety engine',icon:'shield',description:'Check interactions, allergies and contraindications.'},{to:'workspace/controlled-drug-register',label:'Controlled drugs',icon:'audit',description:'Maintain signed controlled-stock records.'},{to:'workspace/stock-count',label:'Stock count',icon:'box',description:'Count, investigate and approve variance.'},{to:'workspace/cold-chain-chart',label:'Cold chain',icon:'activity',description:'Monitor temperature and excursions.'},{to:'workspace/expiry-calendar',label:'Expiry calendar',icon:'calendar',description:'Prioritise short-dated stock.'},{to:'workspaces',label:'All pharmacy pages',icon:'dashboard',description:'Open the complete pharmacist page centre.'},
  ],
}
export default function Dashboard(){ return <RoleOperationsDashboard config={config}/> }
