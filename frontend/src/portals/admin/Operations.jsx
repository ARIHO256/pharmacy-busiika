import OperationalWorkspace, { field, statusColumn } from '../../components/OperationalWorkspace'
import { operationsApi } from '../../api/endpoints'

const reason = field('reason', 'Reason', 'textarea')
export default function Operations() {
  return <OperationalWorkspace title="Operational governance" sections={[
    { resource: 'identities', label: 'Patient identities',
      description: 'Review potential duplicates before merging. Original clinical record ownership is preserved.',
      columns: [{ key: 'given_name', label: 'Given name' }, { key: 'family_name', label: 'Family name' }, { key: 'birth_date', label: 'Date of birth' }, { key: 'merged_into', label: 'Canonical identity' }],
      create: { label: 'Create identity', fields: [field('given_name', 'Given name'), field('family_name', 'Family name'), field('birth_date', 'Date of birth', 'date', { required: false })] },
      actions: (row) => [
        { label: 'Potential duplicates', immediate: true, request: () => operationsApi.actionGet('identities', row.id, 'candidates') },
        ...(row.merged_into ? [{ label: 'Reverse merge', action: 'unmerge', fields: [reason] }] : [
          { label: 'Link patient account', action: 'link', fields: [field('patient', 'Patient account ID', 'number', { min: 1 })] },
          { label: 'Add identifier', action: 'identifier', fields: [field('system', 'Identifier namespace'), field('value', 'Identifier value')] },
          { label: 'Merge after review', action: 'merge', fields: [field('target', 'Canonical identity ID', 'number', { min: 1 }), reason] },
        ]),
      ],
    },
    { resource: 'clinical-rules', label: 'Clinical rules',
      description: 'Publish only reviewed, evidence-backed rules. This catalogue does not guarantee a complete medication safety check.',
      columns: [{ key: 'code', label: 'Rule' }, { key: 'version', label: 'Version' }, { key: 'kind', label: 'Type' }, { key: 'severity', label: 'Severity' }, { key: 'active', label: 'Active', render: (row) => row.active ? 'Yes' : 'No' }],
      create: { label: 'Submit rule version', fields: [field('code', 'Rule code'), field('version', 'Version', 'number', { min: 1 }), field('kind', 'Type', 'select', { options: [{ id: 'interaction', name: 'Interaction' }, { id: 'duplication', name: 'Duplication' }] }), field('medicine_a', 'First medicine'), field('medicine_b', 'Second medicine'), field('severity', 'Severity', 'select', { options: ['info', 'warning', 'critical'].map((id) => ({ id, name: id })) }), field('message', 'Clinical message', 'textarea'), field('evidence_url', 'Evidence reference', 'url')] },
      actions: (row) => [{ label: 'Review details', preview: true }, { label: row.active ? 'Deactivate' : 'Approve version', action: row.active ? 'deactivate' : 'approve', fields: [] }],
    },
    { resource: 'documents', label: 'Private documents', organization: true,
      columns: [{ key: 'filename', label: 'Document' }, { key: 'patient', label: 'Patient' }, statusColumn, { key: 'scanned_at', label: 'Scanned at' }],
      create: { label: 'Upload and scan', multipart: true, fields: [field('patient', 'Patient ID (optional)', 'number', { required: false }), field('file', 'Document', 'file')] },
      actions: (row) => row.status === 'clean' ? [{ label: 'Download', immediate: true, request: () => operationsApi.downloadDocument(row.id, row.filename) }] : [],
    },
    { resource: 'research-exports', label: 'Research aggregates',
      description: 'A different administrator must approve each request. Only consenting patients contribute, and small groups are suppressed.',
      columns: [{ key: 'purpose', label: 'Purpose' }, statusColumn, { key: 'approved_at', label: 'Approved at' }],
      create: { label: 'Request aggregate export', fields: [field('purpose', 'Research purpose', 'textarea')] },
      actions: (row) => [...(row.status === 'requested' ? [{ label: 'Review and approve', action: 'approve', fields: [] }] : []), { label: 'View aggregate', preview: true }],
    },
    { resource: 'copilot-models', label: 'Copilot governance',
      description: 'Enable only evaluated administrative drafting models after independent approval.',
      columns: [{ key: 'name', label: 'Model' }, { key: 'version', label: 'Version' }, { key: 'intended_use', label: 'Intended use' }, { key: 'active', label: 'Active', render: (row) => row.active ? 'Yes' : 'No' }],
      create: { label: 'Register evaluated model', fields: ({ context }) => [field('name', 'Model name'), field('version', 'Model version'), field('adapter', 'Approved provider adapter', 'select', { options: (context.copilot_adapters || []).map((id) => ({ id, name: id })) }), field('evaluation_reference', 'Evaluation report reference')] },
      actions: (row) => [{ label: 'Review model', preview: true }, { label: row.active ? 'Deactivate' : 'Approve model', action: row.active ? 'deactivate' : 'approve', fields: [] }],
    },
    { resource: 'copilot-drafts', label: 'Administrative drafts',
      description: 'Review generated text before use. Accepted drafts are never automatically published into clinical records.',
      columns: [{ key: 'model', label: 'Model' }, { key: 'author', label: 'Author' }, statusColumn],
      create: { label: 'Generate administrative draft', fields: [field('model', 'Approved model ID', 'number', { min: 1 }), field('source_text', 'Source text', 'textarea')] },
      actions: (row) => [{ label: 'Read draft', preview: true }, ...(row.status === 'draft' ? ['accepted', 'rejected'].map((decision) => ({ label: decision === 'accepted' ? 'Accept draft' : 'Reject draft', action: 'review', defaults: { decision }, fields: [field('note', 'Review note', 'textarea')] })) : [])],
    },
  ]} />
}
