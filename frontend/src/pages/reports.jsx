import { useState } from 'react'
import { ENDPOINTS, api, download, query } from '../api.js'
import { Async, DataTable, monthStartISO, todayISO, useApi } from '../lib/ui.jsx'

const REPORTS = [
  { key: 'employees', label: 'Employee report', path: ENDPOINTS.reports.employees, filters: ['department_id', 'status'] },
  { key: 'attendance', label: 'Attendance report', path: ENDPOINTS.reports.attendance, filters: ['dates', 'department_id'] },
  { key: 'leaves', label: 'Leave report', path: ENDPOINTS.reports.leaves, filters: ['dates', 'department_id', 'leaveStatus'] },
  { key: 'payroll', label: 'Payroll report', path: ENDPOINTS.reports.payroll, filters: ['period', 'department_id'] },
]

export function ReportsPage({ notify }) {
  const [active, setActive] = useState(REPORTS[0])
  const [filters, setFilters] = useState({
    from_date: monthStartISO(),
    to_date: todayISO(),
    department_id: '',
    status: '',
    year: new Date().getFullYear(),
    month: '',
  })

  const departments = useApi(() => api.get(ENDPOINTS.organization.departments), [])
  const headcount = useApi(() => api.get(ENDPOINTS.reports.headcount), [])

  const params = () => {
    const base = { department_id: filters.department_id }
    if (active.filters.includes('dates')) {
      base.from_date = filters.from_date
      base.to_date = filters.to_date
    }
    if (active.filters.includes('status') || active.filters.includes('leaveStatus')) {
      base.status = filters.status
    }
    if (active.filters.includes('period')) {
      base.year = filters.year
      base.month = filters.month
    }
    return base
  }

  const state = useApi(
    () => api.get(`${active.path}${query(params())}`),
    [active.key, filters.from_date, filters.to_date, filters.department_id, filters.status, filters.year, filters.month],
  )

  const set = patch => setFilters(current => ({ ...current, ...patch }))
  const headcountRows = Array.isArray(headcount.data?.rows) ? headcount.data.rows : []
  const maxHeadcount = Math.max(1, ...headcountRows.map(r => Number(r.headcount) || 0))

  return (
    <section className="reports-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">REPORTS</p>
          <h2>Answers you can export.</h2>
          <p>Filter, review, then download the full set as CSV.</p>
        </div>
        <button
          className="primary-button"
          onClick={() => {
            download(`${active.path}${query({ ...params(), export: true })}`, `${active.key}.csv`)
            notify('CSV downloaded')
          }}
        >
          Export CSV
        </button>
      </section>

      <div>
        <div className="tabs">
          {REPORTS.map(report => (
            <button
              key={report.key}
              className={active.key === report.key ? 'active' : ''}
              onClick={() => setActive(report)}
            >
              {report.label}
            </button>
          ))}
        </div>

        <div className="toolbar">
          {active.filters.includes('dates') && (
            <>
              <label>From</label>
              <input type="date" value={filters.from_date} onChange={e => set({ from_date: e.target.value })} />
              <label>To</label>
              <input type="date" value={filters.to_date} onChange={e => set({ to_date: e.target.value })} />
            </>
          )}

          {active.filters.includes('period') && (
            <>
              <label>Year</label>
              <input type="number" value={filters.year} onChange={e => set({ year: e.target.value })} />
              <label>Month</label>
              <select value={filters.month} onChange={e => set({ month: e.target.value })}>
                <option value="">All months</option>
                {Array.from({ length: 12 }, (_, i) => (
                  <option key={i + 1} value={i + 1}>{i + 1}</option>
                ))}
              </select>
            </>
          )}

          <label>Department</label>
          <select value={filters.department_id} onChange={e => set({ department_id: e.target.value })}>
            <option value="">All departments</option>
            {(departments.data || []).map(d => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>

          {active.filters.includes('leaveStatus') && (
            <>
              <label>Status</label>
              <select value={filters.status} onChange={e => set({ status: e.target.value })}>
                <option value="">All</option>
                {['PENDING', 'APPROVED', 'REJECTED', 'CANCELLED'].map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </>
          )}
        </div>
      </div>

      <Async state={state}>
        {data => {
          const columns = Array.isArray(data?.columns) ? data.columns : []
          const rows = Array.isArray(data?.rows) ? data.rows : []
          const count = Number.isFinite(Number(data?.count)) ? Number(data.count) : rows.length

          return (
            <>
              <p className="form-note">{count} rows</p>
            <DataTable
              columns={columns.map(c => String(c).replace(/_/g, ' '))}
              rows={rows.slice(0, 200)}
              empty="No data for these filters."
              renderRow={(row, index) => (
                <tr key={index}>
                  {columns.map(column => (
                    <td key={column}>{String(row[column] ?? '')}</td>
                  ))}
                </tr>
              )}
            />
            {rows.length > 200 && (
              <p className="form-note">
                Showing the first 200 rows — export to CSV for the full set.
              </p>
            )}
            </>
          )
        }}
      </Async>

      <Async state={headcount}>
        {data => (
          <section className="panel">
            <h3>Headcount by department</h3>
            <div className="bar-chart">
              {(Array.isArray(data?.rows) ? data.rows : []).map(row => (
                <p key={row.department}>
                  <span>{row.department}</span>
                  <i>
                    <b style={{ width: `${(row.headcount / maxHeadcount) * 100}%` }} />
                  </i>
                  <strong>{row.headcount}</strong>
                </p>
              ))}
            </div>
          </section>
        )}
      </Async>
    </section>
  )
}
