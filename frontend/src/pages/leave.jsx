import { useMemo, useState } from 'react'
import { ENDPOINTS, api, query } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  EmptyState,
  Modal,
  Pager,
  StatusChip,
  formatDate,
  formatDateRange,
  todayISO,
  useAction,
  useApi,
} from '../lib/ui.jsx'

/**
 * Mirrors the server's day count: weekly offs and holidays don't consume leave,
 * so a Friday→Monday request costs 2 days, not 4.
 */
function useWorkingDayCount(from, to, isHalfDay, policy, holidays) {
  return useMemo(() => {
    if (!from || !to) return 0
    if (isHalfDay) return 0.5
    const start = new Date(`${from}T00:00:00`)
    const end = new Date(`${to}T00:00:00`)
    if (Number.isNaN(start) || Number.isNaN(end) || end < start) return 0

    const workingDays = policy?.working_days || [1, 2, 3, 4, 5]
    const holidayDates = new Set((holidays || []).map(h => h.date))
    let count = 0
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const iso = d.toISOString().slice(0, 10)
      const isoWeekday = d.getDay() === 0 ? 7 : d.getDay()
      if (workingDays.includes(isoWeekday) && !holidayDates.has(iso)) count += 1
    }
    return count
  }, [from, to, isHalfDay, policy, holidays])
}

function ApplyLeaveModal({ balances, policy, holidays, onClose, onApplied }) {
  const [form, setForm] = useState({
    leave_type_id: balances[0]?.leave_type_id || '',
    from_date: todayISO(),
    to_date: todayISO(),
    is_half_day: false,
    half_day_session: 'FIRST_HALF',
    reason: '',
  })
  const [file, setFile] = useState(null)
  const { run, pending, error } = useAction(() => {
    onApplied()
    onClose()
  })

  const days = useWorkingDayCount(form.from_date, form.to_date, form.is_half_day, policy, holidays)
  const selected = balances.find(b => b.leave_type_id === Number(form.leave_type_id))
  const overBalance = selected?.is_paid && days > selected.available

  function submit(event) {
    event.preventDefault()
    const payload = {
      ...form,
      leave_type_id: Number(form.leave_type_id),
      half_day_session: form.is_half_day ? form.half_day_session : null,
    }
    if (file) {
      const body = new FormData()
      Object.entries(payload).forEach(([key, value]) => {
        if (value !== null && value !== '') body.append(key, value)
      })
      body.append('file', file)
      run(() => api.post(ENDPOINTS.leave.withAttachment, body), 'Leave request submitted')
    } else {
      run(() => api.post(ENDPOINTS.leave.apply, payload), 'Leave request submitted')
    }
  }

  const set = patch => setForm(current => ({ ...current, ...patch }))

  return (
    <Modal title="Request time off" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label>Leave type</label>
        <select
          value={form.leave_type_id}
          onChange={e => set({ leave_type_id: e.target.value })}
          required
        >
          {balances.map(b => (
            <option key={b.leave_type_id} value={b.leave_type_id}>
              {b.leave_type_name} — {b.available} available
            </option>
          ))}
        </select>

        <label>
          <input
            type="checkbox"
            checked={form.is_half_day}
            onChange={e =>
              set({ is_half_day: e.target.checked, to_date: e.target.checked ? form.from_date : form.to_date })
            }
          />{' '}
          Half day
        </label>

        {form.is_half_day && (
          <select
            value={form.half_day_session}
            onChange={e => set({ half_day_session: e.target.value })}
          >
            <option value="FIRST_HALF">First half</option>
            <option value="SECOND_HALF">Second half</option>
          </select>
        )}

        <label>From</label>
        <input
          type="date"
          value={form.from_date}
          onChange={e =>
            set({
              from_date: e.target.value,
              to_date: form.is_half_day || form.to_date < e.target.value ? e.target.value : form.to_date,
            })
          }
          required
        />

        <label>To</label>
        <input
          type="date"
          value={form.to_date}
          min={form.from_date}
          disabled={form.is_half_day}
          onChange={e => set({ to_date: e.target.value })}
          required
        />

        <p className="form-note">
          This request uses <b>{days}</b> leave day{days === 1 ? '' : 's'} — weekends and holidays
          are excluded.
          {selected && ` ${selected.available} available in ${selected.leave_type_name}.`}
        </p>
        {overBalance && (
          <p className="form-error">
            That is more than your {selected.leave_type_name} balance of {selected.available} days.
          </p>
        )}

        <label>Reason</label>
        <textarea
          value={form.reason}
          onChange={e => set({ reason: e.target.value })}
          required
          minLength={3}
          rows={3}
          placeholder="A short note for your manager"
        />

        <label>Attachment (optional)</label>
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />

        {error && <p className="form-error">{error}</p>}

        <button className="primary-button" disabled={pending || days === 0 || overBalance}>
          {pending ? 'Submitting…' : 'Submit request'}
        </button>
      </form>
    </Modal>
  )
}

