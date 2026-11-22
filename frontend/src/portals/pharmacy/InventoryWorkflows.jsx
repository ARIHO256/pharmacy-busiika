import { useAuth } from '../../auth/AuthContext'
import OperationalWorkspace, { field, statusColumn } from '../../components/OperationalWorkspace'

const reviewRoles = new Set(['admin', 'pharmacy', 'pharmacist', 'facility_manager'])
const reason = (label = 'Reason') => field('reason', label, 'textarea')
const witness = field('witness', 'Witness account ID for controlled stock', 'number', { required: false, min: 1 })
const medicine = (context) => field('medicine', 'Medicine', 'select', { numeric: true, options: context.medicines || [] })

export function Procurement() {
  const { user } = useAuth()
  const canReview = reviewRoles.has(user?.role)
  return <OperationalWorkspace title="Procurement" organizationType="pharmacy" sections={[{
    resource: 'pharmacy-purchases',
    label: 'Purchase orders',
    description: 'Approve orders before receiving stock. Add or identify the supplier batch in Batch Stock & Safety before recording a delivery.',
    organization: true,
    columns: [
      { key: 'supplier_name', label: 'Supplier' }, statusColumn, { key: 'status_reason', label: 'Status note' },
      { key: 'lines', label: 'Receipts and outstanding quantities', render: ({ lines }) => (
        <ul>{lines.map((line) => <li key={line.id}>
          {line.medicine_name} · {line.received} / {line.ordered} received · UGX {line.unit_cost.toLocaleString()} per unit
          {!!line.receipts.length && <details className="mt-1 mb-2">
            <summary className="cursor-pointer">Delivery history</summary>
            <ul className="pl-4">{line.receipts.map((receipt) => <li key={receipt.id}>
              {new Date(receipt.received_at).toLocaleDateString()} · Batch {receipt.batch_number} · {receipt.quantity} units
              <p>{receipt.reason}</p>
            </li>)}</ul>
          </details>}
        </li>)}</ul>
      ) },
    ],
    create: { label: 'New purchase order', permission: 'purchase_edit', fields: ({ context }) => [
      field('supplier', 'Supplier', 'select', { numeric: true, options: context.pharmacy_suppliers || [] }),
    ] },
    actions: (row) => [
      ...(row.status === 'draft' ? [{
        label: 'Add medicine', permission: 'purchase_edit', action: 'add-line', fields: ({ context }) => [
          medicine(context), field('ordered', 'Quantity in base units', 'number', { min: 1 }),
          field('unit_cost', 'Unit cost (UGX)', 'number', { min: 0 }),
        ],
      }] : []),
      ...(row.status === 'draft' && row.lines.length ? [{
        label: 'Remove medicine', permission: 'purchase_edit', action: 'remove-line', fields: [
          field('line', 'Order line', 'select', { numeric: true, options: row.lines.map((line) => ({ id: line.id, name: line.medicine_name })) }),
        ],
      }] : []),
      ...(row.status === 'draft' && canReview ? [
        ...(row.lines.length ? [{ label: 'Approve order', permission: 'purchase_approve', action: 'transition', defaults: { action: 'approve' }, fields: [reason()] }] : []),
        { label: 'Cancel order', permission: 'purchase_approve', action: 'transition', defaults: { action: 'cancel' }, fields: [reason()] },
      ] : []),
      ...(row.status === 'approved' ? [
        ...(row.lines.some((line) => line.ordered > line.received) ? [{
          label: 'Record delivery', permission: 'purchase_receive', action: 'receive', defaults: () => ({ reference: crypto.randomUUID() }),
          fields: [
            field('line', 'Order line', 'select', { numeric: true, options: row.lines
              .filter((line) => line.ordered > line.received)
              .map((line) => ({ id: line.id, name: `${line.medicine_name} · ${line.ordered - line.received} outstanding` })) }),
            field('batch', 'Batch reference', 'number', { min: 1 }),
            field('quantity', 'Accepted quantity', 'number', { min: 1 }),
            field('packs', 'Quantity is in packs', 'checkbox', { required: false }),
            reason('Delivery reference and any shortages or damage'), witness,
          ],
        }] : []),
        ...(canReview ? [{
          label: 'Close order', permission: 'purchase_approve', action: 'transition', defaults: { action: 'close' },
          fields: [reason('Closure reason, including any outstanding quantity')],
        }] : []),
      ] : []),
    ],
  }]} />
}

export function Stocktake() {
  const { user } = useAuth()
  return <OperationalWorkspace title="Stocktake" organizationType="pharmacy" sections={[{
    resource: 'pharmacy-stocktakes',
    label: 'Batch counts',
    description: 'Use the batch reference from Batch Stock & Safety. A different staff member reviews the count before any stock adjustment is posted.',
    organization: true,
    columns: [
      { key: 'medicine_name', label: 'Medicine' }, { key: 'batch_number', label: 'Batch' },
      { key: 'expected', label: 'System count' }, { key: 'counted', label: 'Physical count' },
      { key: 'difference', label: 'Difference', render: (row) => row.counted - row.expected },
      statusColumn, { key: 'review_reason', label: 'Review note' },
    ],
    create: { label: 'Record physical count', permission: 'stock_count', fields: [
      field('batch', 'Batch reference', 'number', { min: 1 }),
      field('counted', 'Physical quantity', 'number', { min: 0 }), reason('Count note'),
    ] },
    actions: (row) => [
      { label: 'View count', preview: true },
      ...(row.status === 'pending' && reviewRoles.has(user?.role) && row.created_by !== user.id ? [
        { label: 'Approve count', permission: 'stock_approve', action: 'review', defaults: { action: 'approve' }, fields: [reason('Review note'), witness] },
        { label: 'Reject count', permission: 'stock_approve', action: 'review', defaults: { action: 'reject' }, fields: [reason('Rejection reason')] },
      ] : []),
    ],
  }]} />
}

const formularyFields = [
  field('strength', 'Strength'),
  field('dosage_form', 'Dosage form'),
  field('register_entry', 'Medicine Register reference', 'number', { required: false, min: 1 }),
]

export function Formulary() {
  const { user } = useAuth()
  const canReview = reviewRoles.has(user?.role)
  return <OperationalWorkspace title="Formulary" organizationType="pharmacy" sections={[{
    resource: 'pharmacy-formulary',
    label: 'Approved pharmacy medicines',
    organization: true,
    columns: [
      { key: 'medicine_name', label: 'Medicine' }, { key: 'strength', label: 'Strength' },
      { key: 'dosage_form', label: 'Dosage form' }, { key: 'register_code', label: 'Register number' },
      { key: 'active', label: 'Status', render: (row) => row.active ? 'Active' : 'Inactive' },
    ],
    create: canReview ? { label: 'Add formulary entry', permission: 'catalogue_edit', fields: ({ context }) => [medicine(context), ...formularyFields] } : null,
    actions: (row) => canReview ? [{
      label: 'Edit entry', permission: 'catalogue_edit', action: 'configure', prefill: true,
      defaults: { active: false }, fields: [...formularyFields, field('active', 'Active', 'checkbox')],
    }] : [],
  }]} />
}
