import Handoffs from './portals/facility/Handoffs'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth, ROLE_HOME } from './auth/AuthContext'
import { PharmacyStaffLayout } from './portals/pharmacy/PharmacyPermissions'
import PortalLayout from './layouts/PortalLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import AcceptInvitation from './pages/AcceptInvitation'
import LandingPage from './pages/LandingPage'
import NotificationPreferences from './pages/NotificationPreferences'
import { Spinner } from './components/ui'
import * as patient from './portals/patient/routes.jsx'
import * as doctor from './portals/doctor/routes.jsx'
import * as pharmacy from './portals/pharmacy/routes.jsx'
import * as lab from './portals/lab/routes.jsx'
import FacilityWorkspace, { LegacyHospitalPath, NursingWorkspace } from './portals/facility/FacilityWorkspace'
import FacilityHomePage from './pages/FacilityHomePage'
import * as insurance from './portals/insurance/routes.jsx'
import * as admin from './portals/admin/routes.jsx'
import * as nurse from './portals/nurse/routes.jsx'
import * as reception from './portals/reception/routes.jsx'
import * as cashier from './portals/cashier/routes.jsx'
import * as facility from './portals/facility/routes.jsx'
import * as pharmacist from './portals/pharmacist/routes.jsx'
import * as labstaff from './portals/labstaff/routes.jsx'

function RequireRole({ roles, children }) {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role) && user.role !== 'admin') return <Navigate to={ROLE_HOME[user.role] || '/patient'} replace />
  return children
}

function Portal({ mod, role, title, path = role, roles = [role] }) {
  const usesHandoffs = ['doctor', 'nurse', 'receptionist', 'cashier', 'lab_technician', 'pharmacist'].includes(role)
  const nav = usesHandoffs ? [...mod.nav, {
    to: `/${path}/handoffs`, label: role === 'doctor' ? 'Next Steps' : 'Patient Handoffs', icon: 'clipboard', group: 'Patient care',
  }] : mod.nav
  return (
    <Route
      path={`/${path}`}
      element={
        <RequireRole roles={roles}>
          {role === 'facility_manager' ? <FacilityWorkspace /> : role === 'pharmacist'
            ? <PharmacyStaffLayout title={title} nav={nav} role={role} home="/pharmacist/rx-orders" />
            : role === 'nurse' ? <NursingWorkspace title={title} nav={nav} />
              : <PortalLayout title={title} nav={nav} role={role} />}
        </RequireRole>
      }
    >
      {usesHandoffs && <Route path="handoffs" element={<Handoffs />} />}
      {mod.routes.map((r) => (
        <Route key={r.path || 'index'} path={r.path} element={r.element} index={r.index} />
      ))}
    </Route>
  )
}


function DashboardHome() {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />
  return <Navigate to={user ? ROLE_HOME[user.role] || '/patient' : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<FacilityHomePage />} />
      <Route path="/platform" element={<LandingPage />} />
      <Route path="/dashboard" element={<DashboardHome />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register key="patient" accountRole="patient" />} />
      <Route path="/onboard-facility" element={<Register key="facility" accountRole="hospital" />} />
      <Route path="/accept-invitation/:token" element={<AcceptInvitation />} />
      <Route path="/notification-settings" element={<RequireRole roles={Object.keys(ROLE_HOME)}><NotificationPreferences /></RequireRole>} />
      {Portal({ mod: patient, role: 'patient', title: 'Patient Portal' })}
      {Portal({ mod: doctor, role: 'doctor', title: 'Doctor Portal' })}
      {Portal({ mod: nurse, role: 'nurse', title: 'Nursing Workspace' })}
      {Portal({ mod: reception, role: 'receptionist', path: 'reception', roles: ['receptionist', 'records_officer'], title: 'Front Desk Workspace' })}
      {Portal({ mod: cashier, role: 'cashier', title: 'Billing & Collections' })}
      {Portal({ mod: facility, role: 'facility_manager', path: 'facility', roles: ['facility_manager', 'hospital'], title: 'MyDoctor Facility' })}
      {Portal({ mod: pharmacist, role: 'pharmacist', path: 'pharmacist', roles: ['pharmacist', 'storekeeper'], title: 'Pharmacist Workspace' })}
      {Portal({ mod: labstaff, role: 'lab_technician', path: 'lab-staff', title: 'Laboratory Staff Workspace' })}
      {Portal({ mod: pharmacy, role: 'pharmacy', title: 'Pharmacy Portal' })}
      {Portal({ mod: lab, role: 'lab', title: 'Laboratory Portal' })}
      <Route path="/hospital/*" element={<LegacyHospitalPath />} />
      {Portal({ mod: insurance, role: 'insurance', title: 'Insurance Portal', roles: ['insurance', 'insurance_officer'] })}
      {Portal({ mod: admin, role: 'admin', title: 'Admin Dashboard' })}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
