import { useState } from 'react'
import { ENDPOINTS, STATIC_BASE, api, query } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  Modal,
  MONTHS,
  Pager,
  RevealToggle,
  StatusChip,
  formatDate,
  money,
  titleCase,
  todayISO,
  useAction,
  useApi,
  useRevealAmounts,
} from '../lib/ui.jsx'

function lastMonth() {
  const now = new Date()
  const date = new Date(now.getFullYear(), now.getMonth() - 1, 1)
  return { month: date.getMonth() + 1, year: date.getFullYear() }
}

function AssignSalaryModal({ employees, structures, onClose, onDone }) {
  const [employeeId, setEmployeeId] = useState('')
  const [structureId, setStructureId] = useState(structures[0]?.id || '')
  const [ctc, setCtc] = useState(1200000)
  const { run, pending, error } = useAction()

  // Live breakup — the same numbers the server will store.
  const preview = useApi(
    () =>
      structureId && ctc > 0
        ? api.get(`${ENDPOINTS.payroll.preview(structureId)}${query({ ctc })}`)
        : Promise.resolve([]),
    [structureId, ctc],
  )

  const earnings = (preview.data || []).filter(c => c.component_type === 'EARNING')
  const deductions = (preview.data || []).filter(c => c.component_type === 'DEDUCTION')
  const gross = earnings.reduce((sum, c) => sum + c.monthly_amount, 0)
  const totalDeductions = deductions.reduce((sum, c) => sum + c.monthly_amount, 0)

  async function submit(event) {
    event.preventDefault()
    const result = await run(() =>
      api.post(ENDPOINTS.payroll.salaries(employeeId), {
        structure_id: Number(structureId),
        ctc: Number(ctc),
        effective_from: todayISO(),
        payment_mode: 'BANK_TRANSFER',
      }),
    )
    if (result) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal title="Assign salary structure" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label>Employee</label>
        <select value={employeeId} onChange={e => setEmployeeId(e.target.value)} required>
          <option value="">Choose an employee</option>
          {employees.map(e => (
            <option key={e.id} value={e.id}>
              {e.full_name} — {e.employee_code}
            </option>
          ))}
        </select>

        <label>Structure</label>
        <select value={structureId} onChange={e => setStructureId(e.target.value)} required>
          {structures.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>

        <label>Annual CTC</label>
        <input
          type="number"
          min="1"
          step="1000"
          value={ctc}
          onChange={e => setCtc(Number(e.target.value))}
          required
        />

        {preview.data?.length > 0 && (
          <>
            <p className="form-note">
              Monthly gross {money(gross)} · deductions {money(totalDeductions)} · net{' '}
              <b>{money(gross - totalDeductions)}</b>
            </p>
            <DataTable
              columns={['Component', 'Type', 'Monthly']}
              rows={preview.data}
              renderRow={row => (
                <tr key={row.component_id}>
                  <td>{row.name}</td>
                  <td>{titleCase(row.component_type)}</td>
                  <td>{money(row.monthly_amount)}</td>
                </tr>
              )}
            />
          </>
        )}

        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending || !employeeId}>
          {pending ? 'Saving…' : 'Assign salary'}
        </button>
      </form>
    </Modal>
  )
}

