// Shared helpers for the doctor portal

export const fmtMoney = (n) => `UGX ${Number(n || 0).toLocaleString()}`

export const statusColor = (s) =>
  ({
    pending: 'yellow',
    confirmed: 'green',
    cancelled: 'slate',
    completed: 'blue',
    missed: 'red',
    paid: 'green',
    failed: 'red',
    refunded: 'purple',
    verified: 'green',
    suspended: 'red',
    new: 'yellow',
  }[s] || 'slate')

export const WEEKDAYS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
]

// Parse "13:00-14:00, 17:00-18:00" -> [{start:'13:00',end:'14:00'},...]
export function parseBreaks(text) {
  if (!text?.trim()) return []
  const out = []
  for (const part of text.split(',')) {
    const m = part.trim().match(/^(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})$/)
    if (!m) throw new Error(`Invalid break range "${part.trim()}" — use HH:MM-HH:MM, comma-separated`)
    out.push({ start: m[1], end: m[2] })
  }
  return out
}

export const breaksToText = (breaks) =>
  Array.isArray(breaks) ? breaks.map((b) => `${b.start || b.start_time}-${b.end || b.end_time}`).join(', ') : ''

// Parse "2025-12-25, 2025-12-26" -> ['2025-12-25','2025-12-26']
export function parseHolidays(text) {
  if (!text?.trim()) return []
  return text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}
