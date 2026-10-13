import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function AuthPage({ mode }) {
  const isRegister = mode === 'register'
  const { user, loading, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (loading) return <div className="min-h-screen flex items-center justify-center text-sm text-ink-muted bg-base">Loading LeetTrack…</div>
  if (user) return <Navigate to="/" replace />

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (isRegister) await signUp({ username: username.trim(), email: email.trim(), password })
      else await signIn({ email: email.trim(), password })
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Unable to authenticate. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const inputClass = 'w-full px-3.5 py-3 rounded-lg bg-base-card border border-base-border text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-accent'
  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-4 py-10">
      <div className="w-full max-w-md rounded-2xl border border-base-border bg-base-raised p-7 shadow-card">
        <div className="flex items-center gap-2 mb-7">
          <span className="w-8 h-8 rounded-md bg-accent flex items-center justify-center text-white font-mono font-bold">{'{}'}</span>
          <span className="text-ink font-semibold text-lg">LeetTrack</span>
        </div>
        <h1 className="text-2xl font-semibold text-ink">{isRegister ? 'Create your account' : 'Welcome back'}</h1>
        <p className="text-sm text-ink-muted mt-2 mb-6">{isRegister ? 'Start tracking your DSA progress and revisions.' : 'Log in to continue your revision plan.'}</p>
        <form onSubmit={submit} className="space-y-4">
          {isRegister && <label className="block text-sm text-ink-muted">Username
            <input className={`${inputClass} mt-1.5`} value={username} onChange={e => setUsername(e.target.value)} minLength={3} maxLength={40} autoComplete="username" required />
          </label>}
          <label className="block text-sm text-ink-muted">Email
            <input className={`${inputClass} mt-1.5`} type="email" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" maxLength={254} required />
          </label>
          <label className="block text-sm text-ink-muted">Password
            <input className={`${inputClass} mt-1.5`} type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete={isRegister ? 'new-password' : 'current-password'} minLength={isRegister ? 12 : 1} maxLength={128} required />
            {isRegister && <span className="block text-xs text-ink-faint mt-1">Use at least 12 characters.</span>}
          </label>
          {error && <div role="alert" className="rounded-lg border border-hard/30 bg-hard-bg p-3 text-sm text-hard">{error}</div>}
          <button disabled={busy} className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-60">
            {busy ? 'Please wait…' : isRegister ? 'Create account' : 'Log in'}
          </button>
        </form>
        <p className="text-sm text-ink-muted mt-6 text-center">
          {isRegister ? 'Already have an account? ' : 'New to LeetTrack? '}
          <Link className="text-accent hover:underline" to={isRegister ? '/login' : '/register'}>{isRegister ? 'Log in' : 'Create an account'}</Link>
        </p>
      </div>
    </div>
  )
}
