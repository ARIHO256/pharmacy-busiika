import { Input, Select, Textarea } from '../../components/ui'

export function normalizeFieldValue(kind, value) {
  if (kind === 'number') return value === '' || value == null ? null : Number(value)
  if (kind === 'boolean') return Boolean(value)
  if (kind === 'list') {
    if (Array.isArray(value)) return value
    return String(value || '').split('\n').map((item) => item.trim()).filter(Boolean)
  }
  if (kind === 'json') {
    if (typeof value !== 'string') return value || {}
    if (!value.trim()) return {}
    return JSON.parse(value)
  }
  return value
}

export function initialFieldValue(spec) {
  if (spec.kind === 'boolean') return false
  if (spec.kind === 'list') return ''
  if (spec.kind === 'json') return '{}'
  return ''
}

export default function FormField({ name, spec, value, onChange }) {
  const common = { label: spec.label, required: spec.required, value: value ?? '', onChange: (event) => onChange(name, event.target.value) }
  if (spec.kind === 'textarea') return <Textarea {...common} rows={4} />
  if (spec.kind === 'json') return <Textarea {...common} rows={6} spellCheck="false" placeholder='{"key":"value"}' />
  if (spec.kind === 'list') return <Textarea {...common} rows={4} placeholder="One item per line" />
  if (spec.kind === 'boolean') {
    return (
      <label className="flex min-h-12 items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
        <input type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(name, event.target.checked)} className="h-4 w-4 rounded border-slate-300 text-primary-600" />
        <span><strong className="block text-sm text-slate-700">{spec.label}</strong><small className="text-xs text-slate-500">Enable this option</small></span>
      </label>
    )
  }
  if (spec.kind === 'select') {
    return <Select {...common}><option value="">Select…</option>{(spec.options || []).map((option) => <option key={option} value={option}>{String(option).replaceAll('_', ' ')}</option>)}</Select>
  }
  const type = spec.kind === 'datetime' ? 'datetime-local' : spec.kind === 'date' ? 'date' : spec.kind === 'number' ? 'number' : 'text'
  return <Input {...common} type={type} step={spec.kind === 'number' ? 'any' : undefined} />
}
