import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import './LandingPage.css'

const Icon = ({ name, size = 20 }) => {
  const icons = {
    calendar: <><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
    shield: <><path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></>,
    video: <><rect x="3" y="6" width="13" height="12" rx="3"/><path d="m16 10 5-3v10l-5-3"/></>,
    file: <><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 13h6M9 17h4"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
    pill: <><path d="m10.5 4.5 9 9a4.2 4.2 0 0 1-6 6l-9-9a4.2 4.2 0 0 1 6-6Z"/><path d="m8 14 6-6"/></>,
    flask: <><path d="M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4A2 2 0 0 0 19 18l-5-9V3"/><path d="M8 15h8"/></>,
    building: <><path d="M4 21V7l8-4 8 4v14M8 10h1M15 10h1M8 14h1M15 14h1M9 21v-4h6v4"/></>,
    wallet: <><path d="M4 6h14a2 2 0 0 1 2 2v11H5a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3h12"/><path d="M15 11h7v5h-7a2.5 2.5 0 0 1 0-5Z"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/></>,
    globe: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18M12 3a15 15 0 0 0 0 18"/></>,
    arrow: <><path d="M5 12h14"/><path d="M14 7l5 5-5 5"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    phone: <><path d="M22 16.9v3a2 2 0 0 1-2.2 2A19.8 19.8 0 0 1 3 5.2 2 2 0 0 1 5 3h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L9 11a16 16 0 0 0 4 4l1.3-1.3a2 2 0 0 1 2.1-.5c1 .4 1.9.6 2.9.7a2 2 0 0 1 1.7 2Z"/></>,
    doctor: <><path d="M8 3h8M12 3v4M7 21v-3a5 5 0 0 1 10 0v3"/><circle cx="12" cy="11" r="4"/><path d="M4 21h16"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="3"/><path d="m4 7 8 6 8-6"/></>,
    chat: <><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5A8.6 8.6 0 0 1 8 18.8L3 20l1.2-5A8.5 8.5 0 1 1 21 11.5Z"/></>,
    chart: <><path d="M4 19h16"/><path d="M7 15V9"/><path d="M12 15V5"/><path d="M17 15v-3"/></>,
    bolt: <><path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z"/></>,
    lab: <><path d="M9 3h6"/><path d="M10 3v5l-5 9a2 2 0 0 0 1.7 3h10.6A2 2 0 0 0 19 17l-5-9V3"/><path d="M8 15h8"/></>,
    admin: <><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 20h8"/><path d="M12 18v2"/></>,
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {icons[name] || icons.check}
    </svg>
  )
}

const patientSteps = [
  { id: '1.1', icon: 'users', title: 'Register / Login', text: 'Phone, email or social sign in for patients and families.' },
  { id: '1.2', icon: 'file', title: 'Complete Profile', text: 'Personal details, medical history, allergies and emergency contacts.' },
  { id: '1.3', icon: 'search', title: 'Find Services', text: 'Search doctors, hospitals, pharmacies and laboratories from one search layer.' },
  { id: '1.4', icon: 'doctor', title: 'Choose Doctor', text: 'Compare profile, reviews, specialization, fees and availability.' },
  { id: '1.5', icon: 'calendar', title: 'Book Appointment', text: 'Select date, time, service line and care modality.' },
  { id: '1.6', icon: 'wallet', title: 'Make Payment', text: 'Support mobile money, cards, wallet and insured checkout flows.' },
  { id: '1.7', icon: 'video', title: 'Consultation', text: 'Chat, voice or secure video consultation with documentation.' },
  { id: '1.8', icon: 'pill', title: 'Get Prescription', text: 'Receive e-prescriptions, care notes and diagnostic requests.' },
  { id: '1.9', icon: 'check', title: 'Follow Up', text: 'Rebook, rate the doctor, take lab tests and continue care.' },
]

