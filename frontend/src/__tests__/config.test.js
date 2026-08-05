import { describe, it, expect } from 'vitest'
import { ROLE_EXPERIENCE, getRoleExperience } from '../config/roleExperience.js'
import { PAGE_CATALOG, pagesForRole } from '../portals/deep/pageCatalog.js'

describe('role experience configuration', () => {
  it('defines an experience for every primary portal role', () => {
    for (const role of ['patient', 'doctor', 'nurse', 'receptionist', 'cashier', 'admin', 'pharmacist']) {
      expect(ROLE_EXPERIENCE, `missing experience for ${role}`).toHaveProperty(role)
      expect(getRoleExperience(role).label).toBeTruthy()
    }
  })

  it('falls back to a safe default for unknown roles', () => {
    expect(getRoleExperience('no-such-role')).toBeTruthy()
  })
})

describe('deep page catalog', () => {
  it('declares deep pages for the seeded enterprise roles', () => {
    const roles = Object.keys(PAGE_CATALOG)
    expect(roles.length).toBeGreaterThanOrEqual(37)
    const total = roles.reduce((sum, role) => sum + pagesForRole(role).length, 0)
    expect(total).toBeGreaterThan(300)
  })

  it('gives every page a slug and label', () => {
    for (const role of Object.keys(PAGE_CATALOG)) {
      for (const page of pagesForRole(role)) {
        expect(page.slug, `page without slug in ${role}`).toBeTruthy()
        expect(page.label, `page without label in ${role}`).toBeTruthy()
      }
    }
  })
})

describe('API client module', () => {
  it('exposes API objects with callable members', async () => {
    const mod = await import('../api/endpoints.js')
    const apiObjects = Object.entries(mod).filter(([, value]) => value && typeof value === 'object')
    expect(apiObjects.length).toBeGreaterThan(10)
    for (const [name, api] of apiObjects) {
      for (const [action, fn] of Object.entries(api)) {
        expect(typeof fn, `${name}.${action} is not callable`).toBe('function')
      }
    }
  })
})
