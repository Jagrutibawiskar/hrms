import { useState } from 'react'
import { ENDPOINTS, api, authenticate } from '../api.js'
import { landingRoute, useSession } from '../session.jsx'

function BrandPanel({ eyebrow, title, blurb }) {
  return (
    <div className="auth-brand-panel">
      <a className="brand auth-brand" href="#/">
        <span className="brand-mark">
          <i />
          <i />
          <i />
        </span>
        <span>
          Luma<span>HR</span>
        </span>
      </a>
      <div className="auth-message">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {blurb && <p>{blurb}</p>}
      </div>
    </div>
  )
}

export function AuthPage({ mode }) {
  const isSignup = mode === 'signup'
  const { setMe } = useSession()
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState([])
  const [loading, setLoading] = useState(false)
  const [values, setValues] = useState({
    fullName: '',
    email: '',
    password: '',
  })

  function setField(name, value) {
    setValues(current => ({ ...current, [name]: value }))
  }

  async function finishAuth(path, payload) {
    const me = await authenticate(path, payload)
    setMe(me)
    window.location.hash = landingRoute(me)
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    setFieldErrors([])
    setLoading(true)
    // The backend takes first_name / last_name, not a single full_name field.
    const fullName = values.fullName.trim()
    const [firstName, ...rest] = fullName.split(/\s+/)

    const payload = isSignup
      ? {
          email: values.email,
          password: values.password,
          first_name: firstName || 'There',
          last_name: rest.join(' ') || null,
        }
      : { email: values.email, password: values.password }

    try {
      await finishAuth(isSignup ? ENDPOINTS.auth.signup : ENDPOINTS.auth.login, payload)
    } catch (err) {
      setError(err.message)
      setFieldErrors(err.fields || [])
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <BrandPanel
        eyebrow={isSignup ? 'Start your people-first chapter' : 'Welcome back'}
        title={isSignup ? 'Good work starts with a better workday.' : 'Your team is doing great things.'}
        blurb={
          isSignup
            ? 'Bring your people, time and growth into one beautifully connected place.'
            : 'Sign in to pick up where your people work left off.'
        }
      />
      <div className="auth-form-panel">
        <a className="back-home" href="#/">
          ← Back to website
        </a>
        <section className="auth-card">
          <p className="eyebrow">{isSignup ? 'Create your workspace' : 'Sign in to LumaHR'}</p>
          <h2>{isSignup ? 'Let’s get started.' : 'Good to see you.'}</h2>
          <p className="auth-subtitle">
            {isSignup ? 'You’ll set up your company in the next step.' : 'New to LumaHR?'}{' '}
            {!isSignup && <a href="#/signup">Create an account</a>}
          </p>

          <form className="auth-form" onSubmit={submit}>
            {isSignup && (
              <>
                <label>Full name</label>
                <input
                  name="full-name"
                  required
                  placeholder="Your full name"
                  autoComplete="name"
                  value={values.fullName}
                  onChange={event => setField('fullName', event.target.value)}
                />
              </>
            )}
            <label>Work email</label>
            <input
              name="email"
              required
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              value={values.email}
              onChange={event => setField('email', event.target.value)}
            />
            <label>Password</label>
            <div className="password-field">
              <input
                name="password"
                required
                minLength="8"
                type={showPassword ? 'text' : 'password'}
                placeholder="At least 8 characters"
                autoComplete={isSignup ? 'new-password' : 'current-password'}
                value={values.password}
                onChange={event => setField('password', event.target.value)}
              />
              <button type="button" onClick={() => setShowPassword(!showPassword)}>
                {showPassword ? 'Hide' : 'Show'}
              </button>
            </div>

            {!isSignup && (
              <a className="forgot-link" href="#/forgot-password">
                Forgot password?
              </a>
            )}

            {error && <p className="form-error">{error}</p>}
            {fieldErrors.map(item => (
              <p className="form-error" key={item.field}>
                {item.field}: {item.message}
              </p>
            ))}

            <button className="primary-button auth-submit" disabled={loading}>
              {loading ? 'Please wait…' : isSignup ? 'Create your account' : 'Sign in to LumaHR'}
            </button>
          </form>

          {isSignup && (
            <p className="switch-auth">
              Already have an account? <a href="#/login">Log in</a>
            </p>
          )}
        </section>
      </div>
    </main>
  )
}

export function PasswordPage({ reset = false }) {
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setMessage('')
    const form = new FormData(event.currentTarget)
    try {
      if (reset) {
        await api.post(ENDPOINTS.auth.resetPassword, {
          token: form.get('token'),
          new_password: form.get('password'),
        })
        setMessage('Your password has been reset. You can sign in now.')
      } else {
        const response = await api.post(ENDPOINTS.auth.forgotPassword, {
          email: form.get('email'),
        })
        setMessage(response.message)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <BrandPanel
        eyebrow="Account security"
        title={reset ? 'Choose a new password.' : 'We’ll help you get back in.'}
      />
      <div className="auth-form-panel">
        <a className="back-home" href="#/login">
          ← Back to login
        </a>
        <section className="auth-card">
          <p className="eyebrow">{reset ? 'Reset password' : 'Forgot password'}</p>
          <h2>{reset ? 'Set a new password.' : 'Check your inbox.'}</h2>
          <p className="auth-subtitle">
            {reset
              ? 'Use the reset token from your email to continue.'
              : 'Enter your work email and we’ll send a reset link.'}
          </p>

          <form className="auth-form" onSubmit={submit}>
            {reset ? (
              <>
                <label>Reset token</label>
                <input name="token" required placeholder="Paste token from email" />
                <label>New password</label>
                <input
                  name="password"
                  type="password"
                  minLength="8"
                  required
                  placeholder="At least 8 characters"
                />
              </>
            ) : (
              <>
                <label>Work email</label>
                <input name="email" type="email" required placeholder="you@company.com" />
              </>
            )}
            {error && <p className="form-error">{error}</p>}
            {message && <p className="form-success">{message}</p>}
            <button className="primary-button auth-submit" disabled={loading}>
              {loading ? 'Please wait…' : reset ? 'Reset password' : 'Send reset link'}
            </button>
          </form>

          <p className="switch-auth">
            {!reset && <a href="#/reset-password">Have a token already?</a>}
            {' · '}
            <a href="#/login">Back to log in</a>
          </p>
        </section>
      </div>
    </main>
  )
}
