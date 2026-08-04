import React from 'react'
import HealthIcon from '../icons/HealthIcon'

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const styles = {
    primary: 'border-transparent bg-gradient-to-r from-primary-700 to-primary-500 text-white shadow-[0_9px_22px_rgba(36,104,196,.18)] hover:brightness-105',
    outline: 'border-slate-300 bg-white text-slate-700 hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700',
    danger: 'border-rose-600 bg-rose-600 text-white hover:bg-rose-700',
    ghost: 'border-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  }
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant] || styles.primary} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Card({ title, subtitle, actions, children, className = '', icon }) {
  return (
    <section className={`overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_10px_30px_rgba(9,31,58,.055)] ${className}`}>
      {(title || actions) && (
        <div className="flex items-center justify-between gap-4 border-b border-slate-100 px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            {icon && <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-700"><HealthIcon name={icon} size={18}/></span>}
            <div className="min-w-0">
              <h3 className="truncate font-semibold text-slate-900">{title}</h3>
              {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
            </div>
          </div>
          <div className="shrink-0">{actions}</div>
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function Input({ label, error, hint, className = '', ...props }) {
  return (
    <label className={`block ${className}`}>
      {label && <span className="mb-1.5 block text-sm font-semibold text-slate-700">{label}</span>}
      <input
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-primary-500 focus:ring-4 focus:ring-primary-100"
        {...props}
      />
      {hint && !error && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
      {error && <span className="mt-1 block text-xs font-medium text-rose-600">{error}</span>}
    </label>
  )
}

export function Select({ label, children, className = '', ...props }) {
  return (
    <label className={`block ${className}`}>
      {label && <span className="mb-1.5 block text-sm font-semibold text-slate-700">{label}</span>}
      <select
        className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 shadow-sm outline-none transition focus:border-primary-500 focus:ring-4 focus:ring-primary-100"
        {...props}
      >
        {children}
      </select>
    </label>
  )
}

export function Modal({ open, onClose, title, children, wide }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[130] flex items-center justify-center p-4">
      <button type="button" className="absolute inset-0 cursor-default bg-slate-950/55 backdrop-blur-sm" onClick={onClose} aria-label="Close dialog" />
      <section className={`relative max-h-[90vh] w-full overflow-y-auto rounded-2xl border border-white/20 bg-white shadow-2xl ${wide ? 'max-w-4xl' : 'max-w-lg'}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white/95 px-5 py-4 backdrop-blur">
          <h3 className="font-semibold text-slate-900">{title}</h3>
          <button onClick={onClose} className="grid h-9 w-9 place-items-center rounded-xl text-slate-400 hover:bg-slate-100 hover:text-slate-700" aria-label="Close"><HealthIcon name="close" size={19}/></button>
        </div>
        <div className="p-5">{children}</div>
      </section>
    </div>
  )
}

const badgeColors = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  yellow: 'border-amber-200 bg-amber-50 text-amber-700',
  red: 'border-rose-200 bg-rose-50 text-rose-700',
  blue: 'border-sky-200 bg-sky-50 text-sky-700',
  slate: 'border-slate-200 bg-slate-50 text-slate-600',
  purple: 'border-violet-200 bg-violet-50 text-violet-700',
  orange: 'border-orange-200 bg-orange-50 text-orange-700',
}

export function Badge({ color = 'slate', children }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badgeColors[color] || badgeColors.slate}`}>
      {children}
    </span>
  )
}

export function Table({ columns, rows, empty = 'No data yet' }) {
  if (!rows?.length) return <div className="py-10 text-center text-sm text-slate-400">{empty}</div>
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-slate-500">
            {columns.map((column) => <th key={column.key} className="pb-3 pr-4 font-semibold">{column.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.id ?? index} className="border-b border-slate-100 last:border-b-0 hover:bg-slate-50/80">
              {columns.map((column) => <td key={column.key} className="py-3 pr-4 text-slate-700">{column.render ? column.render(row) : row[column.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-400">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-primary-600" />
      {label}
    </div>
  )
}

export function Stat({ label, value, icon = 'activity', tone = 'text-primary-700', caption }) {
  return (
    <article className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-5 shadow-[0_10px_30px_rgba(9,31,58,.055)] transition hover:-translate-y-0.5 hover:border-primary-200 hover:shadow-[0_16px_36px_rgba(9,31,58,.09)]">
      <span className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-primary-600 via-sky-400 to-transparent opacity-70" />
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-slate-500">{label}</span>
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary-50 text-primary-700 transition group-hover:bg-primary-100"><HealthIcon name={icon} size={20}/></span>
      </div>
      <div className={`mt-3 text-2xl font-bold tracking-tight ${tone}`}>{value}</div>
      {caption && <div className="mt-1 text-xs text-slate-400">{caption}</div>}
    </article>
  )
}

export function Stars({ value = 0 }) {
  return (
    <span className="text-sm text-amber-400">
      {'★'.repeat(Math.round(value))}
      <span className="text-slate-200">{'★'.repeat(5 - Math.round(value))}</span>
      <span className="ml-1 text-xs text-slate-400">{Number(value || 0).toFixed(1)}</span>
    </span>
  )
}

export function Textarea({ label, error, className = '', ...props }) {
  return (
    <label className={`block ${className}`}>
      {label && <span className="mb-1.5 block text-sm font-semibold text-slate-700">{label}</span>}
      <textarea
        className="min-h-28 w-full resize-y rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-800 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-primary-500 focus:ring-4 focus:ring-primary-100"
        {...props}
      />
      {error && <span className="mt-1 block text-xs font-medium text-rose-600">{error}</span>}
    </label>
  )
}

export function Alert({ tone = 'info', title, children, className = '' }) {
  const tones = {
    info: 'border-primary-200 bg-primary-50 text-primary-900',
    success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    warning: 'border-amber-200 bg-amber-50 text-amber-900',
    danger: 'border-rose-200 bg-rose-50 text-rose-900',
  }
  return (
    <div role="status" className={`rounded-2xl border px-4 py-3 text-sm ${tones[tone] || tones.info} ${className}`}>
      {title && <div className="mb-1 font-semibold">{title}</div>}
      <div className="leading-6">{children}</div>
    </div>
  )
}

export function SectionHeading({ eyebrow, title, description, actions }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="text-xs font-bold uppercase tracking-[0.16em] text-primary-600">{eyebrow}</div>}
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
        {description && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  )
}

export function EmptyState({ icon = 'plus', title, description, action }) {
  return (
    <div className="py-12 text-center">
      <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-primary-50 text-primary-700"><HealthIcon name={icon} size={23}/></div>
      <div className="mt-3 font-semibold text-slate-800">{title}</div>
      {description && <div className="mx-auto mt-1 max-w-md text-sm leading-6 text-slate-500">{description}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
