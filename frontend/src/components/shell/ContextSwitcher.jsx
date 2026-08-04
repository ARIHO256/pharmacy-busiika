import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ROLE_HOME, useAuth } from '../../auth/AuthContext'
import HealthIcon from '../icons/HealthIcon'

function contextLabel(context) {
  const scope = [context.organization_name, context.location_name, context.department_name].filter(Boolean).join(' · ')
  return `${context.title || context.role_code.replaceAll('_', ' ')}${scope ? ` — ${scope}` : ''}`
}

export default function ContextSwitcher() {
  const { activeContext, availableContexts, activateContext, activeRole } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)

  if (!availableContexts?.length) return null

  const choose = async (context) => {
    if (context.id === activeContext?.id) {
      setOpen(false)
      return
    }
    setBusy(true)
    try {
      const updated = await activateContext(context.id)
      const role = updated?.active_context?.role_code || updated?.role || activeRole
      navigate(ROLE_HOME[role] || '/dashboard', { replace: true })
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="healthos-context-wrap">
      <button type="button" className="healthos-context-trigger" onClick={() => setOpen((value) => !value)} aria-expanded={open} disabled={busy}>
        <span className="healthos-context-icon"><HealthIcon name="building" size={16}/></span>
        <span className="healthos-context-copy">
          <small>Active role & facility</small>
          <strong>{activeContext ? contextLabel(activeContext) : activeRole?.replaceAll('_', ' ')}</strong>
        </span>
        <HealthIcon name="chevron" size={13}/>
      </button>
      {open && (
        <div className="healthos-context-menu">
          <header>
            <strong>Switch working context</strong>
            <small>Permissions, menus and data scope update immediately.</small>
          </header>
          <div className="healthos-context-list">
            {availableContexts.map((context) => (
              <button key={context.id} type="button" onClick={() => choose(context)} className={context.id === activeContext?.id ? 'is-active' : ''}>
                <span className="healthos-context-check"><HealthIcon name={context.id === activeContext?.id ? 'check' : 'user'} size={15}/></span>
                <span><strong>{context.title || context.role_code.replaceAll('_', ' ')}</strong><small>{[context.organization_name, context.location_name, context.department_name].filter(Boolean).join(' · ') || 'Platform-wide context'}</small></span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