function RunDetail({ runId, onClose, notify }) {
  const state = useApi(() => api.get(ENDPOINTS.payroll.run(runId)), [runId])
  const { run: act, pending } = useAction(message => {
    notify(message)
    state.reload()
  })
  const { can } = useSession()
  const { revealed, toggle, show } = useRevealAmounts()
  const amount = value => (revealed ? money(value) : <span className="masked">••••••</span>)
  const [search, setSearch] = useState('')
  const [openItem, setOpenItem] = useState(null)

  return (
    <Modal title="Payroll run" onClose={onClose}>
      <Async state={state}>
        {data => (
          <div className="payroll-detail">
            <div className="payroll-runs-head">
              <div>
                <h3>
                  {MONTHS[data.month - 1]} {data.year}
                </h3>
                <StatusChip status={data.status} />
              </div>
              <div className="actions">
                <RevealToggle revealed={revealed} onToggle={toggle} label="pay" />
                {data.status === 'PENDING_REVIEW' && can('payroll:approve') && (
                  <button
                    className="table-action approve"
                    disabled={pending}
                    onClick={() => act(() => api.post(ENDPOINTS.payroll.approveRun(runId)), 'Payroll approved')}
                  >
                    Approve
                  </button>
                )}
                {['APPROVED', 'PAID'].includes(data.status) && (
                  <button
                    className="table-action"
                    disabled={pending}
                    onClick={() =>
                      act(() => api.post(ENDPOINTS.payroll.runPayslips(runId)), 'Payslips generated')
                    }
                  >
                    Generate payslips
                  </button>
                )}
                {data.status === 'APPROVED' && can('payroll:approve') && (
                  <button
                    className="table-action"
                    disabled={pending}
                    onClick={() => act(() => api.post(ENDPOINTS.payroll.markPaid(runId)), 'Payroll marked paid')}
                  >
                    Mark paid
                  </button>
                )}
              </div>
            </div>

            <section className="stat-row">
              {[
                [String(data.employee_count), 'Employees'],
                [show(money(data.total_gross)), 'Gross'],
                [show(money(data.total_deductions)), 'Deductions'],
                [show(money(data.total_net)), 'Net payable'],
              ].map(([value, label]) => (
                <article key={label}>
                  <strong className={revealed ? '' : 'masked'}>{value}</strong>
                  <b>{label}</b>
                </article>
              ))}
            </section>

            {data.notes && <p className="payroll-note">Skipped: {data.notes}</p>}

            <section className="toolbar">
              <label>Employee</label>
              <input
                type="search"
                className="grow"
                placeholder="Filter by name or employee code"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </section>

            <DataTable
              columns={[
                'Employee', 'Working', 'Present', 'Leave taken', 'LOP', 'Paid days',
                'Gross', 'Deductions', 'Net', '',
              ]}
              rows={data.items.filter(row => {
                const needle = search.trim().toLowerCase()
                if (!needle) return true
                return `${row.employee_name} ${row.employee_code}`.toLowerCase().includes(needle)
              })}
              empty="No employee matches that search."
              renderRow={row => {
                const lop = row.lop_breakdown || {}
                const leaveTaken = (lop.paid_leave_days || 0) + (lop.unpaid_leave_days || 0)
                return (
                  <tr key={row.id}>
                    <td>
                      <b>{row.employee_name}</b>
                      <small> {row.employee_code}</small>
                    </td>
                    <td>{row.working_days}</td>
                    <td>{lop.present_days ?? '—'}</td>
                    <td>
                      {leaveTaken || '—'}
                      {leaveTaken > 0 && (
                        <small>
                          {' '}
                          ({lop.paid_leave_days || 0} paid
                          {lop.unpaid_leave_days ? `, ${lop.unpaid_leave_days} unpaid` : ''})
                        </small>
                      )}
                    </td>
                    <td>{row.lop_days || '—'}</td>
                    <td>{row.paid_days}</td>
                    <td>{amount(row.gross_earnings)}</td>
                    <td>{amount(row.total_deductions)}</td>
                    <td>
                      <b>{amount(row.net_pay)}</b>
                    </td>
                    <td>
                      <button className="table-action" onClick={() => setOpenItem(row)}>
                        How?
                      </button>
                    </td>
                  </tr>
                )
              }}
            />

            {openItem && (
              <CalculationDetail
                item={openItem}
                revealed={revealed}
                onClose={() => setOpenItem(null)}
              />
            )}
          </div>
        )}
      </Async>
    </Modal>
  )
}

/**
 * Shows the full chain from attendance to net pay, so HR can answer
 * "why is this person's salary lower this month?" without leaving the screen.
 */
