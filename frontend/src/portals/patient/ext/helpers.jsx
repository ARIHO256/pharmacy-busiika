// Shared helpers for patient extension pages (messages, prescriptions, services).

export const ugx = (n) => `UGX ${Number(n || 0).toLocaleString()}`

export const fmtDT = (iso) => (iso ? new Date(iso).toLocaleString() : '—')
export const fmtD = (iso) => (iso ? new Date(iso).toLocaleDateString() : '—')

const colorMap = {
  new: 'yellow',
  pending: 'yellow',
  booked: 'yellow',
  submitted: 'yellow',
  confirmed: 'blue',
  prepared: 'blue',
  processing: 'blue',
  sample_collected: 'blue',
  delivered: 'green',
  completed: 'green',
  approved: 'green',
  valid: 'green',
  paid: 'green',
  cancelled: 'red',
  rejected: 'red',
  failed: 'red',
}

export const statusColor = (status) => colorMap[String(status || '').toLowerCase()] || 'slate'

export const errMsg = (e, fallback = 'Something went wrong') =>
  e?.response?.data?.detail || fallback
