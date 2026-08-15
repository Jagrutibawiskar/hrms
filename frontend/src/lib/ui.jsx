import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api.js'

// ---------------------------------------------------------------- formatting

export const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

export function initials(name) {
  return String(name || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0].toUpperCase())
    .join('')
}

/** Backend sends UTC ISO strings; render them in the viewer's timezone. */
export function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function formatDate(value, options = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!value) return '—'
  const date = value instanceof Date ? value : new Date(`${value}${/T/.test(value) ? '' : 'T00:00:00'}`)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString([], options)
}

export function formatDateRange(from, to) {
  if (from === to) return formatDate(from, { day: 'numeric', month: 'short' })
  return `${formatDate(from, { day: 'numeric', month: 'short' })} – ${formatDate(to, { day: 'numeric', month: 'short' })}`
}

export function todayISO() {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  return new Date(now.getTime() - offset * 60000).toISOString().slice(0, 10)
}

export function monthStartISO() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
}

export function money(value, currency = 'INR') {
  const amount = Number(value || 0)
  try {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return amount.toLocaleString()
  }
}

export function hours(value) {
  const n = Number(value || 0)
  return n ? `${n.toFixed(2)} h` : '—'
}

export function titleCase(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase())
}

// ---------------------------------------------------------------- data hooks

/**
 * Runs `loader` on mount and whenever `deps` change.
 * Returns { data, error, loading, reload } so every page handles states the same way.
 */
export function useApi(loader, deps = [], { skip = false } = {}) {
  const [state, setState] = useState({ data: null, error: '', loading: !skip })
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    if (skip) {
      setState({ data: null, error: '', loading: false })
      return
    }
    let cancelled = false
    setState(current => ({ ...current, loading: true, error: '' }))
    Promise.resolve()
      .then(() => loaderRef.current())
      .then(data => {
        if (!cancelled) setState({ data, error: '', loading: false })
      })
      .catch(err => {
        if (!cancelled) setState({ data: null, error: err.message, loading: false })
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce, skip])

  const reload = useCallback(() => setNonce(n => n + 1), [])
  return { ...state, reload }
}

/** Wraps a mutating call with pending/error state and an optional success toast. */
export function useAction(onDone) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  const run = useCallback(
    async (fn, successMessage) => {
      setPending(true)
      setError('')
      try {
        const result = await fn()
        onDone?.(successMessage, result)
        return result
      } catch (err) {
        setError(err instanceof ApiError ? err.message : String(err))
        return null
      } finally {
        setPending(false)
      }
    },
    [onDone],
  )

  return { run, pending, error, setError }
}

// ---------------------------------------------------------------- primitives

export function Loading({ label = 'Loading…' }) {
  return <div className="skeleton" role="status" aria-label={label} />
}

