import { useState } from 'react'
import { ENDPOINTS, api } from '../api.js'
import { Async, DataTable, useAction, useApi } from '../lib/ui.jsx'
import {
  AttendanceRulesPanel,
  BrandingPanel,
  CompliancePanel,
} from './settings-panels.jsx'

const WEEKDAYS = [
  [1, 'Mon'], [2, 'Tue'], [3, 'Wed'], [4, 'Thu'], [5, 'Fri'], [6, 'Sat'], [7, 'Sun'],
]

/** Departments / designations / locations all behave the same — one component covers them. */
function OrgList({ title, listPath, createPath, deletePath, notify, extraLabel }) {
  const state = useApi(() => api.get(listPath), [])
  const { run, pending, error } = useAction(message => {
    notify(message)
    state.reload()
  })
  const [name, setName] = useState('')

  return (
    <article className="panel">
      <div className="panel-title">
        <h3>{title}</h3>
      </div>

      <form
        className="add-row"
        onSubmit={event => {
          event.preventDefault()
          if (!name.trim()) return
          run(() => api.post(createPath, { name: name.trim() }), `${title} added`).then(() =>
            setName(''),
          )
        }}
      >
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder={`Add a ${title.toLowerCase().replace(/s$/, '')}`}
        />
        <button className="primary-button" disabled={pending}>
          Add
        </button>
      </form>

      {error && <p className="form-error">{error}</p>}

      <Async state={state} empty={rows => !rows || rows.length === 0} emptyTitle={`No ${title.toLowerCase()} yet.`}>
        {rows => (
          <DataTable
            columns={['Name', extraLabel || 'Status', '']}
            rows={rows}
            renderRow={row => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>
                  {extraLabel
                    ? row.employee_count ?? row.city ?? '—'
                    : row.is_active
                      ? 'Active'
                      : 'Inactive'}
                </td>
                <td>
                  <button
                    className="table-action"
                    onClick={() => {
                      if (window.confirm(`Remove ${row.name}?`))
                        run(() => api.del(deletePath(row.id)), `${row.name} removed`)
                    }}
                  >
                    Remove
                  </button>
                </td>
              </tr>
            )}
          />
        )}
      </Async>
    </article>
  )
}

function CompanyPanel({ notify }) {
  const state = useApi(() => api.get(ENDPOINTS.company.current), [])
  const { run, pending, error } = useAction(message => {
    notify(message)
    state.reload()
  })

  return (
    <article className="panel">
      <div className="panel-title">
        <h3>Company details</h3>
      </div>
      <Async state={state}>
        {company => (
          <form
            className="form-grid"
            onSubmit={event => {
              event.preventDefault()
              const form = new FormData(event.currentTarget)
              run(
                () =>
                  api.patch(ENDPOINTS.company.current, {
                    name: form.get('name'),
                    industry: form.get('industry'),
                    email: form.get('email'),
                    phone: form.get('phone'),
                    website: form.get('website') || null,
                    address: form.get('address'),
                    city: form.get('city'),
                    state: form.get('state'),
                    country: form.get('country'),
                    postal_code: form.get('postal_code'),
                  }),
                'Company details saved',
              )
            }}
          >
            <label>Company name</label>
            <input name="name" defaultValue={company.name} required />
            <label>Industry</label>
            <input name="industry" defaultValue={company.industry} required />
            <label>Email</label>
            <input name="email" type="email" defaultValue={company.email} required />
            <label>Phone</label>
            <input name="phone" defaultValue={company.phone} required />
            <label>Website</label>
            <input name="website" defaultValue={company.website || ''} />
            <label>Address</label>
            <input name="address" defaultValue={company.address} required />
            <label>City</label>
            <input name="city" defaultValue={company.city} required />
            <label>State</label>
            <input name="state" defaultValue={company.state} required />
            <label>Country</label>
            <input name="country" defaultValue={company.country} required />
            <label>Postal code</label>
            <input name="postal_code" defaultValue={company.postal_code} required />
            {error && <p className="form-error">{error}</p>}
            <button className="primary-button" disabled={pending}>
              {pending ? 'Saving…' : 'Save changes'}
            </button>
          </form>
        )}
      </Async>
    </article>
  )
}

