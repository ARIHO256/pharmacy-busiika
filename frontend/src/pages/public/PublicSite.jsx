import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import HealthIcon from '../../components/icons/HealthIcon'
import { authApi, enterpriseApi, servicesApi } from '../../api/endpoints'

const PAGE_COPY = {
  about: ['About HealthPilot', 'A connected healthcare operating system for patients, professionals and facilities.', ['Verified healthcare access', 'Coordinated clinical records', 'Transparent billing and insurance', 'Secure role-based operations']],
  contact: ['Contact HealthPilot', 'Reach the right team for care access, partnerships, technical support or compliance.', ['Patient support', 'Facility onboarding', 'Professional verification', 'Privacy and compliance']],
  help: ['Help centre', 'Practical guidance for registration, bookings, consultations, payments and facility workflows.', ['Getting started', 'Appointments and telehealth', 'Payments and receipts', 'Account security']],
  faq: ['Frequently asked questions', 'Answers to the most common patient, professional and organization questions.', ['Who can register?', 'How verification works', 'How records are protected', 'How payments are confirmed']],
  pricing: ['Plans built for every care setting', 'Start with individual care access and scale to multi-branch healthcare operations.', ['Patient access', 'Professional practice', 'Facility operations', 'Enterprise integrations']],
  privacy: ['Privacy policy', 'How HealthPilot collects, protects, uses and discloses personal and health information.', ['Lawful and transparent use', 'Minimum necessary access', 'Patient rights', 'Security and retention']],
  terms: ['Terms and conditions', 'The rules governing use of HealthPilot services, accounts, bookings and organization workspaces.', ['Account responsibilities', 'Clinical service boundaries', 'Payment terms', 'Acceptable use']],
  'medical-disclaimer': ['Medical disclaimer', 'HealthPilot supports care coordination but does not replace emergency services or independent clinical judgement.', ['Emergency limitations', 'Professional responsibility', 'Information accuracy', 'No self-diagnosis guarantee']],
  cookies: ['Cookie notice', 'How essential, preference and analytics technologies are used on the platform.', ['Essential security cookies', 'Preference storage', 'Analytics controls', 'Consent choices']],
  accessibility: ['Accessibility statement', 'Our commitment to usable, understandable and inclusive healthcare experiences.', ['Keyboard navigation', 'Readable contrast', 'Assistive technology', 'Continuous testing']],
  'data-processing': ['Data processing information', 'A clear summary of controller, processor, sharing and retention responsibilities.', ['Processing purposes', 'Authorized recipients', 'Cross-border safeguards', 'Retention and deletion']],
  'browser-compatibility': ['Browser compatibility', 'Use a current browser for the safest and most reliable HealthPilot experience.', ['Chrome and Chromium', 'Firefox', 'Safari', 'Microsoft Edge']],
}

const DIRECTORY_CONFIG = {
  doctors: { title: 'Verified healthcare professionals', icon: 'doctor', load: () => authApi.doctors({ verified: true }) },
  facilities: { title: 'Hospitals and clinics', icon: 'hospital', load: () => servicesApi.providers('hospitals') },
  pharmacies: { title: 'Pharmacies', icon: 'pill', load: () => servicesApi.providers('pharmacies') },
  laboratories: { title: 'Laboratories', icon: 'flask', load: () => servicesApi.providers('labs') },
  insurance: { title: 'Insurance organizations', icon: 'insurance', load: () => servicesApi.providers('insurance') },
  services: { title: 'Healthcare services', icon: 'heart', load: () => servicesApi.providers('hospitals') },
}

function PublicHeader() {
  return (
    <header className="public-site-header">
      <Link to="/" className="public-site-brand"><span><HealthIcon name="heart" size={19}/></span><strong>HealthPilot</strong><small>Connected HealthOS</small></Link>
      <nav aria-label="Public navigation">
        <Link to="/about">About</Link><Link to="/directory/doctors">Find care</Link><Link to="/pricing">Pricing</Link><Link to="/help">Help</Link>
      </nav>
      <div className="public-site-actions"><Link to="/login">Sign in</Link><Link className="public-primary-link" to="/register">Get started</Link></div>
    </header>
  )
}

