import { useEffect, useState } from 'react'
import { enterpriseApi } from '../../api/endpoints'
import { Alert, Spinner } from '../../components/ui'
import RecordWorkspace from '../enterprise/RecordWorkspace'

export default function AdminWorkflowWorkspace() {
  const [types, setTypes] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    enterpriseApi.schema()
      .then(({ data }) => setTypes(Object.keys(data.schemas || {})))
      .catch((err) => setError(err.response?.data?.detail || 'Could not load enterprise workflow schemas.'))
  }, [])
  if (error) return <Alert tone="danger" title="Enterprise workflows unavailable">{error}</Alert>
  if (!types) return <Spinner label="Loading all clinical and operational workflows…" />
  return <RecordWorkspace module={{ id: 'admin-enterprise-workflows', label: 'All Enterprise Workflows', icon: 'activity', group: 'Platform operations', description: 'Create, assign, transition and audit every schema-driven clinical, operational, finance, records, verification and security workflow.', recordTypes: types, kind: 'records' }} />
}
