import { useEffect, useState } from 'react'
import { ENDPOINTS, api, currentPosition, query } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  Modal,
  Pager,
  StatusChip,
  formatDate,
  formatTime,
  hours,
  monthStartISO,
  titleCase,
  todayISO,
  useAction,
  useApi,
} from '../lib/ui.jsx'

/** Live timer seeded from the server clock so a wrong client clock can't skew it. */
function useWorkedTimer(checkInIso, active) {
  const [text, setText] = useState('00:00:00')
  useEffect(() => {
    if (!active || !checkInIso) return
    const start = new Date(checkInIso).getTime()
    const tick = () => {
      const diff = Math.max(Date.now() - start, 0)
      const h = String(Math.floor(diff / 3600000)).padStart(2, '0')
      const m = String(Math.floor((diff % 3600000) / 60000)).padStart(2, '0')
      const s = String(Math.floor((diff % 60000) / 1000)).padStart(2, '0')
      setText(`${h}:${m}:${s}`)
    }
    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [checkInIso, active])
  return text
}

export function CheckInCard({ notify, onDone }) {
  const state = useApi(() => api.get(ENDPOINTS.attendance.today), [])
  const [locating, setLocating] = useState(false)
  const { run, pending, error } = useAction(message => {
    notify?.(message)
    state.reload()
    onDone?.()
  })

  const today = state.data
  const working = Boolean(today?.checked_in && !today?.checked_out)
  const timer = useWorkedTimer(today?.check_in, working)

  /**
   * Punching in/out sends coordinates when the company geofences attendance.
   * WFH check-in is off-site by design, so it skips the location prompt.
   */
  async function punch(path, body, message) {
    let coords = null
    if (today?.geofence_enabled && !body.is_wfh) {
      setLocating(true)
      coords = await currentPosition()
      setLocating(false)
      if (!coords) {
        notify?.('Location permission is required to mark attendance.')
        return
      }
    }
    run(() => api.post(path, { ...body, ...(coords || {}) }), message)
  }

  if (state.loading || !today) return <section className="punch">Loading…</section>

  const banner = today.on_leave
    ? "You're on approved leave today."
    : today.is_holiday
      ? `Holiday: ${today.holiday_name}`
      : !today.is_working_day
        ? 'Today is a weekly off.'
        : null

  const busy = pending || locating

  return (
    <section className="punch">
      <div>
        <p className="eyebrow">TODAY</p>
        <h3>{formatDate(today.date, { weekday: 'long', day: 'numeric', month: 'long' })}</h3>
        {banner && <small className="banner">{banner}</small>}
        {today.geofence_enabled && (
          <small className="banner">
            📍 You must be within {today.geofence_radius_m} m of {today.geofence_location}
          </small>
        )}
      </div>

      <div className="controls">
        {!today.checked_in && (
          <>
            <div className="clock">
              {formatTime(today.server_time)}
              <small>{locating ? 'Finding your location…' : 'Not checked in yet'}</small>
            </div>
            <button
              className="primary-button"
              disabled={busy || today.on_leave}
              onClick={() => punch(ENDPOINTS.attendance.checkIn, { is_wfh: false }, 'Checked in')}
            >
              {locating ? 'Locating…' : pending ? 'Please wait…' : 'Check in'}
            </button>
            <button
              className="ghost"
              disabled={busy || today.on_leave}
              onClick={() =>
                punch(ENDPOINTS.attendance.checkIn, { is_wfh: true }, 'Checked in from home')
              }
            >
              Check in from home
            </button>
          </>
        )}

        {working && (
          <>
            <div className="clock">
              {timer}
              <small>since {formatTime(today.check_in)}</small>
            </div>
            <button
              className="primary-button"
              disabled={busy}
              onClick={() => punch(ENDPOINTS.attendance.checkOut, {}, 'Checked out')}
            >
              {locating ? 'Locating…' : pending ? 'Please wait…' : 'Check out'}
            </button>
          </>
        )}

        {today.checked_out && (
          <>
            <div className="clock">
              {hours(today.working_hours)}
              <small>
                {formatTime(today.check_in)} → {formatTime(today.check_out)}
              </small>
            </div>
            <StatusChip status={today.status} />
          </>
        )}
      </div>

      {error && <p className="inline-error">{error}</p>}
    </section>
  )
}

function MyAttendance({ notify }) {
  const [range, setRange] = useState({ from_date: monthStartISO(), to_date: todayISO() })
  const records = useApi(
    () => api.get(`${ENDPOINTS.attendance.mine}${query(range)}`),
    [range.from_date, range.to_date],
  )
  const summary = useApi(
    () => api.get(`${ENDPOINTS.attendance.mySummary}${query(range)}`),
    [range.from_date, range.to_date],
  )

  return (
    <>
      <CheckInCard notify={notify} onDone={records.reload} />

      <section className="toolbar">
        <label>From</label>
        <input
          type="date"
          value={range.from_date}
          onChange={e => setRange({ ...range, from_date: e.target.value })}
        />
        <label>To</label>
        <input
          type="date"
          value={range.to_date}
          onChange={e => setRange({ ...range, to_date: e.target.value })}
        />
      </section>

      <Async state={summary}>
        {data => (
          <section className="stat-row">
            {[
              ['Present', data.present],
              ['WFH', data.wfh],
              ['Late', data.late],
              ['Half day', data.half_day],
              ['Leave', data.leave],
              ['Absent', data.absent],
            ].map(([label, value]) => (
              <div key={label}>
                <strong>{value}</strong>
                <small>{label}</small>
              </div>
            ))}
            <div>
              <strong>{hours(data.total_hours)}</strong>
              <small>Total logged</small>
            </div>
          </section>
        )}
      </Async>

      <Async state={records}>
        {rows => (
          <DataTable
            columns={['Date', 'Check in', 'Check out', 'Hours', 'Status']}
            rows={rows}
            empty="No attendance in this range."
            renderRow={row => (
              <tr key={row.id}>
                <td>{formatDate(row.date)}</td>
                <td>{formatTime(row.check_in)}</td>
                <td>{formatTime(row.check_out)}</td>
                <td>{hours(row.working_hours)}</td>
                <td>
                  <StatusChip status={row.status} />
                  {row.is_regularized && <small> · regularized</small>}
                </td>
              </tr>
            )}
          />
        )}
      </Async>
    </>
  )
}

const STATUSES = ['PRESENT', 'ABSENT', 'HALF_DAY', 'LATE', 'LEAVE', 'HOLIDAY', 'WFH', 'WEEKEND']

/** HR correction for a single day. The monthly quota is enforced server-side. */
function RegularizeModal({ row, onClose, onDone }) {
  const { run, pending, error } = useAction()
  const [status, setStatus] = useState(row.status)

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const toIso = value => (value ? new Date(value).toISOString() : null)
    const result = await run(() =>
      api.put(ENDPOINTS.attendance.regularize(row.employee_id, row.date), {
        check_in: toIso(form.get('check_in')),
        check_out: toIso(form.get('check_out')),
        status,
        remarks: form.get('remarks'),
      }),
    )
    if (result) {
      onDone()
      onClose()
    }
  }

  const localValue = iso => {
    if (!iso) return ''
    const d = new Date(iso)
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  }

  return (
    <Modal title={`Regularize ${formatDate(row.date)}`} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <p className="form-note">
          Correcting attendance for <b>{row.employee_name}</b>. Each employee may be
          regularized a limited number of times per month — the server rejects the request
          once that allowance is used up.
        </p>

        <label>Check in</label>
        <input name="check_in" type="datetime-local" defaultValue={localValue(row.check_in)} />
        <label>Check out</label>
        <input name="check_out" type="datetime-local" defaultValue={localValue(row.check_out)} />

        <label>Status</label>
        <select value={status} onChange={e => setStatus(e.target.value)}>
          {STATUSES.map(s => (
            <option key={s} value={s}>{titleCase(s)}</option>
          ))}
        </select>

        <label>Reason (required)</label>
        <input name="remarks" required placeholder="e.g. Missed punch — verified with manager" />

        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Saving…' : 'Save correction'}
        </button>
      </form>
    </Modal>
  )
}

