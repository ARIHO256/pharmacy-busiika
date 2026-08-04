import React from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth, ROLE_HOME } from './auth/AuthContext'
import PortalLayout from './layouts/PortalLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import AcceptInvitation from './pages/AcceptInvitation'
import LandingPage from './pages/LandingPage'
import NotificationPreferences from './pages/NotificationPreferences'
import ForgotPassword from './pages/ForgotPassword'
import ResetPassword from './pages/ResetPassword'
import VerifyEmail from './pages/VerifyEmail'
import SecuritySettings from './pages/SecuritySettings'
import ReleaseAcceptancePage from './pages/ReleaseAcceptancePage'
import { PublicInfoPage, PublicDirectoryPage, PublicProfilePage, SystemStatusPage, ErrorPage } from './pages/public/PublicSite'
import { Spinner } from './components/ui'
import * as patient from './portals/patient/routes.jsx'
import * as doctor from './portals/doctor/routes.jsx'
import * as pharmacy from './portals/pharmacy/routes.jsx'
import * as lab from './portals/lab/routes.jsx'
import * as hospital from './portals/hospital/routes.jsx'
import * as insurance from './portals/insurance/routes.jsx'
import * as admin from './portals/admin/routes.jsx'
import * as nurse from './portals/nurse/routes.jsx'
import * as reception from './portals/reception/routes.jsx'
import * as cashier from './portals/cashier/routes.jsx'
import * as facility from './portals/facility/routes.jsx'
import * as pharmacist from './portals/pharmacist/routes.jsx'
import * as labstaff from './portals/labstaff/routes.jsx'
import * as radiology from './portals/radiology/routes.jsx'
import * as emergency from './portals/emergency/routes.jsx'
import * as theatre from './portals/theatre/routes.jsx'
import { makeEnterprisePortal } from './portals/enterprise/routes.jsx'
import { portalRoles } from './portals/enterprise/roleCatalog.js'

const RELEASE_ACCEPTANCE_ROLES = ['admin', 'platform_super_admin', 'operations_admin', 'compliance_admin', 'clinical_safety_admin', 'medical_director', 'doctor', 'nurse', 'midwife', 'lab_technician', 'pharmacist', 'accountant', 'finance_manager', 'records_officer', 'compliance_officer', 'it_support']

