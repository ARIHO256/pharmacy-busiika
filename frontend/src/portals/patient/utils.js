// Shared helpers for the patient portal
export const fmtUGX = (n) => `UGX ${Number(n || 0).toLocaleString()}`

export const APPT_STATUS_COLORS = {
  pending: 'yellow',
  confirmed: 'green',
  cancelled: 'slate',
  completed: 'blue',
  missed: 'red',
}

export const INVOICE_STATUS_COLORS = {
  pending: 'yellow',
  paid: 'green',
  failed: 'red',
  refunded: 'slate',
}

export const todayISO = () => new Date().toISOString().slice(0, 10)

export const fmtTime = (t) => (t ? String(t).slice(0, 5) : '')