function CalculationDetail({ item, revealed, onClose }) {
  const lop = item.lop_breakdown || {}
  const cash = value => (revealed ? money(value) : '••••••')
  const proration = item.working_days ? item.paid_days / item.working_days : 1

  return (
    <Modal title={`How ${item.employee_name}'s pay was calculated`} onClose={onClose}>
      <ol className="calc-steps">
        <li>
          <b>Working days in the month</b>
          <span>{item.working_days}</span>
          <small>Weekends and company holidays already excluded.</small>
        </li>
        <li>
          <b>Attendance recorded</b>
          <span>{lop.present_days ?? 0} present</span>
          <small>
            {[
              lop.paid_leave_days ? `${lop.paid_leave_days} paid leave` : null,
              lop.unpaid_leave_days ? `${lop.unpaid_leave_days} unpaid leave` : null,
              lop.absent_days ? `${lop.absent_days} absent` : null,
              lop.half_days ? `${lop.half_days} half-day` : null,
            ].filter(Boolean).join(' · ') || 'Nothing else recorded.'}
          </small>
        </li>
        <li>
          <b>Loss of pay</b>
          <span>{item.lop_days} days</span>
          <small>
            Absences + unpaid leave + half of each half-day. Paid leave never reduces pay,
            which is why {lop.paid_leave_days || 0} paid leave day
            {(lop.paid_leave_days || 0) === 1 ? '' : 's'} cost nothing.
          </small>
        </li>
        <li>
          <b>Payable days</b>
          <span>
            {item.paid_days} of {item.working_days}
          </span>
          <small>Components are prorated to {(proration * 100).toFixed(1)}%.</small>
        </li>
        <li>
          <b>Earnings</b>
          <span>{cash(item.gross_earnings)}</span>
          <small>
            {(item.earnings_breakdown || [])
              .map(line => `${line.name} ${revealed ? money(line.amount) : '•••'}`)
              .join(' · ')}
          </small>
        </li>
        <li>
          <b>Deductions</b>
          <span>−{cash(item.total_deductions)}</span>
          <small>
            {(item.deductions_breakdown || [])
              .map(line => `${line.name} ${revealed ? money(line.amount) : '•••'}`)
              .join(' · ') || 'None applied.'}
          </small>
        </li>
        <li className="total">
          <b>Net pay</b>
          <span>{cash(item.net_pay)}</span>
        </li>
      </ol>
    </Modal>
  )
}

