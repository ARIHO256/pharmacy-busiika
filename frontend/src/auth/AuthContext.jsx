import { createContext, useContext, useEffect, useState } from 'react'
import { authApi } from '../api/endpoints'

const AuthContext = createContext(null)

export const ROLE_HOME = {
  patient: '/patient',
  doctor: '/doctor',
  nurse: '/nurse',
  receptionist: '/reception',
  records_officer: '/reception',
  cashier: '/cashier',
  pharmacist: '/pharmacist',
  lab_technician: '/lab-staff',
  facility_manager: '/facility',
  insurance_officer: '/insurance',
  storekeeper: '/pharmacist',
  pharmacy: '/pharmacy',
  lab: '/lab',
  hospital: '/hospital',
  insurance: '/insurance',
  admin: '/admin',
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access')
    if (!token) return setLoading(false)
    authApi
      .me()
      .then((res) => setUser(res.data))
      .catch(() => localStorage.clear())
      .finally(() => setLoading(false))
  }, [])

  const login = async (email, password) => {
    const { data } = await authApi.login(email, password)
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    const me = await authApi.me()
    setUser(me.data)
    return me.data
  }

  const register = async (payload) => {
    const { data } = await authApi.register(payload)
    localStorage.setItem('access', data.tokens.access)
    localStorage.setItem('refresh', data.tokens.refresh)
    const me = await authApi.me()
    setUser(me.data)
    return me.data
  }

  const logout = () => {
    localStorage.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
