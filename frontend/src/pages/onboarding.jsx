import { useEffect, useState } from 'react'
import { ENDPOINTS, api, reissueToken } from '../api.js'
import { useSession } from '../session.jsx'
import { todayISO } from '../lib/ui.jsx'

const STEPS = [
  { slug: 'company', label: 'Company' },
  { slug: 'organization', label: 'Organization' },
  { slug: 'work-policy', label: 'Work policy' },
  { slug: 'leave-policy', label: 'Leave policy' },
  { slug: 'admin', label: 'Admin profile' },
  { slug: 'employees', label: 'Employees' },
]

const SIZES = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+']
const WEEKDAYS = [
  [1, 'Mon'], [2, 'Tue'], [3, 'Wed'], [4, 'Thu'], [5, 'Fri'], [6, 'Sat'], [7, 'Sun'],
]

/** Repeating name inputs for step 2 — departments, designations, locations. */
function NameList({ label, items, setItems, placeholder }) {
  return (
    <div className="onboard-list">
      <label>{label}</label>
      {items.map((value, index) => (
        <div className="password-field" key={index}>
          <input
            value={value}
            placeholder={placeholder}
            onChange={event => {
              const next = [...items]
              next[index] = event.target.value
              setItems(next)
            }}
          />
          {items.length > 1 && (
            <button
              type="button"
              onClick={() => setItems(items.filter((_, i) => i !== index))}
              aria-label={`Remove ${label}`}
            >
              Remove
            </button>
          )}
        </div>
      ))}
      <button type="button" className="text-action" onClick={() => setItems([...items, ''])}>
        + Add another
      </button>
    </div>
  )
}