function PublicFooter() {
  return (
    <footer className="public-site-footer">
      <div><strong>HealthPilot HealthOS</strong><p>Connected, secure and role-aware healthcare.</p></div>
      <div><h3>Care</h3><Link to="/directory/doctors">Doctors</Link><Link to="/directory/facilities">Facilities</Link><Link to="/directory/pharmacies">Pharmacies</Link><Link to="/directory/laboratories">Laboratories</Link></div>
      <div><h3>Company</h3><Link to="/about">About</Link><Link to="/contact">Contact</Link><Link to="/help">Help centre</Link><Link to="/faq">FAQs</Link></div>
      <div><h3>Trust</h3><Link to="/privacy">Privacy</Link><Link to="/terms">Terms</Link><Link to="/medical-disclaimer">Medical disclaimer</Link><Link to="/accessibility">Accessibility</Link></div>
    </footer>
  )
}

export function PublicInfoPage({ pageKey }) {
  const [title, intro, topics] = PAGE_COPY[pageKey] || PAGE_COPY.about
  return (
    <div className="public-site-shell">
      <PublicHeader />
      <main className="public-info-main">
        <section className="public-info-hero"><span>HealthPilot public information</span><h1>{title}</h1><p>{intro}</p></section>
        <section className="public-info-grid">
          {topics.map((topic, index) => <article key={topic}><span>{String(index + 1).padStart(2, '0')}</span><h2>{topic}</h2><p>Clear guidance, accountable ownership and secure digital workflows are provided for this area.</p><Link to={pageKey === 'contact' ? '/help' : '/register'}>{pageKey === 'contact' ? 'Open support' : 'Continue'} <HealthIcon name="chevron" size={14}/></Link></article>)}
        </section>
        <section className="public-callout"><div><span>Need personal assistance?</span><h2>Access support without losing your place in the care journey.</h2></div><Link to="/contact">Contact support</Link></section>
      </main>
      <PublicFooter />
    </div>
  )
}

function normalizeRows(response) {
  const value = response?.data ?? response ?? []
  if (Array.isArray(value)) return value
  return value.results || value.items || value.providers || value.doctors || []
}

