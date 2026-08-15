const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'

/** Public branding assets (company logos) are served outside the /api/v1 prefix. */
export const STATIC_BASE =
  import.meta.env.VITE_STATIC_BASE_URL || API_BASE.replace(/\/api\/v1\/?$/, '/static')

// Single source of truth for the backend contract (see backend/FRONTEND_GUIDE.md).
export const ENDPOINTS = {
  auth: {
    signup: '/auth/signup',
    login: '/auth/login',
    logout: '/auth/logout',
    refresh: '/auth/refresh',
    me: '/auth/me',
    verifyEmail: '/auth/verify-email',
    forgotPassword: '/auth/forgot-password',
    resetPassword: '/auth/reset-password',
    changePassword: '/auth/change-password',
  },
  company: {
    create: '/companies',
    list: '/companies',
    current: '/companies/current',
    logo: '/companies/current/logo',
  },
  compliance: { get: '/compliance', update: '/compliance', status: '/compliance/status' },
  onboarding: {
    status: '/onboarding/status',
    company: '/onboarding/company',
    organization: '/onboarding/organization',
    workPolicy: '/onboarding/work-policy',
    leavePolicy: '/onboarding/leave-policy',
    admin: '/onboarding/admin',
    employees: '/onboarding/employees',
    importEmployees: '/onboarding/employees/import',
    csvTemplate: '/onboarding/employees/csv-template',
    skipEmployees: '/onboarding/skip-employees',
    complete: '/onboarding/complete',
  },
  organization: {
    departments: '/organization/departments',
    designations: '/organization/designations',
    locations: '/organization/locations',
    leaveTypes: '/organization/leave-types',
    workPolicies: '/organization/work-policies',
    defaultWorkPolicy: '/organization/work-policies/default',
    department: id => `/organization/departments/${id}`,
    designation: id => `/organization/designations/${id}`,
    location: id => `/organization/locations/${id}`,
    leaveType: id => `/organization/leave-types/${id}`,
  },
  dashboard: { hr: '/dashboard/hr', me: '/dashboard/me' },
  employees: {
    list: '/employees',
    me: '/employees/me',
    byId: id => `/employees/${id}`,
    team: id => `/employees/${id}/team`,
    deactivate: id => `/employees/${id}/deactivate`,
    activate: id => `/employees/${id}/activate`,
    csvTemplate: '/employees/csv-template',
    import: '/employees/import',
  },
  hr: {
    employeeCodePreview: '/hr/employee-code/preview',
    draftEmployee: '/hr/employees/draft',
    personal: id => `/hr/employees/${id}/personal`,
    contact: id => `/hr/employees/${id}/contact`,
    employment: id => `/hr/employees/${id}/employment`,
    bank: id => `/hr/employees/${id}/bank`,
    statutory: id => `/hr/employees/${id}/statutory`,
    review: id => `/hr/employees/${id}/review`,
    complete: id => `/hr/employees/${id}/complete`,
    documentPolicy: '/hr/document-policy',
    documentChecklist: id => `/hr/employees/${id}/documents/checklist`,
    verifyDocument: id => `/hr/documents/${id}/verify`,
    rejectDocument: id => `/hr/documents/${id}/reject`,
    documents: '/hr/documents',
    documentsDashboard: '/hr/documents/dashboard',
    overview: '/hr/overview',
  },
  attendance: {
    today: '/attendance/today',
    mine: '/attendance/me',
    mySummary: '/attendance/me/summary',
    list: '/attendance',
    checkIn: '/attendance/check-in',
    checkOut: '/attendance/check-out',
    backfill: '/attendance/backfill',
    summaryFor: id => `/attendance/summary/${id}`,
    regularize: (id, day) => `/attendance/${id}/${day}`,
  },
  leave: {
    mine: '/leaves/me',
    balances: '/leaves/balances',
    balancesFor: id => `/leaves/balances/${id}`,
    adjustBalance: '/leaves/balances',
    requests: '/leaves/requests',
    pending: '/leaves/requests/pending',
    apply: '/leaves',
    withAttachment: '/leaves/with-attachment',
    approve: id => `/leaves/${id}/approve`,
    reject: id => `/leaves/${id}/reject`,
    cancel: id => `/leaves/${id}/cancel`,
    edit: id => `/leaves/${id}`,
  },
  holidays: {
    list: '/holidays',
    upcoming: '/holidays/upcoming',
    bulk: '/holidays/bulk',
    byId: id => `/holidays/${id}`,
  },
  payroll: {
    components: '/payroll/components',
    component: id => `/payroll/components/${id}`,
    structures: '/payroll/structures',
    preview: id => `/payroll/structures/${id}/preview`,
    salaries: id => `/payroll/salaries/${id}`,
    mySalary: '/payroll/salaries/me/current',
    runs: '/payroll/runs',
    run: id => `/payroll/runs/${id}`,
    approveRun: id => `/payroll/runs/${id}/approve`,
    runPayslips: id => `/payroll/runs/${id}/payslips`,
    markPaid: id => `/payroll/runs/${id}/mark-paid`,
    myPayslips: '/payroll/payslips/me',
    payslip: id => `/payroll/payslips/${id}`,
  },
  documents: {
    mine: '/documents/me',
    forEmployee: id => `/documents/employee/${id}`,
    upload: '/documents',
    download: id => `/documents/${id}/download`,
    byId: id => `/documents/${id}`,
  },
  notifications: {
    list: '/notifications',
    count: '/notifications/count',
    markRead: '/notifications/read',
    byId: id => `/notifications/${id}`,
  },
  reports: {
    employees: '/reports/employees',
    attendance: '/reports/attendance',
    leaves: '/reports/leaves',
    payroll: '/reports/payroll',
    headcount: '/reports/headcount',
  },
}

