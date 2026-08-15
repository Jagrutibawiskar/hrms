import { useCallback, useEffect, useState } from 'react'
import { ENDPOINTS, api, getViewingCompany, setViewingCompany } from '../api.js'
import { useSession } from '../session.jsx'
import { formatDate, initials, useApi } from '../lib/ui.jsx'

import { EmployeeHome, HrHome, ManagerHome } from './home.jsx'
import { PeoplePage } from './people.jsx'
import { AttendancePage } from './attendance.jsx'
import { LeavePage } from './leave.jsx'
import { HolidaysPage } from './holidays.jsx'
import { PayrollPage, PayslipsPage } from './payroll.jsx'
import { DocumentsPage } from './documents.jsx'
import { ReportsPage } from './reports.jsx'
import { SettingsPage } from './settings.jsx'
import { ProfilePage } from './profile.jsx'

/** Nav is derived from permissions, so each role sees only what it can actually use. */
function navFor(can) {
  const items = ['Home']
  if (can('employee:read_all', 'employee:read_team')) items.push('People')
  items.push('Attendance', 'Leave', 'Holidays')
  if (can('payroll:read_all')) items.push('Payroll')
  items.push('Payslips', 'Documents')
  if (can('report:view')) items.push('Reports')
  if (can('organization:manage')) items.push('Settings')
  items.push('My profile')
  return items
}

const WORKSPACE_LABEL = {
  hr: 'PEOPLE OPERATIONS',
  manager: 'MANAGER WORKSPACE',
  employee: 'EMPLOYEE WORKSPACE',
}

