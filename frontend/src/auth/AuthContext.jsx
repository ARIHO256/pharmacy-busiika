import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { authApi, enterpriseApi } from '../api/endpoints'

const AuthContext = createContext(null)

export const ROLE_HOME = {
  patient: '/patient',
  doctor: '/doctor',
  clinical_officer: '/clinical-officer',
  dentist: '/dentist',
  physiotherapist: '/physiotherapy',
  nutritionist: '/nutrition',
  psychologist: '/psychology',
  medical_director: '/medical-director',
  nurse: '/nurse',
  midwife: '/midwife',
  theatre_nurse: '/theatre-nurse',
  receptionist: '/reception',
  records_officer: '/records',
  cashier: '/cashier',
  accountant: '/accounting',
  pharmacist: '/pharmacist',
  lab_technician: '/lab-staff',
  radiologist: '/radiology',
  radiographer: '/radiography',
  anaesthetist: '/anaesthesia',
  facility_manager: '/facility',
  finance_manager: '/finance',
  procurement_officer: '/procurement',
  quality_officer: '/quality',
  compliance_officer: '/compliance',
  hr_officer: '/hr',
  it_support: '/it-operations',
  ambulance_dispatcher: '/dispatch',
  paramedic: '/paramedic',
  insurance_officer: '/insurance-officer',
  claims_reviewer: '/claims-review',
  storekeeper: '/storekeeping',
  pharmacy: '/pharmacy',
  lab: '/lab',
  hospital: '/hospital',
  insurance: '/insurance',
  admin: '/admin',
  platform_super_admin: '/admin',
  operations_admin: '/admin',
  compliance_admin: '/admin',
  clinical_safety_admin: '/admin',
}

export function effectiveRoleFor(user) {
  return user?.active_context?.role_code || user?.role || ''
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = async () => {
    const { data } = await authApi.me()
    setUser(data)
    return data
  }

  useEffect(() => {
    const token = localStorage.getItem('access')
    if (!token) {
      setLoading(false)
      return
    }
    refreshUser()
      .catch(() => {
        localStorage.clear()
        setUser(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const finalizeLogin = async (data) => {
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    return refreshUser()
  }

  const login = async (email, password) => {
    const { data } = await authApi.login(email, password)
    if (data.mfa_required) return data
    return finalizeLogin(data)
  }

  const verifyMfa = async (challengeId, code) => {
    const { data } = await authApi.verifyMfa(challengeId, code)
    return finalizeLogin(data)
  }

  const register = async (payload) => {
    const { data } = await authApi.register(payload)
    localStorage.setItem('access', data.tokens.access)
    localStorage.setItem('refresh', data.tokens.refresh)
    return refreshUser()
  }

  const activateContext = async (contextId) => {
    await enterpriseApi.activateContext(contextId)
    return refreshUser()
  }

  const logout = async () => {
    const refresh = localStorage.getItem('refresh')
    try {
      if (refresh) await authApi.logout(refresh)
    } catch {
      // The browser session is always cleared even when the API is unavailable.
    } finally {
      localStorage.clear()
      setUser(null)
    }
  }

  const value = useMemo(() => ({
    user,
    loading,
    login,
    verifyMfa,
    register,
    logout,
    setUser,
    refreshUser,
    activateContext,
    activeRole: effectiveRoleFor(user),
    activeContext: user?.active_context || null,
    availableContexts: user?.available_contexts || [],
  }), [user, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
