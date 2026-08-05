import { describe, it, expect } from 'vitest'
import { parseBreaks, breaksToText, parseHolidays, statusColor, fmtMoney, WEEKDAYS } from '../portals/doctor/util.js'

describe('parseBreaks', () => {
  it('parses comma-separated HH:MM ranges', () => {
    expect(parseBreaks('13:00-14:00, 17:00-18:00')).toEqual([
      { start: '13:00', end: '14:00' },
      { start: '17:00', end: '18:00' },
    ])
  })

  it('returns an empty list for blank input', () => {
    expect(parseBreaks('')).toEqual([])
    expect(parseBreaks('   ')).toEqual([])
    expect(parseBreaks(undefined)).toEqual([])
  })

  it('rejects malformed ranges', () => {
    expect(() => parseBreaks('13:00 to 14:00')).toThrow(/Invalid break range/)
    expect(() => parseBreaks('25:99')).toThrow(/Invalid break range/)
  })
})

describe('breaksToText', () => {
  it('round-trips parsed breaks', () => {
    const breaks = parseBreaks('13:00-14:00, 17:00-18:00')
    expect(breaksToText(breaks)).toBe('13:00-14:00, 17:00-18:00')
  })

  it('accepts API-shaped start_time/end_time fields', () => {
    expect(breaksToText([{ start_time: '12:00', end_time: '13:00' }])).toBe('12:00-13:00')
  })

  it('handles non-array input', () => {
    expect(breaksToText(null)).toBe('')
  })
})

describe('parseHolidays', () => {
  it('splits and trims dates', () => {
    expect(parseHolidays('2025-12-25, 2025-12-26 ,')).toEqual(['2025-12-25', '2025-12-26'])
  })

  it('returns an empty list for blank input', () => {
    expect(parseHolidays('')).toEqual([])
  })
})

describe('statusColor', () => {
  it('maps known statuses and falls back to slate', () => {
    expect(statusColor('confirmed')).toBe('green')
    expect(statusColor('suspended')).toBe('red')
    expect(statusColor('something-else')).toBe('slate')
  })
})

describe('fmtMoney', () => {
  it('formats UGX amounts with thousands separators', () => {
    expect(fmtMoney(20000)).toBe('UGX 20,000')
    expect(fmtMoney(undefined)).toBe('UGX 0')
  })
})

describe('WEEKDAYS', () => {
  it('covers all seven days', () => {
    expect(WEEKDAYS).toHaveLength(7)
    expect(WEEKDAYS.map((d) => d.value)).toEqual([0, 1, 2, 3, 4, 5, 6])
  })
})
