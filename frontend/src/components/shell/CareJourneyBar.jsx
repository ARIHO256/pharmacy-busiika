import { NavLink } from 'react-router-dom'
import HealthIcon from '../icons/HealthIcon'

const roleJourneys = {
  patient: [
    ['search', 'Find care', '/patient/doctors'],
    ['calendar', 'Book', '/patient/appointments'],
    ['wallet', 'Pay', '/patient/invoices'],
    ['video', 'Consult', '/patient/messages'],
    ['prescription', 'Prescription', '/patient/prescriptions'],
    ['heart', 'Follow-up', '/patient/health-record'],
  ],
  doctor: [
    ['clock', 'Availability', '/doctor/availability'],
    ['calendar', 'Appointments', '/doctor/appointments'],
    ['video', 'Consult', '/doctor/consult'],
    ['clipboard', 'Document', '/doctor/clinical'],
    ['prescription', 'Prescribe', '/doctor/prescriptions'],
    ['money', 'Earnings', '/doctor/earnings'],
  ],
  pharmacy: [
    ['prescription', 'Receive Rx', '/pharmacy/rx-orders'],
    ['box', 'Check stock', '/pharmacy/inventory'],
    ['clipboard', 'Fulfil', '/pharmacy/orders'],
    ['truck', 'Dispatch', '/pharmacy/orders'],
  ],
  lab: [
    ['clipboard', 'Receive order', '/lab/orders'],
    ['flask', 'Collect sample', '/lab/orders'],
    ['activity', 'Process', '/lab/orders'],
    ['file', 'Publish result', '/lab/orders'],
  ],
  hospital: [
    ['calendar', 'Booking', '/hospital/bookings'],
    ['hospital', 'Care service', '/hospital/services'],
    ['bed', 'Capacity', '/hospital/beds'],
    ['file', 'Report', '/hospital'],
  ],
  insurance: [
    ['shield', 'Coverage', '/insurance/policies'],
    ['clipboard', 'Claim', '/insurance/claims'],
    ['check', 'Decision', '/insurance/claims'],
    ['money', 'Settlement', '/insurance'],
  ],
  admin: [
    ['users', 'Users', '/admin/users'],
    ['doctor', 'Verify', '/admin/registry'],
    ['calendar', 'Monitor care', '/admin/appointments'],
    ['money', 'Finance', '/admin/finance'],
    ['shield', 'Compliance', '/admin/compliance'],
  ],
}

export default function CareJourneyBar({ role }) {
  const items = roleJourneys[role] || roleJourneys.patient
  return (
    <div className="care-journey-bar" aria-label="Workflow shortcuts">
      <div className="care-journey-inner">
        <span className="care-journey-label">CARE FLOW</span>
        {items.map(([icon, label, to], index) => (
          <div className="care-journey-step" key={`${label}-${to}`}>
            <NavLink to={to} className={({ isActive }) => isActive ? 'is-active' : ''}>
              <HealthIcon name={icon} size={15}/>
              <span>{label}</span>
            </NavLink>
            {index < items.length - 1 && <HealthIcon name="chevron" size={13} className="care-step-chevron"/>}
          </div>
        ))}
      </div>
    </div>
  )
}
