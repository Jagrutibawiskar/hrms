import { useState } from 'react'
import { ENDPOINTS, api, download } from '../api.js'
import { useSession } from '../session.jsx'
import {
  Async,
  DataTable,
  Modal,
  formatDate,
  titleCase,
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

export function DocumentsPage({ notify }) {
  const { can } = useSession()
  const canManage = can('document:manage')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [employeeId, setEmployeeId] = useState('')

  const employees = useApi(() => api.get(`${ENDPOINTS.employees.list}?page_size=200`), [], {
    skip: !canManage,
  })

  const state = useApi(
    () =>
      canManage && employeeId
        ? api.get(ENDPOINTS.documents.forEmployee(employeeId))
        : api.get(ENDPOINTS.documents.mine),
    [canManage, employeeId],
  )

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

      <Async
        state={state}
        empty={rows => !rows || rows.length === 0}
        emptyTitle="No documents here yet."
        emptyHint={canManage ? 'Upload one to get started.' : 'Your HR team will add them here.'}
      >
        {rows => (
          <DataTable
            columns={['Document', 'Type', 'Size', 'Added', 'Visibility', '']}
            rows={rows}
            renderRow={row => (
              <tr key={row.id}>
                <td>
                  <b>{row.title}</b>
                  <br />
                  <small>{row.file_name}</small>
                </td>
                <td>{titleCase(row.document_type)}</td>
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
        )}
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
    </section>
  )
}
