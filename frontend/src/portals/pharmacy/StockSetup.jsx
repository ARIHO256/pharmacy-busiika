import { useState } from 'react'
import { Link } from 'react-router-dom'
import { servicesApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Modal, Spinner, Table, Textarea } from '../../components/ui'
import { getError, useRemote } from '../staff/shared'
import { usePharmacyPermissions } from './PharmacyPermissions'

const blankLot = () => ({ batch_number: '', expires_on: '', packs: 0, units: 0, witness: '' })

export default function StockSetup() {
  const allows = usePharmacyPermissions()
  const [search, setSearch] = useState('')
  const products = useRemote(() => servicesApi.pharmacyWorkspaceData('stock-setup', { search }), [search])
  const alerts = useRemote(() => servicesApi.pharmacyWorkspaceData('stock-alerts'), [])
  const [product, setProduct] = useState(null)
  const [lots, setLots] = useState([])
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function reconcile(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await servicesApi.savePharmacyWorkspace('stock-setup', {
        medicine: product.id, expected_stock: product.stock, reason,
        lots: lots.map(({ witness, ...lot }) => ({ ...lot, ...(witness && { witness: Number(witness) }) })),
      })
      setProduct(null)
      products.reload()
      alerts.reload()
    } catch (failure) {
      setError(getError(failure))
    } finally {
      setBusy(false)
    }
  }

  return <div className="space-y-4">
    <Card title="Stock setup and reconciliation">
      <Input label="Search medicines needing setup" value={search} onChange={(event) => setSearch(event.target.value)} />
      {products.error ? <Alert tone="danger">{products.error}</Alert> : products.loading && !products.data ? <Spinner /> :
        <Table rows={products.data || []} empty="No medicines need opening stock setup." columns={[
          { key: 'name', label: 'Medicine' }, { key: 'stock', label: 'Recorded stock' },
          { key: 'action', label: 'Next step', render: (row) => row.sale_type === 'unclassified'
            ? <Link className="text-primary-700 underline" to="../inventory">Classify in Medicine Inventory</Link>
            : allows('stock_receive') && <Button variant="outline" onClick={() => {
              setProduct(row)
              setLots([blankLot()])
              setReason('')
              setError('')
            }}>Reconcile lots</Button> },
        ]} />}
    </Card>
    {alerts.error ? <Alert tone="danger">{alerts.error}</Alert> : alerts.data && <>
      <Card title="Expiry, quarantine and recalls" subtitle="Batches expiring within 90 days and stock under restriction.">
        <Table rows={alerts.data.batches} empty="No batches need review." columns={[
          { key: 'medicine__name', label: 'Medicine' }, { key: 'batch_number', label: 'Lot' },
          { key: 'expires_on', label: 'Expiry' }, { key: 'quantity', label: 'Units' }, { key: 'status', label: 'Status' },
        ]} />
      </Card>
      <Card title="Reorder worklist">
        <Table rows={alerts.data.reorders} empty="No medicines are at their configured reorder level." columns={[
          { key: 'name', label: 'Medicine' }, { key: 'available', label: 'Available units' }, { key: 'reorder_level', label: 'Reorder level' },
        ]} />
      </Card>
      <Card title="Outstanding supplier deliveries">
        <Table rows={alerts.data.deliveries} empty="No outstanding deliveries." columns={[
          { key: 'purchase_id', label: 'Order' }, { key: 'medicine__name', label: 'Medicine' },
          { key: 'remaining', label: 'Units outstanding', render: (row) => row.ordered - row.received },
        ]} />
      </Card>
    </>}
    {product && <Modal open wide title={`Reconcile ${product.name}`} onClose={() => { if (!busy) setProduct(null) }}>
      <form className="space-y-4" onSubmit={reconcile}>
        <p>Recorded stock is {product.stock} {product.unit_label}. Each pack contains {product.units_per_pack} base units. Enter the quantities you physically counted by lot.</p>
        {lots.map((lot, index) => {
          const change = (key) => (event) => setLots((current) =>
            current.map((item, i) => i === index ? { ...item, [key]: event.target.value } : item))
          return <fieldset className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2" key={index}>
            <Input label="Lot number" required maxLength={120} value={lot.batch_number} onChange={change('batch_number')} />
            <Input label="Expiry date" required type="date" value={lot.expires_on} onChange={change('expires_on')} />
            <Input label="Whole packs" required type="number" min="0" value={lot.packs} onChange={change('packs')} />
            <Input label="Loose units" required type="number" min="0" value={lot.units} onChange={change('units')} />
            {product.sale_type === 'controlled' && <Input label="Independent witness ID" required type="number" min="1" value={lot.witness} onChange={change('witness')} />}
            <Button type="button" variant="outline" onClick={() => setLots(lots.filter((_, i) => i !== index))}>Remove lot</Button>
          </fieldset>
        })}
        <Button type="button" variant="outline" onClick={() => setLots([...lots, blankLot()])}>Add lot</Button>
        <p className="font-semibold">Verified total {lots.reduce((sum, lot) => sum + Number(lot.packs) * product.units_per_pack + Number(lot.units), 0)} units</p>
        {!lots.length && <Alert tone="warning">Saving with zero lots will record zero stock.</Alert>}
        <Textarea label="Count reference and reason" required maxLength={1200} value={reason} onChange={(event) => setReason(event.target.value)} />
        {error && <Alert tone="danger">{error}</Alert>}
        <Button disabled={busy}>Save verified count</Button>
      </form>
    </Modal>}
  </div>
}
