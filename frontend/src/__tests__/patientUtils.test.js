import { describe, it, expect } from 'vitest'
import { fmtUGX, fmtTime, todayISO, APPT_STATUS_COLORS, INVOICE_STATUS_COLORS } from '../portals/patient/utils.js'

describe('fmtUGX', () => {
  it('formats amounts with thousands separators', () => {
    expect(fmtUGX(1500000)).toBe('UGX 1,500,000')
    expect(fmtUGX(0)).toBe('UGX 0')
    expect(fmtUGX(null)).toBe('UGX 0')
  })
})

describe('fmtTime', () => {
  it('trims API times to HH:MM', () => {
    expect(fmtTime('09:30:00')).toBe('09:30')
    expect(fmtTime('')).toBe('')
    expect(fmtTime(null)).toBe('')
  })
})

describe('todayISO', () => {
  it('returns an ISO date', () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})

describe('status color maps', () => {
  it('cover the appointment lifecycle', () => {
    for (const status of ['pending', 'confirmed', 'cancelled', 'completed', 'missed']) {
      expect(APPT_STATUS_COLORS[status]).toBeTruthy()
    }
  })

  it('cover the invoice lifecycle', () => {
    for (const status of ['pending', 'paid', 'failed', 'refunded']) {
      expect(INVOICE_STATUS_COLORS[status]).toBeTruthy()
    }
  })
})