function RequireRole({ roles, children }) {
  const { user, loading, activeRole } = useAuth()
  if (loading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  const role = activeRole || user.role
  if (!roles.includes(role)) return <Navigate to={ROLE_HOME[role] || '/patient'} replace />
  return children
}

function Portal({ mod, role, title, path = role, roles = [role] }) {
  return (
    <Route
      path={`/${path}`}
      element={
        <RequireRole roles={roles}>
          <PortalLayout title={title} nav={mod.nav} role={role} />
        </RequireRole>
      }
    >
      {mod.routes.map((r, index) => (
        <Route key={r.key || r.path || index} path={r.path} element={r.element} index={r.index} />
      ))}
    </Route>
  )
}


function DashboardHome() {
  const { user, loading, activeRole } = useAuth()
  if (loading) return <Spinner />
  const role = activeRole || user?.role
  return <Navigate to={user ? ROLE_HOME[role] || '/patient' : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/about" element={<PublicInfoPage pageKey="about" />} />
      <Route path="/contact" element={<PublicInfoPage pageKey="contact" />} />
      <Route path="/help" element={<PublicInfoPage pageKey="help" />} />
      <Route path="/faq" element={<PublicInfoPage pageKey="faq" />} />
      <Route path="/pricing" element={<PublicInfoPage pageKey="pricing" />} />
      <Route path="/privacy" element={<PublicInfoPage pageKey="privacy" />} />
      <Route path="/terms" element={<PublicInfoPage pageKey="terms" />} />
      <Route path="/medical-disclaimer" element={<PublicInfoPage pageKey="medical-disclaimer" />} />
      <Route path="/cookies" element={<PublicInfoPage pageKey="cookies" />} />
      <Route path="/accessibility" element={<PublicInfoPage pageKey="accessibility" />} />
      <Route path="/data-processing" element={<PublicInfoPage pageKey="data-processing" />} />
      <Route path="/browser-compatibility" element={<PublicInfoPage pageKey="browser-compatibility" />} />
      <Route path="/status" element={<SystemStatusPage />} />
      {['doctors', 'facilities', 'pharmacies', 'laboratories', 'insurance', 'services'].map((kind) => <Route key={kind} path={`/directory/${kind}`} element={<PublicDirectoryPage kind={kind} />} />)}
      {['doctors', 'facilities', 'pharmacies', 'laboratories', 'insurance'].map((kind) => <Route key={`${kind}-profile`} path={`/directory/${kind}/:id`} element={<PublicProfilePage kind={kind} />} />)}
      <Route path="/403" element={<ErrorPage code={403} />} />
      <Route path="/500" element={<ErrorPage code={500} />} />
      <Route path="/maintenance" element={<ErrorPage code="maintenance" />} />
      <Route path="/offline" element={<ErrorPage code="offline" />} />
      <Route path="/dashboard" element={<DashboardHome />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password/:tokenId/:token" element={<ResetPassword />} />
      <Route path="/verify-email/:tokenId/:token" element={<VerifyEmail />} />
      <Route path="/accept-invitation/:token" element={<AcceptInvitation />} />
      <Route path="/security" element={<RequireRole roles={Object.keys(ROLE_HOME)}><SecuritySettings /></RequireRole>} />
      <Route path="/notification-settings" element={<RequireRole roles={Object.keys(ROLE_HOME)}><NotificationPreferences /></RequireRole>} />
      <Route path="/release-acceptance" element={<RequireRole roles={RELEASE_ACCEPTANCE_ROLES}><ReleaseAcceptancePage /></RequireRole>} />
      {Portal({ mod: patient, role: 'patient', title: 'Patient Portal' })}
      {Portal({ mod: doctor, role: 'doctor', title: 'Clinical Workspace', roles: ['doctor', 'clinical_officer', 'dentist', 'physiotherapist', 'nutritionist', 'psychologist', 'medical_director'] })}
      {Portal({ mod: nurse, role: 'nurse', title: 'Nursing Workspace', roles: ['nurse', 'midwife', 'theatre_nurse'] })}
      {Portal({ mod: reception, role: 'receptionist', path: 'reception', roles: ['receptionist', 'records_officer'], title: 'Front Desk Workspace' })}
      {Portal({ mod: cashier, role: 'cashier', title: 'Billing & Collections', roles: ['cashier', 'accountant'] })}
      {Portal({ mod: facility, role: 'facility_manager', path: 'facility', title: 'Facility Operations', roles: ['facility_manager', 'finance_manager', 'procurement_officer', 'quality_officer', 'compliance_officer', 'hr_officer', 'it_support'] })}
      {Portal({ mod: pharmacist, role: 'pharmacist', path: 'pharmacist', roles: ['pharmacist', 'storekeeper'], title: 'Pharmacist Workspace' })}
      {Portal({ mod: labstaff, role: 'lab_technician', path: 'lab-staff', title: 'Laboratory Staff Workspace' })}
      {Portal({ mod: pharmacy, role: 'pharmacy', title: 'Pharmacy Portal' })}
      {Portal({ mod: lab, role: 'lab', title: 'Laboratory Portal' })}
      {Portal({ mod: hospital, role: 'hospital', title: 'Hospital Portal' })}
      {Portal({ mod: insurance, role: 'insurance', title: 'Insurance Portal', roles: ['insurance', 'insurance_officer', 'claims_reviewer'] })}
      {Portal({ mod: radiology, role: 'radiologist', path: 'radiology', roles: ['radiologist', 'radiographer'], title: 'Radiology Workspace' })}
      {Portal({ mod: emergency, role: 'paramedic', path: 'emergency', roles: ['paramedic', 'ambulance_dispatcher'], title: 'Emergency Operations' })}
      {Portal({ mod: theatre, role: 'anaesthetist', path: 'theatre', roles: ['anaesthetist'], title: 'Theatre & Anaesthesia' })}
      {Portal({ mod: admin, role: 'admin', title: 'Admin Dashboard', roles: ['admin', 'platform_super_admin', 'operations_admin', 'compliance_admin', 'clinical_safety_admin'] })}
      {portalRoles().map((enterpriseRole) => {
        const enterprise = makeEnterprisePortal(enterpriseRole)
        return <React.Fragment key={enterpriseRole}>{Portal({ mod: enterprise, role: enterpriseRole, path: enterprise.portal.path, title: enterprise.portal.title, roles: [enterpriseRole] })}</React.Fragment>
      })}
      <Route path="*" element={<ErrorPage code={404} />} />
    </Routes>
  )
}
