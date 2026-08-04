import { useEffect, useRef, useState } from 'react'
import { enterpriseApi } from '../../../api/endpoints'
import HealthIcon from '../../../components/icons/HealthIcon'

export default function EntitySearchSelect({ kind, label, value, onChange, placeholder, role, required = false, hint = '' }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const requestRef = useRef(0)

  useEffect(() => {
    if (!value) {
      setSelected(null)
      setQuery('')
    }
  }, [value])

  useEffect(() => {
    if (!open || query.trim().length < 1) return undefined
    const timer = setTimeout(async () => {
      const requestId = ++requestRef.current
      setLoading(true)
      try {
        const { data } = await enterpriseApi.lookup(kind, query, role ? { role } : {})
        if (requestId === requestRef.current) setResults(data?.results || [])
      } catch {
        if (requestId === requestRef.current) setResults([])
      } finally {
        if (requestId === requestRef.current) setLoading(false)
      }
    }, 220)
    return () => clearTimeout(timer)
  }, [kind, open, query, role])

  const choose = (item) => {
    setSelected(item)
    setQuery(item.label)
    setOpen(false)
    onChange(item.id, item)
  }

  return (
    <label className="relative block">
      <span className="mb-1.5 flex items-center justify-between gap-2 text-sm font-semibold text-slate-700">
        <span>{label}{required ? <span className="ml-1 text-rose-500">*</span> : null}</span>
        {selected?.meta?.status ? <small className="rounded-full bg-slate-100 px-2 py-0.5 font-medium capitalize text-slate-500">{selected.meta.status.replaceAll('_', ' ')}</small> : null}
      </span>
      <div className={`flex items-center gap-2 rounded-xl border bg-white px-3 shadow-sm transition ${open ? 'border-primary-500 ring-4 ring-primary-100' : 'border-slate-300'}`}>
        <HealthIcon name="search" size={17} className="shrink-0 text-slate-400" />
        <input
          value={query}
          required={required && !value}
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value)
            setSelected(null)
            onChange('', null)
            setOpen(true)
          }}
          placeholder={placeholder || `Search ${kind}`}
          className="min-w-0 flex-1 border-0 bg-transparent py-2.5 text-sm text-slate-800 outline-none placeholder:text-slate-400"
          autoComplete="off"
        />
        {value ? <button type="button" className="grid h-7 w-7 place-items-center rounded-lg text-slate-400 hover:bg-slate-100" onClick={() => { setSelected(null); setQuery(''); onChange('', null) }} aria-label={`Clear ${label}`}><HealthIcon name="close" size={15}/></button> : null}
      </div>
      {hint ? <small className="mt-1 block text-xs text-slate-400">{hint}</small> : null}
      {open && query.trim().length > 0 ? (
        <div className="absolute z-40 mt-2 max-h-72 w-full overflow-auto rounded-2xl border border-slate-200 bg-white p-2 shadow-2xl">
          {loading ? <div className="flex items-center gap-2 px-3 py-4 text-sm text-slate-400"><span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-primary-600"/> Searching…</div> : results.length ? results.map((item) => (
            <button key={item.id} type="button" onClick={() => choose(item)} className="flex w-full items-start gap-3 rounded-xl px-3 py-3 text-left hover:bg-primary-50">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary-100 text-xs font-bold text-primary-700">{String(item.label || '?').split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</span>
              <span className="min-w-0"><strong className="block truncate text-sm text-slate-800">{item.label}</strong><small className="mt-0.5 block truncate text-slate-500">{item.subtitle || 'Select this record'}</small></span>
            </button>
          )) : <div className="px-3 py-5 text-center text-sm text-slate-400">No matching {kind} records.</div>}
        </div>
      ) : null}
    </label>
  )
}
