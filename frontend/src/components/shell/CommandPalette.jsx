import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import HealthIcon from '../icons/HealthIcon'

export default function CommandPalette({ open, onClose, nav = [], roleLabel = 'Portal' }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    setQuery('')
    const timer = window.setTimeout(() => inputRef.current?.focus(), 30)
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(timer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, onClose])

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return nav
    return nav.filter((item) => `${item.label} ${item.group || ''} ${item.description || ''}`.toLowerCase().includes(needle))
  }, [nav, query])

  if (!open) return null

  const go = (to) => {
    navigate(to)
    onClose()
  }

  return (
    <div className="command-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="command-dialog" role="dialog" aria-modal="true" aria-label={`${roleLabel} navigation search`} onMouseDown={(event) => event.stopPropagation()}>
        <div className="command-search-row">
          <HealthIcon name="search" size={20} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={`Search ${roleLabel.toLowerCase()} pages and actions…`}
            aria-label="Search pages"
          />
          <kbd>ESC</kbd>
        </div>
        <div className="command-results">
          <div className="command-section-label">Navigate</div>
          {results.length === 0 ? (
            <div className="command-empty">No matching page found.</div>
          ) : (
            results.map((item) => (
              <button key={item.to} type="button" onClick={() => go(item.to)} className="command-result">
                <span className="command-result-icon"><HealthIcon name={item.icon || 'file'} size={18} /></span>
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.description || item.group || 'Open page'}</small>
                </span>
                <HealthIcon name="chevron" size={16} />
              </button>
            ))
          )}
        </div>
        <footer className="command-footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> browse</span>
          <span><kbd>↵</kbd> open</span>
          <span>MyDoctor HealthOS</span>
        </footer>
      </section>
    </div>
  )
}