function NotificationBell({ onNavigate }) {
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const [items, setItems] = useState([])

  const loadCount = useCallback(async () => {
    try {
      const data = await api.get(ENDPOINTS.notifications.count)
      setCount(data.unread)
    } catch {
      // A failing badge must never break the page.
    }
  }, [])

  useEffect(() => {
    loadCount()
    // No websockets in MVP-1 — poll the badge.
    const timer = setInterval(loadCount, 60000)
    return () => clearInterval(timer)
  }, [loadCount])

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      try {
        const page = await api.get(`${ENDPOINTS.notifications.list}?page_size=8`)
        setItems(page.items)
      } catch {
        setItems([])
      }
    }
  }

  async function markAllRead() {
    await api.post(ENDPOINTS.notifications.markRead, {})
    setCount(0)
    setItems(current => current.map(item => ({ ...item, is_read: true })))
  }

  return (
    <div className="dash-tool">
      <button
        className="bell"
        data-unread={count > 0}
        onClick={toggle}
        aria-expanded={open}
        aria-label={`Notifications${count > 0 ? `, ${count} unread` : ''}`}
      >
        Notifications{count > 0 ? ` (${count})` : ''}
      </button>
      {open && (
        <div className="notif-panel">
          <p className="notif-head">
            Notifications
            {count > 0 && (
              <button className="text-action" onClick={markAllRead}>
                Mark all read
              </button>
            )}
          </p>
          {items.length === 0 ? (
            <p className="form-note">You’re all caught up.</p>
          ) : (
            items.map(item => (
              <div className={`notif-row${item.is_read ? '' : ' unread'}`} key={item.id}>
                <b>{item.title}</b>
                <p>{item.message}</p>
                <div className="notif-meta">
                  <time dateTime={item.created_at}>{formatDate(item.created_at)}</time>
                  {item.action_url && (
                    <button
                      className="notif-open"
                      onClick={() => {
                        const target = item.action_url.split('/')[1] || ''
                        const map = {
                          leaves: 'Leave',
                          employees: 'People',
                          documents: 'Documents',
                          payroll: 'Payroll',
                          payslips: 'Payslips',
                        }
                        if (map[target]) onNavigate(map[target])
                        setOpen(false)
                      }}
                    >
                      Open →
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Executive-only company picker. Choosing a company sets the X-Company-Id header
 * for every later request, so the whole app re-scopes to that tenant.
 */
function CompanySwitcher({ onSwitch }) {
  const companies = useApi(() => api.get(ENDPOINTS.company.list), [])
  const [selected, setSelected] = useState(getViewingCompany() || '')

  // Land on the first company automatically so the app is never in a blank state.
  useEffect(() => {
    if (!selected && companies.data?.length) {
      const first = String(companies.data[0].id)
      setSelected(first)
      setViewingCompany(first)
      onSwitch()
    }
  }, [companies.data, selected, onSwitch])

  if (!companies.data?.length) return null

  return (
    <div className="company-switcher">
      <label htmlFor="company-switch">Viewing</label>
      <select
        id="company-switch"
        value={selected}
        onChange={event => {
          setSelected(event.target.value)
          setViewingCompany(event.target.value)
          onSwitch()
        }}
      >
        {companies.data.map(company => (
          <option key={company.id} value={company.id}>
            {company.name}
          </option>
        ))}
      </select>
    </div>
  )
}

export function DashboardPage() {
  const session = useSession()
  const { me, can, workspace, signOut } = session
  const [activeNav, setActiveNav] = useState('Home')
  const [toast, setToast] = useState('')

  const notify = useCallback(message => {
    if (!message) return
    setToast(message)
    window.setTimeout(() => setToast(''), 2800)
  }, [])

  const company = useApi(() => api.get(ENDPOINTS.company.current), [])
  const navItems = navFor(can)

  useEffect(() => {
    if (!navItems.includes(activeNav)) setActiveNav('Home')
  }, [navItems, activeNav])

  const shared = { notify, onNavigate: setActiveNav, session }

  const content = (() => {
    switch (activeNav) {
      case 'Home':
        return workspace === 'hr' ? (
          <HrHome {...shared} />
        ) : workspace === 'manager' ? (
          <ManagerHome {...shared} />
        ) : (
          <EmployeeHome {...shared} />
        )
      case 'People':
        return <PeoplePage {...shared} />
      case 'Attendance':
        return <AttendancePage {...shared} />
      case 'Leave':
        return <LeavePage {...shared} />
      case 'Holidays':
        return <HolidaysPage {...shared} />
      case 'Payroll':
        return <PayrollPage {...shared} />
      case 'Payslips':
        return <PayslipsPage {...shared} />
      case 'Documents':
        return <DocumentsPage {...shared} />
      case 'Reports':
        return <ReportsPage {...shared} />
      case 'Settings':
        return <SettingsPage {...shared} />
      case 'My profile':
        return <ProfilePage {...shared} />
      default:
        return <HrHome {...shared} />
    }
  })()

  const displayName = me?.user
    ? [me.user.first_name, me.user.last_name].filter(Boolean).join(' ') || me.user.email
    : 'Loading…'
  const roleLabel = me?.roles?.[0]?.replace(/_/g, ' ').toLowerCase() || ''

  return (
    <main className="dashboard">
      <aside className="dash-sidebar">
        {/* The company's own logo replaces the product mark once uploaded. */}
        {company.data?.logo_url ? (
          <a className="brand dash-brand company-brand" href="#/">
            <img src={company.data.logo_url} alt={company.data.name} />
          </a>
        ) : (
          <a className="brand dash-brand" href="#/">
            <span className="brand-mark">
              <i />
              <i />
              <i />
            </span>
            <span>
              Luma<span>HR</span>
            </span>
          </a>
        )}
        <p className="dash-workspace">{WORKSPACE_LABEL[workspace]}</p>
        <nav aria-label="Workspace navigation">
          {navItems.map(item => (
            <button
              key={item}
              className={activeNav === item ? 'active' : ''}
              onClick={() => setActiveNav(item)}
            >
              {item}
            </button>
          ))}
        </nav>
        <div className="dash-help">
          <b>{company.data?.name || 'Your workspace'}</b>
          <p>
            {company.data
              ? `${company.data.city}, ${company.data.country}`
              : 'Loading company details…'}
          </p>
        </div>
        <button className="dash-user" onClick={signOut} title="Sign out">
          <span>{initials(displayName)}</span>
          <div>
            <b>{displayName}</b>
            <small>{roleLabel}</small>
          </div>
          <i>⏻</i>
        </button>
      </aside>

      <section className="dash-main">
        <header className="dash-top">
          <div>
            <p>{formatDate(new Date(), { weekday: 'long', day: 'numeric', month: 'long' })}</p>
            <h1>
              {activeNav === 'Home'
                ? `Good day, ${me?.user?.first_name || 'there'}.`
                : activeNav}
            </h1>
          </div>
          <div className="dashboard-header-tools">
            {me?.is_executive && (
              <CompanySwitcher
                onSwitch={() => {
                  // Everything on screen belongs to the old company — reload it all.
                  session.reload()
                  window.location.reload()
                }}
              />
            )}
            <NotificationBell onNavigate={setActiveNav} />
          </div>
        </header>
        {content}
      </section>

      {toast && (
        <div className="dash-toast" role="status">
          {toast}
        </div>
      )}
    </main>
  )
}
