import { useState } from 'react'
import { ENDPOINTS, STATIC_BASE, api, getAccessToken } from '../api.js'
import { Async, useAction, useApi } from '../lib/ui.jsx'

/* ------------------------------------------------------------------ branding */

export function BrandingPanel({ notify }) {
  const state = useApi(() => api.get(ENDPOINTS.company.current), [])
  const [preview, setPreview] = useState(null)
  const { run, pending, error } = useAction(message => {
    notify(message)
    state.reload()
  })

  async function upload(file) {
    if (!file) return
    setPreview(URL.createObjectURL(file))
    const body = new FormData()
    body.append('file', file)
    await run(() => api.post(ENDPOINTS.company.logo, body), 'Logo updated')
    setPreview(null)
  }

  return (
    <article className="panel">
      <div className="panel-title">
        <h3>Company logo</h3>
      </div>
      <Async state={state}>
        {company => {
          const current = preview || company.logo_url
          return (
            <>
              <div className="logo-editor">
                <div className="logo-frame">
                  {current ? (
                    <img src={current} alt={`${company.name} logo`} />
                  ) : (
                    <span>{company.name?.[0] || '?'}</span>
                  )}
                </div>
                <div>
                  <p className="form-note">
                    Shown in the sidebar, on every payslip and on documents you generate.
                    PNG, JPEG, WEBP or SVG, up to 10 MB. A wide, transparent PNG works best.
                  </p>
                  <div className="actions">
                    <label className="table-action" style={{ cursor: 'pointer' }}>
                      {pending ? 'Uploading…' : company.logo_url ? 'Replace logo' : 'Upload logo'}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/webp,image/svg+xml"
                        hidden
                        onChange={e => upload(e.target.files?.[0])}
                      />
                    </label>
                    {company.logo_url && (
                      <button
                        className="table-action decline"
                        disabled={pending}
                        onClick={() => run(() => api.del(ENDPOINTS.company.logo), 'Logo removed')}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              </div>
              {error && <p className="form-error">{error}</p>}
            </>
          )
        }}
      </Async>
    </article>
  )
}

/* ------------------------------------------------------------------ attendance rules */

export function AttendanceRulesPanel({ notify }) {
  const company = useApi(() => api.get(ENDPOINTS.company.current), [])
  const locations = useApi(() => api.get(ENDPOINTS.organization.locations), [])
  const { run, pending, error } = useAction(message => {
    notify(message)
    company.reload()
    locations.reload()
  })
  const [locating, setLocating] = useState(null)

  /** Fills a location's coordinates from the browser, for the admin sitting in the office. */
  function useMyPosition(location) {
    if (!navigator.geolocation) return
    setLocating(location.id)
    navigator.geolocation.getCurrentPosition(
      pos => {
        setLocating(null)
        run(
          () =>
            api.patch(ENDPOINTS.organization.location(location.id), {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
            }),
          `${location.name} pinned to your current position`,
        )
      },
      () => {
        setLocating(null)
        notify('Could not read your location. Allow location access and try again.')
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  return (
    <>
      <article className="panel">
        <div className="panel-title">
          <h3>Attendance rules</h3>
        </div>
        <Async state={company}>
          {data => (
            <form
              className="form-grid"
              onSubmit={event => {
                event.preventDefault()
                const form = new FormData(event.currentTarget)
                run(
                  () =>
                    api.patch(ENDPOINTS.company.current, {
                      geofence_enabled: form.get('geofence_enabled') === 'on',
                      max_regularizations_per_month: Number(form.get('max_regularizations')),
                    }),
                  'Attendance rules saved',
                )
              }}
            >
              <label className="inline">
                <input
                  type="checkbox"
                  name="geofence_enabled"
                  defaultChecked={data.geofence_enabled}
                />{' '}
                Require employees to be on site to check in
              </label>
              <p className="form-note">
                When on, check-in and check-out are refused unless the employee is within
                their office's radius. Working from home is exempt. Offices without
                coordinates stay unrestricted, so set them below first.
              </p>

              <label>Regularizations allowed per employee per month</label>
              <input
                name="max_regularizations"
                type="number"
                min="0"
                max="31"
                defaultValue={data.max_regularizations_per_month}
                required
              />
              <p className="form-note">
                Once an employee has used this many attendance corrections in a calendar
                month, further corrections are refused. Re-editing a day that was already
                corrected does not consume another.
              </p>

              {error && <p className="form-error">{error}</p>}
              <button className="primary-button" disabled={pending}>
                {pending ? 'Saving…' : 'Save rules'}
              </button>
            </form>
          )}
        </Async>
      </article>

      <article className="panel">
        <div className="panel-title">
          <h3>Office locations &amp; radius</h3>
        </div>
        <Async state={locations}>
          {rows => (
            <div className="geo-list">
              {rows.map(location => (
                <div className="geo-row" key={location.id}>
                  <div>
                    <b>{location.name}</b>
                    <small>
                      {location.latitude != null
                        ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)} · ${location.geofence_radius_m} m`
                        : 'No coordinates — this office is not fenced'}
                    </small>
                  </div>
                  <form
                    className="geo-inputs"
                    onSubmit={event => {
                      event.preventDefault()
                      const form = new FormData(event.currentTarget)
                      run(
                        () =>
                          api.patch(ENDPOINTS.organization.location(location.id), {
                            latitude: form.get('lat') ? Number(form.get('lat')) : null,
                            longitude: form.get('lng') ? Number(form.get('lng')) : null,
                            geofence_radius_m: Number(form.get('radius')),
                          }),
                        `${location.name} updated`,
                      )
                    }}
                  >
                    <input
                      name="lat"
                      placeholder="Latitude"
                      defaultValue={location.latitude ?? ''}
                      step="any"
                      type="number"
                    />
                    <input
                      name="lng"
                      placeholder="Longitude"
                      defaultValue={location.longitude ?? ''}
                      step="any"
                      type="number"
                    />
                    <input
                      name="radius"
                      type="number"
                      min="10"
                      max="10000"
                      defaultValue={location.geofence_radius_m}
                      title="Radius in metres"
                    />
                    <button className="table-action" disabled={pending}>
                      Save
                    </button>
                    <button
                      type="button"
                      className="table-action"
                      disabled={pending || locating === location.id}
                      onClick={() => useMyPosition(location)}
                    >
                      {locating === location.id ? 'Locating…' : 'Use my position'}
                    </button>
                  </form>
                </div>
              ))}
            </div>
          )}
        </Async>
      </article>
    </>
  )
}

/* ------------------------------------------------------------------ compliance */

export function CompliancePanel({ notify }) {
  const state = useApi(() => api.get(ENDPOINTS.compliance.get), [])
  const status = useApi(() => api.get(ENDPOINTS.compliance.status), [])
  const { run, pending, error } = useAction(message => {
    notify(message)
    state.reload()
    status.reload()
  })

  return (
    <>
      <article className="panel">
        <div className="panel-title">
          <h3>Compliance readiness</h3>
        </div>
        <Async state={status}>
          {data => (
            <div className="check-list">
              {data.checks.map(check => (
                <div className={`check-row${check.ok ? ' ok' : ''}`} key={check.label}>
                  <span aria-hidden="true">{check.ok ? '✓' : '!'}</span>
                  <div>
                    <b>{check.label}</b>
                    <small>{check.detail}</small>
                  </div>
                </div>
              ))}
              <p className="form-note">
                {data.ready
                  ? 'All statutory details are on file.'
                  : 'Fill in the flagged items below — payroll runs without them, but filings will not.'}
              </p>
            </div>
          )}
        </Async>
      </article>

      <article className="panel">
        <div className="panel-title">
          <h3>Statutory details</h3>
        </div>
        <Async state={state}>
          {data => (
            <form
              className="form-grid"
              onSubmit={event => {
                event.preventDefault()
                const form = new FormData(event.currentTarget)
                const num = key => (form.get(key) === '' ? null : Number(form.get(key)))
                const text = key => form.get(key) || null
                run(
                  () =>
                    api.put(ENDPOINTS.compliance.update, {
                      pf_enabled: form.get('pf_enabled') === 'on',
                      pf_number: text('pf_number'),
                      pf_employee_rate: num('pf_employee_rate'),
                      pf_wage_ceiling: num('pf_wage_ceiling'),
                      esi_enabled: form.get('esi_enabled') === 'on',
                      esi_number: text('esi_number'),
                      esi_employee_rate: num('esi_employee_rate'),
                      esi_wage_ceiling: num('esi_wage_ceiling'),
                      pt_enabled: form.get('pt_enabled') === 'on',
                      pt_state: text('pt_state'),
                      pt_monthly_amount: num('pt_monthly_amount'),
                      tds_enabled: form.get('tds_enabled') === 'on',
                      tan: text('tan'),
                      pan: text('pan'),
                      gstin: text('gstin'),
                      cin: text('cin'),
                      labour_licence_number: text('labour_licence_number'),
                      max_weekly_hours: num('max_weekly_hours'),
                      min_break_minutes: num('min_break_minutes'),
                    }),
                  'Compliance details saved',
                )
              }}
            >
              <p className="form-note">
                Switching a deduction off here removes it from the next payroll run —
                existing payslips are never altered.
              </p>

              <label className="inline">
                <input type="checkbox" name="pf_enabled" defaultChecked={data.pf_enabled} />{' '}
                Provident Fund (PF)
              </label>
              <div className="two-up">
                <input name="pf_number" placeholder="PF establishment code" defaultValue={data.pf_number || ''} />
                <input name="pf_employee_rate" type="number" step="0.01" placeholder="Employee %" defaultValue={data.pf_employee_rate} />
              </div>
              <input name="pf_wage_ceiling" type="number" placeholder="Wage ceiling" defaultValue={data.pf_wage_ceiling} />

              <label className="inline">
                <input type="checkbox" name="esi_enabled" defaultChecked={data.esi_enabled} />{' '}
                Employee State Insurance (ESI)
              </label>
              <div className="two-up">
                <input name="esi_number" placeholder="ESI code" defaultValue={data.esi_number || ''} />
                <input name="esi_employee_rate" type="number" step="0.01" placeholder="Employee %" defaultValue={data.esi_employee_rate} />
              </div>
              <input name="esi_wage_ceiling" type="number" placeholder="Wage ceiling" defaultValue={data.esi_wage_ceiling} />

              <label className="inline">
                <input type="checkbox" name="pt_enabled" defaultChecked={data.pt_enabled} />{' '}
                Professional Tax (PT)
              </label>
              <div className="two-up">
                <input name="pt_state" placeholder="State" defaultValue={data.pt_state || ''} />
                <input name="pt_monthly_amount" type="number" placeholder="Monthly amount" defaultValue={data.pt_monthly_amount} />
              </div>

              <label className="inline">
                <input type="checkbox" name="tds_enabled" defaultChecked={data.tds_enabled} /> TDS
              </label>
              <input name="tan" placeholder="TAN" defaultValue={data.tan || ''} />

              <label>Company registration</label>
              <div className="two-up">
                <input name="pan" placeholder="PAN" defaultValue={data.pan || ''} />
                <input name="gstin" placeholder="GSTIN" defaultValue={data.gstin || ''} />
              </div>
              <div className="two-up">
                <input name="cin" placeholder="CIN" defaultValue={data.cin || ''} />
                <input
                  name="labour_licence_number"
                  placeholder="Labour licence no."
                  defaultValue={data.labour_licence_number || ''}
                />
              </div>

              <label>Working-hours limits</label>
              <div className="two-up">
                <input name="max_weekly_hours" type="number" step="0.5" placeholder="Max weekly hours" defaultValue={data.max_weekly_hours} />
                <input name="min_break_minutes" type="number" placeholder="Min break (minutes)" defaultValue={data.min_break_minutes} />
              </div>

              {error && <p className="form-error">{error}</p>}
              <button className="primary-button" disabled={pending}>
                {pending ? 'Saving…' : 'Save compliance details'}
              </button>
            </form>
          )}
        </Async>
      </article>
    </>
  )
}
