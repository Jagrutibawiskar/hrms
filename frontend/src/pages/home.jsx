import { ENDPOINTS, api } from '../api.js'
import {
  Async,
  EmptyState,
  StatusChip,
  formatDate,
  formatDateRange,
  hours,
  initials,
  useApi,
  useAction,
} from '../lib/ui.jsx'
import { CheckInCard } from './attendance.jsx'

export function HrHome({ notify, onNavigate }) {
  const state = useApi(() => api.get(ENDPOINTS.dashboard.hr), [])
  const { run } = useAction(message => {
    notify(message)
    state.reload()
  })

  return (
    <Async state={state}>
      {data => {
        const c = data.counts
        const stats = [
          [c.total_employees, 'Total employees', `${c.active_employees} active`],
          [c.present_today, 'Present today', `${c.wfh_today} working remotely`],
          [data.pending.pending_leave_requests, 'Leave approvals', 'Needs review'],
          [c.on_leave_today, 'On leave today', `${c.late_today} arrived late`],
        ]

        return (
          <>
            <section className="page-hero">
              <div>
                <p className="eyebrow">TODAY AT A GLANCE</p>
                <h2>Here’s the shape of your team.</h2>
                <p>Clear signals for the things that need your attention.</p>
              </div>
              <button className="primary-button" onClick={() => onNavigate('People')}>
                View people
              </button>
            </section>

            <section className="stat-row">
              {stats.map(([value, label, hint]) => (
                <article key={label}>
                  <strong>{value}</strong>
                  <b>{label}</b>
                  <small>{hint}</small>
                </article>
              ))}
            </section>

            <section className="grid-2">
              <article>
                <div className="card-heading">
                  <div>
                    <p className="eyebrow">APPROVAL INBOX</p>
                    <h3>Leave requests waiting.</h3>
                  </div>
                  <button onClick={() => onNavigate('Leave')}>View all</button>
                </div>
                {data.recent_leave_requests.length === 0 ? (
                  <EmptyState title="No requests waiting." hint="Everything is approved." />
                ) : (
                  data.recent_leave_requests.map(request => (
                    <div className="feed-row" key={request.id}>
                      <span>{initials(request.employee_name)}</span>
                      <p>
                        <b>{request.employee_name}</b>
                        <small>
                          {request.leave_type} · {request.days} day
                          {request.days === 1 ? '' : 's'} ·{' '}
                          {formatDateRange(request.from_date, request.to_date)}
                        </small>
                      </p>
                      <button
                        onClick={() =>
                          run(
                            () =>
                              api.post(ENDPOINTS.leave.approve(request.id), {
                                comment: 'Approved from dashboard',
                              }),
                            `${request.employee_name}'s leave approved`,
                          )
                        }
                      >
                        Approve
                      </button>
                    </div>
                  ))
                )}
              </article>

              <article>
                <p className="eyebrow">TEAM SNAPSHOT</p>
                <h3>Today’s attendance mix.</h3>
                <div className="bar-chart">
                  {[
                    ['Present', c.present_today],
                    ['WFH', c.wfh_today],
                    ['On leave', c.on_leave_today],
                    ['Late', c.late_today],
                    ['Absent', c.absent_today],
                  ].map(([label, value]) => (
                    <p key={label}>
                      <span>{label}</span>
                      <i>
                        <b
                          style={{
                            width: `${c.active_employees ? Math.min((value / c.active_employees) * 100, 100) : 0}%`,
                          }}
                        />
                      </i>
                      <strong>{value}</strong>
                    </p>
                  ))}
                </div>
                <button className="text-action" onClick={() => onNavigate('Attendance')}>
                  Open attendance
                </button>
              </article>
            </section>

            <section className="grid-2">
              <article>
                <p className="eyebrow">NEW JOINERS</p>
                <h3>Recently joined.</h3>
                {data.new_joiners.length === 0 ? (
                  <EmptyState title="No new joiners in the last 30 days." />
                ) : (
                  data.new_joiners.map(person => (
                    <div className="feed-row" key={person.id}>
                      <span>{initials(person.full_name)}</span>
                      <p>
                        <b>{person.full_name}</b>
                        <small>
                          {person.designation_name || person.employee_code} · joined{' '}
                          {formatDate(person.date)}
                        </small>
                      </p>
                    </div>
                  ))
                )}
              </article>

              <article>
                <p className="eyebrow">COMING UP</p>
                <h3>Birthdays &amp; holidays.</h3>
                {data.upcoming_birthdays.slice(0, 4).map(person => (
                  <div className="feed-row" key={`b-${person.id}`}>
                    <span>🎂</span>
                    <p>
                      <b>{person.full_name}</b>
                      <small>{formatDate(person.date, { day: 'numeric', month: 'long' })}</small>
                    </p>
                  </div>
                ))}
                {data.upcoming_holidays.map(holiday => (
                  <div className="feed-row" key={`h-${holiday.id}`}>
                    <span>📅</span>
                    <p>
                      <b>{holiday.name}</b>
                      <small>{formatDate(holiday.date)}</small>
                    </p>
                  </div>
                ))}
                {data.upcoming_birthdays.length === 0 && data.upcoming_holidays.length === 0 && (
                  <EmptyState title="Nothing coming up." />
                )}
              </article>
            </section>
          </>
        )
      }}
    </Async>
  )
}