/** Admin/HR correction of someone else's request. Balances are re-run server-side. */
function EditLeaveModal({ request, leaveTypes, onClose, onDone }) {
  const [form, setForm] = useState({
    leave_type_id: request.leave_type_id,
    from_date: request.from_date,
    to_date: request.to_date,
    is_half_day: request.is_half_day,
    half_day_session: request.half_day_session || 'FIRST_HALF',
    reason: request.reason,
    edit_note: '',
  })
  const { run, pending, error } = useAction()
  const set = patch => setForm(current => ({ ...current, ...patch }))

  async function submit(event) {
    event.preventDefault()
    const result = await run(() =>
      api.patch(ENDPOINTS.leave.edit(request.id), {
        ...form,
        leave_type_id: Number(form.leave_type_id),
        half_day_session: form.is_half_day ? form.half_day_session : null,
      }),
    )
    if (result) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal title={`Edit leave — ${request.employee_name}`} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <p className="form-note">
          Currently <b>{request.days} day(s)</b> of {request.leave_type_name}, status{' '}
          {request.status.toLowerCase()}. Changing the dates releases the old days and
          re-reserves the new ones, so the employee's balance stays correct.
        </p>

        <label>Leave type</label>
        <select value={form.leave_type_id} onChange={e => set({ leave_type_id: e.target.value })}>
          {leaveTypes.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>

        <label className="inline">
          <input
            type="checkbox"
            checked={form.is_half_day}
            onChange={e =>
              set({ is_half_day: e.target.checked, to_date: e.target.checked ? form.from_date : form.to_date })
            }
          />{' '}
          Half day
        </label>

        <label>From</label>
        <input
          type="date"
          value={form.from_date}
          onChange={e =>
            set({
              from_date: e.target.value,
              to_date: form.is_half_day ? e.target.value : form.to_date,
            })
          }
          required
        />
        <label>To</label>
        <input
          type="date"
          value={form.to_date}
          min={form.from_date}
          disabled={form.is_half_day}
          onChange={e => set({ to_date: e.target.value })}
          required
        />

        <label>Reason</label>
        <textarea rows={2} value={form.reason} onChange={e => set({ reason: e.target.value })} />

        <label>Why are you editing this? (recorded on the request)</label>
        <input
          value={form.edit_note}
          onChange={e => set({ edit_note: e.target.value })}
          placeholder="e.g. Employee returned a day early"
        />

        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Saving…' : 'Save changes'}
        </button>
      </form>
    </Modal>
  )
}

function MyLeave({ notify }) {
  const [applyOpen, setApplyOpen] = useState(false)
  const [page, setPage] = useState(1)

  const balances = useApi(() => api.get(ENDPOINTS.leave.balances), [])
  const policies = useApi(() => api.get(ENDPOINTS.organization.workPolicies), [])
  const holidays = useApi(() => api.get(ENDPOINTS.holidays.list), [])
  const requests = useApi(
    () => api.get(`${ENDPOINTS.leave.mine}${query({ page, page_size: 10 })}`),
    [page],
  )

  const { run } = useAction(message => {
    notify(message)
    requests.reload()
    balances.reload()
  })

  return (
    <>
      <section className="page-hero">
        <div>
          <p className="eyebrow">TIME OFF</p>
          <h2>Your leave, at a glance.</h2>
        </div>
        <button
          className="primary-button"
          disabled={!balances.data?.length}
          onClick={() => setApplyOpen(true)}
        >
          Request time off
        </button>
      </section>

      <Async state={balances}>
        {rows => (
          <section className="balance-grid">
            {rows.map(balance => {
              // Unpaid leave has no annual quota, so "0 / 0" is meaningless —
              // show what's been taken instead of a bogus allowance.
              const unlimited = balance.total === 0
              return (
                <article key={balance.leave_type_id}>
                  <p className="eyebrow">{balance.leave_type_code}</p>
                  <h3>{balance.leave_type_name}</h3>
                  {unlimited ? (
                    <strong>
                      {balance.used} <small>taken</small>
                    </strong>
                  ) : (
                    <strong>
                      {balance.available} <small>/ {balance.total}</small>
                    </strong>
                  )}
                  {!unlimited && (
                    <div className="progress">
                      <span style={{ width: `${(balance.used / balance.total) * 100}%` }} />
                    </div>
                  )}
                  <small>
                    {unlimited
                      ? `No annual limit${balance.pending ? ` · ${balance.pending} pending` : ''}`
                      : `${balance.used} used · ${balance.pending} pending`}
                  </small>
                </article>
              )
            })}
          </section>
        )}
      </Async>

      <Async state={requests}>
        {data => (
          <>
            <DataTable
              columns={['Type', 'Dates', 'Days', 'Status', 'Applied', '']}
              rows={data.items}
              empty="You haven’t requested any leave yet."
              renderRow={row => (
                <tr key={row.id}>
                  <td>{row.leave_type_name}</td>
                  <td>{formatDateRange(row.from_date, row.to_date)}</td>
                  <td>{row.days}</td>
                  <td>
                    <StatusChip status={row.status} />
                    {row.action_comment && <small> · {row.action_comment}</small>}
                  </td>
                  <td>{formatDate(row.applied_at)}</td>
                  <td>
                    {['PENDING', 'APPROVED'].includes(row.status) && (
                      <button
                        className="table-action"
                        onClick={() =>
                          run(() => api.post(ENDPOINTS.leave.cancel(row.id)), 'Leave request cancelled')
                        }
                      >
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              )}
            />
            <Pager page={data.page} totalPages={data.total_pages} total={data.total} onChange={setPage} />
          </>
        )}
      </Async>

      {applyOpen && balances.data && (
        <ApplyLeaveModal
          balances={balances.data}
          policy={policies.data?.[0]}
          holidays={holidays.data}
          onClose={() => setApplyOpen(false)}
          onApplied={() => {
            notify('Leave request submitted')
            requests.reload()
            balances.reload()
          }}
        />
      )}
    </>
  )
}

function LeaveInbox({ notify }) {
  const { can } = useSession()
  const canEdit = can('leave:manage')
  const [status, setStatus] = useState('PENDING')
  const [page, setPage] = useState(1)
  const [editing, setEditing] = useState(null)

  const [employeeId, setEmployeeId] = useState('')

  const state = useApi(
    () =>
      api.get(
        `${ENDPOINTS.leave.requests}${query({ status, employee_id: employeeId, page, page_size: 15 })}`,
      ),
    [status, employeeId, page],
  )
  const leaveTypes = useApi(() => api.get(ENDPOINTS.organization.leaveTypes), [])
  const people = useApi(() => api.get(`${ENDPOINTS.employees.list}?page_size=200`), [])
  const { run, pending } = useAction(message => {
    notify(message)
    state.reload()
  })

  return (
    <section>
      <section className="toolbar">
        <label>Employee</label>
        <select
          className="grow"
          value={employeeId}
          onChange={e => {
            setEmployeeId(e.target.value)
            setPage(1)
          }}
        >
          <option value="">All employees</option>
          {(people.data?.items || []).map(person => (
            <option key={person.id} value={person.id}>
              {person.full_name} — {person.employee_code}
            </option>
          ))}
        </select>

        <label>Status</label>
        <select
          value={status}
          onChange={e => {
            setStatus(e.target.value)
            setPage(1)
          }}
        >
          {['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED', ''].map(s => (
            <option key={s || 'all'} value={s}>
              {s || 'All'}
            </option>
          ))}
        </select>
      </section>

      <Async state={state}>
        {data => (
          <>
            <DataTable
              columns={['Employee', 'Type', 'Dates', 'Days', 'Reason', 'Status', 'Action']}
              rows={data.items}
              empty="Nothing to review."
              renderRow={row => (
                <tr key={row.id}>
                  <td>
                    <b>{row.employee_name}</b>
                    <small> {row.employee_code}</small>
                  </td>
                  <td>{row.leave_type_name}</td>
                  <td>{formatDateRange(row.from_date, row.to_date)}</td>
                  <td>{row.days}</td>
                  <td>{row.reason}</td>
                  <td>
                    <StatusChip status={row.status} />
                  </td>
                  <td>
                    <div className="actions">
                      {row.status === 'PENDING' && can('leave:approve', 'leave:manage') && (
                        <>
                          <button
                            className="table-action approve"
                            disabled={pending}
                            onClick={() =>
                              run(
                                () => api.post(ENDPOINTS.leave.approve(row.id), { comment: 'Approved' }),
                                `${row.employee_name}'s leave approved`,
                              )
                            }
                          >
                            Approve
                          </button>
                          <button
                            className="table-action decline"
                            disabled={pending}
                            onClick={() => {
                              const comment = window.prompt(`Reason for rejecting ${row.employee_name}'s request?`)
                              if (comment)
                                run(
                                  () => api.post(ENDPOINTS.leave.reject(row.id), { comment }),
                                  `${row.employee_name}'s leave rejected`,
                                )
                            }}
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {/* Editing is admin/HR only — managers can approve but not rewrite. */}
                      {canEdit && row.status !== 'CANCELLED' && (
                        <button className="table-action" onClick={() => setEditing(row)}>
                          Edit
                        </button>
                      )}
                      {!canEdit && row.status !== 'PENDING' && (
                        <small>{row.action_comment || '—'}</small>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            />
            <Pager page={data.page} totalPages={data.total_pages} total={data.total} onChange={setPage} />
          </>
        )}
      </Async>

      {editing && leaveTypes.data && (
        <EditLeaveModal
          request={editing}
          leaveTypes={leaveTypes.data}
          onClose={() => setEditing(null)}
          onDone={() => {
            notify('Leave request updated')
            state.reload()
          }}
        />
      )}
    </section>
  )
}

export function LeavePage({ notify }) {
  const { can } = useSession()
  const canReview = can('leave:approve', 'leave:manage', 'leave:read_all', 'leave:read_team')
  const [tab, setTab] = useState('mine')

  if (!canReview) return <section className="leave-page"><MyLeave notify={notify} /></section>

  return (
    <section className="leave-page">
      <div className="tabs">
        <button className={tab === 'mine' ? 'active' : ''} onClick={() => setTab('mine')}>
          My leave
        </button>
        <button className={tab === 'inbox' ? 'active' : ''} onClick={() => setTab('inbox')}>
          {can('leave:read_all') ? 'All requests' : 'Team requests'}
        </button>
      </div>
      {tab === 'mine' ? <MyLeave notify={notify} /> : <LeaveInbox notify={notify} />}
    </section>
  )
}