export function PayrollPage({ notify }) {
  const { can } = useSession()
  const [page, setPage] = useState(1)
  const [openRun, setOpenRun] = useState(null)
  const [assignOpen, setAssignOpen] = useState(false)
  const [period, setPeriod] = useState(lastMonth())
  const { revealed, toggle } = useRevealAmounts()
  const amount = value => (revealed ? money(value) : <span className="masked">••••••</span>)

  const runs = useApi(
    () => api.get(`${ENDPOINTS.payroll.runs}${query({ page, page_size: 12 })}`),
    [page],
  )
  const structures = useApi(() => api.get(ENDPOINTS.payroll.structures), [])
  const employees = useApi(() => api.get(`${ENDPOINTS.employees.list}?page_size=200`), [])

  const { run: act, pending, error } = useAction(message => {
    notify(message)
    runs.reload()
  })

  return (
    <section className="payroll-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">PAYROLL</p>
          <h2>Run payroll with confidence.</h2>
          <p>
            Salaries, attendance and unpaid leave are pulled together automatically —
            loss-of-pay is computed, not typed in.
          </p>
        </div>
        <div className="actions">
          <RevealToggle revealed={revealed} onToggle={toggle} label="pay" />
          {can('salary:manage') && (
            <button className="primary-button" onClick={() => setAssignOpen(true)}>
              Assign salary
            </button>
          )}
        </div>
      </section>

      {can('payroll:process') && (
        <section className="toolbar">
          <label>Month</label>
          <select
            value={period.month}
            onChange={e => setPeriod({ ...period, month: Number(e.target.value) })}
          >
            {MONTHS.map((name, index) => (
              <option key={name} value={index + 1}>{name}</option>
            ))}
          </select>
          <label>Year</label>
          <input
            type="number"
            value={period.year}
            onChange={e => setPeriod({ ...period, year: Number(e.target.value) })}
          />
          <button
            className="primary-button"
            disabled={pending}
            onClick={() =>
              act(
                () => api.post(ENDPOINTS.payroll.runs, { month: period.month, year: period.year }),
                `Payroll processed for ${MONTHS[period.month - 1]} ${period.year}`,
              )
            }
          >
            {pending ? 'Processing…' : 'Process payroll'}
          </button>
        </section>
      )}

      {error && <p className="form-error">{error}</p>}

      <Async state={runs}>
        {data => (
          <>
            <DataTable
              columns={['Period', 'Status', 'Employees', 'Gross', 'Deductions', 'Net', '']}
              rows={data.items}
              empty="No payroll has been run yet."
              renderRow={row => (
                <tr key={row.id}>
                  <td>
                    <b>
                      {MONTHS[row.month - 1]} {row.year}
                    </b>
                  </td>
                  <td><StatusChip status={row.status} /></td>
                  <td>{row.employee_count}</td>
                  <td>{amount(row.total_gross)}</td>
                  <td>{amount(row.total_deductions)}</td>
                  <td><b>{amount(row.total_net)}</b></td>
                  <td>
                    <button className="table-action" onClick={() => setOpenRun(row.id)}>
                      Open
                    </button>
                    {can('payroll:process') && ['DRAFT', 'PENDING_REVIEW'].includes(row.status) && (
                      <button
                        className="table-action decline"
                        onClick={() => {
                          if (window.confirm(`Delete payroll for ${MONTHS[row.month - 1]} ${row.year}?`))
                            act(() => api.del(ENDPOINTS.payroll.run(row.id)), 'Payroll run deleted')
                        }}
                      >
                        Delete
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

      {openRun && (
        <RunDetail
          runId={openRun}
          notify={notify}
          onClose={() => {
            setOpenRun(null)
            runs.reload()
          }}
        />
      )}

      {assignOpen && structures.data && employees.data && (
        <AssignSalaryModal
          employees={employees.data.items}
          structures={structures.data}
          onClose={() => setAssignOpen(false)}
          onDone={() => notify('Salary structure assigned')}
        />
      )}
    </section>
  )
}

function PayslipPreview({ payslip, onClose }) {
  const snapshot = payslip.snapshot || {}
  const employee = snapshot.employee || {}
  const totals = snapshot.totals || {}
  const days = snapshot.days || {}

  const company = snapshot.company || {}
  const logoUrl = company.logo_path ? `${STATIC_BASE}/${company.logo_path}` : null
  const lopReasons = [
    days.absent_days ? `${days.absent_days} absent` : null,
    days.unpaid_leave_days ? `${days.unpaid_leave_days} unpaid leave` : null,
    days.half_days ? `${days.half_days} half-day` : null,
  ].filter(Boolean)

  return (
    <Modal title={`Payslip ${payslip.payslip_number}`} onClose={onClose}>
      <div className="slip">
        <div className="slip-brand">
          {logoUrl ? (
            <img src={logoUrl} alt={company.name || 'Company logo'} />
          ) : (
            <span className="slip-brand-fallback">{(company.name || '?')[0]}</span>
          )}
          <div>
            <b>{company.name || 'Your company'}</b>
            {company.city && (
              <small>
                {company.city}
                {company.state ? `, ${company.state}` : ''}
              </small>
            )}
          </div>
        </div>

        <div className="slip-head">
          <div>
            <h3>{employee.name}</h3>
            <small>
              {employee.code} · {employee.designation || '—'} · {employee.department || '—'}
            </small>
          </div>
          <div>
            <b>
              {MONTHS[payslip.month - 1]} {payslip.year}
            </b>
            <small>
              {days.paid_days} paid of {days.working_days} days
              {days.lop_days > 0 ? ` · ${days.lop_days} LOP` : ''}
            </small>
            {lopReasons.length > 0 && <small>({lopReasons.join(' · ')})</small>}
          </div>
        </div>

        {/* The attendance the pay was derived from, so the payslip is self-explaining. */}
        <div className="slip-attendance">
          {[
            ['Working days', days.working_days],
            ['Present', days.present_days],
            ['Paid leave', days.paid_leave_days],
            ['Unpaid leave', days.unpaid_leave_days],
            ['Absent', days.absent_days],
            ['Loss of pay', days.lop_days],
            ['Payable days', days.paid_days],
          ].map(([label, value]) => (
            <div key={label}>
              <small>{label}</small>
              <b>{value ?? 0}</b>
            </div>
          ))}
        </div>

        <div className="slip-cols">
          <div>
            <p className="eyebrow">EARNINGS</p>
            {(snapshot.earnings || []).map(line => (
              <p key={line.code}>
                <span>{line.name}</span>
                <b>{money(line.amount)}</b>
              </p>
            ))}
            <p>
              <span>
                <b>Gross</b>
              </span>
              <b>{money(totals.gross_earnings)}</b>
            </p>
          </div>
          <div>
            <p className="eyebrow">DEDUCTIONS</p>
            {(snapshot.deductions || []).map(line => (
              <p key={line.code}>
                <span>{line.name}</span>
                <b>{money(line.amount)}</b>
              </p>
            ))}
            <p>
              <span>
                <b>Total</b>
              </span>
              <b>{money(totals.total_deductions)}</b>
            </p>
          </div>
        </div>

        <div className="slip-net">
          <span>Net pay</span>
          <strong>{money(totals.net_pay)}</strong>
        </div>
      </div>

      <div className="slip-actions">
        <button className="primary-button" onClick={() => window.print()}>
          Print / Save as PDF
        </button>
      </div>
    </Modal>
  )
}

export function PayslipsPage() {
  const [open, setOpen] = useState(null)
  const state = useApi(() => api.get(ENDPOINTS.payroll.myPayslips), [])
  const salary = useApi(() => api.get(ENDPOINTS.payroll.mySalary), [])
  const { revealed, toggle } = useRevealAmounts()
  const amount = value => (revealed ? money(value) : <span className="masked">••••••</span>)

  return (
    <section className="payslips-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">MY PAY</p>
          <h2>Your payslips.</h2>
        </div>
        <div className="actions">
          {salary.data && (
            <div className="pay-summary">
              <strong>{revealed ? money(salary.data.net_monthly) : '••••••'}</strong>
              <small>
                net per month · CTC {revealed ? money(salary.data.ctc) : '••••••'}
              </small>
            </div>
          )}
          <RevealToggle revealed={revealed} onToggle={toggle} label="pay" />
        </div>
      </section>

      <Async
        state={state}
        empty={rows => !rows || rows.length === 0}
        emptyTitle="No payslips yet."
        emptyHint="They appear here once payroll has been approved."
      >
        {rows => (
          <DataTable
            columns={['Period', 'Payslip no.', 'Net pay', 'Generated', '']}
            rows={rows}
            renderRow={row => (
              <tr key={row.id}>
                <td>
                  <b>
                    {MONTHS[row.month - 1]} {row.year}
                  </b>
                </td>
                <td>{row.payslip_number}</td>
                <td>
                  <b>{amount(row.net_pay)}</b>
                </td>
                <td>{formatDate(row.generated_at)}</td>
                <td>
                  <button className="table-action" onClick={() => setOpen(row)}>
                    View
                  </button>
                </td>
              </tr>
            )}
          />
        )}
      </Async>

      {open && <PayslipPreview payslip={open} onClose={() => setOpen(null)} />}
    </section>
  )
}