export function ManagerHome({ notify, onNavigate, session }) {
  const me = useApi(() => api.get(ENDPOINTS.dashboard.me), [])
  const pending = useApi(() => api.get(ENDPOINTS.leave.pending), [])
  const team = useApi(
    () => api.get(`${ENDPOINTS.employees.list}?page_size=50`),
    [],
  )
  const { run } = useAction(message => {
    notify(message)
    pending.reload()
  })

  return (
    <Async state={me}>
      {dashboard => (
        <section>
          <section className="page-hero">
            <div>
              <p className="eyebrow">YOUR TEAM</p>
              <h2>Keep the team moving with care.</h2>
              <p>See who needs attention and make the next decision clear.</p>
            </div>
            <button className="primary-button" onClick={() => onNavigate('People')}>
              View my team
            </button>
          </section>

          <section className="stat-row">
            {[
              [team.data ? Math.max(team.data.total - 1, 0) : '—', 'Direct reports', 'In your line'],
              [pending.data ? pending.data.length : '—', 'Leave approvals', 'Waiting for you'],
              [dashboard.pending_leaves, 'My open requests', 'Awaiting decision'],
              [dashboard.unread_notifications, 'Notifications', 'Unread'],
            ].map(([value, label, hint]) => (
              <article key={label}>
                <strong>{value}</strong>
                <b>{label}</b>
                <small>{hint}</small>
              </article>
            ))}
          </section>

          <CheckInCard notify={notify} />

          <section className="grid-2">
            <article>
              <div className="card-heading">
                <div>
                  <p className="eyebrow">APPROVAL INBOX</p>
                  <h3>Make time off easy.</h3>
                </div>
                <button onClick={() => onNavigate('Leave')}>View all</button>
              </div>
              <Async
                state={pending}
                empty={rows => !rows || rows.length === 0}
                emptyTitle="You’re all caught up."
                emptyHint="No leave requests need approval right now."
              >
                {rows =>
                  rows.map(request => (
                    <div className="feed-row" key={request.id}>
                      <span>{initials(request.employee_name)}</span>
                      <p>
                        <b>{request.employee_name}</b>
                        <small>
                          {request.leave_type_name} · {request.days} day
                          {request.days === 1 ? '' : 's'} ·{' '}
                          {formatDateRange(request.from_date, request.to_date)}
                        </small>
                      </p>
                      <div>
                        <button
                          className="table-action approve"
                          onClick={() =>
                            run(
                              () =>
                                api.post(ENDPOINTS.leave.approve(request.id), {
                                  comment: 'Approved',
                                }),
                              `${request.employee_name}'s leave approved`,
                            )
                          }
                        >
                          Approve
                        </button>
                        <button
                          className="table-action decline"
                          onClick={() => {
                            const comment = window.prompt(
                              `Why are you rejecting ${request.employee_name}'s request?`,
                            )
                            if (comment)
                              run(
                                () =>
                                  api.post(ENDPOINTS.leave.reject(request.id), { comment }),
                                `${request.employee_name}'s leave rejected`,
                              )
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))
                }
              </Async>
            </article>

            <article>
              <p className="eyebrow">MY MONTH</p>
              <h3>Your attendance.</h3>
              <div className="bar-chart">
                {[
                  ['Present', dashboard.attendance_this_month.present],
                  ['WFH', dashboard.attendance_this_month.wfh],
                  ['Late', dashboard.attendance_this_month.late],
                  ['Leave', dashboard.attendance_this_month.leave],
                ].map(([label, value]) => (
                  <p key={label}>
                    <span>{label}</span>
                    <i>
                      <b
                        style={{
                          width: `${Math.min((value / Math.max(dashboard.attendance_this_month.working_days, 1)) * 100, 100)}%`,
                        }}
                      />
                    </i>
                    <strong>{value}</strong>
                  </p>
                ))}
              </div>
              <p className="form-note">
                {hours(dashboard.attendance_this_month.total_hours)} logged ·{' '}
                {hours(dashboard.attendance_this_month.average_hours)} average
              </p>
            </article>
          </section>
        </section>
      )}
    </Async>
  )
}

export function EmployeeHome({ notify, onNavigate }) {
  const state = useApi(() => api.get(ENDPOINTS.dashboard.me), [])

  return (
    <Async state={state}>
      {data => (
        <>
          <section className="page-hero">
            <div>
              <p className="eyebrow">YOUR WORKSPACE</p>
              <h2>Welcome back, {data.full_name.split(' ')[0]}.</h2>
              <p>Everything you need for today, in one place.</p>
            </div>
          </section>

          <CheckInCard notify={notify} onDone={state.reload} />

          <section className="balance-grid">
            {data.leave_balances.map(balance => {
              // Unpaid leave carries no quota — don't render a "0 / 0" allowance.
              const unlimited = balance.total === 0
              return (
                <article key={balance.code}>
                  <p className="eyebrow">{balance.code}</p>
                  <h3>{balance.leave_type}</h3>
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
                  <small>{unlimited ? 'No annual limit' : `${balance.used} used`}</small>
                </article>
              )
            })}
          </section>

          <section className="grid-2">
            <article>
              <div className="card-heading">
                <div>
                  <p className="eyebrow">THIS MONTH</p>
                  <h3>Your attendance.</h3>
                </div>
                <button onClick={() => onNavigate('Attendance')}>Open</button>
              </div>
              <div className="stat-row">
                {[
                  ['Present', data.attendance_this_month.present],
                  ['WFH', data.attendance_this_month.wfh],
                  ['Late', data.attendance_this_month.late],
                  ['Leave', data.attendance_this_month.leave],
                  ['Absent', data.attendance_this_month.absent],
                ].map(([label, value]) => (
                  <div key={label}>
                    <strong>{value}</strong>
                    <small>{label}</small>
                  </div>
                ))}
              </div>
              <p className="form-note">
                {hours(data.attendance_this_month.total_hours)} logged this month
              </p>
            </article>

            <article>
              <div className="card-heading">
                <div>
                  <p className="eyebrow">UPCOMING HOLIDAYS</p>
                  <h3>Plan ahead.</h3>
                </div>
                <button onClick={() => onNavigate('Holidays')}>All holidays</button>
              </div>
              {data.upcoming_holidays.length === 0 ? (
                <EmptyState title="No holidays coming up." />
              ) : (
                data.upcoming_holidays.map(holiday => (
                  <div className="feed-row" key={holiday.id}>
                    <span>📅</span>
                    <p>
                      <b>{holiday.name}</b>
                      <small>{formatDate(holiday.date)}</small>
                    </p>
                    <StatusChip status={holiday.holiday_type} />
                  </div>
                ))
              )}
            </article>
          </section>
        </>
      )}
    </Async>
  )
}
