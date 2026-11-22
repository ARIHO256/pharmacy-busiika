import OperationalWorkspace, { field, statusColumn } from '../../components/OperationalWorkspace'
import { operationsApi } from '../../api/endpoints'

const benefitFields = [field('coverage_percent', 'Coverage percentage', 'number', { min: 0, max: 100 }), field('annual_limit', 'Annual benefit limit', 'number', { min: 0 }), field('requires_authorization', 'Requires preauthorization', 'checkbox', { required: false })]
export default function Benefits() {
  return <OperationalWorkspace title="Benefits and claim review" sections={[
    { resource: 'benefits', label: 'Benefit rules', organization: true,
      columns: [{ key: 'policy', label: 'Policy' }, { key: 'service_code', label: 'Service code' }, { key: 'coverage_percent', label: 'Coverage %' }, { key: 'annual_limit', label: 'Annual limit' }],
      create: { label: 'Add benefit rule', fields: ({ context }) => [field('policy', 'Policy', 'select', { numeric: true, options: context.policies || [] }), field('service_code', 'Service code'), ...benefitFields] },
      actions: (row) => [{ label: 'Configure', prefill: true, fields: [...benefitFields, field('active', 'Active', 'checkbox', { required: false })], request: ({ payload }) => operationsApi.configureBenefit(row.id, payload) }],
    },
    { resource: 'authorizations', label: 'Preauthorizations', organization: true,
      columns: [{ key: 'coverage', label: 'Coverage' }, { key: 'service_code', label: 'Service code' }, { key: 'requested_amount', label: 'Requested' }, { key: 'approved_amount', label: 'Approved' }, { key: 'expires_on', label: 'Expiry' }, statusColumn],
      create: { label: 'Request authorization', fields: ({ context }) => [field('coverage', 'Patient coverage', 'select', { numeric: true, options: context.coverages || [] }), field('service_code', 'Service code'), field('requested_amount', 'Requested amount', 'number', { min: 1 }), field('expires_on', 'Expiry date', 'date')] },
      actions: (row) => row.status === 'requested' ? ['approved', 'rejected'].map((status) => ({ label: status === 'approved' ? 'Approve' : 'Reject', action: 'decide', defaults: { status }, fields: [field('reason', 'Decision reason', 'textarea'), ...(status === 'approved' ? [field('approved_amount', 'Approved amount', 'number', { min: 1, max: row.requested_amount })] : [])] })) : [],
    },
    { resource: 'claim-assessments', label: 'Claim assessments', organization: true,
      description: 'Apply policy rules and authorization limits. Assessment does not transfer money.',
      columns: [{ key: 'claim', label: 'Claim' }, { key: 'service_code', label: 'Service' }, { key: 'decision', label: 'Decision' }, { key: 'covered_amount', label: 'Covered' }, { key: 'patient_amount', label: 'Patient share' }],
      create: { label: 'Prepare assessment', fields: ({ context }) => [field('claim', 'Submitted claim', 'select', { numeric: true, options: context.claims || [] }), field('service_code', 'Service code'), field('authorization', 'Preauthorization ID', 'number', { required: false })] },
      actions: (row) => [
        ...(row.decision === 'pending' ? [{ label: 'Assess against policy', action: 'assess', fields: [] }] : []),
        { label: 'Decision details', preview: true },
        { label: 'Reconciliation totals', immediate: true, request: ({ organization }) => operationsApi.reconciliation(organization) },
      ],
    },
  ]} />
}
