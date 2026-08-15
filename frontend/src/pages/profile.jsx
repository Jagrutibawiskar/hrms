import { useState } from 'react'
import { ENDPOINTS, api } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  formatDate,
  initials,
  money,
  titleCase,
  useAction,
  useApi,
} from '../lib/ui.jsx'

function ChangePassword({ notify }) {
  const { run, pending, error } = useAction(notify)
  const [done, setDone] = useState(false)

  return (
    <article className="panel">
      <div className="panel-title">
        <h3>Password</h3>
      </div>
      <form
        className="form-grid"
        onSubmit={async event => {
          event.preventDefault()
          const form = new FormData(event.currentTarget)
          const target = event.currentTarget
          const result = await run(
            () =>
              api.post(ENDPOINTS.auth.changePassword, {
                current_password: form.get('current_password'),
                new_password: form.get('new_password'),
              }),
            'Password changed',
          )
          if (result) {
            target.reset()
            setDone(true)
          }
        }}
      >
        <label>Current password</label>
        <input name="current_password" type="password" required />
        <label>New password</label>
        <input name="new_password" type="password" minLength={8} required />
        {error && <p className="form-error">{error}</p>}
        {done && <p className="form-success">Your password has been updated.</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Saving…' : 'Change password'}
        </button>
      </form>
    </article>
  )
}

export function ProfilePage({ notify }) {
  const { me, signOut } = useSession()
  const state = useApi(() => api.get(ENDPOINTS.employees.me), [])
  const salary = useApi(() => api.get(ENDPOINTS.payroll.mySalary), [])

  return (
    <section className="profile-page">
      <Async state={state}>
        {employee => {
          const roles = Array.isArray(employee?.roles) ? employee.roles : []
          const salaryComponents = Array.isArray(salary.data?.components) ? salary.data.components : []

          return (
            <>
            <section className="profile-banner">
              <span className="avatar-lg">{initials(employee.full_name)}</span>
              <div className="profile-copy">
                <p className="eyebrow">{employee.employee_code}</p>
                <h2>{employee.full_name}</h2>
                <p>
                  {employee.employment?.designation_name || '—'} ·{' '}
                  {employee.employment?.department_name || '—'}
                </p>
                <div className="role-tags">
                  {roles.map(role => (
                    <span key={role} className="chip">
                      {titleCase(role)}
                    </span>
                  ))}
                </div>
              </div>
              <button className="table-action" onClick={signOut}>
                Sign out
              </button>
            </section>

            <div className="profile-cards">
              <article className="panel">
                <div className="panel-title">
                  <h3>Employment</h3>
                </div>
                <dl className="detail-list">
                  {[
                    ['Work email', employee.work_email],
                    ['Department', employee.employment?.department_name],
                    ['Designation', employee.employment?.designation_name],
                    ['Location', employee.employment?.location_name],
                    ['Reporting manager', employee.employment?.manager_name],
                    ['Joining date', formatDate(employee.employment?.joining_date)],
                    ['Employment type', titleCase(employee.employment?.employment_type)],
                    ['Status', titleCase(employee.status)],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value || '—'}</dd>
                    </div>
                  ))}
                </dl>
              </article>

              <article className="panel">
                <div className="panel-title">
                  <h3>Personal</h3>
                </div>
                <dl className="detail-list">
                  {[
                    ['Phone', employee.personal?.phone],
                    ['Date of birth', formatDate(employee.personal?.date_of_birth)],
                    ['Gender', titleCase(employee.personal?.gender)],
                    ['Personal email', employee.personal?.personal_email],
                    [
                      'Address',
                      [employee.personal?.address_line1, employee.personal?.city, employee.personal?.state]
                        .filter(Boolean)
                        .join(', '),
                    ],
                    ['Emergency contact', employee.personal?.emergency_contact_name],
                    ['Emergency phone', employee.personal?.emergency_contact_phone],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <dt>{label}</dt>
                      <dd>{value || '—'}</dd>
                    </div>
                  ))}
                </dl>
                <p className="form-note">
                  Ask your HR team to update these details.
                </p>
              </article>

              {salary.data && (
                <article className="panel">
                  <div className="panel-title">
                    <h3>Salary</h3>
                  </div>
                  <p className="form-note">
                    CTC {money(salary.data.ctc)} · Net {money(salary.data.net_monthly)} per month
                  </p>
                  <DataTable
                    columns={['Component', 'Type', 'Monthly']}
                    rows={salaryComponents}
                    renderRow={row => (
                      <tr key={row.component_id}>
                        <td>{row.name}</td>
                        <td>{titleCase(row.component_type)}</td>
                        <td>{money(row.monthly_amount)}</td>
                      </tr>
                    )}
                  />
                </article>
              )}

              <ChangePassword notify={notify} />
            </div>
            </>
          )
        }}
      </Async>

      {!state.loading && state.error && (
        <article className="panel">
          <p className="form-note">
            {me?.user?.email} is signed in, but no employee record is linked to this account yet.
          </p>
          <ChangePassword notify={notify} />
        </article>
      )}
    </section>
  )
}
