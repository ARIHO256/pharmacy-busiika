import { useAuth } from '../../auth/AuthContext'
import OperationalWorkspace, { field, statusColumn } from '../../components/OperationalWorkspace'
import { operationsApi } from '../../api/endpoints'

const reason = field('reason', 'Reason', 'textarea')
const movement = (kind, label) => ({ label, permission: kind === 'received' ? 'stock_receive' : 'stock_dispense', action: 'movement', defaults: () => ({ kind, reference: crypto.randomUUID() }), fields: [
  field('quantity', 'Quantity', 'number', { min: 1 }),
  ...(kind === 'received' ? [field('packs', 'Quantity is in packs', 'checkbox', { required: false })] : []),
  reason, field('patient', 'Patient ID (for dispensing)', 'number', { required: false }),
  field('prescription_item', 'Prescription item ID', 'number', { required: false }),
  field('witness', 'Independent witness ID (controlled stock)', 'number', { required: false }),
], request: ({ payload, row }) => operationsApi.action('medicine-batches', row.id, 'movement', { ...payload, quantity: ['dispensed', 'destroyed'].includes(kind) ? -Math.abs(payload.quantity) : payload.quantity }) })

export default function StockControl() {
  const { user } = useAuth()
  return <OperationalWorkspace title="Batch stock and medicine safety" organizationType="pharmacy" sections={[{
    resource: 'medicine-batches', label: 'Medicine batches', organization: true,
    description: 'Add opening stock by batch and expiry. Use receipts and the movement register for later stock changes.',
    columns: [{ key: 'medicine_name', label: 'Medicine' }, { key: 'batch_number', label: 'Batch' }, { key: 'expires_on', label: 'Expiry' }, { key: 'quantity', label: 'Quantity' }, statusColumn],
    create: { label: 'Add batch', permission: 'stock_receive', fields: ({ context }) => [
      field('medicine', 'Medicine', 'select', { numeric: true, options: context.medicines || [] }),
      field('batch_number', 'Batch number'), field('expires_on', 'Expiry date', 'date'),
      field('supplier', 'Supplier', 'select', { required: false, numeric: true, options: context.pharmacy_suppliers || [] }),
      field('controlled', 'Controlled medicine', 'checkbox', { required: false }),
      field('opening_packs', 'Opening whole packs', 'number', { min: 0, required: false }),
      field('opening_quantity', 'Opening loose units', 'number', { min: 0, required: false }),
      field('opening_witness', 'Witness account ID for controlled opening stock', 'number', { min: 1, required: false }),
      field('min_temperature', 'Minimum temperature °C', 'number', { required: false, step: '0.01' }),
      field('max_temperature', 'Maximum temperature °C', 'number', { required: false, step: '0.01' }),
    ] },
    actions: (row) => [
      movement('received', 'Receive'),
      ...(user?.role === 'pharmacist' ? [movement('dispensed', 'Dispense')] : []),
      { label: 'Movement register', immediate: true, request: () => operationsApi.actionGet('medicine-batches', row.id, 'register') },
      { label: 'Record temperature', permission: 'stock_safety', action: 'transition', defaults: { action: 'temperature' }, fields: [field('temperature', 'Temperature °C', 'number', { step: '0.01' })] },
      ...(row.status === 'available' ? [
        { label: 'Quarantine', permission: 'stock_safety', action: 'transition', defaults: { action: 'quarantine' }, fields: [reason] },
        { label: 'Recall', permission: 'stock_safety', action: 'transition', defaults: { action: 'recall' }, fields: [reason] },
      ] : []),
      ...(row.status === 'quarantined' && user?.role === 'pharmacist' ? [{ label: 'Release after review', permission: 'stock_safety', action: 'transition', defaults: { action: 'release' }, fields: [reason] }] : []),
    ],
  }]} />
}
