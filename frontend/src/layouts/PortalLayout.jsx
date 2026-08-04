import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import { getRoleExperience } from '../config/roleExperience'
import HealthIcon from '../components/icons/HealthIcon'
import CareJourneyBar from '../components/shell/CareJourneyBar'
import CommandPalette from '../components/shell/CommandPalette'
import SupportWidget from '../components/shell/SupportWidget'
import NotificationCenter from '../components/shell/NotificationCenter'
import ContextSwitcher from '../components/shell/ContextSwitcher'
import { enterpriseApi } from '../api/endpoints'

const RELEASE_REVIEW_ROLES = new Set(['admin','platform_super_admin','operations_admin','compliance_admin','clinical_safety_admin','medical_director','doctor','nurse','midwife','lab_technician','pharmacist','accountant','finance_manager','records_officer','compliance_officer','it_support'])

function initials(user) {
  const value = [user?.first_name, user?.last_name].filter(Boolean).map((part) => part[0]).join('')
  return (value || user?.email?.[0] || 'M').slice(0, 2).toUpperCase()
}


function roleIcon(role) {
  return {
    patient: 'heart',
    doctor: 'doctor',
    clinical_officer: 'doctor', dentist: 'doctor', physiotherapist: 'activity', nutritionist: 'heart', psychologist: 'heart', medical_director: 'shield',
    nurse: 'activity', midwife: 'activity', theatre_nurse: 'activity', paramedic: 'activity',
    receptionist: 'calendar',
    records_officer: 'file',
    cashier: 'money', accountant: 'money', finance_manager: 'money',
    pharmacist: 'pill',
    storekeeper: 'pill',
    lab_technician: 'flask', radiologist: 'activity', radiographer: 'activity', anaesthetist: 'activity',
    facility_manager: 'hospital', procurement_officer: 'file', quality_officer: 'shield', compliance_officer: 'shield', hr_officer: 'users', it_support: 'settings', ambulance_dispatcher: 'calendar',
    pharmacy: 'pill',
    lab: 'flask',
    hospital: 'hospital',
    insurance: 'insurance',
    insurance_officer: 'insurance', claims_reviewer: 'insurance',
    admin: 'shield',
  }[role] || 'heart'
}

function groupNavigation(nav) {
  return nav.reduce((groups, item) => {
    const key = item.group || 'Workspace'
    if (!groups[key]) groups[key] = []
    groups[key].push(item)
    return groups
  }, {})
}

function isItemActive(pathname, item) {
  if (item.end) return pathname === item.to
  return pathname === item.to || pathname.startsWith(`${item.to}/`)
}

