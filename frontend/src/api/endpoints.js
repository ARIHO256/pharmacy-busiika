import client from './client'

// ===== auth & accounts =====
export const authApi = {
  login: (email, password) => client.post('/auth/token/', { email, password }),
  verifyMfa: (challenge_id, code) => client.post('/auth/mfa/verify/', { challenge_id, code }),
  forgotPassword: (email) => client.post('/auth/password/forgot/', { email }),
  resetPassword: (token_id, token, password) => client.post('/auth/password/reset/', { token_id, token, password }),
  changePassword: (payload) => client.post('/auth/password/change/', payload),
  requestEmailVerification: () => client.post('/auth/email-verification/request/'),
  requestPhoneVerification: () => client.post('/auth/phone-verification/request/'),
  verifyPhone: (token_id, code) => client.post('/auth/phone-verification/verify/', { token_id, code }),
  sessions: () => client.get('/auth/sessions/'),
  revokeSession: (token_id = 'all') => client.post('/auth/sessions/', { token_id }),
  logout: (refresh) => client.post('/auth/logout/', { refresh }),
  verifyEmail: (token_id, token) => client.post('/auth/email-verification/verify/', { token_id, token }),
  security: () => client.get('/auth/security/'),
  updateSecurity: (payload) => client.patch('/auth/security/', payload),
  securityEvents: () => client.get('/auth/security/events/'),
  register: (payload) => client.post('/auth/register/', payload),
  invitation: (token) => client.get(`/workforce/invitations/${token}/`),
  acceptInvitation: (token, payload) => client.post(`/workforce/invitations/${token}/`, payload),
  me: () => client.get('/auth/me/'),
  updateMe: (payload) => client.patch('/auth/me/', payload),
  updateProfile: (payload) => client.patch('/auth/me/profile/', payload),
  dependents: () => client.get('/auth/dependents/'),
  addDependent: (payload) => client.post('/auth/dependents/', payload, { headers: { 'Content-Type': 'multipart/form-data' } }),
  updateDependent: (id, payload) => client.patch(`/auth/dependents/${id}/`, payload, { headers: { 'Content-Type': 'multipart/form-data' } }),
  revokeDependent: (id) => client.delete(`/auth/dependents/${id}/`),
  doctors: (params) => client.get('/doctors/', { params }),
  doctor: (id) => client.get(`/doctors/${id}/`),
  uploadLicense: (formData) =>
    client.post('/doctors/verify-upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

// ===== appointments =====
export const appointmentApi = {
  slots: (doctorId, date) => client.get(`/doctors/${doctorId}/slots/`, { params: { date } }),
  book: (payload) => client.post('/appointments/', payload),
  list: (params) => client.get('/appointments/', { params }),
  act: (id, action) => client.post(`/appointments/${id}/${action}/`),
  myAvailability: () => client.get('/availability/'),
  saveAvailability: (payload) => client.post('/availability/', payload),
  deleteAvailability: (id) => client.delete(`/availability/${id}/`),
}

// ===== communication =====
export const chatApi = {
  conversations: () => client.get('/conversations/'),
  open: (doctorId) => client.post('/conversations/', { doctor_id: doctorId }),
  messages: (id) => client.get(`/conversations/${id}/messages/`),
  send: (id, formData) =>
    client.post(`/conversations/${id}/messages/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  notifications: (params) => client.get('/notifications/', { params }),
  markRead: (id) => client.post(`/notifications/${id}/read/`),
  markAllRead: () => client.post('/notifications/read-all/'),
  preferences: () => client.get('/notifications/preferences/'),
  updatePreferences: (payload) => client.patch('/notifications/preferences/', payload),
  videoRoom: (appointmentId) => client.get(`/appointments/${appointmentId}/video-room/`),
}

// ===== payments =====
export const paymentApi = {
  initiate: (payload) => client.post('/payments/initiate/', payload),
  status: (invoiceNumber) => client.get(`/payments/status/${invoiceNumber}/`),
  invoices: () => client.get('/payments/invoices/'),
  receipt: (id) => client.get(`/payments/invoices/${id}/receipt/`),
  invoicePdf: (id) => client.get(`/payments/invoices/${id}/pdf/`, { responseType: 'blob' }),
  sendInvoice: (id) => client.post(`/payments/invoices/${id}/send/`),
  receiptPdf: (id) => client.get(`/payments/receipts/${id}/pdf/`, { responseType: 'blob' }),
  earnings: () => client.get('/payments/earnings/'),
  withdraw: (amount) => client.post('/payments/withdraw/', { amount }),
}

// ===== prescriptions =====
export const prescriptionApi = {
  create: (appointmentId, payload) =>
    client.post(`/appointments/${appointmentId}/prescription/`, payload),
  list: () => client.get('/prescriptions/'),
  detail: (id) => client.get(`/prescriptions/${id}/`),
  sendToPharmacy: (id, pharmacyId) =>
    client.post(`/prescriptions/${id}/send-to-pharmacy/`, { pharmacy_id: pharmacyId }),
}

// ===== services =====
export const servicesApi = {
  providers: (kind, params) => client.get(`/services/${kind}/`, { params }),
  medicines: (params) => client.get('/services/medicines/', { params }),
  saveMedicine: (payload) => client.post('/services/medicines/', payload),
  deleteMedicine: (id) => client.delete(`/services/medicines/${id}/`),
  cart: () => client.get('/services/cart/'),
  addCart: (medicine_id, qty) => client.post('/services/cart/', { medicine_id, qty }),
  removeCart: (id) => client.delete(`/services/cart/${id}/`),
  checkout: (payload) => client.post('/services/orders/checkout/', payload),
  orders: () => client.get('/services/orders/'),
  updateOrder: (id, status) => client.post(`/services/orders/${id}/update/`, { status }),
  pharmacyOrders: () => client.get('/services/pharmacy-orders/'),
  updatePharmacyOrder: (id, status) =>
    client.post(`/services/pharmacy-orders/${id}/update/`, { status }),
  dispensingRecords: (id) => client.get(`/services/pharmacy-orders/${id}/dispensing/`),
  recordDispensing: (id, payload) => client.post(`/services/pharmacy-orders/${id}/dispensing/`, payload),
  suppliers: () => client.get('/services/suppliers/'),
  saveSupplier: (payload) => client.post('/services/suppliers/', payload),
  deleteSupplier: (id) => client.delete(`/services/suppliers/${id}/`),
  labPanels: (params) => client.get('/services/lab-panels/', { params }),
  saveLabPanel: (payload) => client.post('/services/lab-panels/', payload),
  updateLabPanel: (id, payload) => client.patch(`/services/lab-panels/${id}/`, payload),
  deleteLabPanel: (id) => client.delete(`/services/lab-panels/${id}/`),
  orderLabPanel: (id, payload) => client.post(`/services/lab-panels/${id}/order/`, payload),
  labTests: (params) => client.get('/services/lab-tests/', { params }),
  saveLabTest: (payload) => client.post('/services/lab-tests/', payload),
  bookLab: (payload) => client.post('/services/lab-orders/', payload),
  labOrdersManage: () => client.get('/services/lab-orders/manage/'),
  updateLabOrder: (id, formData) =>
    client.post(`/services/lab-orders/${id}/update/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  myLabOrders: () => client.get('/services/lab-orders/'),
  labResults: (orderId) => client.get(`/services/lab-orders/${orderId}/results/`),
  publishLabResult: (orderId, payload) => client.post(`/services/lab-orders/${orderId}/results/`, payload),
  acknowledgeCriticalResult: (resultId, notes = '') => client.post(`/services/lab-results/${resultId}/acknowledge/`, { notes }),
  specimenEvents: (orderId) => client.get(`/services/lab-orders/${orderId}/specimen-events/`),
  addSpecimenEvent: (orderId, payload) => client.post(`/services/lab-orders/${orderId}/specimen-events/`, payload),
  hospitalServices: (params) => client.get('/services/hospital-services/', { params }),
  saveHospitalService: (payload) => client.post('/services/hospital-services/', payload),
  bookHospital: (payload) => client.post('/services/hospital-bookings/', payload),
  hospitalBookingsManage: () => client.get('/services/hospital-bookings/manage/'),
  updateHospitalBooking: (id, status) =>
    client.post(`/services/hospital-bookings/${id}/update/`, { status }),
  beds: () => client.get('/services/beds/'),
  saveBed: (payload) => client.post('/services/beds/', payload),
  toggleBed: (id) => client.post(`/services/beds/${id}/toggle/`),
  policies: (params) => client.get('/services/policies/', { params }),
  savePolicy: (payload) => client.post('/services/policies/', payload),
  updatePolicy: (id, payload) => client.patch(`/services/policies/${id}/`, payload),
  policyBenefits: (policyId) => client.get(`/services/policies/${policyId}/benefits/`),
  savePolicyBenefit: (policyId, payload) => client.post(`/services/policies/${policyId}/benefits/`, payload),
  updatePolicyBenefit: (id, payload) => client.patch(`/services/policy-benefits/${id}/`, payload),
  deletePolicyBenefit: (id) => client.delete(`/services/policy-benefits/${id}/`),
  verifyCoverage: (payload) => client.post('/services/coverage/verify/', payload),
  eligibilityHistory: () => client.get('/services/coverage/eligibility-history/'),
  preauthorizations: (params) => client.get('/services/preauthorizations/', { params }),
  requestPreauthorization: (payload) => client.post('/services/preauthorizations/', payload),
  decidePreauthorization: (id, payload) => client.post(`/services/preauthorizations/${id}/decide/`, payload),
  submitClaim: (payload) => client.post('/services/claims/', payload),
  myClaims: () => client.get('/services/claims/'),
  claimsManage: (params) => client.get('/services/claims/manage/', { params }),
  decideClaim: (id, payload) => client.post(`/services/claims/${id}/decide/`, typeof payload === 'string' ? { action: payload } : payload),
  remittances: () => client.get('/services/remittances/'),
  myCoverage: () => client.get('/services/coverage/'),
}

// ===== reviews =====
export const reviewApi = {
  add: (appointmentId, payload) => client.post(`/appointments/${appointmentId}/review/`, payload),
  forDoctor: (doctorId) => client.get(`/doctors/${doctorId}/reviews/`),
}

// ===== admin =====
export const adminApi = {
  overview: () => client.get('/admin/overview/'),
  users: (params) => client.get('/admin/users/', { params }),
  setStatus: (id, payload) => client.post(`/admin/users/${id}/set-status/`, payload),
  appointments: (params) => client.get('/admin/appointments/', { params }),
  finance: () => client.get('/admin/finance/'),
  reviews: () => client.get('/admin/reviews/'),
  audit: () => client.get('/admin/audit/'),
}


// ===== provider/facility registries =====
export const registryApi = {
  organizations: (params) => client.get('/registry/organizations/', { params }),
  myOrganizations: () => client.get('/registry/organizations/mine/'),
  organization: (publicId) => client.get(`/registry/organizations/${publicId}/`),
  updateOrganization: (publicId, payload) => client.patch(`/registry/organizations/${publicId}/`, payload),
  setOrganizationStatus: (publicId, status, reason = '') => client.post(`/registry/organizations/${publicId}/status/`, { status, reason }),
  credentials: (params) => client.get('/registry/credentials/', { params }),
  createCredential: (payload) => client.post('/registry/credentials/', payload),
  verifyCredential: (id, status, reason = '') => client.post(`/registry/credentials/${id}/verify/`, { status, reason }),
  practitionerRoles: (params) => client.get('/registry/practitioner-roles/', { params }),
  careRelationships: (params) => client.get('/registry/care-relationships/', { params }),
}

// ===== standards and integration =====
export const interoperabilityApi = {
  capabilityStatement: () => client.get('/interoperability/fhir/metadata/'),
  patientSummary: (patientId) => client.get(`/interoperability/fhir/patients/${patientId}/summary/`),
  terminology: (params) => client.get('/interoperability/terminology/concepts/', { params }),
  outbox: (params) => client.get('/interoperability/outbox/', { params }),
}

// ===== longitudinal clinical record =====
const patientParam = (patientId) => (patientId ? { patient_id: patientId } : undefined)

export const clinicalApi = {
  summary: (patientId) => client.get('/clinical/summary/', { params: patientParam(patientId) }),
  timeline: (patientId) => client.get('/clinical/timeline/', { params: patientParam(patientId) }),
  allergies: (patientId) => client.get('/clinical/allergies/', { params: patientParam(patientId) }),
  addAllergy: (payload, patientId) => client.post('/clinical/allergies/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
  updateAllergy: (id, payload) => client.patch(`/clinical/allergies/${id}/`, payload),
  conditions: (patientId) => client.get('/clinical/conditions/', { params: patientParam(patientId) }),
  addCondition: (payload, patientId) => client.post('/clinical/conditions/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
  updateCondition: (id, payload) => client.patch(`/clinical/conditions/${id}/`, payload),
  medications: (patientId) => client.get('/clinical/medications/', { params: patientParam(patientId) }),
  addMedication: (payload, patientId) => client.post('/clinical/medications/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
  updateMedication: (id, payload) => client.patch(`/clinical/medications/${id}/`, payload),
  observations: (patientId, category) => client.get('/clinical/observations/', { params: { ...(patientId ? { patient_id: patientId } : {}), ...(category ? { category } : {}) } }),
  addObservation: (payload, patientId) => client.post('/clinical/observations/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
  encounters: (patientId) => client.get('/clinical/encounters/', { params: patientParam(patientId) }),
  saveEncounter: (payload) => client.post('/clinical/encounters/', payload),
  updateEncounter: (id, payload) => client.patch(`/clinical/encounters/${id}/`, payload),
  finalizeEncounter: (id) => client.post(`/clinical/encounters/${id}/finalize/`),
  amendEncounter: (id, payload) => client.post(`/clinical/encounters/${id}/amend/`, payload),
  referrals: (patientId, params = {}) => client.get('/clinical/referrals/', { params: { ...(patientParam(patientId) || {}), ...params } }),
  addReferral: (payload, patientId) => client.post('/clinical/referrals/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
  referralAction: (id, action, payload = {}) => client.post(`/clinical/referrals/${id}/action/`, { action, ...payload }),
  carePlans: (patientId) => client.get('/clinical/care-plans/', { params: patientParam(patientId) }),
  addCarePlan: (payload, patientId) => client.post('/clinical/care-plans/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
}

// ===== privacy, consent & compliance =====
export const governanceApi = {
  consents: () => client.get('/governance/consents/'),
  grantConsent: (payload) => client.post('/governance/consents/', payload),
  revokeConsent: (id, reason) => client.post(`/governance/consents/${id}/revoke/`, { reason }),
  patientConsents: (patientId) => client.get(`/governance/patients/${patientId}/consents/`),
  breakGlass: () => client.get('/governance/break-glass/'),
  startBreakGlass: (payload) => client.post('/governance/break-glass/', payload),
  endBreakGlass: (id) => client.post(`/governance/break-glass/${id}/end/`),
  reviewBreakGlass: (id, payload) => client.post(`/governance/break-glass/${id}/review/`, payload),
  complianceOverview: () => client.get('/governance/compliance/overview/'),
  auditEvents: (params) => client.get('/governance/audit/', { params }),
}


// ===== facility workforce & patient flow =====
export const workforceApi = {
  summary: () => client.get('/workforce/summary/'),
  departments: () => client.get('/workforce/departments/'),
  createDepartment: (payload) => client.post('/workforce/departments/', payload),
  staff: () => client.get('/workforce/staff/'),
  inviteStaff: (payload) => client.post('/workforce/staff/', payload),
  setStaffStatus: (id, status) => client.post(`/workforce/staff/${id}/status/`, { status }),
  patients: (search = '') => client.get('/workforce/patients/', { params: { search } }),
  registerPatient: (payload) => client.post('/workforce/patients/', payload),
  visits: (params) => client.get('/workforce/visits/', { params }),
  checkIn: (payload) => client.post('/workforce/visits/', payload),
  updateVisit: (id, payload) => client.post(`/workforce/visits/${id}/action/`, payload),
  triage: (params) => client.get('/workforce/triage/', { params }),
  saveTriage: (payload) => client.post('/workforce/triage/', payload),
  nursingNotes: (params) => client.get('/workforce/nursing-notes/', { params }),
  addNursingNote: (payload) => client.post('/workforce/nursing-notes/', payload),
  medicationAdministrations: (params) => client.get('/workforce/medication-administrations/', { params }),
  recordMedicationAdministration: (payload) => client.post('/workforce/medication-administrations/', payload),
}

// ===== cashier, invoices and printable receipts =====
export const billingApi = {
  summary: () => client.get('/billing/summary/'),
  invoices: (params) => client.get('/billing/invoices/', { params }),
  createInvoice: (payload) => client.post('/billing/invoices/', payload),
  recordPayment: (invoiceId, payload) => client.post(`/billing/invoices/${invoiceId}/payments/`, payload),
  receipt: (receiptId) => client.get(`/payments/receipts/${receiptId}/`),
  invoicePdf: (invoiceId) => client.get(`/payments/invoices/${invoiceId}/pdf/`, { responseType: 'blob' }),
  receiptPdf: (receiptId) => client.get(`/payments/receipts/${receiptId}/pdf/`, { responseType: 'blob' }),
  sendInvoice: (invoiceId) => client.post(`/payments/invoices/${invoiceId}/send/`),
  shifts: () => client.get('/billing/shifts/'),
  openShift: (payload = {}) => client.post('/billing/shifts/', payload),
  closeShift: (shiftId, payload = {}) => client.post(`/billing/shifts/${shiftId}/close/`, payload),
  adjustments: () => client.get('/billing/adjustments/'),
  requestAdjustment: (payload) => client.post('/billing/adjustments/', payload),
  actAdjustment: (id, action, note = '') => client.post(`/billing/adjustments/${id}/action/`, { action, note }),
  refunds: () => client.get('/billing/refunds/'),
  requestRefund: (payload) => client.post('/billing/refunds/', payload),
  actRefund: (id, action, note = '') => client.post(`/billing/refunds/${id}/action/`, { action, note }),
}

// ===== enterprise operations: inpatient, imaging, inventory, subscriptions and support =====
export const operationsApi = {
  summary: (params) => client.get('/operations/summary/', { params }),
  wards: (params) => client.get('/operations/wards/', { params }),
  createWard: (payload) => client.post('/operations/wards/', payload),
  beds: (params) => client.get('/operations/beds/', { params }),
  createBed: (payload) => client.post('/operations/beds/', payload),
  admissions: (params) => client.get('/operations/admissions/', { params }),
  createAdmission: (payload) => client.post('/operations/admissions/', payload),
  actAdmission: (id, payload) => client.post(`/operations/admissions/${id}/action/`, payload),
  dischargeSummary: (id, payload) => payload ? client.post(`/operations/admissions/${id}/discharge-summary/`, payload) : client.get(`/operations/admissions/${id}/discharge-summary/`),
  wardTasks: (params) => client.get('/operations/ward-tasks/', { params }),
  createWardTask: (payload) => client.post('/operations/ward-tasks/', payload),
  actWardTask: (id, payload) => client.post(`/operations/ward-tasks/${id}/action/`, payload),
  clinicalRounds: (params) => client.get('/operations/clinical-rounds/', { params }),
  createClinicalRound: (payload) => client.post('/operations/clinical-rounds/', payload),
  imagingOrders: (params) => client.get('/operations/imaging-orders/', { params }),
  createImagingOrder: (payload) => client.post('/operations/imaging-orders/', payload),
  actImagingOrder: (id, payload) => client.post(`/operations/imaging-orders/${id}/action/`, payload),
  imagingReport: (id) => client.get(`/operations/imaging-orders/${id}/report/`),
  saveImagingReport: (id, payload) => client.post(`/operations/imaging-orders/${id}/report/`, payload),
  inventoryItems: (params) => client.get('/operations/inventory/items/', { params }),
  createInventoryItem: (payload) => client.post('/operations/inventory/items/', payload),
  inventoryBatches: (params) => client.get('/operations/inventory/batches/', { params }),
  createInventoryBatch: (payload) => client.post('/operations/inventory/batches/', payload),
  stockMovements: (params) => client.get('/operations/inventory/movements/', { params }),
  createStockMovement: (payload) => client.post('/operations/inventory/movements/', payload),
  purchaseOrders: (params) => client.get('/operations/procurement/purchase-orders/', { params }),
  createPurchaseOrder: (payload) => client.post('/operations/procurement/purchase-orders/', payload),
  actPurchaseOrder: (id, action) => client.post(`/operations/procurement/purchase-orders/${id}/action/`, { action }),
  subscriptionPlans: (params) => client.get('/operations/subscriptions/plans/', { params }),
  createSubscriptionPlan: (payload) => client.post('/operations/subscriptions/plans/', payload),
  subscriptions: () => client.get('/operations/subscriptions/'),
  subscribe: (payload) => client.post('/operations/subscriptions/', payload),
  cancelSubscription: (id) => client.post(`/operations/subscriptions/${id}/cancel/`),
  supportTickets: () => client.get('/operations/support/tickets/'),
  createSupportTicket: (payload) => client.post('/operations/support/tickets/', payload),
  actSupportTicket: (id, payload) => client.post(`/operations/support/tickets/${id}/action/`, payload),
  announcements: () => client.get('/operations/announcements/'),
  analytics: (params) => client.get('/operations/analytics/enterprise/', { params }),
  emergencyCases: (params) => client.get('/operations/emergency/cases/', { params }),
  createEmergencyCase: (payload) => client.post('/operations/emergency/cases/', payload),
  actEmergencyCase: (id, payload) => client.post(`/operations/emergency/cases/${id}/action/`, payload),
  ambulanceDispatches: (params) => client.get('/operations/emergency/dispatches/', { params }),
  createAmbulanceDispatch: (payload) => client.post('/operations/emergency/dispatches/', payload),
  actAmbulanceDispatch: (id, payload) => client.post(`/operations/emergency/dispatches/${id}/action/`, payload),
  surgicalCases: (params) => client.get('/operations/theatre/cases/', { params }),
  createSurgicalCase: (payload) => client.post('/operations/theatre/cases/', payload),
  actSurgicalCase: (id, payload) => client.post(`/operations/theatre/cases/${id}/action/`, payload),
  surgicalChecklist: (id) => client.get(`/operations/theatre/cases/${id}/checklist/`),
  saveSurgicalChecklist: (id, payload) => client.post(`/operations/theatre/cases/${id}/checklist/`, payload),
  maternityEpisodes: (params) => client.get('/operations/maternity/episodes/', { params }),
  createMaternityEpisode: (payload) => client.post('/operations/maternity/episodes/', payload),
  actMaternityEpisode: (id, payload) => client.post(`/operations/maternity/episodes/${id}/action/`, payload),
  staffShifts: (params) => client.get('/operations/workforce/shifts/', { params }),
  createStaffShift: (payload) => client.post('/operations/workforce/shifts/', payload),
  actStaffShift: (id, payload) => client.post(`/operations/workforce/shifts/${id}/action/`, payload),
  leaveRequests: (params) => client.get('/operations/workforce/leave/', { params }),
  createLeaveRequest: (payload) => client.post('/operations/workforce/leave/', payload),
  actLeaveRequest: (id, payload) => client.post(`/operations/workforce/leave/${id}/action/`, payload),
  qualityIncidents: (params) => client.get('/operations/quality/incidents/', { params }),
  createQualityIncident: (payload) => client.post('/operations/quality/incidents/', payload),
  actQualityIncident: (id, payload) => client.post(`/operations/quality/incidents/${id}/action/`, payload),
  privacyRequests: (params) => client.get('/operations/privacy/requests/', { params }),
  createPrivacyRequest: (payload) => client.post('/operations/privacy/requests/', payload),
  actPrivacyRequest: (id, payload) => client.post(`/operations/privacy/requests/${id}/action/`, payload),
  createAnnouncement: (payload) => client.post('/operations/announcements/', payload),
}

export const accessApi = {
  permissions: () => client.get('/workforce/permissions/'),
  roles: () => client.get('/workforce/roles/'),
  createRole: (payload) => client.post('/workforce/roles/', payload),
  updateRole: (id, payload) => client.patch(`/workforce/roles/${id}/`, payload),
  assignments: () => client.get('/workforce/role-assignments/'),
  assignRole: (payload) => client.post('/workforce/role-assignments/', payload),
  revokeAssignment: (id) => client.delete(`/workforce/role-assignments/${id}/`),
}

export const notificationAdminApi = {
  devices: () => client.get('/notifications/devices/'),
  registerDevice: (payload) => client.post('/notifications/devices/', payload),
  templates: () => client.get('/admin/notification-templates/'),
  saveTemplate: (payload) => client.post('/admin/notification-templates/', payload),
  broadcast: (payload) => client.post('/admin/notification-broadcast/', payload),
}

// ===== enterprise hospital operating system =====
export const enterpriseApi = {
  schema: () => client.get('/enterprise/schema/'),
  summary: () => client.get('/enterprise/summary/'),
  roleDashboard: () => client.get('/enterprise/dashboard/role/'),
  lookup: (kind, q = '', params = {}) => client.get('/enterprise/lookups/', { params: { kind, q, ...params } }),
  readiness: () => client.get('/enterprise/readiness/'),
  currentContext: () => client.get('/enterprise/context/current/'),
  contexts: (params) => client.get('/enterprise/contexts/', { params }),
  createContext: (payload) => client.post('/enterprise/contexts/', payload),
  activateContext: (id) => client.post(`/enterprise/contexts/${id}/activate/`),
  delegations: (params) => client.get('/enterprise/delegations/', { params }),
  createDelegation: (payload) => client.post('/enterprise/delegations/', payload),
  revokeDelegation: (id) => client.post(`/enterprise/delegations/${id}/revoke/`),
  records: (params) => client.get('/enterprise/records/', { params }),
  record: (id) => client.get(`/enterprise/records/${id}/`),
  createRecord: (payload) => client.post('/enterprise/records/', payload),
  updateRecord: (id, payload) => client.patch(`/enterprise/records/${id}/`, payload),
  deleteRecord: (id) => client.delete(`/enterprise/records/${id}/`),
  transitionRecord: (id, payload) => client.post(`/enterprise/records/${id}/transition/`, payload),
  attachRecord: (id, formData) => client.post(`/enterprise/records/${id}/attachments/`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  resource: (resource, params) => client.get(`/enterprise/${resource}/`, { params }),
  createResource: (resource, payload) => client.post(`/enterprise/${resource}/`, payload),
  updateResource: (resource, id, payload) => client.patch(`/enterprise/${resource}/${id}/`, payload),
  deleteResource: (resource, id) => client.delete(`/enterprise/${resource}/${id}/`),
  publishContent: (id) => client.post(`/enterprise/content/${id}/publish/`),
  patientMergeAction: (id, action) => client.post(`/enterprise/patient-merges/${id}/action/`, { action }),
  telemedicineAction: (id, payload) => client.post(`/enterprise/telemedicine-sessions/${id}/action/`, payload),
  eventDeliveryAction: (id, action, reason = '') => client.post(`/enterprise/event-deliveries/${id}/action/`, { action, reason }),
  verificationAction: (id, payload) => client.post(`/enterprise/verification-automation/${id}/action/`, payload),
  runReport: (id, parameters = {}) => client.post(`/enterprise/saved-reports/${id}/run/`, { parameters }),
  issuePartnerToken: (id, payload) => client.post(`/enterprise/partner-apps/${id}/token/`, payload),
  medicationSafety: (payload) => client.post('/enterprise/clinical/medication-safety/', payload),
  pacsHealth: (id) => client.post(`/enterprise/pacs-nodes/${id}/health/`),
  imagingViewer: (id) => client.get(`/enterprise/imaging-studies/${id}/viewer/`),
  nearestAmbulances: (params) => client.get('/enterprise/ambulances/nearest/', { params }),
  duplicatePatientScan: (payload = {}) => client.post('/enterprise/records/duplicate-scan/', payload),
  providerHealth: (id) => client.post(`/enterprise/notification-providers/${id}/health/`),
  fhirExportMe: () => client.get('/enterprise/fhir/export/me/'),
  fhirExportPatient: (id) => client.get(`/enterprise/fhir/export/patients/${id}/`),
  runReplay: (id) => client.post(`/enterprise/replay-requests/${id}/run/`),
  publicContent: (params) => client.get('/enterprise/public/content/', { params }),
}

// ===== transactional page journeys =====
export const journeyApi = {
  definition: (slug) => client.get(`/journeys/pages/${slug}/definition/`),
  data: (slug, params = {}) => client.get(`/journeys/pages/${slug}/data/`, { params }),
  cases: (slug, params = {}) => client.get(`/journeys/pages/${slug}/cases/`, { params }),
  createCase: (slug, payload) => client.post(`/journeys/pages/${slug}/cases/`, payload),
  case: (publicId) => client.get(`/journeys/cases/${publicId}/`),
  updateCase: (publicId, payload) => client.patch(`/journeys/cases/${publicId}/`, payload),
  act: (publicId, payload) => client.post(`/journeys/cases/${publicId}/actions/`, payload),
  comments: (publicId) => client.get(`/journeys/cases/${publicId}/comments/`),
  addComment: (publicId, payload) => client.post(`/journeys/cases/${publicId}/comments/`, payload),
  dashboard: () => client.get('/journeys/dashboard/'),
  documents: () => client.get('/journeys/documents/'),
  operationalActions: (params = {}) => client.get('/journeys/operational-actions/', { params }),
  releaseAcceptances: (params = {}) => client.get('/journeys/release-acceptances/', { params }),
  createReleaseAcceptance: (payload) => client.post('/journeys/release-acceptances/', payload),
  updateReleaseAcceptance: (id, payload) => client.patch(`/journeys/release-acceptances/${id}/`, payload),
  productionReadiness: (params = {}) => client.get('/journeys/production-readiness/', { params }),
  documentDownloadUrl: (publicId) => `${client.defaults.baseURL}/journeys/documents/${publicId}/download/`,
}

export const privilegedAccessApi = {
  list: (params = {}) => client.get('/governance/privileged-access/', { params }),
  request: (payload) => client.post('/governance/privileged-access/', payload),
  decide: (id, payload) => client.post(`/governance/privileged-access/${id}/decision/`, payload),
}

export const platformAdminApi = {
  search: (q, kind = 'all') => client.get('/journeys/admin/search/', { params: { q, kind } }),
  user: (id) => client.get(`/journeys/admin/users/${id}/`),
  userAction: (id, payload) => client.post(`/journeys/admin/users/${id}/actions/`, payload),
  contexts: (userId) => client.get(`/journeys/admin/users/${userId}/contexts/`),
  createContext: (userId, payload) => client.post(`/journeys/admin/users/${userId}/contexts/`, payload),
  updateContext: (id, payload) => client.patch(`/journeys/admin/contexts/${id}/`, payload),
  revokeContext: (id) => client.delete(`/journeys/admin/contexts/${id}/`),
  transferOwnership: (organizationId, payload) => client.post(`/journeys/admin/organizations/${organizationId}/ownership/`, payload),
  systemHealth: () => client.get('/journeys/admin/system-health/'),
}
