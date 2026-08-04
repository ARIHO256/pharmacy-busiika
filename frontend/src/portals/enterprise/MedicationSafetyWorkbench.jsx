import { useEffect, useMemo, useState } from 'react'
import { enterpriseApi } from '../../api/endpoints'
import { Alert, Badge, Button, Card, EmptyState, Input, Spinner, Textarea } from '../../components/ui'

const rowsFrom = (value) => Array.isArray(value) ? value : value?.results || []
const toneFor = (severity) => severity === 'contraindicated' || severity === 'major' ? 'red' : severity === 'moderate' ? 'orange' : 'blue'

export default function MedicationSafetyWorkbench() {
  const [catalog, setCatalog] = useState([])
  const [selected, setSelected] = useState([])
  const [allergies, setAllergies] = useState('')
  const [conditions, setConditions] = useState('')
  const [flags, setFlags] = useState({ pregnant: false, renal_impairment: false, hepatic_impairment: false })
  const [query, setQuery] = useState('')
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    enterpriseApi.resource('medication-knowledge', { active: true }).then(({ data }) => setCatalog(rowsFrom(data))).catch(() => setCatalog([]))
  }, [])

  const medicines = useMemo(() => catalog.filter((row) => `${row.generic_name} ${(row.brand_names || []).join(' ')}`.toLowerCase().includes(query.toLowerCase())), [catalog, query])
  const toggle = (id) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])
  const run = async () => {
    setBusy(true); setError(''); setResult(null)
    try {
      const { data } = await enterpriseApi.medicationSafety({
        medicine_ids: selected,
        allergies: allergies.split(',').map((value) => value.trim()).filter(Boolean),
        conditions: conditions.split(',').map((value) => value.trim()).filter(Boolean),
        ...flags,
      })
      setResult(data)
    } catch (err) {
      setError(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message))
    } finally { setBusy(false) }
  }

  return <div className="space-y-5">
    <Card title="Medication Safety Workbench" subtitle="Review interactions, allergies, contraindications, pregnancy, renal and hepatic guidance before prescribing or dispensing." icon="shield">
      {error && <Alert tone="danger" title="Safety check failed">{error}</Alert>}
      <div className="grid gap-5 xl:grid-cols-[1.1fr_.9fr]">
        <div className="space-y-3">
          <Input label="Find medicines" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Generic or brand name" />
          <div className="max-h-80 space-y-2 overflow-auto rounded-2xl border border-slate-200 p-3">
            {medicines.length ? medicines.map((medicine) => <label key={medicine.id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-100 p-3 hover:bg-slate-50">
              <input type="checkbox" checked={selected.includes(medicine.id)} onChange={() => toggle(medicine.id)} className="mt-1" />
              <span><strong className="block text-sm text-slate-800">{medicine.generic_name}</strong><small className="text-slate-500">{(medicine.brand_names || []).join(', ') || 'No brand names recorded'} · {(medicine.strengths || []).join(', ')}</small></span>
            </label>) : <EmptyState icon="pill" title="No medicine knowledge records" description="An administrator or pharmacist must populate the medication knowledge catalogue." />}
          </div>
        </div>
        <div className="space-y-3">
          <Textarea label="Known allergies" value={allergies} onChange={(event) => setAllergies(event.target.value)} placeholder="penicillin, Panadol" hint="Separate terms with commas." />
          <Textarea label="Clinical conditions" value={conditions} onChange={(event) => setConditions(event.target.value)} placeholder="active bleeding, liver disease" hint="Separate terms with commas." />
          <div className="grid gap-2 sm:grid-cols-3">
            {[['pregnant', 'Pregnant'], ['renal_impairment', 'Renal impairment'], ['hepatic_impairment', 'Hepatic impairment']].map(([name, label]) => <label key={name} className="flex items-center gap-2 rounded-xl border border-slate-200 p-3 text-sm font-medium text-slate-700"><input type="checkbox" checked={flags[name]} onChange={(event) => setFlags({ ...flags, [name]: event.target.checked })} />{label}</label>)}
          </div>
          <Button onClick={run} disabled={!selected.length || busy}>{busy ? 'Checking…' : `Check ${selected.length} medicine${selected.length === 1 ? '' : 's'}`}</Button>
        </div>
      </div>
    </Card>
    {busy && <Spinner />}
    {result && <Card title="Clinical decision-support result" subtitle={result.safe_to_continue ? 'No major stop signal was found. Clinical judgement is still required.' : 'A major or contraindicated warning requires review.'} icon="activity">
      <div className="mb-4 flex flex-wrap gap-2"><Badge color={result.safe_to_continue ? 'green' : 'red'}>{result.safe_to_continue ? 'No major stop signal' : 'Stop and review'}</Badge>{result.requires_pharmacist_review && <Badge color="orange">Pharmacist review required</Badge>}</div>
      <div className="space-y-3">{result.warnings?.length ? result.warnings.map((warning, index) => <div key={`${warning.type}-${index}`} className="rounded-2xl border border-slate-200 p-4"><div className="flex items-center justify-between gap-3"><strong className="text-slate-800">{warning.title || warning.type}</strong><Badge color={toneFor(warning.severity)}>{warning.severity || 'information'}</Badge></div><p className="mt-2 text-sm text-slate-600">{warning.clinical_effect || warning.detail || warning.management}</p>{warning.management && <p className="mt-2 text-sm font-medium text-slate-700">Management: {warning.management}</p>}</div>) : <Alert tone="success" title="No catalogue warning found">This result depends on the completeness and licensing of the medication knowledge catalogue.</Alert>}</div>
    </Card>}
  </div>
}