export function PublicDirectoryPage({ kind }) {
  const config = DIRECTORY_CONFIG[kind] || DIRECTORY_CONFIG.doctors
  const [rows, setRows] = useState([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setLoading(true)
    config.load().then((response) => { if (active) setRows(normalizeRows(response)) }).catch(() => { if (active) setError('The directory service is temporarily unavailable. You can still register or contact support.') }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [kind])
  const filtered = useMemo(() => rows.filter((row) => JSON.stringify(row).toLowerCase().includes(query.toLowerCase())), [rows, query])
  return (
    <div className="public-site-shell">
      <PublicHeader />
      <main className="public-directory-main">
        <section className="public-directory-hero"><div><span>Verified healthcare network</span><h1>{config.title}</h1><p>Search trusted providers, compare services and continue to secure booking.</p></div><div className="public-directory-search"><HealthIcon name="search" size={18}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, service or location"/></div></section>
        {error && <div className="public-notice">{error}</div>}
        <section className="public-directory-grid">
          {loading ? Array.from({ length: 6 }).map((_, index) => <div className="public-directory-card is-loading" key={index}/>) : filtered.map((row, index) => {
            const name = row.full_name || row.name || row.organization_name || row.display_name || `Provider ${index + 1}`
            const subtitle = row.speciality || row.organization_type || row.location || row.address || 'Verified HealthPilot network member'
            const id = row.id || index
            return <article className="public-directory-card" key={`${id}-${name}`}><div className="public-directory-avatar"><HealthIcon name={config.icon} size={25}/></div><div><span className="public-verified"><HealthIcon name="shield" size={13}/> Verified profile</span><h2>{name}</h2><p>{subtitle}</p><div className="public-directory-meta"><span>{row.location || row.district || 'Location available'}</span><span>{row.consultation_fee ? `UGX ${row.consultation_fee}` : 'Contact for pricing'}</span></div></div><Link to={`/directory/${kind}/${id}`}>View profile</Link></article>
          })}
          {!loading && !filtered.length && <div className="public-empty"><HealthIcon name="search" size={26}/><h2>No matching profiles</h2><p>Try another name, service or location.</p></div>}
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}

export function PublicProfilePage({ kind }) {
  const { id } = useParams()
  return (
    <div className="public-site-shell">
      <PublicHeader />
      <main className="public-profile-main">
        <section className="public-profile-hero"><div className="public-profile-mark"><HealthIcon name={DIRECTORY_CONFIG[kind]?.icon || 'hospital'} size={34}/></div><div><span className="public-verified"><HealthIcon name="shield" size={14}/> Public verification summary</span><h1>Provider profile</h1><p>Profile reference #{id}. Protected clinical and licence evidence remains available only to authorised users.</p></div><Link to="/login">Sign in to book</Link></section>
        <section className="public-profile-grid"><article><h2>Services and expertise</h2><p>Verified service information, consultation modes and availability are presented here once returned by the provider directory.</p></article><article><h2>Location and access</h2><p>Facility location, hours, accessibility and care instructions.</p></article><article><h2>Verification</h2><p>Current HealthPilot verification status without exposing private licence files.</p></article><article><h2>Patient experience</h2><p>Approved reviews, communication options and booking policies.</p></article></section>
      </main>
      <PublicFooter />
    </div>
  )
}

export function SystemStatusPage() {
  const [status, setStatus] = useState({ state: 'checking', checkedAt: null, checks: {} })
  useEffect(() => {
    let active = true
    const load = () => enterpriseApi.readiness().then(({ data }) => {
      if (!active) return
      setStatus({ state: data?.ready ? 'ready' : 'degraded', checks: data?.checks || {}, checkedAt: new Date(data?.checked_at || Date.now()) })
    }).catch(() => active && setStatus({ state: 'offline', checks: {}, checkedAt: new Date() }))
    load()
    const timer = window.setInterval(load, 30000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  const serviceRows = [
    ['Web application', navigator.onLine],
    ['Django API', status.state !== 'offline' && status.state !== 'checking'],
    ['Database', status.checks.database],
    ['Cache and sessions', status.checks.cache],
    ['Private object storage', status.checks.private_storage_configured],
    ['Malware scanner', status.checks.malware_scanner_configured],
    ['Event pipeline', status.checks.event_pipeline],
    ['Telemedicine provider', Boolean(status.checks.telemedicine_provider)],
  ]
  const operational = status.state === 'ready'
  const serviceLabel = (value) => status.state === 'checking' ? 'Checking' : value === true ? 'Operational' : value ? String(value) : 'Not configured'
  return <div className="public-site-shell"><PublicHeader/><main className="public-status-main"><section><span className={operational ? 'is-operational' : 'is-degraded'}/><div><p>HealthPilot service status</p><h1>{operational ? 'All required core checks are healthy' : status.state === 'checking' ? 'Checking platform services' : 'One or more services require attention'}</h1><small>{status.checkedAt ? `Checked ${status.checkedAt.toLocaleString()}` : 'Connecting to health checks…'}</small></div></section>{serviceRows.map(([service,value]) => <article key={service}><strong>{service}</strong><span>{serviceLabel(value)}</span></article>)}</main><PublicFooter/></div>
}

export function ErrorPage({ code = 404, title, message }) {
  const copy = { 403: ['Access restricted', 'Your current role or organization context does not permit this action.'], 404: ['Page not found', 'The page may have moved, or the address may be incorrect.'], 500: ['Something went wrong', 'The incident has been captured. Return safely and try again.'], maintenance: ['Scheduled maintenance', 'HealthPilot is temporarily unavailable while services are improved.'], offline: ['You are offline', 'Reconnect to continue with live clinical and operational data.'] }
  const [defaultTitle, defaultMessage] = copy[code] || copy[404]
  return <main className="public-error-page"><div><span>{typeof code === 'number' ? code : 'HealthPilot'}</span><HealthIcon name={code === 403 ? 'shield' : code === 'offline' ? 'activity' : 'heart'} size={38}/><h1>{title || defaultTitle}</h1><p>{message || defaultMessage}</p><div><Link to="/">Public home</Link><Link to="/dashboard">My dashboard</Link></div></div></main>
}
