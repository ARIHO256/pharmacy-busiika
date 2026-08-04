import { useEffect, useState } from 'react'
import { appointmentApi } from '../../api/endpoints'
import { Badge, Button, Card, Input, Spinner } from '../../components/ui'
import { WEEKDAYS, breaksToText, parseBreaks, parseHolidays } from './util'

const emptyForm = { start_time: '08:00', end_time: '17:00', slot_minutes: 30, breaks: '', holidays: '', is_active: true }

function DayRow({ day, rows, onChanged }) {
  const [form, setForm] = useState(emptyForm)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await appointmentApi.saveAvailability({
        weekday: day.value,
        start_time: form.start_time,
        end_time: form.end_time,
        slot_minutes: Number(form.slot_minutes) || 30,
        breaks: parseBreaks(form.breaks),
        holidays: parseHolidays(form.holidays),
        is_active: form.is_active,
      })
      setAdding(false)
      setForm(emptyForm)
      onChanged()
    } catch (err) {
      setError(err.message && !err.response ? err.message : err.response?.data?.detail || 'Could not save availability')
    } finally {
      setBusy(false)
    }
  }

  async function remove(id) {
    setBusy(true)
    try {
      await appointmentApi.deleteAvailability(id)
      onChanged()
    } catch {
      /* keep list as-is */
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={day.label} className="h-full">
      {rows.length === 0 && !adding && <p className="text-sm text-slate-400">No schedule set.</p>}
      <ul className="space-y-3">
        {rows.map((r) => (
          <li key={r.id} className="border border-slate-200 rounded-lg p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium text-slate-700">
                {(r.start_time || '').slice(0, 5)} – {(r.end_time || '').slice(0, 5)}
              </span>
              <div className="flex items-center gap-2">
                <Badge color={r.is_active ? 'green' : 'slate'}>{r.is_active ? 'active' : 'inactive'}</Badge>
                <button
                  onClick={() => remove(r.id)}
                  disabled={busy}
                  className="text-rose-500 hover:text-rose-700 text-xs font-medium disabled:opacity-50"
                >
                  Delete
                </button>
              </div>
            </div>
            <div className="mt-1.5 text-slate-500 space-y-0.5">
              <div>{r.slot_minutes} min slots</div>
              {Array.isArray(r.breaks) && r.breaks.length > 0 && <div>Breaks: {breaksToText(r.breaks)}</div>}
              {Array.isArray(r.holidays) && r.holidays.length > 0 && <div>Holidays: {r.holidays.join(', ')}</div>}
            </div>
          </li>
        ))}
      </ul>

      {adding ? (
        <form onSubmit={submit} className="mt-4 space-y-3 border-t border-slate-100 pt-4">
          <div className="grid grid-cols-2 gap-3">
            <Input label="Start time" type="time" value={form.start_time} onChange={set('start_time')} required />
            <Input label="End time" type="time" value={form.end_time} onChange={set('end_time')} required />
          </div>
          <Input
            label="Slot length (minutes)"
            type="number"
            min="5"
            max="240"
            value={form.slot_minutes}
            onChange={set('slot_minutes')}
            required
          />
          <Input
            label="Breaks (e.g. 13:00-14:00, comma-separated)"
            value={form.breaks}
            onChange={set('breaks')}
            placeholder="13:00-14:00"
          />
          <Input
            label="Holidays (dates, comma-separated)"
            value={form.holidays}
            onChange={set('holidays')}
            placeholder="2025-12-25, 2025-12-26"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={form.is_active} onChange={set('is_active')} className="rounded" />
            Active
          </label>
          {error && <p className="text-xs text-rose-600">{error}</p>}
          <div className="flex gap-2">
            <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save'}</Button>
            <Button type="button" variant="outline" onClick={() => { setAdding(false); setError('') }}>Cancel</Button>
          </div>
        </form>
      ) : (
        <Button variant="outline" className="mt-4 w-full" onClick={() => setAdding(true)}>
          + Add schedule
        </Button>
      )}
    </Card>
  )
}

export default function Availability() {
  const [rows, setRows] = useState(null)

  const load = () => appointmentApi.myAvailability().then((r) => setRows(r.data || [])).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  if (!rows) return <Spinner label="Loading availability…" />

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">
        Set your weekly consultation schedule. Patients can only book free slots within these hours.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {WEEKDAYS.map((day) => (
          <DayRow key={day.value} day={day} rows={rows.filter((r) => r.weekday === day.value)} onChanged={load} />
        ))}
      </div>
    </div>
  )
}
