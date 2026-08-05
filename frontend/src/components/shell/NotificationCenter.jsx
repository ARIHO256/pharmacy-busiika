import { useEffect, useRef, useState } from 'react'
import { chatApi } from '../../api/endpoints'
import HealthIcon from '../icons/HealthIcon'

function formatTime(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

export default function NotificationCenter() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(false)
  const wrap = useRef(null)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await chatApi.notifications({ limit: 25 })
      const rows = Array.isArray(data) ? data : data.results || []
      setItems(rows)
      setUnread(Array.isArray(data) ? rows.filter((item) => !item.is_read).length : data.unread_count || 0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => {})
    const interval = window.setInterval(() => load().catch(() => {}), 60000)
    let socket
    let reconnect
    let failures = 0
    let stopped = false
    const connect = () => {
      if (stopped) return
      const token = localStorage.getItem('access')
      if (!token) return
      const apiBase = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:4000/api`
      const url = new URL(apiBase, window.location.origin)
      const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${url.host}/ws/notifications/?token=${encodeURIComponent(token)}`)
      socket.onopen = () => { failures = 0 }
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'notification' && message.notification) {
            setItems((rows) => [message.notification, ...rows.filter((row) => row.id !== message.notification.id)].slice(0, 25))
            if (!message.notification.is_read) setUnread((value) => value + 1)
          }
        } catch { /* Ignore malformed provider frames. */ }
      }
      socket.onclose = (event) => {
        if (stopped) return
        // Auth rejections (4401) stop the socket entirely; polling above remains
        // the fallback channel. Transient closes retry with capped backoff.
        if (event.code === 4401) return
        failures += 1
        if (failures > 6) return
        const delay = Math.min(5000 * 2 ** (failures - 1), 60000)
        reconnect = window.setTimeout(connect, delay)
      }
    }
    connect()
    return () => {
      stopped = true
      window.clearInterval(interval)
      window.clearTimeout(reconnect)
      if (socket) { socket.onclose = null; socket.close() }
    }
  }, [])

  useEffect(() => {
    const outside = (event) => {
      if (open && wrap.current && !wrap.current.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', outside)
    return () => document.removeEventListener('mousedown', outside)
  }, [open])

  const read = async (item) => {
    if (!item.is_read) {
      await chatApi.markRead(item.id)
      setItems((old) => old.map((row) => row.id === item.id ? { ...row, is_read: true } : row))
      setUnread((value) => Math.max(0, value - 1))
    }
    if (item.action_url) window.location.assign(item.action_url)
  }

  const readAll = async () => {
    await chatApi.markAllRead()
    setItems((old) => old.map((row) => ({ ...row, is_read: true })))
    setUnread(0)
  }

  return (
    <div className="relative" ref={wrap}>
      <button type="button" className="healthos-icon-button notification-button" aria-label={`Notifications${unread ? `, ${unread} unread` : ''}`} onClick={() => setOpen((value) => !value)}>
        <HealthIcon name="bell" size={19}/>
        {unread > 0 && <span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full bg-rose-600 px-1 text-[10px] font-bold text-white">{unread > 99 ? '99+' : unread}</span>}
      </button>
      {open && (
        <section className="absolute right-0 z-[140] mt-3 w-[min(92vw,390px)] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
          <header className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div><strong className="text-sm text-slate-900">Notifications</strong><p className="text-xs text-slate-500">Care, billing and account updates</p></div>
            {unread > 0 && <button type="button" onClick={readAll} className="text-xs font-semibold text-primary-700">Mark all read</button>}
          </header>
          <div className="max-h-[430px] overflow-y-auto">
            {loading && !items.length && <div className="p-8 text-center text-sm text-slate-400">Loading notifications…</div>}
            {!loading && !items.length && <div className="p-8 text-center text-sm text-slate-400">You are all caught up.</div>}
            {items.map((item) => (
              <button key={item.id} type="button" onClick={() => read(item)} className={`flex w-full gap-3 border-b border-slate-100 p-4 text-left last:border-0 hover:bg-slate-50 ${item.is_read ? '' : 'bg-primary-50/50'}`}>
                <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${item.is_read ? 'bg-slate-200' : ['critical', 'high'].includes(item.priority) ? 'bg-rose-500' : 'bg-primary-500'}`} />
                <span className="min-w-0"><strong className="block truncate text-sm text-slate-800">{item.title}</strong><span className="mt-1 block text-xs leading-5 text-slate-500">{item.body}</span><small className="mt-1 block text-[11px] text-slate-400">{formatTime(item.created_at)}</small></span>
              </button>
            ))}
          </div>
          <footer className="border-t border-slate-100 bg-slate-50 px-4 py-3 text-right">
            <button type="button" className="text-xs font-semibold text-primary-700 hover:underline" onClick={() => window.location.assign('/notification-settings')}>Notification settings</button>
          </footer>
        </section>
      )}
    </div>
  )
}
