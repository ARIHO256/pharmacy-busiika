import { useState } from 'react'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Spinner, Table } from '../../components/ui'
import { money, useRemote } from '../staff/shared'

export default function Reports() {
  const [range, setRange] = useState({ start: '', end: '' })
  const [dates, setDates] = useState({})
  const report = useRemote(() => servicesApi.pharmacyReports(dates), [dates])
  const data = report.data
  const format = (value) => money(value, data.currency)
  const submit = (event) => {
    event.preventDefault()
    setDates(Object.fromEntries(Object.entries(range).filter(([, value]) => value)))
  }

  return <div className="space-y-4">
    <Card title="Pharmacy reports">
      <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
        <Input type="date" label="From" value={range.start} onChange={(e) => setRange({ ...range, start: e.target.value })} />
        <Input type="date" label="Through" min={range.start || undefined} value={range.end} onChange={(e) => setRange({ ...range, end: e.target.value })} />
        <Button disabled={report.loading}>Apply dates</Button>
      </form>
    </Card>
    {report.error && <Alert tone="danger">{report.error}</Alert>}
    {report.loading ? <Spinner /> : !report.error && data && <>
      <Card title="Recorded sales" subtitle={`${data.start} to ${data.end}`}>
        <div className="mb-4 flex flex-wrap gap-x-10 gap-y-3">
          <Metric label="Confirmed payments" value={format(data.sales.revenue)} />
          <Metric label="Paid orders" value={data.sales.paid_orders} />
        </div>
        <Table rows={data.sales.payment_methods.map((row) => ({ ...row, id: row.method }))} empty="No confirmed payments in this period" columns={[
          { key: 'method', label: 'Payment method', render: (row) => row.method.replaceAll('_', ' ') },
          { key: 'total', label: 'Amount received', render: (row) => format(row.total) },
        ]} />
      </Card>
      <Card title="Estimated gross margin" subtitle="Based on paid sales with traceable purchase costs for every unit.">
        <div className="flex flex-wrap gap-x-10 gap-y-3">
          <Metric label="Sales with known costs" value={format(data.margin.costed_revenue)} />
          <Metric label="Estimated cost of goods sold" value={format(data.margin.estimated_cost)} />
          <Metric label="Estimated gross margin" value={format(data.margin.estimated_gross_margin)} />
          <Metric label="Sales with missing costs" value={format(data.margin.uncosted_revenue)} />
        </div>
      </Card>
      <Card title="Estimated stock valuation" subtitle={`Current saleable stock as of ${data.stock_as_of}, using batch purchase costs.`}>
        <div className="flex flex-wrap gap-x-10 gap-y-3">
          <Metric label="Stock value with known costs" value={format(data.stock.estimated_value)} />
          <Metric label="Units with known costs" value={data.stock.counted_units} />
          <Metric label="Units with missing costs" value={data.stock.unknown_cost_units} />
          <Metric label="Unbatched units" value={data.stock.unbatched_units} />
          <Metric label="Expired, recalled or quarantined units" value={data.stock.excluded_units} />
        </div>
      </Card>
    </>}
  </div>
}

function Metric({ label, value }) {
  return <div><div className="text-sm text-slate-600">{label}</div><strong className="text-xl text-slate-900">{value}</strong></div>
}
