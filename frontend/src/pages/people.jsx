import { useState } from 'react'
import { ENDPOINTS, api, download, query } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  Modal,
  Pager,
  PersonCell,
  StatusChip,
  formatDate,
  initials,
  money,
  titleCase,
  todayISO,
  useAction,
  useApi,
} from '../lib/ui.jsx'

const EMPLOYMENT_TYPES = ['FULL_TIME', 'PART_TIME', 'CONTRACT', 'INTERN', 'CONSULTANT']
const ROLES = ['EMPLOYEE', 'MANAGER', 'HR', 'COMPANY_ADMIN']
const STATUSES = ['ACTIVE', 'PROBATION', 'NOTICE_PERIOD', 'INACTIVE', 'TERMINATED', 'RESIGNED']

function AddEmployeeModal({ options, onClose, onCreated }) {
  const [created, setCreated] = useState(null)
  const { run, pending, error } = useAction()

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const value = key => {
      const raw = form.get(key)
      return raw === null || String(raw).trim() === '' ? null : String(raw).trim()
    }

    const payload = {
      first_name: value('first_name'),
      last_name: value('last_name'),
      work_email: value('work_email'),
      employee_code: value('employee_code'),
      role: value('role') || 'EMPLOYEE',
      create_login: form.get('create_login') === 'on',
      password: value('password'),
      status: value('status') || 'ACTIVE',
      employment: {
        department_id: value('department_id') ? Number(value('department_id')) : null,
        designation_id: value('designation_id') ? Number(value('designation_id')) : null,
        location_id: value('location_id') ? Number(value('location_id')) : null,
        manager_id: value('manager_id') ? Number(value('manager_id')) : null,
        joining_date: value('joining_date') || todayISO(),
        employment_type: value('employment_type') || 'FULL_TIME',
        is_manager: form.get('is_manager') === 'on',
      },
      personal: {
        phone: value('phone'),
        date_of_birth: value('date_of_birth'),
        gender: value('gender'),
      },
    }

    const result = await run(() => api.post(ENDPOINTS.employees.list, payload))
    if (result) {
      onCreated()
      // The generated password is returned once and never again.
      if (result.generated_password) setCreated(result)
      else onClose()
    }
  }

  if (created) {
    return (
      <Modal title="Employee added" onClose={onClose}>
        <p>
          <b>{created.employee.full_name}</b> ({created.employee.employee_code}) has been added.
        </p>
        <p className="form-note">
          Their temporary password is shown once — copy it now and share it securely.
        </p>
        <div className="password-field">
          <input readOnly value={created.generated_password} />
          <button
            type="button"
            onClick={() => navigator.clipboard?.writeText(created.generated_password)}
          >
            Copy
          </button>
        </div>
        <button className="primary-button" onClick={onClose}>
          Done
        </button>
      </Modal>
    )
  }

  return (
    <Modal title="Add an employee" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label>First name</label>
        <input name="first_name" required />
        <label>Last name</label>
        <input name="last_name" />
        <label>Work email</label>
        <input name="work_email" type="email" required />
        <label>Employee code</label>
        <input name="employee_code" placeholder="Leave blank to auto-generate" />

        <label>Department</label>
        <select name="department_id">
          <option value="">—</option>
          {(options.departments || []).map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>

        <label>Designation</label>
        <select name="designation_id">
          <option value="">—</option>
          {(options.designations || []).map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>

        <label>Location</label>
        <select name="location_id">
          <option value="">—</option>
          {(options.locations || []).map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>

        <label>Reporting manager</label>
        <select name="manager_id">
          <option value="">—</option>
          {(options.managers || []).map(m => (
            <option key={m.id} value={m.id}>{m.full_name}</option>
          ))}
        </select>

        <label>Joining date</label>
        <input name="joining_date" type="date" defaultValue={todayISO()} required />

        <label>Employment type</label>
        <select name="employment_type" defaultValue="FULL_TIME">
          {EMPLOYMENT_TYPES.map(t => (
            <option key={t} value={t}>{titleCase(t)}</option>
          ))}
        </select>

        <label>Role</label>
        <select name="role" defaultValue="EMPLOYEE">
          {ROLES.map(r => (
            <option key={r} value={r}>{titleCase(r)}</option>
          ))}
        </select>

        <label>Phone</label>
        <input name="phone" />
        <label>Date of birth</label>
        <input name="date_of_birth" type="date" />
        <label>Gender</label>
        <select name="gender">
          <option value="">—</option>
          {['MALE', 'FEMALE', 'OTHER', 'UNDISCLOSED'].map(g => (
            <option key={g} value={g}>{titleCase(g)}</option>
          ))}
        </select>

        <label>
          <input type="checkbox" name="is_manager" /> This person manages others
        </label>
        <label>
          <input type="checkbox" name="create_login" defaultChecked /> Create a login account
        </label>
        <label>Password (blank = auto-generate)</label>
        <input name="password" type="text" minLength={8} placeholder="At least 8 characters" />

        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Adding…' : 'Add employee'}
        </button>
      </form>
    </Modal>
  )
}

function ImportModal({ onClose, onDone }) {
  const [result, setResult] = useState(null)
  const { run, pending, error } = useAction()

  async function submit(event) {
    event.preventDefault()
    const file = new FormData(event.currentTarget).get('file')
    if (!file || !file.name) return
    const body = new FormData()
    body.append('file', file)
    const data = await run(() => api.post(ENDPOINTS.employees.import, body))
    if (data) {
      setResult(data)
      onDone()
    }
  }

  return (
    <Modal title="Import employees from CSV" onClose={onClose}>
      {result ? (
        <>
          <p>
            <b>{result.created}</b> created, <b>{result.failed}</b> failed.
          </p>
          {result.errors.length > 0 && (
            <DataTable
              columns={['Row', 'Problem']}
              rows={result.errors}
              renderRow={row => (
                <tr key={row.row}>
                  <td>{row.row}</td>
                  <td>{row.error}</td>
                </tr>
              )}
            />
          )}
          <button className="primary-button" onClick={onClose}>Done</button>
        </>
      ) : (
        <form className="form-grid" onSubmit={submit}>
          <p className="form-note">
            Columns: employee_code, first_name, last_name, work_email, department, designation,
            location, manager_email, joining_date, employment_type, phone, date_of_birth, gender.
            Good rows are saved even if others fail.
          </p>
          <button
            type="button"
            className="table-action"
            onClick={() => download(ENDPOINTS.employees.csvTemplate, 'employee_import_template.csv')}
          >
            Download template
          </button>
          <input name="file" type="file" accept=".csv" required />
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button" disabled={pending}>
            {pending ? 'Importing…' : 'Import'}
          </button>
        </form>
      )}
    </Modal>
  )
}

function EmployeeDetail({ employeeId, onClose, notify, canManage }) {
  const state = useApi(() => api.get(ENDPOINTS.employees.byId(employeeId)), [employeeId])
  const salary = useApi(() => api.get(ENDPOINTS.payroll.salaries(employeeId)), [employeeId], {
    skip: !canManage,
  })
  const documents = useApi(() => api.get(ENDPOINTS.documents.forEmployee(employeeId)), [employeeId])
  const balances = useApi(() => api.get(ENDPOINTS.leave.balancesFor(employeeId)), [employeeId])
  const [tab, setTab] = useState('overview')

  const { run } = useAction(message => {
    notify(message)
    state.reload()
  })

  return (
    <Modal title="Employee profile" onClose={onClose}>
      <Async state={state}>
        {employee => (
          <div>
            <div className="detail-head">
              <span className="avatar-lg">{initials(employee.full_name)}</span>
              <div>
                <h3>{employee.full_name}</h3>
                <small>
                  {employee.employee_code} · {employee.work_email}
                </small>
                <StatusChip status={employee.status} />
              </div>
            </div>

            <div className="tabs">
              {['overview', 'personal', 'leave', 'documents', canManage && 'salary']
                .filter(Boolean)
                .map(name => (
                  <button
                    key={name}
                    className={tab === name ? 'active' : ''}
                    onClick={() => setTab(name)}
                  >
                    {titleCase(name)}
                  </button>
                ))}
            </div>

            {tab === 'overview' && (
              <dl className="detail-list">
                {[
                  ['Department', employee.employment?.department_name],
                  ['Designation', employee.employment?.designation_name],
                  ['Location', employee.employment?.location_name],
                  ['Manager', employee.employment?.manager_name],
                  ['Joining date', formatDate(employee.employment?.joining_date)],
                  ['Employment type', titleCase(employee.employment?.employment_type)],
                  ['Roles', employee.roles.join(', ')],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value || '—'}</dd>
                  </div>
                ))}
              </dl>
            )}

            {tab === 'personal' && (
              <dl className="detail-list">
                {[
                  ['Phone', employee.personal?.phone],
                  ['Date of birth', formatDate(employee.personal?.date_of_birth)],
                  ['Gender', titleCase(employee.personal?.gender)],
                  ['Personal email', employee.personal?.personal_email],
                  ['City', employee.personal?.city],
                  ['Emergency contact', employee.personal?.emergency_contact_name],
                  ['Emergency phone', employee.personal?.emergency_contact_phone],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value || '—'}</dd>
                  </div>
                ))}
              </dl>
            )}

            {tab === 'leave' && (
              <Async state={balances}>
                {rows => (
                  <DataTable
                    columns={['Type', 'Allocated', 'Used', 'Pending', 'Available']}
                    rows={rows}
                    renderRow={row => (
                      <tr key={row.leave_type_id}>
                        <td>{row.leave_type_name}</td>
                        <td>{row.total}</td>
                        <td>{row.used}</td>
                        <td>{row.pending}</td>
                        <td>{row.available}</td>
                      </tr>
                    )}
                  />
                )}
              </Async>
            )}

            {tab === 'documents' && (
              <Async state={documents}>
                {rows => (
                  <DataTable
                    columns={['Title', 'Type', 'Visible', '']}
                    rows={rows}
                    empty="No documents uploaded."
                    renderRow={row => (
                      <tr key={row.id}>
                        <td>{row.title}</td>
                        <td>{titleCase(row.document_type)}</td>
                        <td>{row.is_visible_to_employee ? 'Employee' : 'HR only'}</td>
                        <td>
                          <button
                            className="table-action"
                            onClick={() => download(ENDPOINTS.documents.download(row.id), row.file_name)}
                          >
                            Download
                          </button>
                        </td>
                      </tr>
                    )}
                  />
                )}
              </Async>
            )}

            {tab === 'salary' && canManage && (
              <Async state={salary}>
                {rows =>
                  rows.length === 0 ? (
                    <p className="form-note">No salary structure assigned yet.</p>
                  ) : (
                    <>
                      <p className="form-note">
                        CTC {money(rows[0].ctc)} · Gross {money(rows[0].gross_monthly)}/mo · Net{' '}
                        {money(rows[0].net_monthly)}/mo
                      </p>
                      <DataTable
                        columns={['Component', 'Type', 'Monthly']}
                        rows={rows[0].components}
                        renderRow={row => (
                          <tr key={row.component_id}>
                            <td>{row.name}</td>
                            <td>{titleCase(row.component_type)}</td>
                            <td>{money(row.monthly_amount)}</td>
                          </tr>
                        )}
                      />
                    </>
                  )
                }
              </Async>
            )}

            {canManage && (
              <div className="actions">
                {employee.status === 'ACTIVE' ? (
                  <button
                    className="table-action decline"
                    onClick={() => {
                      const reason = window.prompt('Reason for deactivating?') || null
                      run(
                        () =>
                          api.post(ENDPOINTS.employees.deactivate(employee.id), {
                            exit_date: todayISO(),
                            exit_reason: reason,
                            status: 'INACTIVE',
                          }),
                        `${employee.full_name} deactivated`,
                      )
                    }}
                  >
                    Deactivate
                  </button>
                ) : (
                  <button
                    className="table-action approve"
                    onClick={() =>
                      run(
                        () => api.post(ENDPOINTS.employees.activate(employee.id)),
                        `${employee.full_name} reactivated`,
                      )
                    }
                  >
                    Reactivate
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </Async>
    </Modal>
  )
}

export function PeoplePage({ notify }) {
  const { can } = useSession()
  const canManage = can('employee:create')

  const [filters, setFilters] = useState({ search: '', department_id: '', status: '', page: 1 })
  const [selected, setSelected] = useState(null)
  const [addOpen, setAddOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)

  const departments = useApi(() => api.get(ENDPOINTS.organization.departments), [])
  const designations = useApi(() => api.get(ENDPOINTS.organization.designations), [])
  const locations = useApi(() => api.get(ENDPOINTS.organization.locations), [])

  const state = useApi(
    () => api.get(`${ENDPOINTS.employees.list}${query({ ...filters, page_size: 15 })}`),
    [filters.search, filters.department_id, filters.status, filters.page],
  )

  const set = patch => setFilters(current => ({ ...current, ...patch, page: 1 }))

  return (
    <section>
      <section className="page-hero">
        <div>
          <p className="eyebrow">DIRECTORY</p>
          <h2>{can('employee:read_all') ? 'Everyone at your company.' : 'Your team.'}</h2>
          <p>Search, filter and open any profile.</p>
        </div>
        {canManage && (
          <div className="actions">
            <button className="ghost-button" onClick={() => setImportOpen(true)}>
              Import CSV
            </button>
            <button className="primary-button" onClick={() => setAddOpen(true)}>
              Add employee
            </button>
          </div>
        )}
      </section>

      <section className="toolbar">
        <input
          type="search"
          placeholder="Search by name, code or email"
          value={filters.search}
          onChange={e => set({ search: e.target.value })}
        />
        <select value={filters.department_id} onChange={e => set({ department_id: e.target.value })}>
          <option value="">All departments</option>
          {(departments.data || []).map(d => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
        <select value={filters.status} onChange={e => set({ status: e.target.value })}>
          <option value="">All statuses</option>
          {STATUSES.map(s => (
            <option key={s} value={s}>{titleCase(s)}</option>
          ))}
        </select>
      </section>

      <Async state={state}>
        {page => (
          <>
            <DataTable
              columns={['Employee', 'Department', 'Designation', 'Manager', 'Joined', 'Type', 'Status', '']}
              rows={page.items}
              empty="No employees match these filters."
              renderRow={row => (
                <tr key={row.id}>
                  <td>
                    <PersonCell
                      name={row.full_name}
                      code={row.employee_code}
                      secondary={row.work_email}
                    />
                  </td>
                  <td>{row.department_name || '—'}</td>
                  <td>{row.designation_name || '—'}</td>
                  <td>{row.manager_name || '—'}</td>
                  <td>{formatDate(row.joining_date)}</td>
                  <td>{titleCase(row.employment_type)}</td>
                  <td><StatusChip status={row.status} /></td>
                  <td>
                    <button className="table-action" onClick={() => setSelected(row.id)}>
                      View
                    </button>
                  </td>
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

      {selected && (
        <EmployeeDetail
          employeeId={selected}
          canManage={canManage}
          notify={notify}
          onClose={() => {
            setSelected(null)
            state.reload()
          }}
        />
      )}

      {addOpen && (
        <AddEmployeeModal
          options={{
            departments: departments.data,
            designations: designations.data,
            locations: locations.data,
            managers: state.data?.items || [],
          }}
          onClose={() => setAddOpen(false)}
          onCreated={() => {
            notify('Employee added')
            state.reload()
          }}
        />
      )}

      {importOpen && (
        <ImportModal
          onClose={() => setImportOpen(false)}
          onDone={() => {
            notify('Import finished')
            state.reload()
          }}
        />
      )}
    </section>
  )
}