export function ErrorNote({ message, onRetry }) {
  if (!message) return null
  return (
    <div className="inline-error" role="alert">
      {message}
      {onRetry && (
        <button className="table-action" style={{ marginLeft: 12 }} onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, hint, action }) {
  return (
    <div className="empty">
      <b>{title}</b>
      {hint && <small>{hint}</small>}
      {action}
    </div>
  )
}

/**
 * Renders loading / error / empty / content so no page repeats the branching.
 */
export function Async({ state, empty, children, emptyTitle = 'Nothing here yet.', emptyHint }) {
  if (state.loading) return <Loading />
  if (state.error) return <ErrorNote message={state.error} onRetry={state.reload} />
  const isEmpty = typeof empty === 'function' ? empty(state.data) : empty
  if (isEmpty) return <EmptyState title={emptyTitle} hint={emptyHint} />
  return children(state.data)
}

/** Semantic tone per status — green = good, amber = needs attention, red = problem. */
const STATUS_TONE = {
  PRESENT: 'ok', APPROVED: 'ok', ACTIVE: 'ok', PAID: 'ok', PUBLIC: 'ok',
  LATE: 'warn', HALF_DAY: 'warn', PENDING: 'warn', PENDING_REVIEW: 'warn',
  DRAFT: 'warn', PROBATION: 'warn', NOTICE_PERIOD: 'warn', OPTIONAL: 'warn',
  ABSENT: 'bad', REJECTED: 'bad', TERMINATED: 'bad',
  WFH: 'info', LEAVE: 'info', HOLIDAY: 'info', RESTRICTED: 'info', COMPANY: 'info',
  WEEKEND: 'mute', INACTIVE: 'mute', CANCELLED: 'mute', RESIGNED: 'mute',
}

export function StatusChip({ status }) {
  if (!status) return null
  return (
    <span className="chip" data-tone={STATUS_TONE[status] || 'mute'}>
      {titleCase(status)}
    </span>
  )
}

/** Person cell: avatar + name + secondary line, used across every directory table. */
export function PersonCell({ name, code, secondary }) {
  return (
    <div className="cell-person">
      <span className="avatar">{initials(name)}</span>
      <div>
        <b>
          {name}
          {code && <span className="cell-code">{code}</span>}
        </b>
        {secondary && <small>{secondary}</small>}
      </div>
    </div>
  )
}

/** Table that scrolls horizontally on narrow screens instead of breaking the page. */
export function DataTable({ columns, rows, renderRow, empty = 'No records found.' }) {
  const safeColumns = Array.isArray(columns) ? columns : []
  const safeRows = Array.isArray(rows) ? rows : []

  return (
    <div className="data-table">
      <table>
        <thead>
          <tr>
            {safeColumns.map((column, index) => (
              <th key={index} className={typeof column === 'object' && column.num ? 'num' : ''}>
                {typeof column === 'object' ? column.label : column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {safeRows.length === 0 ? (
            <tr className="empty-row">
              <td colSpan={Math.max(safeColumns.length, 1)}>{empty}</td>
            </tr>
          ) : (
            safeRows.map(renderRow)
          )}
        </tbody>
      </table>
    </div>
  )
}

export function Pager({ page, totalPages, total, onChange }) {
  const label = `${total} record${total === 1 ? '' : 's'}`
  if (!totalPages || totalPages <= 1) return <div className="pager"><span>{label}</span></div>
  return (
    <div className="pager">
      <span>
        Page {page} of {totalPages} · {label}
      </span>
      <span>
        <button disabled={page <= 1} onClick={() => onChange(page - 1)}>
          ← Previous
        </button>{' '}
        <button disabled={page >= totalPages} onClick={() => onChange(page + 1)}>
          Next →
        </button>
      </span>
    </div>
  )
}

export function Modal({ title, children, onClose }) {
  useEffect(() => {
    const onKey = event => event.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={event => event.stopPropagation()} role="dialog" aria-modal="true">
        <button className="modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3>{title}</h3>
        {children}
      </div>
    </div>
  )
}

export function Field({ label, children, hint }) {
  return (
    <>
      <label>{label}</label>
      {children}
      {hint && <small className="onboard-note">{hint}</small>}
    </>
  )
}

/**
 * Salary figures stay masked until the viewer deliberately reveals them, so payroll
 * can be reviewed without exposing everyone's pay to whoever walks past the screen.
 * The choice is per-session and never persisted.
 */
export function useRevealAmounts() {
  const [revealed, setRevealed] = useState(false)
  const show = value => (revealed ? value : '••••••')
  return { revealed, setRevealed, show, toggle: () => setRevealed(v => !v) }
}

export function RevealToggle({ revealed, onToggle, label = 'amounts' }) {
  return (
    <button
      type="button"
      className="reveal-toggle"
      onClick={onToggle}
      aria-pressed={revealed}
      title={revealed ? `Hide ${label}` : `Show ${label}`}
    >
      <span aria-hidden="true">{revealed ? '🙈' : '👁️'}</span>
      {revealed ? `Hide ${label}` : `Show ${label}`}
    </button>
  )
}

export function StatCard({ value, label, hint }) {
  return (
    <article>
      <strong>{value}</strong>
      <b>{label}</b>
      {hint && <small>{hint}</small>}
    </article>
  )
}
