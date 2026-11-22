import { Alert } from '../../components/ui'
import { useAuth } from '../../auth/AuthContext'
import OperationalWorkspace, { field, statusColumn } from '../../components/OperationalWorkspace'

const note = (label = 'Note') => field('note', label, 'textarea')
const text = (key, label) => ({ key, label })
const reference = (key, label, required = true) => field(key, label, 'number', { min: 1, required })
const witness = (key) => reference(key, 'Witness account ID for controlled stock', false)

export function PharmacySafety() {
  const { user } = useAuth()
  if (user?.role !== 'pharmacist') return <Alert>Verified pharmacist access is required.</Alert>
  return <OperationalWorkspace title="Pharmacy safety" organizationType="pharmacy" sections={[
    {
      resource: 'pharmacy-returns',
      label: 'Patient returns',
      organization: true,
      description: 'Use the movement reference from the completed order. Returned medicines are held separately from saleable stock.',
      columns: [text('medicine_name', 'Medicine'), text('batch_number', 'Batch'), text('quantity', 'Quantity'),
        text('disposition', 'Disposition'), text('disposition_note', 'Disposal or supplier reference')],
      create: { label: 'Record patient return', fields: [
        reference('movement', 'Dispensing movement reference'), reference('quantity', 'Quantity'), witness('intake_witness'),
        field('reason', 'Return reason and physical storage location', 'textarea'),
      ] },
      actions: (row) => row.disposition === 'segregated' ? [
        { label: 'Record destruction', action: 'resolve', defaults: { disposition: 'destroyed' }, fields: [note('Destruction reference and details'), witness('witness')] },
        { label: 'Record supplier return', action: 'resolve', defaults: { disposition: 'returned_to_supplier' }, fields: [note('Supplier return reference and details'), witness('witness')] },
      ] : [],
    },
    {
      resource: 'pharmacy-recalls',
      label: 'Recall follow-up',
      organization: true,
      description: 'Recalling a batch in Batch Stock & Safety creates follow-up records for patients with traced handovers.',
      columns: [text('medicine_name', 'Medicine'), text('batch_number', 'Batch'), text('patient_name', 'Patient'),
        text('handed_over', 'Units handed over'), text('recovered', 'Units recovered'), statusColumn, text('notes', 'Latest note')],
      actions: (row) => row.status === 'resolved' ? [] : [
        ...(!row.notified_at ? [{ label: 'Send in-app alert', action: 'follow_up', defaults: { action: 'notify' }, fields: [note()] }] : []),
        { label: 'Record contact', action: 'follow_up', defaults: { action: 'contacted' }, fields: [note()] },
        { label: 'Record unreachable', action: 'follow_up', defaults: { action: 'unreachable' }, fields: [note()] },
        { label: 'Resolve follow-up', action: 'follow_up', defaults: { action: 'resolved' }, fields: [note('Outcome and quantity reconciliation')] },
      ],
    },
    {
      resource: 'pharmacy-safety-reports',
      label: 'Safety incidents',
      organization: true,
      description: 'Record medication errors, suspected adverse reactions, and quality defects. Log the reference after filing an external report.',
      columns: [text('kind', 'Incident type'), text('description', 'Description'), text('state', 'Status'),
        text('external_reference', 'External report reference')],
      create: { label: 'New safety incident', fields: [
        field('kind', 'Incident type', 'select', { options: [
          { id: 'medication_error', name: 'Medication error' },
          { id: 'adverse_reaction', name: 'Suspected adverse reaction' },
          { id: 'quality_defect', name: 'Quality defect' },
        ] }),
        reference('movement', 'Dispensing movement reference', false), field('description', 'Incident details', 'textarea'),
      ] },
      actions: (row) => [
        ...(row.state === 'open' ? [{ label: 'Record external report', action: 'resolve', defaults: { state: 'reported' },
          fields: [field('external_reference', 'Report reference or channel'), note()] }] : []),
        ...(row.state !== 'closed' ? [{ label: 'Close incident', action: 'resolve', defaults: { state: 'closed' }, fields: [note('Outcome and follow-up')] }] : []),
      ],
    },
  ]} />
}

export function PharmacyTransfers() {
  const { user } = useAuth()
  if (user?.role !== 'pharmacist') return <Alert>Verified pharmacist access is required.</Alert>
  return <OperationalWorkspace title="Branch transfers" organizationType="pharmacy" sections={[{
    resource: 'pharmacy-transfers',
    label: 'Stock transfers',
    organization: true,
    description: 'Create matching batch records at both pharmacies before requesting a transfer. Both products need the same linked formulary reference.',
    columns: [text('medicine_name', 'Medicine'), text('source', 'Source batch'), text('destination_name', 'Destination'),
      text('destination', 'Destination batch'), text('quantity', 'Quantity'), statusColumn],
    create: { label: 'Request transfer', fields: [
      reference('source', 'Source batch reference'), reference('destination', 'Destination batch reference'),
      reference('quantity', 'Quantity'), field('reason', 'Reason', 'textarea'),
    ] },
    actions: (row, context) => {
      const branches = context?.organizations || []
      return [
        ...(row.status === 'requested' && branches.some((org) => org.id === row.organization) ? [
          { label: 'Dispatch stock', action: 'transition', defaults: { action: 'dispatch' }, fields: [note('Dispatch and transport reference')] },
          { label: 'Cancel request', action: 'transition', defaults: { action: 'cancel' }, fields: [note()] },
        ] : []),
        ...(row.status === 'dispatched' && (user?.role === 'admin' || branches.some((org) => org.id === row.destination_organization)) ? [
          { label: 'Receive stock', action: 'transition', defaults: { action: 'receive' }, fields: [note('Receipt and condition confirmation')] },
          { label: 'Segregate shipment', action: 'transition', defaults: { action: 'segregate' }, fields: [note('Condition, storage location and follow-up')] },
        ] : []),
      ]
    },
  }]} />
}
