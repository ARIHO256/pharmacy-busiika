import { useEffect, useState } from 'react'
import { Alert, Badge, Card, Spinner } from '../../components/ui'
import { adminApi, governanceApi } from '../../api/endpoints'
import { fmtDateTime } from './helpers'

const ACTION_COLORS = [
  [/verify/i, 'green'],
  [/suspend/i, 'red'],
  [/activate/i, 'blue'],
  [/pay|paid|invoice/i, 'purple'],
  [/appointment|book/i, 'blue'],
]

function actionColor(action = '') {
  for (const [re, color] of ACTION_COLORS) if (re.test(action)) return color
  return 'slate'
}

export default function Audit() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    Promise.allSettled([adminApi.audit(), governanceApi.auditEvents({ limit: 200 })]).then(([legacy, governance]) => {
      if (!active) return
      const platformEvents = legacy.status === 'fulfilled' ? legacy.value.data.map((event) => ({
        ...event, id: `platform:${event.id}`, source: 'Platform',
      })) : []
      const clinicalEvents = governance.status === 'fulfilled' ? governance.value.data.map((event) => ({
        id: `governance:${event.id}`, source: 'Governance', action: event.action,
        user: event.actor_name, created_at: event.created_at,
        meta: { ...event.metadata, purpose: event.purpose, decision: event.decision,
          resource: [event.resource_type, event.resource_id].filter(Boolean).join(' ') },
      })) : []
      if (legacy.status === 'rejected' || governance.status === 'rejected') {
        setError('Some audit records could not be loaded.')
      }
      setItems([...platformEvents, ...clinicalEvents].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)))
    })
    return () => { active = false }
  }, [])

  if (items === null) return <Spinner label="Loading audit log…" />

  return (
    <Card title={`Recent audit events (${items.length})`}>
      {error && <Alert tone="danger" className="mb-4">{error}</Alert>}
      {items.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-8">No audit events yet</p>
      ) : (
        <ol className="relative border-l border-slate-200 ml-2 space-y-6">
          {items.map((log) => (
            <li key={log.id} className="ml-6">
              <span className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-primary-600 ring-4 ring-primary-50" />
              <div className="flex flex-wrap items-center gap-2">
                <Badge>{log.source}</Badge>
                <Badge color={actionColor(log.action)}>{log.action}</Badge>
                <span className="text-sm text-slate-600">{log.user || 'system'}</span>
                <span className="text-xs text-slate-400">{fmtDateTime(log.created_at)}</span>
              </div>
              {log.meta && Object.keys(log.meta).length > 0 && (
                <pre className="mt-2 text-xs bg-slate-50 border border-slate-100 rounded-lg p-3 overflow-x-auto text-slate-600">
                  {JSON.stringify(log.meta, null, 2)}
                </pre>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}
