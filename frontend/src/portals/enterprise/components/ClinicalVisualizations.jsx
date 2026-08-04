import { Badge, Card } from '../../../components/ui'
import HealthIcon from '../../../components/icons/HealthIcon'

const num = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback
const payload = (row) => row?.payload || {}
const byTime = (rows) => [...rows].sort((a, b) => new Date(a.occurred_at || a.created_at) - new Date(b.occurred_at || b.created_at))

function Sparkline({ values, min, max, label, unit = '' }) {
  const clean = values.map((v) => num(v)).filter((v) => Number.isFinite(v))
  const low = min ?? Math.min(...clean, 0)
  const high = max ?? Math.max(...clean, 1)
  const points = clean.length ? clean.map((v, index) => `${10 + (index * 280) / Math.max(clean.length - 1, 1)},${90 - ((v - low) / Math.max(high - low, 1)) * 70}`).join(' ') : ''
  return <div className="rounded-2xl border border-slate-200 bg-white p-4"><div className="flex items-center justify-between"><strong className="text-sm text-slate-800">{label}</strong><span className="text-xl font-bold text-primary-700">{clean.at(-1) ?? '—'}{unit}</span></div><svg viewBox="0 0 300 100" className="mt-3 h-28 w-full overflow-visible"><line x1="10" x2="290" y1="90" y2="90" stroke="#cbd5e1"/><line x1="10" x2="10" y1="15" y2="90" stroke="#cbd5e1"/>{points ? <><polyline points={points} fill="none" stroke="currentColor" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" className="text-primary-600"/>{clean.map((v, i) => { const [x,y] = points.split(' ')[i].split(','); return <circle key={`${x}-${y}`} cx={x} cy={y} r="4" fill="white" stroke="currentColor" strokeWidth="3" className="text-primary-600"/> })}</> : <text x="150" y="55" textAnchor="middle" fill="#94a3b8" fontSize="12">Add observations to populate this chart</text>}</svg></div>
}

function Partograph({ rows }) {
  const entries = byTime(rows).slice(-12)
  return <Card title="Visual partograph" subtitle="Labour progress, foetal heart rate and maternal safety" icon="activity"><div className="grid gap-4 xl:grid-cols-3"><Sparkline label="Cervical dilation" values={entries.map((r) => payload(r).cervical_dilation_cm)} min={0} max={10} unit=" cm"/><Sparkline label="Foetal heart rate" values={entries.map((r) => payload(r).fetal_heart_rate)} min={80} max={200} unit=" bpm"/><div className="rounded-2xl border border-slate-200 bg-slate-950 p-5 text-white"><small className="uppercase tracking-[.16em] text-primary-200">Labour safety</small><div className="mt-4 space-y-3">{entries.slice(-4).reverse().map((r) => <div key={r.id} className="flex items-center justify-between rounded-xl bg-white/10 p-3"><span className="text-sm">{new Date(r.occurred_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span><Badge color={r.priority === 'critical' ? 'red' : 'green'}>{r.status}</Badge></div>)}{!entries.length && <p className="text-sm text-primary-100">No labour observations recorded yet.</p>}</div></div></div></Card>
}

function Anaesthesia({ rows }) {
  const entries = byTime(rows).slice(-16)
  return <Card title="Anaesthesia and intraoperative chart" subtitle="Continuous observations, fluids, medicines and recovery readiness" icon="heart"><div className="grid gap-4 xl:grid-cols-2"><Sparkline label="Heart rate" values={entries.map((r) => payload(r).heart_rate)} min={30} max={180} unit=" bpm"/><Sparkline label="SpO₂" values={entries.map((r) => payload(r).spo2)} min={70} max={100} unit="%"/></div><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{['airway_plan','asa_class','anaesthesia_technique','recovery_score'].map((key) => <div key={key} className="rounded-xl border border-slate-100 bg-slate-50 p-3"><small className="capitalize text-slate-500">{key.replaceAll('_',' ')}</small><strong className="mt-1 block text-slate-800">{payload(entries.at(-1))[key] || 'Not recorded'}</strong></div>)}</div></Card>
}

function FluidBalance({ rows }) {
  const entries = byTime(rows).slice(-8)
  const intake = entries.reduce((sum, row) => sum + num(payload(row).intake_ml), 0)
  const output = entries.reduce((sum, row) => sum + num(payload(row).output_ml), 0)
  const max = Math.max(intake, output, 1)
  return <Card title="Fluid balance" subtitle="Cumulative intake, output and current balance" icon="activity"><div className="grid gap-5 md:grid-cols-[1fr_1fr_.8fr]"><div><div className="mb-2 flex justify-between text-sm"><span>Intake</span><strong>{intake} mL</strong></div><div className="h-5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-sky-500" style={{width:`${(intake/max)*100}%`}}/></div></div><div><div className="mb-2 flex justify-between text-sm"><span>Output</span><strong>{output} mL</strong></div><div className="h-5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-amber-500" style={{width:`${(output/max)*100}%`}}/></div></div><div className={`rounded-2xl p-4 text-white ${intake-output < -500 ? 'bg-rose-600' : 'bg-primary-700'}`}><small>Net balance</small><strong className="mt-1 block text-2xl">{intake-output} mL</strong></div></div></Card>
}

function MedicationBoard({ rows }) {
  const entries = rows.slice(0, 12)
  return <Card title="Electronic medication administration record" subtitle="Due, given, omitted and overdue doses" icon="pill"><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{entries.map((row) => <div key={row.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><div><strong className="text-sm text-slate-900">{payload(row).medication || row.title}</strong><p className="mt-1 text-xs text-slate-500">{payload(row).dose || 'Dose pending'} · {payload(row).route || 'Route pending'}</p></div><Badge color={row.status === 'given' || row.status === 'completed' ? 'green' : row.status === 'omitted' ? 'red' : 'yellow'}>{row.status}</Badge></div><div className="mt-3 flex items-center gap-2 text-xs text-slate-500"><HealthIcon name="clock" size={14}/> {payload(row).scheduled_at || new Date(row.occurred_at).toLocaleString()}</div></div>)}{!entries.length && <div className="col-span-full py-8 text-center text-sm text-slate-400">No medication doses scheduled.</div>}</div></Card>
}

function RiskAndObservation({ rows }) {
  const entries = byTime(rows).slice(-12)
  const latest = payload(entries.at(-1))
  const score = num(latest.early_warning_score ?? latest.score)
  return <Card title="Observation and early-warning board" subtitle="Vitals, risk score and escalation" icon="alert"><div className="grid gap-4 xl:grid-cols-[1.2fr_1.2fr_.7fr]"><Sparkline label="Temperature" values={entries.map((r) => payload(r).temperature_c)} min={34} max={42} unit="°"/><Sparkline label="Respiratory rate" values={entries.map((r) => payload(r).respiratory_rate)} min={5} max={45}/><div className={`rounded-2xl p-5 text-white ${score >= 7 ? 'bg-rose-600' : score >= 4 ? 'bg-amber-500' : 'bg-emerald-600'}`}><small>Early warning score</small><strong className="mt-2 block text-5xl">{entries.length ? score : '—'}</strong><p className="mt-3 text-xs opacity-90">{score >= 7 ? 'Urgent senior review' : score >= 4 ? 'Escalate and increase monitoring' : 'Continue routine observation'}</p></div></div></Card>
}

function GrowthChart({ rows }) {
  const entries = byTime(rows).slice(-16)
  return <Card title="Growth and child-health chart" subtitle="Weight, height and longitudinal follow-up" icon="users"><div className="grid gap-4 lg:grid-cols-2"><Sparkline label="Weight" values={entries.map((r) => payload(r).weight_kg)} min={0} unit=" kg"/><Sparkline label="Height" values={entries.map((r) => payload(r).height_cm)} min={0} unit=" cm"/></div></Card>
}

function QualityChart({ rows, title = 'Laboratory quality control' }) {
  const entries = byTime(rows).slice(-20)
  const values = entries.map((r) => num(payload(r).observed_value ?? payload(r).value))
  const mean = values.length ? values.reduce((a,b)=>a+b,0)/values.length : 0
  return <Card title={title} subtitle="Levey–Jennings style trend and out-of-control detection" icon="flask"><Sparkline label="Control value" values={values} min={mean ? mean * .8 : 0} max={mean ? mean * 1.2 : 10}/><div className="mt-3 flex flex-wrap gap-2"><Badge color="green">Mean {mean.toFixed(2)}</Badge><Badge color={values.some((v)=>mean && Math.abs(v-mean)>mean*.15) ? 'red':'blue'}>{values.some((v)=>mean && Math.abs(v-mean)>mean*.15) ? 'Review outlier':'Within expected range'}</Badge></div></Card>
}

function ColdChain({ rows }) {
  const entries = byTime(rows).slice(-24)
  const values = entries.map((r) => payload(r).temperature_c)
  return <Card title="Cold-chain monitoring" subtitle="Temperature trend, excursion detection and quarantine action" icon="activity"><Sparkline label="Storage temperature" values={values} min={0} max={12} unit="°C"/><div className="mt-3 flex gap-2"><Badge color={values.some((v)=>num(v)<2||num(v)>8)?'red':'green'}>{values.some((v)=>num(v)<2||num(v)>8)?'Excursion detected':'2–8°C maintained'}</Badge></div></Card>
}

function RadiationDose({ rows }) {
  const entries = rows.slice(0, 8)
  return <Card title="Radiation dose dashboard" subtitle="Exposure, repeat studies and dose alerts" icon="shield"><div className="space-y-3">{entries.map((row) => { const dose=num(payload(row).dose_mgy ?? payload(row).dlp); return <div key={row.id} className="grid grid-cols-[minmax(120px,1fr)_2fr_auto] items-center gap-3"><span className="truncate text-sm font-medium text-slate-700">{row.patient_name || row.title}</span><div className="h-3 rounded-full bg-slate-100"><div className={`h-full rounded-full ${dose>50?'bg-rose-500':'bg-primary-500'}`} style={{width:`${Math.min(dose,100)}%`}}/></div><Badge color={dose>50?'red':'blue'}>{dose || '—'} mGy</Badge></div>})}{!entries.length && <div className="py-8 text-center text-sm text-slate-400">No dose records.</div>}</div></Card>
}

function DispatchMap({ rows }) {
  const entries = rows.slice(0, 10)
  return <Card title="Live ambulance and incident map" subtitle="Fleet position, destination and response status" icon="truck"><div className="relative h-[340px] overflow-hidden rounded-2xl border border-slate-200 bg-[linear-gradient(#e2e8f0_1px,transparent_1px),linear-gradient(90deg,#e2e8f0_1px,transparent_1px)] bg-[size:32px_32px]"><div className="absolute inset-0 bg-gradient-to-br from-sky-50/70 via-transparent to-emerald-50/70"/>{entries.map((row,index) => { const p=payload(row); const left=Math.abs(num(p.longitude,index*13+20))%80+8; const top=Math.abs(num(p.latitude,index*17+12))%72+10; return <div key={row.id} className="absolute -translate-x-1/2 -translate-y-1/2" style={{left:`${left}%`,top:`${top}%`}}><div className="group relative"><span className={`grid h-10 w-10 place-items-center rounded-full border-4 border-white text-white shadow-lg ${row.priority==='critical'?'bg-rose-600':'bg-primary-700'}`}><HealthIcon name="truck" size={18}/></span><div className="pointer-events-none absolute left-1/2 top-12 z-10 hidden w-52 -translate-x-1/2 rounded-xl bg-slate-950 p-3 text-xs text-white shadow-xl group-hover:block"><strong>{row.title}</strong><p className="mt-1 text-slate-300">{p.pickup_location || p.destination || row.status}</p></div></div></div>})}<div className="absolute bottom-3 left-3 rounded-xl bg-white/95 px-3 py-2 text-xs font-medium text-slate-600 shadow"><span className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-500"/>Live operational view</div></div></Card>
}

function SurgicalCount({ rows }) {
  return <Card title="Surgical safety and count board" subtitle="Instrument, swab, implant and recovery controls" icon="shield"><div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{rows.slice(0,8).map((row) => <div key={row.id} className="rounded-2xl border border-slate-200 p-4"><div className="flex items-center justify-between"><HealthIcon name="clipboard" size={19} className="text-primary-600"/><Badge color={row.status==='completed'||row.status==='verified'?'green':'yellow'}>{row.status}</Badge></div><strong className="mt-3 block text-sm text-slate-800">{row.patient_name || row.title}</strong><p className="mt-1 text-xs text-slate-500">Expected {payload(row).expected_count || '—'} · Final {payload(row).final_count || '—'}</p></div>)}{!rows.length && <div className="col-span-full py-8 text-center text-sm text-slate-400">No surgical safety records.</div>}</div></Card>
}

function Handover({ rows }) {
  return <Card title="Clinical handover board" subtitle="SBAR communication and accountability" icon="refresh"><div className="grid gap-3 lg:grid-cols-2">{rows.slice(0,8).map((row) => <article key={row.id} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4"><div className="flex items-center justify-between"><strong className="text-sm text-slate-900">{row.patient_name || row.title}</strong><Badge color={row.priority==='critical'?'red':'blue'}>{row.status}</Badge></div><dl className="mt-3 grid grid-cols-[80px_1fr] gap-x-3 gap-y-2 text-xs"><dt className="font-bold text-slate-500">Situation</dt><dd>{payload(row).situation || row.summary || '—'}</dd><dt className="font-bold text-slate-500">Background</dt><dd>{payload(row).background || '—'}</dd><dt className="font-bold text-slate-500">Assessment</dt><dd>{payload(row).assessment || '—'}</dd><dt className="font-bold text-slate-500">Recommendation</dt><dd>{payload(row).recommendation || '—'}</dd></dl></article>)}{!rows.length && <div className="col-span-full py-8 text-center text-sm text-slate-400">No handovers recorded.</div>}</div></Card>
}

const VIEWS = {
  partograph_observation: Partograph,
  anaesthesia_chart: Anaesthesia,
  intraoperative_observation: Anaesthesia,
  pre_anaesthetic_assessment: Anaesthesia,
  fluid_balance: FluidBalance,
  medication_schedule: MedicationBoard,
  medication_dose: MedicationBoard,
  observation_chart: RiskAndObservation,
  risk_assessment: RiskAndObservation,
  growth_measurement: GrowthChart,
  quality_control: QualityChart,
  calibration: QualityChart,
  cold_chain: ColdChain,
  radiation_dose: RadiationDose,
  ambulance_telemetry: DispatchMap,
  prehospital_record: DispatchMap,
  mass_casualty: DispatchMap,
  surgical_count: SurgicalCount,
  implant_usage: SurgicalCount,
  handover: Handover,
}

export default function ClinicalVisualization({ recordType, records }) {
  const View = VIEWS[recordType]
  if (!View) return null
  return <View rows={records || []}/>
}