function WorkPolicyPanel({ notify }) {
  const state = useApi(() => api.get(ENDPOINTS.organization.workPolicies), [])
  const { run, pending, error } = useAction(message => {
    notify(message)
    state.reload()
  })
  const [days, setDays] = useState(null)

  return (
    <article className="panel">
      <div className="panel-title">
        <h3>Work policy</h3>
      </div>
      <Async state={state} empty={rows => !rows || rows.length === 0} emptyTitle="No work policy set.">
        {rows => {
          const policy = rows[0]
          const working = days ?? policy.working_days
          const toggle = day =>
            setDays(current => {
              const base = current ?? policy.working_days
              return base.includes(day) ? base.filter(d => d !== day) : [...base, day]
            })

          return (
            <form
              className="form-grid"
              onSubmit={event => {
                event.preventDefault()
                const form = new FormData(event.currentTarget)
                run(
                  () =>
                    api.put(ENDPOINTS.organization.defaultWorkPolicy, {
                      name: policy.name,
                      working_days: [...working].sort((a, b) => a - b),
                      start_time: `${form.get('start_time')}:00`,
                      end_time: `${form.get('end_time')}:00`,
                      break_start: form.get('break_start') ? `${form.get('break_start')}:00` : null,
                      break_end: form.get('break_end') ? `${form.get('break_end')}:00` : null,
                      full_day_hours: Number(form.get('full_day_hours')),
                      half_day_hours: Number(form.get('half_day_hours')),
                      late_grace_minutes: Number(form.get('late_grace_minutes')),
                    }),
                  'Work policy saved',
                )
              }}
            >
              <label>Working days</label>
              <div className="day-toggle">
                {WEEKDAYS.map(([day, label]) => (
                  <button
                    type="button"
                    key={day}
                    aria-pressed={working.includes(day)}
                    onClick={() => toggle(day)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <label>Start time</label>
              <input name="start_time" type="time" defaultValue={policy.start_time?.slice(0, 5)} required />
              <label>End time</label>
              <input name="end_time" type="time" defaultValue={policy.end_time?.slice(0, 5)} required />
              <label>Break start</label>
              <input name="break_start" type="time" defaultValue={policy.break_start?.slice(0, 5) || ''} />
              <label>Break end</label>
              <input name="break_end" type="time" defaultValue={policy.break_end?.slice(0, 5) || ''} />
              <label>Full day hours</label>
              <input name="full_day_hours" type="number" step="0.5" defaultValue={policy.full_day_hours} required />
              <label>Half day hours</label>
              <input name="half_day_hours" type="number" step="0.5" defaultValue={policy.half_day_hours} required />
              <label>Late grace (minutes)</label>
              <input name="late_grace_minutes" type="number" defaultValue={policy.late_grace_minutes} required />
              {error && <p className="form-error">{error}</p>}
              <button className="primary-button" disabled={pending}>
                {pending ? 'Saving…' : 'Save work policy'}
              </button>
            </form>
          )
        }}
      </Async>
    </article>
  )
}

function LeaveTypesPanel({ notify }) {
  const state = useApi(() => api.get(ENDPOINTS.organization.leaveTypes), [])
  const { run, pending } = useAction(message => {
    notify(message)
    state.reload()
  })

  return (
    <article className="panel">
      <div className="panel-title">
        <h3>Leave types</h3>
      </div>
      <Async state={state}>
        {rows => (
          <DataTable
            columns={['Type', 'Code', 'Annual quota', 'Paid', 'Half day', '']}
            rows={rows}
            renderRow={row => (
              <tr key={row.id}>
                <td>{row.name}</td>
                <td>{row.code}</td>
                <td>
                  <input
                    type="number"
                    min="0"
                    defaultValue={row.annual_quota}
                    style={{ width: '5rem' }}
                    onBlur={event => {
                      const value = Number(event.target.value)
                      if (value !== row.annual_quota)
                        run(
                          () =>
                            api.patch(ENDPOINTS.organization.leaveType(row.id), {
                              annual_quota: value,
                            }),
                          `${row.name} quota updated`,
                        )
                    }}
                  />
                </td>
                <td>{row.is_paid ? 'Yes' : 'No'}</td>
                <td>{row.allow_half_day ? 'Yes' : 'No'}</td>
                <td>
                  <button
                    className="table-action"
                    disabled={pending}
                    onClick={() =>
                      run(
                        () =>
                          api.patch(ENDPOINTS.organization.leaveType(row.id), {
                            is_active: !row.is_active,
                          }),
                        `${row.name} ${row.is_active ? 'disabled' : 'enabled'}`,
                      )
                    }
                  >
                    {row.is_active ? 'Disable' : 'Enable'}
                  </button>
                </td>
              </tr>
            )}
          />
        )}
      </Async>
      <p className="form-note">
        Changing a quota affects balances created from now on. Existing balances can be adjusted per
        employee from their profile.
      </p>
    </article>
  )
}

export function SettingsPage({ notify }) {
  const [panel, setPanel] = useState('company')

  const panels = {
    company: <CompanyPanel notify={notify} />,
    branding: <BrandingPanel notify={notify} />,
    departments: (
      <OrgList
        title="Departments"
        listPath={ENDPOINTS.organization.departments}
        createPath={ENDPOINTS.organization.departments}
        deletePath={ENDPOINTS.organization.department}
        extraLabel="Employees"
        notify={notify}
      />
    ),
    designations: (
      <OrgList
        title="Designations"
        listPath={ENDPOINTS.organization.designations}
        createPath={ENDPOINTS.organization.designations}
        deletePath={ENDPOINTS.organization.designation}
        notify={notify}
      />
    ),
    locations: (
      <OrgList
        title="Locations"
        listPath={ENDPOINTS.organization.locations}
        createPath={ENDPOINTS.organization.locations}
        deletePath={ENDPOINTS.organization.location}
        extraLabel="City"
        notify={notify}
      />
    ),
    'work policy': <WorkPolicyPanel notify={notify} />,
    'leave types': <LeaveTypesPanel notify={notify} />,
    attendance: <AttendanceRulesPanel notify={notify} />,
    compliance: <CompliancePanel notify={notify} />,
  }

  return (
    <section className="settings-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">SETTINGS</p>
          <h2>Configure your workspace.</h2>
        </div>
      </section>

      <div className="settings-layout">
        <nav className="settings-nav">
          {Object.keys(panels).map(key => (
            <button key={key} className={panel === key ? 'active' : ''} onClick={() => setPanel(key)}>
              {key.charAt(0).toUpperCase() + key.slice(1)}
            </button>
          ))}
        </nav>
        <div className="settings-body">{panels[panel]}</div>
      </div>
    </section>
  )
}
