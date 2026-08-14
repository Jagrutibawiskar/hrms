const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

// Single source of truth for the backend contract in FRONTEND_GUIDE.md.
// Browser pages use #/ routes; every server call must use one of these API paths.
export const ENDPOINTS = {
  auth: { signup: '/auth/signup', login: '/auth/login', refresh: '/auth/refresh', me: '/auth/me', forgotPassword: '/auth/forgot-password', resetPassword: '/auth/reset-password', changePassword: '/auth/change-password' },
  dashboard: { hr: '/dashboard/hr', me: '/dashboard/me' },
  onboarding: { status: '/onboarding/status', organization: '/onboarding/organization', workPolicy: '/onboarding/work-policy', leavePolicy: '/onboarding/leave-policy', admin: '/onboarding/admin', employees: '/onboarding/employees', importEmployees: '/onboarding/employees/import', skipEmployees: '/onboarding/skip-employees' },
  company: { create: '/companies', current: '/companies/current' },
  employees: { list: '/employees', me: '/employees/me', byId: id => `/employees/${id}`, csvTemplate: '/employees/csv-template' },
  attendance: { today: '/attendance/today', mine: '/attendance/me', mySummary: '/attendance/me/summary', list: '/attendance', checkIn: '/attendance/check-in', checkOut: '/attendance/check-out', reports: '/reports/attendance' },
  leave: { mine: '/leaves/me', balances: '/leaves/balances', requests: '/leaves/requests', pending: '/leaves/requests/pending', apply: '/leaves', withAttachment: '/leaves/with-attachment' },
  notifications: { list: '/notifications', count: '/notifications/count', markRead: '/notifications/read' },
  payroll: { runs: '/payroll/runs', payslips: '/payroll/payslips/me' },
  documents: { mine: '/documents/me' },
  holidays: { list: '/holidays' },
  reports: { employees: '/reports/employees', attendance: '/reports/attendance', leaves: '/reports/leaves', payroll: '/reports/payroll', headcount: '/reports/headcount' },
  organization: { departments: '/organization/departments', designations: '/organization/designations', locations: '/organization/locations', leaveTypes: '/organization/leave-types', workPolicies: '/organization/work-policies' },
}

let accessToken = null

export function setAccessToken(token) { accessToken = token || null }
export function clearSession() { accessToken = null; sessionStorage.removeItem('luma_refresh_token') }
export function can(me, permission) { return Boolean(me?.permissions?.includes(permission)) }

async function request(path, options = {}, retry = true) {
  const headers = new Headers(options.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  let response
  try { response = await fetch(`${API_BASE}${path}`, { ...options, headers }) }
  catch { throw new Error('Cannot reach the HRMS backend. Start it at http://127.0.0.1:8000.') }
  if (response.status === 401 && retry && sessionStorage.getItem('luma_refresh_token')) {
    await refresh(); return request(path, options, false)
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) { const error = new Error(data.detail || 'Something went wrong.'); error.fields = data.errors || []; throw error }
  return data
}

export async function refresh() {
  const refresh_token = sessionStorage.getItem('luma_refresh_token')
  const data = await request(ENDPOINTS.auth.refresh, { method: 'POST', body: JSON.stringify({ refresh_token }) }, false)
  setAccessToken(data.access_token); sessionStorage.setItem('luma_refresh_token', data.refresh_token); return data
}

export async function authenticate(path, payload) {
  const data = await request(path, { method: 'POST', body: JSON.stringify(payload) }, false)
  setAccessToken(data.tokens.access_token); sessionStorage.setItem('luma_refresh_token', data.tokens.refresh_token)
  return request(ENDPOINTS.auth.me)
}

export const api = { get: path => request(path), post: (path, body) => request(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body) }), patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }) }
