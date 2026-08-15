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

function HolidayModal({ locations, holiday, onClose, onDone }) {
  const { run, pending, error } = useAction()
  const editing = Boolean(holiday)

  async function submit(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const payload = {
      name: form.get('name'),
      date: form.get('date'),
      holiday_type: form.get('holiday_type'),
      location_id: form.get('location_id') ? Number(form.get('location_id')) : null,
      description: form.get('description') || null,
    }
    const result = await run(() =>
      editing ? api.patch(ENDPOINTS.holidays.byId(holiday.id), payload) : api.post(ENDPOINTS.holidays.list, payload),
    )
    if (result) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal title={editing ? 'Edit holiday' : 'Add a holiday'} onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <label>Name</label>
        <input name="name" required placeholder="e.g. Diwali" defaultValue={holiday?.name || ''} />
        <label>Date</label>
        <input name="date" type="date" required defaultValue={holiday?.date || todayISO()} />
        <label>Type</label>
        <select name="holiday_type" defaultValue={holiday?.holiday_type || 'PUBLIC'}>
          {TYPES.map(t => (
            <option key={t} value={t}>{titleCase(t)}</option>
          ))}
        </select>
        <label>Location</label>
        <select name="location_id" defaultValue={holiday?.location_id || ''}>
          <option value="">All locations</option>
          {(locations || []).map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
        <label>Description</label>
        <input name="description" placeholder="Optional note" defaultValue={holiday?.description || ''} />
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Saving…' : editing ? 'Save holiday' : 'Add holiday'}
        </button>
      </form>
    </Modal>
  )
}

function BulkHolidayModal({ onClose, onDone }) {
  const [text, setText] = useState('')
  const { run, pending, error } = useAction()

  async function submit(event) {
    event.preventDefault()
    const rows = text
      .split(/\r?\n/)
      .map(line => line.trim())
      .filter(Boolean)
      .map(line => {
        const [date, name, holiday_type = 'PUBLIC', description = ''] = line.split(',').map(part => part.trim())
        return { date, name, holiday_type, description: description || null }
      })
    const result = await run(() => api.post(ENDPOINTS.holidays.bulk, rows))
    if (result) {
      onDone()
      onClose()
    }
  }

  return (
    <Modal title="Bulk add holidays" onClose={onClose}>
      <form className="form-grid" onSubmit={submit}>
        <p className="form-note">One holiday per line: YYYY-MM-DD, Name, Type, Description</p>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          rows={8}
          placeholder="2026-10-20, Diwali, PUBLIC, Festival holiday"
          required
        />
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" disabled={pending}>
          {pending ? 'Adding…' : 'Add holidays'}
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
  const [editHoliday, setEditHoliday] = useState(null)
  const [bulkOpen, setBulkOpen] = useState(false)

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
            <>
              <button className="ghost-button" onClick={() => setBulkOpen(true)}>
                Bulk add
              </button>
              <button className="primary-button" onClick={() => setAddOpen(true)}>
                Add holiday
              </button>
            </>
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
                    <button className="table-action" onClick={() => setEditHoliday(row)}>
                      Edit
                    </button>
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
        <HolidayModal
          locations={locations.data}
          onClose={() => setAddOpen(false)}
          onDone={() => {
            notify('Holiday added')
            state.reload()
          }}
        />
      )}
      {editHoliday && (
        <HolidayModal
          holiday={editHoliday}
          locations={locations.data}
          onClose={() => setEditHoliday(null)}
          onDone={() => {
            notify('Holiday updated')
            state.reload()
          }}
        />
      )}
      {bulkOpen && (
        <BulkHolidayModal
          onClose={() => setBulkOpen(false)}
          onDone={() => {
            notify('Holidays added')
            state.reload()
          }}
        />
      )}
    </section>
  )
}
