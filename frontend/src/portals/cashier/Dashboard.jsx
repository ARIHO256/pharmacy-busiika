import { Link } from 'react-router-dom'
import { billingApi } from '../../api/endpoints'
import { Alert, Card, Spinner, Stat, Table } from '../../components/ui'
import { money, statusBadge, useRemote } from '../staff/shared'

export default function Dashboard() {
  const summary = useRemote(() => billingApi.summary(), [])
  const invoices = useRemote(() => billingApi.invoices(), [])
  if (summary.loading || invoices.loading) return <Spinner />
  if (summary.error || invoices.error) return <Alert tone="danger">{summary.error || invoices.error}</Alert>
  const data = summary.data || {}
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Stat label="Open invoices" value={data.pending_invoices || 0} icon="file"/><Stat label="Outstanding" value={money(data.outstanding_amount || 0)} icon="money"/><Stat label="Collected today" value={money(data.collected_today || 0)} icon="check"/><Stat label="Receipts today" value={data.receipts_today || 0} icon="activity"/></div>
    <Card title="Recent invoices" actions={<Link to="/cashier/invoices" className="text-sm font-semibold text-primary-700">Open billing desk →</Link>}><Table rows={(invoices.data || []).slice(0, 8)} columns={[{key:'number',label:'Invoice'},{key:'patient_name',label:'Patient'},{key:'amount',label:'Total',render:(i)=>money(i.amount,i.currency)},{key:'balance',label:'Balance',render:(i)=>money(i.balance,i.currency)},{key:'status',label:'Status',render:(i)=>statusBadge(i.status)}]}/></Card>
  </div>
}
