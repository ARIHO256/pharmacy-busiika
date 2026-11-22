import client from './client'

// ===== auth & accounts =====
export const authApi = {
  login: (email, password) => client.post('/auth/token/', { email, password }),
  register: (payload) => client.post('/auth/register/', payload),
  invitation: (token) => client.get(`/workforce/invitations/${token}/`),
  acceptInvitation: (token, payload) => client.post(`/workforce/invitations/${token}/`, payload),
  me: () => client.get('/auth/me/'),
  updateMe: (payload) => client.patch('/auth/me/', payload),
  updateProfile: (payload) => client.patch('/auth/me/profile/', payload),
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
  subscribe: (id, onChange) => {
    if (typeof WebSocket === 'undefined') return () => {}
    let stopped = false
    let socket
    let retry
    let delay = 1000
    const connect = () => {
      if (stopped || !localStorage.getItem('access')) return
      const url = new URL(client.defaults.baseURL || '/api', window.location.href)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      url.pathname = `/ws/conversations/${id}/`
      url.search = ''
      url.hash = ''
      // The development API runs on 4000; production serves /ws on the API origin.
      if (import.meta.env.DEV && url.port === '3000') url.port = '4000'
      try {
        socket = new WebSocket(url)
        socket.onopen = () => socket.send(JSON.stringify({ type: 'authenticate', access_token: localStorage.getItem('access') }))
        socket.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            if (message.type === 'ready') delay = 1000
            if (message.type === 'message.created' || message.type === 'message.receipt') onChange()
          } catch { /* Polling remains available if a refresh hint cannot be read. */ }
        }
        socket.onerror = () => socket.close()
        socket.onclose = () => {
          if (!stopped) {
            retry = setTimeout(connect, delay)
            delay = Math.min(delay * 2, 30000)
          }
        }
      } catch {
        if (!stopped) retry = setTimeout(connect, 30000)
      }
    }
    connect()
    return () => {
      stopped = true
      clearTimeout(retry)
      socket?.close()
    }
  },
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
  invoices: () => client.get('/payments/invoices/'),
  receipt: (id) => client.get(`/payments/invoices/${id}/receipt/`),
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
  medicineTaxonomy: () => client.get('/services/medicine-taxonomy/'),
  manageMedicineTaxonomy: (organization) => client.get('/services/medicine-taxonomy/manage/', { params: { organization } }),
  addMedicineTaxonomyNode: (organization, node) => client.post('/services/medicine-taxonomy/manage/', node, { params: { organization } }),
  updateMedicineTaxonomyNode: (organization, id, changes) =>
    client.patch(`/services/medicine-taxonomy/manage/${id}/`, changes, { params: { organization } }),
  medicines: (params) => client.get('/services/medicines/', { params }),
  saveMedicine: (payload) => client.post('/services/medicines/', payload),
  deleteMedicine: (id) => client.delete(`/services/medicines/${id}/`),
  cart: () => client.get('/services/cart/'),
  addCart: (medicine_id, qty) => client.post('/services/cart/', { medicine_id, qty }),
  removeCart: (id) => client.delete(`/services/cart/${id}/`),
  checkout: (payload) => client.post('/services/orders/checkout/', payload),
  orders: () => client.get('/services/orders/'),
  counterProducts: (search) => client.get('/services/pharmacy/counter-sales/', { params: { search } }),
  counterSale: (sale) => client.post('/services/pharmacy/counter-sales/', sale),
  pharmacyShifts: () => client.get('/services/pharmacy/shifts/'),
  openPharmacyShift: (details) => client.post('/services/pharmacy/shifts/', details),
  closePharmacyShift: (id, details) => client.post(`/services/pharmacy/shifts/${id}/close/`, details),
  orderReceipt: (id) => client.get(`/services/orders/${id}/receipt/`),
  recordOrderPayment: (id, payment) => client.post(`/services/orders/${id}/receipt/`, payment),
  updateOrder: (id, status, extra = {}) => client.post(`/services/orders/${id}/update/`, { status, ...extra }),
  reverseDispense: (id, fields) => client.post(`/services/pharmacy-orders/${id}/update/`, { ...fields, status: 'reverse_dispense' }),
  dispensingBatches: (id) => client.get(`/services/pharmacy-orders/${id}/update/`),
  dispensePrescription: (id, fields) => client.post(`/services/pharmacy-orders/${id}/update/`, { ...fields, status: 'dispense' }),
  pharmacyOrders: () => client.get('/services/pharmacy-orders/'),
  updatePharmacyOrder: (id, status, extra = {}) =>
    client.post(`/services/pharmacy-orders/${id}/update/`, { status, ...extra }),
  reviewPharmacyPrescription: (id, fields) => client.post(`/services/pharmacy-orders/${id}/review/`, fields),
  requestPharmacySubstitution: (id, fields) => client.post(`/services/pharmacy-orders/${id}/substitutions/`, fields),
  pharmacySubstitutions: () => client.get('/services/pharmacy-substitutions/'),
  decidePharmacySubstitution: (id, fields) => client.post(`/services/pharmacy-substitutions/${id}/`, fields),
  suppliers: () => client.get('/services/suppliers/'),
  saveSupplier: (payload) => client.post('/services/suppliers/', payload),
  deleteSupplier: (id) => client.delete(`/services/suppliers/${id}/`),
  labTests: (params) => client.get('/services/lab-tests/', { params }),
  saveLabTest: (payload) => client.post('/services/lab-tests/', payload),
  bookLab: (payload) => client.post('/services/lab-orders/', payload),
  labOrdersManage: () => client.get('/services/lab-orders/manage/'),
  updateLabOrder: (id, formData) =>
    client.post(`/services/lab-orders/${id}/update/`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  myLabOrders: () => client.get('/services/lab-orders/'),
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
  verifyCoverage: (payload) => client.post('/services/coverage/verify/', payload),
  submitClaim: (payload) => client.post('/services/claims/', payload),
  myClaims: () => client.get('/services/claims/'),
  claimsManage: () => client.get('/services/claims/manage/'),
  decideClaim: (id, action) => client.post(`/services/claims/${id}/decide/`, { action }),
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
  referrals: (patientId) => client.get('/clinical/referrals/', { params: patientParam(patientId) }),
  addReferral: (payload, patientId) => client.post('/clinical/referrals/', { ...payload, ...(patientId ? { patient_id: patientId } : {}) }),
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

servicesApi.labResults = (orderId) => client.get(`/services/lab-orders/${orderId}/results/`)
servicesApi.publishLabResult = (orderId, payload) => client.post(`/services/lab-orders/${orderId}/results/`, payload)
servicesApi.acknowledgeCriticalResult = (resultId, notes = '') => client.post(`/services/lab-results/${resultId}/acknowledge/`, { notes })


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
  visitCareTeam: (id) => client.get(`/workforce/visits/${id}/action/`),
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
  shifts: () => client.get('/billing/shifts/'),
  openShift: (payload = {}) => client.post('/billing/shifts/', payload),
  closeShift: (shiftId, payload = {}) => client.post(`/billing/shifts/${shiftId}/close/`, payload),
}

// Existing portal components consume the new operational API without changing their presentation.
export const operationsApi = {
  actionGet: (resource, id, action) => client.get(`/operations/${resource}/${id}/${action}/`),
  configureBenefit: (id, payload) => client.patch(`/operations/benefits/${id}/configure/`, payload),
  reconciliation: (organization) => client.get('/operations/claim-assessments/reconciliation/', { params: { organization } }),
  downloadDocument: async (id, filename) => {
    const response = await client.get(`/operations/documents/${id}/download/`, { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  },
  context: (organization, patientSearch) => client.get('/operations/context/', { params: { organization: organization || undefined, patient_search: patientSearch } }),
  list: (resource, params) => client.get(`/operations/${resource}/`, { params }),
  create: (resource, payload) => client.post(`/operations/${resource}/`, payload),
  action: (resource, id, action, payload) => client.post(`/operations/${resource}/${id}/${action}/`, payload),
  offlineChanges: (nodeId, params) => client.get(`/operations/offline-nodes/${nodeId}/changes/`, { params }),
  offlinePreview: (nodeId, changeId) => client.get(`/operations/offline-nodes/${nodeId}/preview/`, { params: { change: changeId } }),
}
