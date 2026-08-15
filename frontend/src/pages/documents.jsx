import { useState } from 'react'
import { ENDPOINTS, api, download, query } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  Modal,
  StatusChip,
  formatDate,
  titleCase,
  todayISO,
  useAction,
  useApi,
} from '../lib/ui.jsx'

const DOC_TYPES = [
  'AADHAAR', 'PAN', 'OFFER_LETTER', 'JOINING_LETTER', 'EXPERIENCE_LETTER', 'EDUCATION', 'OTHER',
]

function bytes(size) {
  if (!size) return '—'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function UploadModal({ employees, onClose, onDone }) {
  const { run, pending, error } = useAction()

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const result = await run(() => api.post(ENDPOINTS.documents.upload, form))
    if (result) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal title="Upload a document" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label>Employee</label>
        <select name="employee_id" required>
          <option value="">Choose an employee</option>
          {employees.map(e => (
            <option key={e.id} value={e.id}>
              {e.full_name} — {e.employee_code}
            </option>
          ))}
        </select>

        <label>Title</label>
        <input name="title" required placeholder="e.g. Offer Letter" />

        <label>Type</label>
        <select name="document_type" defaultValue="OTHER">
          {DOC_TYPES.map(t => (
            <option key={t} value={t}>{titleCase(t)}</option>
          ))}
        </select>

        <label>Description</label>
        <input name="description" placeholder="Optional" />

        <label>
          <input type="checkbox" name="is_visible_to_employee" value="true" defaultChecked /> Visible
          to the employee
        </label>
        <p className="form-note">
          Leave this unchecked for HR-internal files — the employee will not see or download them.
        </p>

        <label>File</label>
        <input name="file" type="file" required />
        <p className="form-note">PDF, image, Word, CSV or text. Max 10 MB.</p>

        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Uploading…' : 'Upload'}
        </button>
      </form>
    </Modal>
  )
}

function VerifyModal({ doc, onClose, onDone }) {
  const { run, pending, error } = useAction()

  async function verify(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const result = await run(() =>
      api.post(ENDPOINTS.hr.verifyDocument(doc.id), {
        expiry_date: form.get('expiry_date') || null,
        note: form.get('note') || null,
      }),
    )
    if (result) {
      onDone('Document verified')
      onClose()
    }
  }

  return (
    <Modal title={`Verify ${doc.title}`} onClose={onClose}>
      <form className="form-grid" onSubmit={verify}>
        <label>Expiry date</label>
        <input name="expiry_date" type="date" min={todayISO()} />
        <label>Note</label>
        <input name="note" placeholder="Optional" />
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Verifying…' : 'Verify'}
        </button>
      </form>
    </Modal>
  )
}

function RejectModal({ doc, onClose, onDone }) {
  const { run, pending, error } = useAction()

  async function reject(event) {
    event.preventDefault()
    const reason = new FormData(event.currentTarget).get('reason')
    const result = await run(() => api.post(ENDPOINTS.hr.rejectDocument(doc.id), { reason }))
    if (result) {
      onDone('Document rejected')
      onClose()
    }
  }

  return (
    <Modal title={`Reject ${doc.title}`} onClose={onClose}>
      <form className="form-grid" onSubmit={reject}>
        <label>Reason</label>
        <textarea name="reason" required minLength={3} rows={4} />
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Rejecting…' : 'Reject'}
        </button>
      </form>
    </Modal>
  )
}

function ChecklistModal({ employeeId, onClose }) {
  const state = useApi(() => api.get(ENDPOINTS.hr.documentChecklist(employeeId)), [employeeId])

  return (
    <Modal title="Document checklist" onClose={onClose}>
      <Async state={state}>
        {data => (
          <>
            <p className="form-note">
              Required verified: {data.required_verified}/{data.required_total}
            </p>
            <DataTable
              columns={['Document', 'Required', 'Status', 'Expiry']}
              rows={data.rows}
              renderRow={row => (
                <tr key={row.document_type}>
                  <td>{titleCase(row.document_type)}</td>
                  <td>{row.is_required ? 'Yes' : 'No'}</td>
                  <td><StatusChip status={row.missing ? 'PENDING' : row.status} /></td>
                  <td>{formatDate(row.expiry_date)}</td>
                </tr>
              )}
            />
          </>
        )}
      </Async>
    </Modal>
  )
}