const REFRESH_KEY = 'luma_refresh_token'
const ACCESS_KEY = 'luma_access_token'

let accessToken = sessionStorage.getItem(ACCESS_KEY) || null

export function setAccessToken(token) {
  accessToken = token || null
  if (token) sessionStorage.setItem(ACCESS_KEY, token)
  else sessionStorage.removeItem(ACCESS_KEY)
}

export function getAccessToken() {
  return accessToken
}

export function setRefreshToken(token) {
  if (token) sessionStorage.setItem(REFRESH_KEY, token)
  else sessionStorage.removeItem(REFRESH_KEY)
}

export function clearSession() {
  setAccessToken(null)
  setRefreshToken(null)
  sessionStorage.removeItem('luma_viewing_company')
}

export function hasSession() {
  return Boolean(accessToken || sessionStorage.getItem(REFRESH_KEY))
}

const VIEWING_KEY = 'luma_viewing_company'

/**
 * The company an executive is currently looking at. Sent as X-Company-Id on every
 * request; the server ignores it for anyone who isn't an executive.
 */
export function getViewingCompany() {
  return sessionStorage.getItem(VIEWING_KEY) || null
}

export function setViewingCompany(companyId) {
  if (companyId) sessionStorage.setItem(VIEWING_KEY, String(companyId))
  else sessionStorage.removeItem(VIEWING_KEY)
}

/** Permission check — gate UI on these, never on role names. */
export function can(me, ...permissions) {
  return permissions.some(p => Boolean(me?.permissions?.includes(p)))
}

/** Build a query string, dropping empty values so filters stay optional. */
export function query(params = {}) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

export class ApiError extends Error {
  constructor(message, status, fields) {
    super(message)
    this.status = status
    this.fields = fields || []
  }
}

let refreshInFlight = null

async function request(path, options = {}, retry = true) {
  const headers = new Headers(options.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const viewing = getViewingCompany()
  if (viewing) headers.set('X-Company-Id', viewing)
  if (options.body && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  let response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  } catch {
    throw new ApiError('Cannot reach the HRMS backend. Start it at http://127.0.0.1:8000.', 0)
  }

  // Access tokens last 60 minutes — refresh once, then replay the request.
  if (response.status === 401 && retry && sessionStorage.getItem(REFRESH_KEY)) {
    try {
      refreshInFlight = refreshInFlight || refresh()
      await refreshInFlight
    } finally {
      refreshInFlight = null
    }
    return request(path, options, false)
  }

  if (response.status === 204) return null

  const isJson = (response.headers.get('content-type') || '').includes('application/json')
  const data = isJson ? await response.json().catch(() => ({})) : await response.text()

  if (!response.ok) {
    const detail = (isJson && data?.detail) || 'Something went wrong.'
    throw new ApiError(detail, response.status, isJson ? data?.errors : [])
  }
  return data
}

export async function refresh() {
  const refresh_token = sessionStorage.getItem(REFRESH_KEY)
  if (!refresh_token) throw new ApiError('Session expired. Please sign in again.', 401)
  const data = await request(
    ENDPOINTS.auth.refresh,
    { method: 'POST', body: JSON.stringify({ refresh_token }) },
    false,
  )
  setAccessToken(data.access_token)
  setRefreshToken(data.refresh_token)
  return data
}

/** Signup/login, store both tokens, then return the /auth/me payload. */
export async function authenticate(path, payload) {
  const data = await request(path, { method: 'POST', body: JSON.stringify(payload) }, false)
  setAccessToken(data.tokens.access_token)
  setRefreshToken(data.tokens.refresh_token)
  return request(ENDPOINTS.auth.me)
}

/**
 * Creating a company grants COMPANY_ADMIN and attaches the user to a tenant, but the
 * current token still says company_id: null. Refreshing swaps in a token that knows.
 */
export async function reissueToken() {
  await refresh()
  return request(ENDPOINTS.auth.me)
}

export async function download(path, fallbackName) {
  const headers = new Headers()
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const viewingCompany = getViewingCompany()
  if (viewingCompany) headers.set('X-Company-Id', viewingCompany)

  let response = await fetch(`${API_BASE}${path}`, { headers })
  if (response.status === 401 && sessionStorage.getItem(REFRESH_KEY)) {
    await refresh()
    headers.set('Authorization', `Bearer ${accessToken}`)
    response = await fetch(`${API_BASE}${path}`, { headers })
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new ApiError(data.detail || 'Download failed.', response.status)
  }

  const disposition = response.headers.get('content-disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = match ? match[1] : fallbackName || 'download'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/**
 * Asks the browser for the current position.
 * Resolves to null (never rejects) when the user declines or the device can't fix a
 * location — the server then decides whether the punch is still allowed.
 */
export function currentPosition({ timeout = 10000 } = {}) {
  return new Promise(resolve => {
    if (!navigator.geolocation) return resolve(null)
    navigator.geolocation.getCurrentPosition(
      pos => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout, maximumAge: 0 },
    )
  })
}

export const api = {
  get: path => request(path),
  post: (path, body) =>
    request(path, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
    }),
  patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body ?? {}) }),
  put: (path, body) => request(path, { method: 'PUT', body: JSON.stringify(body ?? {}) }),
  del: path => request(path, { method: 'DELETE' }),
}
