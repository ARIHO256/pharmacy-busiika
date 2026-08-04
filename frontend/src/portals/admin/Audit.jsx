import { useEffect, useState } from 'react'
import { Badge, Card, Spinner } from '../../components/ui'
import { adminApi } from '../../api/endpoints'
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
    adminApi
      .audit()
      .then((res) => setItems(res.data))
      .catch(() => {
        setItems([])
        setError('Failed to load audit log.')
      })
  }, [])

  if (error)
    return (
      <Card>
        <p className="text-sm text-rose-600">{error}</p>
      </Card>
    )
  if (items === null) return <Spinner label="Loading audit log…" />

  return (
    <Card title={`Audit Log (${items.length})`}>
      {items.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-8">No audit events yet</p>
      ) : (
        <ol className="relative border-l border-slate-200 ml-2 space-y-6">
          {items.map((log) => (
            <li key={log.id} className="ml-6">
              <span className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-primary-600 ring-4 ring-primary-50" />
              <div className="flex flex-wrap items-center gap-2">
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
