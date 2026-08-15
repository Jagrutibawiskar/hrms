import { useState } from 'react'
import { ENDPOINTS, api, query } from '../api.js'
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

const TYPES = ['PUBLIC', 'OPTIONAL', 'RESTRICTED', 'COMPANY']

function AddHolidayModal({ locations, onClose, onDone }) {
  const { run, pending, error } = useAction()

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const result = await run(() =>
      api.post(ENDPOINTS.holidays.list, {
        name: form.get('name'),
        date: form.get('date'),
        holiday_type: form.get('holiday_type'),
        location_id: form.get('location_id') ? Number(form.get('location_id')) : null,
        description: form.get('description') || null,
      }),
    )
    if (result) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal title="Add a holiday" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label>Name</label>
        <input name="name" required placeholder="e.g. Diwali" />
        <label>Date</label>
        <input name="date" type="date" required defaultValue={todayISO()} />
        <label>Type</label>
        <select name="holiday_type" defaultValue="PUBLIC">
          {TYPES.map(t => (
            <option key={t} value={t}>{titleCase(t)}</option>
          ))}
        </select>
        <label>Location</label>
        <select name="location_id">
          <option value="">All locations</option>
          {(locations || []).map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
        <label>Description</label>
        <input name="description" placeholder="Optional note" />
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Saving…' : 'Add holiday'}
        </button>
      </form>
    </Modal>
  )
}

export function HolidaysPage({ notify }) {
  const { can } = useSession()
  const canManage = can('holiday:manage')
  const [year, setYear] = useState(new Date().getFullYear())
  const [addOpen, setAddOpen] = useState(false)

  const state = useApi(() => api.get(`${ENDPOINTS.holidays.list}${query({ year })}`), [year])
  const locations = useApi(() => api.get(ENDPOINTS.organization.locations), [], {
    skip: !canManage,
  })

  const { run } = useAction(message => {
    notify(message)
    state.reload()
  })

  const today = todayISO()

  return (
    <section className="holidays-page">
      <section className="page-hero">
        <div>
          <p className="eyebrow">CALENDAR</p>
          <h2>Holidays in {year}.</h2>
        </div>
        <div className="actions">
          <button className="ghost-button" onClick={() => setYear(year - 1)}>
            ← {year - 1}
          </button>
          <button className="ghost-button" onClick={() => setYear(year + 1)}>
            {year + 1} →
          </button>
          {canManage && (
            <button className="primary-button" onClick={() => setAddOpen(true)}>
              Add holiday
            </button>
          )}
        </div>
      </section>

      <Async
        state={state}
        empty={rows => !rows || rows.length === 0}
        emptyTitle={`No holidays declared for ${year}.`}
        emptyHint={canManage ? 'Add them so leave and payroll skip those days.' : undefined}
      >
        {rows => (
          <DataTable
            columns={['Holiday', 'Date', 'Type', 'Applies to', canManage ? '' : null].filter(
              c => c !== null,
            )}
            rows={rows}
            renderRow={row => (
              <tr key={row.id} className={row.date < today ? 'attendance-weekend' : ''}>
                <td>
                  <b>{row.name}</b>
                  {row.description && <small> · {row.description}</small>}
                </td>
                <td>
                  {formatDate(row.date, {
                    weekday: 'short',
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                  })}
                </td>
                <td><StatusChip status={row.holiday_type} /></td>
                <td>{row.location_id ? 'One location' : 'All locations'}</td>
                {canManage && (
                  <td>
                    <button
                      className="table-action"
                      onClick={() => {
                        if (window.confirm(`Remove ${row.name}?`))
                          run(() => api.del(ENDPOINTS.holidays.byId(row.id)), 'Holiday removed')
                      }}
                    >
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            )}
          />
        )}
      </Async>

      {addOpen && (
        <AddHolidayModal
          locations={locations.data}
          onClose={() => setAddOpen(false)}
          onDone={() => {
            notify('Holiday added')
            state.reload()
          }}
        />
      )}
    </section>
  )
}
