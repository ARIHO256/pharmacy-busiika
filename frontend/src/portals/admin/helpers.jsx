// Shared helpers for the admin portal (scoped to portals/admin only).

export const money = (n) => `UGX ${Number(n || 0).toLocaleString()}`

export const fmtDate = (s) => {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export const fmtDateTime = (s) => {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

export const fmtTime = (t) => (t ? String(t).slice(0, 5) : '—')

export const appointmentStatusColor = {
  pending: 'yellow', confirmed: 'blue', completed: 'green', cancelled: 'red', missed: 'slate',
}

export const invoiceStatusColor = {
  draft: 'slate', pending: 'yellow', partially_paid: 'blue', paid: 'green',
  failed: 'red', refunded: 'purple', void: 'slate',
}

export const profileStatusColor = {
  verified: 'green', pending: 'yellow', rejected: 'red', suspended: 'red',
  expired: 'slate', revoked: 'red', inactive: 'slate',
}

export const roleColor = {
  patient: 'slate', doctor: 'blue', nurse: 'blue', receptionist: 'yellow',
  records_officer: 'yellow', cashier: 'green', pharmacist: 'green',
  lab_technician: 'purple', facility_manager: 'blue', insurance_officer: 'red',
  storekeeper: 'green', pharmacy: 'green', lab: 'purple', hospital: 'yellow',
  insurance: 'red', admin: 'slate',
}

export const ROLES = [
  'patient', 'doctor', 'nurse', 'receptionist', 'records_officer', 'cashier',
  'pharmacist', 'lab_technician', 'facility_manager', 'insurance_officer',
  'storekeeper', 'pharmacy', 'lab', 'hospital', 'insurance', 'admin',
]

export const BAR_COLORS = [
  'bg-teal-600', 'bg-teal-500', 'bg-teal-400', 'bg-slate-500',
  'bg-slate-400', 'bg-teal-700', 'bg-slate-600',
]

export const STATUS_BAR_COLORS = {
  pending: 'bg-amber-400', confirmed: 'bg-sky-400', completed: 'bg-emerald-500',
  cancelled: 'bg-rose-400', missed: 'bg-slate-400',
}
