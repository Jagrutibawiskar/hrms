import { useEffect, useState } from 'react'
import { SessionProvider, landingRoute, useSession } from './session.jsx'
import { hasSession } from './api.js'

import { HomePage, ModulePage, PlatformPage } from './pages/marketing.jsx'
import { AuthPage, PasswordPage } from './pages/auth.jsx'
import { OnboardingPage } from './pages/onboarding.jsx'
import { DashboardPage } from './pages/workspace.jsx'

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/')
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash || '#/')
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash
}

const PUBLIC_ROUTES = ['#/', '#/login', '#/signup', '#/forgot-password', '#/reset-password', '#/platform']

function Routes() {
  const route = useHashRoute()
  const { me, loading } = useSession()
  const path = route.split('?')[0]

  // Signed-in users shouldn't sit on the login screen, and signed-out users
  // shouldn't reach the workspace.
  useEffect(() => {
    if (loading) return
    const isAuthRoute = ['#/login', '#/signup'].includes(path)
    if (me && isAuthRoute) {
      window.location.hash = landingRoute(me)
      return
    }
    const isProtected = path.startsWith('#/dashboard') || path.startsWith('#/onboarding')
    if (!me && isProtected && !hasSession()) window.location.hash = '#/login'
  }, [me, loading, path])

  if (loading) {
    return (
      <main className="auth-page">
        <div className="auth-form-panel">
          <p className="eyebrow">Loading your workspace…</p>
        </div>
      </main>
    )
  }

  if (path === '#/login') return <AuthPage mode="login" />
  if (path === '#/signup') return <AuthPage mode="signup" />
  if (path === '#/forgot-password') return <PasswordPage />
  if (path === '#/reset-password') return <PasswordPage reset />
  if (path.startsWith('#/onboarding')) return <OnboardingPage />
  if (path.startsWith('#/dashboard')) return <DashboardPage />
  if (path === '#/platform') return <PlatformPage />

  if (path.startsWith('#/module/')) {
    return <ModulePage page={decodeURIComponent(path.replace('#/module/', ''))} action={() => {}} />
  }

  if (!PUBLIC_ROUTES.includes(path) && path !== '#/') {
    return (
      <main className="inner-page">
        <section className="inner-hero">
          <p className="eyebrow">NOT FOUND</p>
          <h1>That page doesn’t exist.</h1>
          <a className="primary-button" href="#/">
            Back to home
          </a>
        </section>
      </main>
    )
  }

  return <HomePage />
}

export function App() {
  return (
    <SessionProvider>
      <Routes />
    </SessionProvider>
  )
}

export default App