export default function PortalLayout({ title, nav = [], role = 'patient' }) {
  const { user, logout, activeRole } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const effectiveRole = activeRole || user?.role || role
  const experience = getRoleExperience(effectiveRole)
  const homePath = ROLE_HOME[effectiveRole] || nav[0]?.to || `/${role}`
  const [mobileOpen, setMobileOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [systemHealth, setSystemHealth] = useState({ state: 'checking', checkedAt: null })

  const visibleNav = useMemo(
    () => nav.filter((item) => !item.roles || item.roles.includes(effectiveRole)),
    [nav, effectiveRole],
  )
  const groupedNav = useMemo(() => groupNavigation(visibleNav), [visibleNav])
  const activeItem = useMemo(
    () => visibleNav.find((item) => isItemActive(location.pathname, item)) || visibleNav[0],
    [location.pathname, visibleNav],
  )

  useEffect(() => {
    setMobileOpen(false)
    setProfileOpen(false)
  }, [location.pathname])

  useEffect(() => {
    let mounted = true
    let timer
    const checkHealth = async () => {
      try {
        const { data } = await enterpriseApi.readiness()
        if (mounted) setSystemHealth({ state: data?.status || 'operational', checkedAt: new Date() })
      } catch {
        if (mounted) setSystemHealth({ state: navigator.onLine ? 'degraded' : 'offline', checkedAt: new Date() })
      }
    }
    checkHealth()
    timer = window.setInterval(checkHealth, 60000)
    const online = () => checkHealth()
    const offline = () => setSystemHealth({ state: 'offline', checkedAt: new Date() })
    window.addEventListener('online', online)
    window.addEventListener('offline', offline)
    return () => {
      mounted = false
      window.clearInterval(timer)
      window.removeEventListener('online', online)
      window.removeEventListener('offline', offline)
    }
  }, [])

  useEffect(() => {
    const onKeyDown = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen((value) => !value)
      }
      if (event.key === 'Escape') {
        setProfileOpen(false)
        setMobileOpen(false)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [])

  const signOut = () => {
    logout()
    navigate('/login')
  }

  const mobileNav = visibleNav.filter((item) => item.group !== 'Settings').slice(0, 5)
  const healthOperational = ['operational', 'ok', 'ready', 'healthy'].includes(String(systemHealth.state).toLowerCase())
  const healthLabel = systemHealth.state === 'checking' ? 'Checking' : healthOperational ? 'Operational' : systemHealth.state === 'offline' ? 'Offline' : 'Degraded'

  return (
    <div className={`healthos-shell role-${effectiveRole}`}>
      <a className="healthos-skip-link" href="#main-content">Skip to main content</a>

      <aside className={`healthos-sidebar ${mobileOpen ? 'is-open' : ''}`} aria-label={`${experience.label} navigation`}>
        <div className="healthos-brand-row">
          <Link to={homePath} className="healthos-brand" aria-label={`${experience.title} home`}>
            <span className="healthos-brand-mark" aria-hidden="true">
              <span className="healthos-brand-pulse" />
              <HealthIcon name="heart" size={19} strokeWidth={2.2} />
            </span>
            <span className="healthos-brand-copy">
              <strong>MyDoctor</strong>
              <small>HealthOS · {experience.label}</small>
            </span>
          </Link>
          <button type="button" className="healthos-icon-button sidebar-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
            <HealthIcon name="close" size={20} />
          </button>
        </div>

        <div className="healthos-role-card">
          <span className={`healthos-role-avatar tone-${experience.avatarTone}`}><HealthIcon name={roleIcon(effectiveRole)} size={20}/></span>
          <span>
            <small>{experience.eyebrow}</small>
            <strong>{experience.title}</strong>
          </span>
        </div>

        <nav className="healthos-sidebar-nav">
          {Object.entries(groupedNav).map(([group, items]) => (
            <section className="healthos-nav-group" key={group}>
              <h2>{group}</h2>
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => `healthos-nav-link ${isActive ? 'is-active' : ''}`}
                  title={item.description}
                >
                  <span className="healthos-nav-icon"><HealthIcon name={item.icon || 'file'} size={18}/></span>
                  <span className="healthos-nav-copy">
                    <strong>{item.label}</strong>
                    {item.badge ? <small className="healthos-nav-badge">{item.badge}</small> : null}
                  </span>
                  <HealthIcon name="chevron" size={14} className="healthos-nav-chevron" />
                </NavLink>
              ))}
            </section>
          ))}
        </nav>

        <div className="healthos-sidebar-footer">
          <div className="healthos-trust-line"><span /> Secure clinical workspace</div>
          <button type="button" className="healthos-signout" onClick={signOut}>
            <HealthIcon name="logout" size={17}/>
            Sign out
          </button>
        </div>
      </aside>

      {mobileOpen && <button type="button" className="healthos-sidebar-backdrop" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" />}

      <div className="healthos-workspace">
        <header className="healthos-topbar">
          <div className="healthos-topbar-left">
            <button type="button" className="healthos-icon-button mobile-menu-trigger" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
              <HealthIcon name="menu" size={21}/>
            </button>
            <Link to={homePath} className="healthos-mobile-brand"><span>M+</span> MyDoctor</Link>
            <div className="healthos-page-context">
              <span>{experience.label} workspace</span>
              <strong>{activeItem?.label || title}</strong>
            </div>
          </div>

          <div className="healthos-topbar-actions">
            <button type="button" className="healthos-search-trigger" onClick={() => setCommandOpen(true)} aria-label="Search pages and actions">
              <HealthIcon name="search" size={18}/>
              <span>Search workspace</span>
              <kbd>Ctrl K</kbd>
            </button>
            <ContextSwitcher />
            <Link to="/status" className={`healthos-system-status is-${healthLabel.toLowerCase()}`} title={`Platform status: ${healthLabel}`}><i /> {healthLabel}</Link>
            <Link className="healthos-quick-action" to={experience.quickAction.to}>
              <HealthIcon name={experience.quickAction.icon} size={17}/>
              <span>{experience.quickAction.label}</span>
            </Link>
            <NotificationCenter />
            <div className="healthos-profile-wrap">
              <button type="button" className="healthos-profile-button" onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen}>
                <span className={`healthos-user-avatar tone-${experience.avatarTone}`}>{initials(user)}</span>
                <span className="healthos-user-copy">
                  <strong>{[user?.first_name, user?.last_name].filter(Boolean).join(' ') || experience.label}</strong>
                  <small>{user?.email || 'Authenticated workspace'}</small>
                </span>
                <HealthIcon name="chevron" size={14}/>
              </button>
              {profileOpen && (
                <div className="healthos-profile-menu">
                  <div className="healthos-profile-summary">
                    <span className={`healthos-user-avatar tone-${experience.avatarTone}`}>{initials(user)}</span>
                    <div><strong>{[user?.first_name, user?.last_name].filter(Boolean).join(' ') || experience.label}</strong><small>{experience.title}</small></div>
                  </div>
                  <Link to={visibleNav.find((item) => item.label.toLowerCase().includes('profile'))?.to || homePath}><HealthIcon name="user" size={17}/> Profile & settings</Link>
                  <Link to="/security"><HealthIcon name="shield" size={17}/> Security centre</Link>
                  <Link to="/notification-settings"><HealthIcon name="bell" size={17}/> Notification preferences</Link>
                  {RELEASE_REVIEW_ROLES.has(effectiveRole) ? <Link to="/release-acceptance"><HealthIcon name="verified" size={17}/> Release acceptance</Link> : null}
                  <Link to="/"><HealthIcon name="globe" size={17}/> Public website</Link>
                  <button type="button" onClick={signOut}><HealthIcon name="logout" size={17}/> Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>

        <CareJourneyBar role={effectiveRole} />

        <main id="main-content" className="healthos-main">
          <section className="healthos-page-heading">
            <div>
              <span className="healthos-page-kicker">{experience.eyebrow}</span>
              <h1>{activeItem?.label || title}</h1>
              <p>{activeItem?.description || experience.description}</p>
            </div>
            <div className="healthos-heading-tools">
              <span><HealthIcon name="shield" size={15}/> Role protected</span>
              <span><HealthIcon name="activity" size={15}/> {healthOperational ? 'Live data' : healthLabel}</span>
            </div>
          </section>
          <Outlet />
        </main>
      </div>

      <nav className="healthos-mobile-bottom-nav" aria-label="Primary mobile navigation" style={{ '--mobile-nav-count': Math.min(6, mobileNav.length + 1) }}>
        {mobileNav.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => isActive ? 'is-active' : ''}>
            <HealthIcon name={item.icon || 'file'} size={19}/>
            <span>{item.label.split(' ')[0]}</span>
          </NavLink>
        ))}
        <button type="button" onClick={() => setMobileOpen(true)}><HealthIcon name="menu" size={19}/><span>More</span></button>
      </nav>

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} nav={visibleNav} roleLabel={experience.label} />
      <SupportWidget />
    </div>
  )
}