const doctorSteps = [
  { id: '5.1', icon: 'users', title: 'Register / Login', text: 'Role-aware onboarding with phone and email verification.' },
  { id: '5.2', icon: 'shield', title: 'Verification', text: 'Upload medical license, certificates and admin review workflow.' },
  { id: '5.3', icon: 'file', title: 'Complete Profile', text: 'Specialty, experience, hospital, bio, services and fees.' },
  { id: '5.4', icon: 'calendar', title: 'Set Availability', text: 'Define workdays, hours, breaks, holidays and telehealth windows.' },
  { id: '5.5', icon: 'mail', title: 'Receive Appointments', text: 'Get requests, confirm bookings and view queue status.' },
  { id: '5.6', icon: 'video', title: 'Consultation', text: 'Run secure consultations with notes, files and patient context.' },
  { id: '5.7', icon: 'pill', title: 'E‑Prescription', text: 'Issue prescriptions, advice and referrals from one workspace.' },
  { id: '5.8', icon: 'wallet', title: 'Earnings', text: 'Track earnings, withdrawals, payouts and reports.' },
]

const systems = [
  {
    id: '2',
    icon: 'calendar',
    title: 'Appointment & Scheduling System',
    accent: 'green',
    bullets: ['Real-time doctor availability', 'Slot booking and confirmation', 'Reminders via SMS, push and email', 'Reschedule and cancellation workflow'],
  },
  {
    id: '3',
    icon: 'chat',
    title: 'Communication System',
    accent: 'violet',
    bullets: ['In-app messaging', 'Audio / video consultation', 'File and image sharing for prescriptions and reports'],
  },
  {
    id: '4',
    icon: 'wallet',
    title: 'Payment & Billing System',
    accent: 'orange',
    bullets: ['Consultation payments', 'Subscriptions and billing plans', 'Commission management', 'Invoices and receipts'],
  },
]

const connectedServices = [
  {
    title: 'Pharmacies',
    icon: 'pill',
    accent: 'green',
    bullets: ['View e-prescriptions', 'Stock and availability checks', 'Home delivery workflows', 'Secure payment reconciliation'],
  },
  {
    title: 'Laboratories',
    icon: 'lab',
    accent: 'violet',
    bullets: ['Lab test orders', 'Sample booking', 'Result upload', 'Patient notification'],
  },
  {
    title: 'Hospitals & Clinics',
    icon: 'building',
    accent: 'cyan',
    bullets: ['OPD appointments', 'In-patient management', 'Bed and service management', 'Reports and analytics'],
  },
  {
    title: 'Health Insurance',
    icon: 'shield',
    accent: 'orange',
    bullets: ['Verify coverage', 'Approvals and authorizations', 'Claims management', 'Digital records'],
  },
]

const adminGroups = [
  {
    title: 'User & Provider Management',
    bullets: ['Doctor verification', 'User management', 'Role management', 'Suspend / activate accounts'],
  },
  {
    title: 'Appointment Management',
    bullets: ['Monitor appointments', 'Missed appointments', 'Reports and analytics'],
  },
  {
    title: 'Financial Management',
    bullets: ['Subscriptions', 'Transactions', 'Commissions', 'Payouts'],
  },
  {
    title: 'Content & Settings',
    bullets: ['Banners and promotions', 'Notifications', 'App settings', 'Support management'],
  },
  {
    title: 'Quality & Compliance',
    bullets: ['Reviews and ratings', 'Complaints', 'Audit logs', 'Policy enforcement'],
  },
]

const benefits = ['Convenience', 'Accessibility', 'Affordability', 'Efficiency', 'Transparency', 'Trust']