/** Inline logo picker used in the last onboarding step. */
function LogoUpload({ notify }) {
  const [logo, setLogo] = useState(null)
  const [busy, setBusy] = useState(false)

  async function upload(file) {
    if (!file) return
    setBusy(true)
    try {
      const body = new FormData()
      body.append('file', file)
      const company = await api.post(ENDPOINTS.company.logo, body)
      setLogo(company.logo_url)
    } catch (err) {
      notify(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="logo-editor">
      <div className="logo-frame">
        {logo ? <img src={logo} alt="Company logo" /> : <span>Logo</span>}
      </div>
      <label className="table-action" style={{ cursor: 'pointer' }}>
        {busy ? 'Uploading…' : logo ? 'Replace' : 'Choose an image'}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/svg+xml"
          hidden
          onChange={e => upload(e.target.files?.[0])}
        />
      </label>
    </div>
  )
}

export function OnboardingPage() {
  const { me, reload, setMe } = useSession()

  const slugFromHash = window.location.hash.split('/').pop()
  const initial = Math.max(0, STEPS.findIndex(s => s.slug === slugFromHash))
  const [step, setStep] = useState(initial === -1 ? 0 : initial)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const [departments, setDepartments] = useState(['Engineering'])
  const [designations, setDesignations] = useState(['Software Engineer'])
  const [locations, setLocations] = useState(['Head Office'])
  const [workingDays, setWorkingDays] = useState([1, 2, 3, 4, 5])

  // Someone who already has a company must not be able to re-run step 1.
  useEffect(() => {
    if (me?.company_id && step === 0) setStep(1)
  }, [me?.company_id, step])

  function goTo(next) {
    setStep(next)
    window.location.hash = `#/onboarding/${STEPS[next].slug}`
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    const form = new FormData(event.currentTarget)
    const value = key => {
      const raw = form.get(key)
      return raw === null ? undefined : String(raw).trim()
    }

    try {
      if (step === 0) {
        await api.post(ENDPOINTS.company.create, {
          name: value('name'),
          industry: value('industry'),
          company_size: value('size'),
          company_type: value('company_type') || null,
          email: value('email'),
          phone: value('phone'),
          website: value('website') || null,
          country: value('country'),
          state: value('state'),
          city: value('city'),
          address: value('address'),
          postal_code: value('postal_code'),
          timezone: 'Asia/Kolkata',
          currency: 'INR',
          fiscal_year_start_month: 4,
        })
        // The current token still says company_id: null — swap it for one that knows.
        const refreshed = await reissueToken()
        setMe(refreshed)
      } else if (step === 1) {
        const clean = list => list.map(s => s.trim()).filter(Boolean)
        await api.post(ENDPOINTS.onboarding.organization, {
          departments: clean(departments).map(name => ({ name })),
          designations: clean(designations).map(name => ({ name })),
          locations: clean(locations).map(name => ({ name, city: value('city') || null })),
        })
      } else if (step === 2) {
        if (workingDays.length === 0) throw new Error('Pick at least one working day.')
        await api.post(ENDPOINTS.onboarding.workPolicy, {
          working_days: [...workingDays].sort((a, b) => a - b),
          start_time: `${value('start_time')}:00`,
          end_time: `${value('end_time')}:00`,
          break_start: value('break_start') ? `${value('break_start')}:00` : null,
          break_end: value('break_end') ? `${value('break_end')}:00` : null,
          full_day_hours: Number(value('full_day_hours')),
          half_day_hours: Number(value('half_day_hours')),
          late_grace_minutes: Number(value('late_grace_minutes')),
        })
      } else if (step === 3) {
        await api.post(ENDPOINTS.onboarding.leavePolicy, { leave_types: [] })
      } else if (step === 4) {
        await api.post(ENDPOINTS.onboarding.admin, {
          first_name: value('first_name'),
          last_name: value('last_name') || null,
          phone: value('phone'),
          designation_name: value('designation') || null,
          joining_date: value('joining_date') || todayISO(),
        })
      } else {
        await api.post(ENDPOINTS.onboarding.skipEmployees)
        await reload()
        window.location.hash = '#/dashboard'
        return
      }

      goTo(step + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const toggleDay = day =>
    setWorkingDays(current =>
      current.includes(day) ? current.filter(d => d !== day) : [...current, day],
    )

  return (
    <main className="onboarding">
      <section>
        <a className="brand" href="#/">
          <span className="brand-mark">
            <i />
            <i />
            <i />
          </span>
          <span>
            Luma<span>HR</span>
          </span>
        </a>
        <p className="eyebrow">SET UP YOUR WORKSPACE</p>
        <h1>{STEPS[step].label}</h1>
        <p>
          Step {step + 1} of {STEPS.length}. You can change any of this later in Settings.
        </p>
        <div className="onboard-progress">
          <span style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
        </div>

        <form className="form-grid" onSubmit={submit}>
          {step === 0 && (
            <>
              <input name="name" placeholder="Company name" required />
              <input name="industry" placeholder="Industry (e.g. Software)" required />
              <select name="size" defaultValue="11-50">
                {SIZES.map(size => (
                  <option key={size} value={size}>
                    {size} people
                  </option>
                ))}
              </select>
              <input name="company_type" placeholder="Company type (e.g. Private Limited)" />
              <input name="email" type="email" placeholder="Company email" required />
              <input name="phone" placeholder="Company phone" required minLength={6} />
              <input name="website" placeholder="Website (optional)" />
              <input name="country" placeholder="Country" defaultValue="India" required />
              <input name="state" placeholder="State" required />
              <input name="city" placeholder="City" required />
              <input name="address" placeholder="Registered address" required />
              <input name="postal_code" placeholder="Postal code" required />
            </>
          )}

          {step === 1 && (
            <>
              <NameList
                label="Departments"
                items={departments}
                setItems={setDepartments}
                placeholder="e.g. Engineering"
              />
              <NameList
                label="Designations"
                items={designations}
                setItems={setDesignations}
                placeholder="e.g. Software Engineer"
              />
              <NameList
                label="Office locations"
                items={locations}
                setItems={setLocations}
                placeholder="e.g. Bengaluru HQ"
              />
              <input name="city" placeholder="City for these locations" />
            </>
          )}

          {step === 2 && (
            <>
              <label>Working days</label>
              <div className="day-toggle">
                {WEEKDAYS.map(([day, name]) => (
                  <button
                    type="button"
                    key={day}
                    aria-pressed={workingDays.includes(day)}
                    onClick={() => toggleDay(day)}
                  >
                    {name}
                  </button>
                ))}
              </div>
              <label>Working hours</label>
              <div className="password-field">
                <input name="start_time" type="time" defaultValue="09:30" required />
                <input name="end_time" type="time" defaultValue="18:30" required />
              </div>
              <label>Break</label>
              <div className="password-field">
                <input name="break_start" type="time" defaultValue="13:00" />
                <input name="break_end" type="time" defaultValue="14:00" />
              </div>
              <label>Full day hours</label>
              <input name="full_day_hours" type="number" step="0.5" defaultValue="8" required />
              <label>Half day hours</label>
              <input name="half_day_hours" type="number" step="0.5" defaultValue="4" required />
              <label>Late grace (minutes)</label>
              <input name="late_grace_minutes" type="number" defaultValue="15" required />
              <p className="form-note">
                Weekly offs are derived from the days you leave unselected.
              </p>
            </>
          )}

          {step === 3 && (
            <p className="form-note">
              We’ve already created the four standard leave types: Casual Leave 12, Sick Leave 6,
              Earned Leave 15 (carry forward) and Unpaid Leave. You can change the allocations any
              time from Settings → Leave types.
            </p>
          )}

          {step === 4 && (
            <>
              <input
                name="first_name"
                placeholder="First name"
                defaultValue={me?.user?.first_name || ''}
                required
              />
              <input
                name="last_name"
                placeholder="Last name"
                defaultValue={me?.user?.last_name || ''}
              />
              <input name="phone" placeholder="Phone" required minLength={6} />
              <input name="designation" placeholder="Your designation (e.g. Founder)" />
              <input name="joining_date" type="date" defaultValue={todayISO()} />
              <p className="form-note">
                This also creates your own employee record, so you appear in the team directory.
              </p>
            </>
          )}

          {step === 5 && (
            <>
              <label>Company logo</label>
              <LogoUpload notify={setError} />
              <p className="form-note">
                Your logo appears in the sidebar, on every payslip and on documents you
                generate. You can add or change it later in Settings → Branding.
              </p>
              <p className="form-note">
                You’re all set. Finish now and add your team from the People page — one at a
                time or by importing a CSV.
              </p>
            </>
          )}

          {error && <p className="form-error">{error}</p>}

          <button className="primary-button" disabled={busy}>
            {busy ? 'Saving…' : step === STEPS.length - 1 ? 'Finish setup' : 'Continue'}
          </button>
        </form>
      </section>
    </main>
  )
}
