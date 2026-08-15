import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ENDPOINTS, api, can, clearSession, hasSession } from './api.js'

const SessionContext = createContext(null)

/**
 * `/auth/me` is the routing brain: it carries roles, permissions, company_id,
 * onboarding state and the linked employee id.
 */
export function SessionProvider({ children }) {
  const [me, setMe] = useState(null)
  const [loading, setLoading] = useState(hasSession())

  const load = useCallback(async () => {
    if (!hasSession()) {
      setMe(null)
      setLoading(false)
      return null
    }
    setLoading(true)
    try {
      const data = await api.get(ENDPOINTS.auth.me)
      setMe(data)
      return data
    } catch {
      clearSession()
      setMe(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const signOut = useCallback(async () => {
    try {
      await api.post(ENDPOINTS.auth.logout)
    } catch {
      // Stateless JWT — clearing the client tokens is what actually ends the session.
    }
    clearSession()
    setMe(null)
    window.location.hash = '#/login'
  }, [])

  const value = useMemo(
    () => ({
      me,
      setMe,
      loading,
      reload: load,
      signOut,
      can: (...permissions) => can(me, ...permissions),
      /** Highest-privilege workspace this user can open. Drives nav and dashboards. */
      workspace: !me
        ? 'employee'
        : can(me, 'dashboard:hr')
          ? 'hr'
          : can(me, 'leave:approve')
            ? 'manager'
            : 'employee',
    }),
    [me, loading, load, signOut],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession() {
  const context = useContext(SessionContext)
  if (!context) throw new Error('useSession must be used inside <SessionProvider>')
  return context
}

/** Where a signed-in user belongs, based on company + onboarding state. */
export function landingRoute(me) {
  if (!me) return '#/login'
  if (!me.company_id) return '#/onboarding/company'
  if (!me.is_onboarded) {
    const step = me.onboarding_step && me.onboarding_step !== 'completed' ? me.onboarding_step : 'organization'
    return `#/onboarding/${step.replace(/_/g, '-')}`
  }
  return '#/dashboard'
}