const portalCards = [
  { name: 'Patient Portal', path: '/patient', icon: 'users', text: 'The complete patient care journey from discovery to follow-up.' },
  { name: 'Doctor Workspace', path: '/doctor', icon: 'doctor', text: 'Scheduling, consultation, clinical documentation and earnings.' },
  { name: 'Pharmacy', path: '/pharmacy', icon: 'pill', text: 'Prescription fulfilment, order management and inventory.' },
  { name: 'Laboratory', path: '/lab', icon: 'lab', text: 'Test catalog, sample booking and results publishing.' },
  { name: 'Hospital & Clinic', path: '/hospital', icon: 'building', text: 'Bookings, services, beds and care operations.' },
  { name: 'Insurance', path: '/insurance', icon: 'shield', text: 'Coverage verification, policies and claims workflows.' },
  { name: 'Admin Dashboard', path: '/admin', icon: 'admin', text: 'Governance, finance, analytics and compliance control center.' },
]

function AccentDots() {
  return (
    <div className="hero-orbits" aria-hidden="true">
      <span className="orbit orbit-one" />
      <span className="orbit orbit-two" />
      <span className="orbit orbit-three" />
      <span className="dot dot-one" />
      <span className="dot dot-two" />
      <span className="dot dot-three" />
    </div>
  )
}