export function DocumentsPage({ notify }) {
  const { can } = useSession()
  const canManage = can('document:manage')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [employeeId, setEmployeeId] = useState('')
  const [mode, setMode] = useState(canManage ? 'register' : 'mine')
  const [filters, setFilters] = useState({ status: '', document_type: '', page: 1 })
  const [verifyDoc, setVerifyDoc] = useState(null)
  const [rejectDoc, setRejectDoc] = useState(null)
  const [checklistEmployee, setChecklistEmployee] = useState(null)

  const employees = useApi(() => api.get(`${ENDPOINTS.employees.list}?page_size=200`), [], {
    skip: !canManage,
  })

  const state = useApi(
    () =>
      canManage && mode === 'register'
        ? api.get(`${ENDPOINTS.hr.documents}${query({ ...filters, employee_id: employeeId, page_size: 15 })}`)
        : canManage && employeeId
        ? api.get(ENDPOINTS.documents.forEmployee(employeeId))
        : api.get(ENDPOINTS.documents.mine),
    [canManage, mode, employeeId, filters.status, filters.document_type, filters.page],
  )
  const dashboard = useApi(() => api.get(ENDPOINTS.hr.documentsDashboard), [], {
    skip: !canManage,
  })

  const { run } = useAction(message => {
    notify(message)
    state.reload()
  })

  return (
    <section className="documents-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">DOCUMENTS</p>
          <h2>{canManage && employeeId ? 'Employee documents.' : 'Your documents.'}</h2>
        </div>
        {canManage && (
          <div className="actions">
            <button className="ghost-button" onClick={() => setMode(mode === 'register' ? 'mine' : 'register')}>
              {mode === 'register' ? 'My docs' : 'HR register'}
            </button>
            <select
              className="hero-select"
              value={employeeId}
              onChange={e => setEmployeeId(e.target.value)}
            >
              <option value="">My documents</option>
              {(employees.data?.items || []).map(e => (
                <option key={e.id} value={e.id}>{e.full_name}</option>
              ))}
            </select>
            <button className="primary-button" onClick={() => setUploadOpen(true)}>
              Upload
            </button>
          </div>
        )}
      </section>

      {canManage && mode === 'register' && (
        <>
          <Async state={dashboard}>
            {data => (
              <section className="stats-row">
                {[
                  ['Total', data.kpis.total],
                  ['Verified', data.kpis.verified],
                  ['Pending', data.kpis.pending],
                  ['Rejected', data.kpis.rejected],
                  ['Missing required', data.employees_with_missing_required],
                ].map(([label, value]) => (
                  <article key={label}><strong>{value}</strong><b>{label}</b></article>
                ))}
              </section>
            )}
          </Async>
          <section className="toolbar">
            <select
              value={filters.status}
              onChange={e => setFilters(current => ({ ...current, status: e.target.value, page: 1 }))}
            >
              <option value="">All statuses</option>
              {['PENDING', 'VERIFIED', 'REJECTED', 'EXPIRED'].map(s => (
                <option key={s} value={s}>{titleCase(s)}</option>
              ))}
            </select>
            <select
              value={filters.document_type}
              onChange={e => setFilters(current => ({ ...current, document_type: e.target.value, page: 1 }))}
            >
              <option value="">All document types</option>
              {DOC_TYPES.map(t => <option key={t} value={t}>{titleCase(t)}</option>)}
            </select>
          </section>
        </>
      )}

      <Async
        state={state}
        empty={rows => !rows || (Array.isArray(rows) ? rows.length === 0 : rows.items?.length === 0)}
        emptyTitle="No documents here yet."
        emptyHint={canManage ? 'Upload one to get started.' : 'Your HR team will add them here.'}
      >
        {data => {
          const rows = Array.isArray(data) ? data : data.items
          return (
          <DataTable
            columns={['Document', 'Employee', 'Type', 'Status', 'Size', 'Added', 'Visibility', '']}
            rows={rows}
            renderRow={row => (
              <tr key={row.id}>
                <td>
                  <b>{row.title}</b>
                  <br />
                  <small>{row.file_name}</small>
                </td>
                <td>{row.employee_name || '—'}</td>
                <td>{titleCase(row.document_type)}</td>
                <td><StatusChip status={row.status} /></td>
                <td>{bytes(row.size_bytes)}</td>
                <td>{formatDate(row.created_at)}</td>
                <td>{row.is_visible_to_employee ? 'Employee' : 'HR only'}</td>
                <td>
                  <button
                    className="table-action"
                    onClick={() => download(ENDPOINTS.documents.download(row.id), row.file_name)}
                  >
                    Download
                  </button>
                  {canManage && row.employee_id && (
                    <button className="table-action" onClick={() => setChecklistEmployee(row.employee_id)}>
                      Checklist
                    </button>
                  )}
                  {canManage && row.status !== 'VERIFIED' && (
                    <button className="table-action approve" onClick={() => setVerifyDoc(row)}>
                      Verify
                    </button>
                  )}
                  {canManage && row.status !== 'REJECTED' && (
                    <button className="table-action decline" onClick={() => setRejectDoc(row)}>
                      Reject
                    </button>
                  )}
                  {canManage && (
                    <button
                      className="table-action"
                      onClick={() => {
                        if (window.confirm(`Delete "${row.title}"?`))
                          run(() => api.del(ENDPOINTS.documents.byId(row.id)), 'Document deleted')
                      }}
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            )}
          />
        )}}
      </Async>

      {uploadOpen && (
        <UploadModal
          employees={employees.data?.items || []}
          onClose={() => setUploadOpen(false)}
          onDone={() => {
            notify('Document uploaded')
            state.reload()
          }}
        />
      )}
      {verifyDoc && (
        <VerifyModal
          doc={verifyDoc}
          onClose={() => setVerifyDoc(null)}
          onDone={message => {
            notify(message)
            state.reload()
            dashboard.reload()
          }}
        />
      )}
      {rejectDoc && (
        <RejectModal
          doc={rejectDoc}
          onClose={() => setRejectDoc(null)}
          onDone={message => {
            notify(message)
            state.reload()
            dashboard.reload()
          }}
        />
      )}
      {checklistEmployee && (
        <ChecklistModal employeeId={checklistEmployee} onClose={() => setChecklistEmployee(null)} />
      )}
    </section>
  )
}