function TeamAttendance({ notify }) {
  const { can } = useSession()
  const [filters, setFilters] = useState({
    from_date: monthStartISO(),
    to_date: todayISO(),
    status: '',
    employee_id: '',
    page: 1,
  })
  const departments = useApi(() => api.get(ENDPOINTS.organization.departments), [])
  const [departmentId, setDepartmentId] = useState('')

  const state = useApi(
    () =>
      api.get(
        `${ENDPOINTS.attendance.list}${query({ ...filters, department_id: departmentId, page_size: 25 })}`,
      ),
    [filters.from_date, filters.to_date, filters.status, filters.page, departmentId],
  )

  const [fixing, setFixing] = useState(null)
  const { run } = useAction(message => {
    notify(message)
    state.reload()
  })

  const set = patch => setFilters(current => ({ ...current, ...patch, page: 1 }))

  return (
    <section>
      <section className="toolbar">
        <label>From</label>
        <input type="date" value={filters.from_date} onChange={e => set({ from_date: e.target.value })} />
        <label>To</label>
        <input type="date" value={filters.to_date} onChange={e => set({ to_date: e.target.value })} />
        <label>Status</label>
        <select value={filters.status} onChange={e => set({ status: e.target.value })}>
          <option value="">All statuses</option>
          {STATUSES.map(s => (
            <option key={s} value={s}>
              {s.replace('_', ' ')}
            </option>
          ))}
        </select>
        <label>Department</label>
        <select value={departmentId} onChange={e => setDepartmentId(e.target.value)}>
          <option value="">All departments</option>
          {(departments.data || []).map(d => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        {can('attendance:manage') && (
          <button
            className="table-action"
            onClick={() =>
              run(
                () => api.post(`${ENDPOINTS.attendance.backfill}${query({ day: filters.to_date })}`),
                'Missing attendance filled in',
              )
            }
            title="Mark missing rows for the end date as absent / weekend / holiday"
          >
            Backfill {formatDate(filters.to_date)}
          </button>
        )}
      </section>

      <Async state={state}>
        {page => (
          <>
            <DataTable
              columns={[
                'Employee', 'Date', 'Check in', 'Check out', 'Hours', 'Status',
                ...(can('attendance:manage') ? [''] : []),
              ]}
              rows={page.items}
              empty="No attendance records match these filters."
              renderRow={row => (
                <tr key={row.id}>
                  <td>
                    <b>{row.employee_name}</b>
                    <small> {row.employee_code}</small>
                  </td>
                  <td>{formatDate(row.date)}</td>
                  <td>{formatTime(row.check_in)}</td>
                  <td>{formatTime(row.check_out)}</td>
                  <td>{hours(row.working_hours)}</td>
                  <td>
                    <StatusChip status={row.status} />
                    {row.late_minutes > 0 && <small> · {row.late_minutes}m late</small>}
                    {row.is_regularized && <small> · regularized</small>}
                  </td>
                  {can('attendance:manage') && (
                    <td>
                      <button className="table-action" onClick={() => setFixing(row)}>
                        Regularize
                      </button>
                    </td>
                  )}
                </tr>
              )}
            />
            <Pager
              page={page.page}
              totalPages={page.total_pages}
              total={page.total}
              onChange={p => setFilters(current => ({ ...current, page: p }))}
            />
          </>
        )}
      </Async>

      {fixing && (
        <RegularizeModal
          row={fixing}
          onClose={() => setFixing(null)}
          onDone={() => {
            notify('Attendance regularized')
            state.reload()
          }}
        />
      )}
    </section>
  )
}

export function AttendancePage({ notify }) {
  const { can } = useSession()
  const canSeeOthers = can('attendance:read_all', 'attendance:read_team')
  const [tab, setTab] = useState('mine')

  if (!canSeeOthers) return <section className="attendance-page"><MyAttendance notify={notify} /></section>

  return (
    <section className="attendance-page">
      <div className="tabs">
        <button className={tab === 'mine' ? 'active' : ''} onClick={() => setTab('mine')}>
          My attendance
        </button>
        <button className={tab === 'team' ? 'active' : ''} onClick={() => setTab('team')}>
          {can('attendance:read_all') ? 'Everyone' : 'My team'}
        </button>
      </div>
      {tab === 'mine' ? <MyAttendance notify={notify} /> : <TeamAttendance notify={notify} />}
    </section>
  )
}