export default function LandingPage() {
  const { user } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const dashboardPath = user ? ROLE_HOME[user.role] || '/patient' : '/login'

  useEffect(() => {
    const close = () => setMenuOpen(false)
    window.addEventListener('resize', close)
    return () => window.removeEventListener('resize', close)
  }, [])

  return (
    <div className="health-landing flowchart-ui">
      <header className="landing-header">
        <div className="landing-container header-inner">
          <Link to="/" className="brand-mark" aria-label="MyDoctor home">
            <span className="brand-symbol"><span /></span>
            <span><strong>MyDoctor</strong><small>Connected Healthcare OS</small></span>
          </Link>

          <nav className="desktop-nav" aria-label="Primary navigation">
            <a href="#platform">Platform</a>
            <a href="#patient-flow">Patient journey</a>
            <a href="#systems">Core systems</a>
            <a href="#doctor-workspace">Doctor workspace</a>
            <a href="#admin-dashboard">Admin</a>
          </nav>

          <div className="header-actions">
            <a className="support-link" href="mailto:support@mydoctor.health"><Icon name="phone" size={17}/> Help & Support</a>
            <Link className="sign-in-link" to={dashboardPath}>{user ? 'Dashboard' : 'Sign in'}</Link>
            <Link className="header-cta" to={user ? dashboardPath : '/register'}>
              {user ? 'Open platform' : 'Create account'} <Icon name="arrow" size={17}/>
            </Link>
          </div>

          <button className="mobile-menu-button" onClick={() => setMenuOpen((value) => !value)} aria-label="Toggle navigation" aria-expanded={menuOpen}>
            <Icon name={menuOpen ? 'close' : 'menu'} size={23}/>
          </button>
        </div>
        {menuOpen && (
          <div className="mobile-nav">
            <a href="#platform" onClick={() => setMenuOpen(false)}>Platform</a>
            <a href="#patient-flow" onClick={() => setMenuOpen(false)}>Patient journey</a>
            <a href="#systems" onClick={() => setMenuOpen(false)}>Core systems</a>
            <a href="#doctor-workspace" onClick={() => setMenuOpen(false)}>Doctor workspace</a>
            <a href="#admin-dashboard" onClick={() => setMenuOpen(false)}>Admin</a>
            <Link to="/login">Sign in</Link>
            <Link className="mobile-primary" to="/register">Create account</Link>
          </div>
        )}
      </header>

      <main>
        <section className="hero-section" id="platform">
          <div className="hero-grid landing-container">
            <div className="hero-copy">
              <div className="eyebrow"><span /> Patients • Doctors • Pharmacies • Labs • Hospitals • Insurance</div>
              <h1>One health platform.<br/>Every care journey.<br/><em>End-to-end.</em></h1>
              <p className="hero-description">
                Modelled directly on your MyDoctor flow architecture, this frontend turns the patient, provider, operations and service ecosystem into one unified digital healthcare experience.
              </p>
              <div className="hero-actions">
                <Link className="primary-button" to={user ? dashboardPath : '/register'}>
                  {user ? 'Open dashboard' : 'Start with MyDoctor'} <Icon name="arrow" size={19}/>
                </Link>
                <a className="secondary-button" href="#patient-flow">View system blueprint <Icon name="arrow" size={19}/></a>
              </div>
              <div className="hero-trust-row">
                <span><i><Icon name="check" size={15}/></i> Verified providers</span>
                <span><i><Icon name="shield" size={15}/></i> Consent-controlled care data</span>
                <span><i><Icon name="globe" size={15}/></i> Connected service network</span>
              </div>
            </div>

            <div className="hero-visual">
              <AccentDots />
              <div className="hero-spotlight" />
              <div className="hero-center-card glass-card">
                <div className="hero-center-badge">MyDoctor Platform</div>
                <div className="hero-center-icon"><Icon name="doctor" size={28} /></div>
                <h3>Clinical, operational and financial coordination</h3>
                <p>The platform orchestrates scheduling, communication, billing, prescriptions, labs and connected healthcare services.</p>
              </div>
              <div className="floating-card card-top-left glass-card">
                <div className="mini-label">2. Scheduling System</div>
                <strong>Real-time availability</strong>
                <span>Slot booking • Confirmations • Reminders</span>
              </div>
              <div className="floating-card card-top-right glass-card">
                <div className="mini-label">5. Doctor Workspace</div>
                <strong>Consult & prescribe</strong>
                <span>Availability • Consultation • E‑Prescriptions</span>
              </div>
              <div className="floating-card card-mid-right glass-card">
                <div className="mini-label">6. Connected Services</div>
                <strong>Pharmacy, Lab, Hospital, Insurance</strong>
                <span>One integrated care network</span>
              </div>
              <div className="floating-card card-bottom-left glass-card">
                <div className="mini-label">4. Billing System</div>
                <strong>Consultation payments</strong>
                <span>Subscriptions • Commissions • Receipts</span>
              </div>
              <div className="floating-card card-bottom-right wide glass-card">
                <div className="mini-label">7. Admin Dashboard</div>
                <strong>Governance, analytics and compliance</strong>
                <span>Users • Appointments • Finance • Audit</span>
              </div>
            </div>
          </div>
        </section>

        <section className="ticker-band">
          <div className="ticker-track">
            {['Patient onboarding', 'Appointment scheduling', 'Telemedicine', 'E‑Prescriptions', 'Pharmacy fulfilment', 'Laboratory testing', 'Hospital operations', 'Insurance claims', 'Admin analytics', 'Compliance & audit'].map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        </section>

        <section className="section-block" id="patient-flow">
          <div className="landing-container">
            <div className="section-intro">
              <span className="section-kicker">1. Patient Journey</span>
              <h2>Map the full patient experience from first sign-in to follow-up care.</h2>
              <p>This section mirrors the patient side of your flowchart and translates it into a scalable product-ready frontend information architecture.</p>
            </div>
            <div className="flow-grid patient-grid">
              {patientSteps.map((step) => (
                <article className="flow-card" key={step.id}>
                  <div className="flow-card-top">
                    <span className="flow-id">{step.id}</span>
                    <span className="flow-icon"><Icon name={step.icon} size={18} /></span>
                  </div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section-block section-block-alt" id="systems">
          <div className="landing-container">
            <div className="section-intro">
              <span className="section-kicker">2–4. Platform Core Systems</span>
              <h2>The operational backbone that makes the app function as a healthcare super platform.</h2>
              <p>These systems act as the application core between patients, clinicians and the broader care ecosystem.</p>
            </div>
            <div className="systems-layout">
              {systems.map((system) => (
                <article key={system.id} className={`system-card accent-${system.accent}`}>
                  <div className="system-head">
                    <span className="system-icon"><Icon name={system.icon} size={20} /></span>
                    <div>
                      <div className="system-id">{system.id}</div>
                      <h3>{system.title}</h3>
                    </div>
                  </div>
                  <ul>
                    {system.bullets.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </article>
              ))}
            </div>
            <div className="connected-services-card">
              <div className="section-intro compact">
                <span className="section-kicker">6. Connected Healthcare Services</span>
                <h2>Extend the platform beyond consultations into a full health ecosystem.</h2>
              </div>
              <div className="service-grid">
                {connectedServices.map((service) => (
                  <article key={service.title} className={`service-card accent-${service.accent}`}>
                    <div className="service-head">
                      <span className="service-icon"><Icon name={service.icon} size={18} /></span>
                      <h3>{service.title}</h3>
                    </div>
                    <ul>
                      {service.bullets.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="section-block" id="doctor-workspace">
          <div className="landing-container split-section">
            <div>
              <div className="section-intro left-tight">
                <span className="section-kicker">5. Doctor Workspace</span>
                <h2>Build the clinician experience as a structured operational workflow.</h2>
                <p>Every doctor-facing module in the frontend is modelled from registration to verification, consultation, prescription and earnings.</p>
              </div>
              <div className="doctor-flow">
                {doctorSteps.map((step) => (
                  <article className="doctor-step" key={step.id}>
                    <span className="doctor-step-id">{step.id}</span>
                    <span className="doctor-step-icon"><Icon name={step.icon} size={16} /></span>
                    <div>
                      <h3>{step.title}</h3>
                      <p>{step.text}</p>
                    </div>
                  </article>
                ))}
              </div>
            </div>
            <div className="workspace-panel glass-panel">
              <div className="section-kicker">Clinical productivity board</div>
              <h3>What the doctor UI should surface first</h3>
              <div className="workspace-stats">
                <div><strong>Today</strong><span>Appointments, queue and pending confirmations</span></div>
                <div><strong>Clinical</strong><span>Notes, history, attachments and e-prescriptions</span></div>
                <div><strong>Operations</strong><span>Availability, reschedules, follow-ups and referrals</span></div>
                <div><strong>Finance</strong><span>Earnings, withdrawals and settlement reports</span></div>
              </div>
            </div>
          </div>
        </section>

        <section className="section-block section-block-alt" id="admin-dashboard">
          <div className="landing-container">
            <div className="section-intro">
              <span className="section-kicker">7. Admin Dashboard</span>
              <h2>A command center for governance, quality, finance and operational insight.</h2>
              <p>The admin frontend should control every domain visible in the healthcare operating system.</p>
            </div>
            <div className="admin-grid">
              {adminGroups.map((group) => (
                <article className="admin-card" key={group.title}>
                  <h3>{group.title}</h3>
                  <ul>
                    {group.bullets.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section-block outcome-section">
          <div className="landing-container outcome-wrap">
            <div className="outcome-card">
              <span className="section-kicker">8. Better Health Outcomes</span>
              <h2>Design the app to improve access, save time and strengthen trust.</h2>
              <ul className="outcome-list">
                <li>Easy access to quality healthcare</li>
                <li>Time saving across the whole patient journey</li>
                <li>Better patient experience and provider productivity</li>
              </ul>
            </div>
            <div className="benefit-card">
              <h3>Key Benefits</h3>
              <div className="benefit-chips">
                {benefits.map((benefit) => (
                  <span key={benefit}><Icon name="check" size={14} /> {benefit}</span>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="section-block portals-section">
          <div className="landing-container">
            <div className="section-intro">
              <span className="section-kicker">Application Surface Map</span>
              <h2>Every major role already has a corresponding frontend portal.</h2>
              <p>This makes the UI directly executable against the architecture instead of remaining just a conceptual flowchart.</p>
            </div>
            <div className="portal-grid">
              {portalCards.map((portal) => (
                <Link key={portal.path} to={portal.path} className="portal-card">
                  <span className="portal-icon"><Icon name={portal.icon} size={18} /></span>
                  <h3>{portal.name}</h3>
                  <p>{portal.text}</p>
                  <span className="portal-link">Open portal <Icon name="arrow" size={15} /></span>
                </Link>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
