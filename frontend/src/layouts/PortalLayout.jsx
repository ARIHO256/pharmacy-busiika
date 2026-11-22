import { useEffect, useMemo, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { ROLE_HOME, useAuth } from '../auth/AuthContext'
import { getRoleExperience } from '../config/roleExperience'
import HealthIcon from '../components/icons/HealthIcon'
import CareJourneyBar from '../components/shell/CareJourneyBar'
import CommandPalette from '../components/shell/CommandPalette'
import SupportWidget from '../components/shell/SupportWidget'
import NotificationCenter from '../components/shell/NotificationCenter'

function initials(user) {
  const value = [user?.first_name, user?.last_name].filter(Boolean).map((part) => part[0]).join('')
  return (value || user?.email?.[0] || 'M').slice(0, 2).toUpperCase()
}


function roleIcon(role) {
  return {
    patient: 'heart',
    doctor: 'doctor',
    nurse: 'activity',
    receptionist: 'calendar',
    records_officer: 'file',
    cashier: 'money',
    pharmacist: 'pill',
    storekeeper: 'pill',
    lab_technician: 'flask',
    facility_manager: 'hospital',
    pharmacy: 'pill',
    lab: 'flask',
    hospital: 'hospital',
    insurance: 'insurance',
    insurance_officer: 'insurance',
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

export default function PortalLayout({ title, nav: items = [], role = 'patient', productLabel, home }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const effectiveRole = user?.role || role
  const nav = useMemo(() => items.filter((item) => !item.roles || item.roles.includes(effectiveRole)), [items, effectiveRole])
  const experience = getRoleExperience(effectiveRole)
  const homePath = home || ROLE_HOME[effectiveRole] || nav[0]?.to || `/${role}`
  const [mobileOpen, setMobileOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const groupedNav = useMemo(() => groupNavigation(nav), [nav])
  const activeItem = useMemo(
    () => nav.find((item) => isItemActive(location.pathname, item)) || nav[0],
    [location.pathname, nav],
  )

  useEffect(() => {
    setMobileOpen(false)
    setProfileOpen(false)
  }, [location.pathname])

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

  const mobileNav = nav.filter((item) => item.group !== 'Settings').slice(0, 5)

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
              <small>{productLabel || `HealthOS · ${experience.label}`}</small>
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
            <span className="healthos-system-status" title="Platform services operational"><i /> Connected</span>
            {(!productLabel || nav.some((item) => item.to === experience.quickAction.to)) && <Link className="healthos-quick-action" to={experience.quickAction.to}>
              <HealthIcon name={experience.quickAction.icon} size={17}/>
              <span>{experience.quickAction.label}</span>
            </Link>}
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
                  <Link to={nav.find((item) => item.label.toLowerCase().includes('profile'))?.to || homePath}><HealthIcon name="user" size={17}/> Profile & settings</Link>
                  {!productLabel && <Link to="/"><HealthIcon name="globe" size={17}/> Public website</Link>}
                  <button type="button" onClick={signOut}><HealthIcon name="logout" size={17}/> Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>

        {!productLabel && <CareJourneyBar role={effectiveRole} />}

        <main id="main-content" tabIndex={-1} className="healthos-main">
          <section className="healthos-page-heading">
            <div>
              <span className="healthos-page-kicker">{experience.eyebrow}</span>
              <h1>{activeItem?.label || title}</h1>
              <p>{activeItem?.description || experience.description}</p>
            </div>
            <div className="healthos-heading-tools">
              <span><HealthIcon name="shield" size={15}/> Role protected</span>
              <span><HealthIcon name="activity" size={15}/> Live data</span>
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

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} nav={nav} roleLabel={experience.label} />
      <SupportWidget />
    </div>
  )
}
