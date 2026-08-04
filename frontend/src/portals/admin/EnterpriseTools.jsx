import { useState } from 'react'
import { enterpriseApi } from '../../api/endpoints'
import { Alert, Button, Card, Input, Textarea } from '../../components/ui'

function JsonResult({ value }) {
  if (!value) return null
  return <pre className="max-h-[420px] overflow-auto rounded-2xl bg-slate-950 p-5 text-xs leading-6 text-slate-100">{JSON.stringify(value, null, 2)}</pre>
}

export default function EnterpriseTools() {
  const [medicineIds, setMedicineIds] = useState('')
  const [allergies, setAllergies] = useState('')
  const [patientId, setPatientId] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const run = async (work) => {
    setError(''); setResult(null)
    try { setResult((await work()).data) } catch (err) { setError(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message)) }
  }
  return <div className="space-y-5">
    {error && <Alert tone="danger" title="Tool could not complete">{error}</Alert>}
    <div className="grid gap-5 xl:grid-cols-2">
      <Card title="Medication safety engine" subtitle="Drug interaction, allergy, condition, pregnancy, renal and hepatic checks" icon="pill">
        <div className="space-y-3">
          <Input label="Medication knowledge IDs" value={medicineIds} onChange={(e) => setMedicineIds(e.target.value)} placeholder="1, 2, 3" />
          <Textarea label="Allergy terms" value={allergies} onChange={(e) => setAllergies(e.target.value)} placeholder="paracetamol, penicillin" />
          <Button onClick={() => run(() => enterpriseApi.medicationSafety({ medicine_ids: medicineIds.split(',').map((v) => v.trim()).filter(Boolean), allergies: allergies.split(',').map((v) => v.trim()).filter(Boolean) }))}>Run safety check</Button>
        </div>
      </Card>
      <Card title="Master patient index" subtitle="Generate scored duplicate-patient candidates for records review" icon="users">
        <p className="mb-4 text-sm leading-6 text-slate-600">The scan compares normalized names, phone numbers, national identifiers, dates of birth and linked identifiers. It creates reviewable candidates rather than merging automatically.</p>
        <Button onClick={() => run(() => enterpriseApi.duplicatePatientScan({ minimum_score: 70 }))}>Run duplicate scan</Button>
      </Card>
      <Card title="FHIR patient export" subtitle="Generate a versioned patient Bundle from the FHIR resource store" icon="file">
        <div className="space-y-3"><Input label="Patient ID" type="number" value={patientId} onChange={(e) => setPatientId(e.target.value)} /><Button onClick={() => run(() => patientId ? enterpriseApi.fhirExportPatient(patientId) : enterpriseApi.fhirExportMe())}>Generate Bundle</Button></div>
      </Card>
      <Card title="Operational endpoints" subtitle="Container probes and Prometheus-compatible metrics" icon="activity">
        <div className="space-y-2 text-sm text-slate-600"><div><code>/api/enterprise/readiness/</code> – database, cache and production-service configuration.</div><div><code>/api/enterprise/metrics/</code> – token-protected Prometheus counters.</div><div><code>/healthz</code> and <code>/readyz</code> – load balancer probes.</div></div>
      </Card>
    </div>
    <JsonResult value={result} />
  </div>
}
