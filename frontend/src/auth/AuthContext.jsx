import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import * as api from '../api/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const onUnauthorized = () => setUser(null)
    window.addEventListener('leettrack:unauthorized', onUnauthorized)
    api.getSession()
      .then((sessionUser) => { if (active) setUser(sessionUser) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => {
      active = false
      window.removeEventListener('leettrack:unauthorized', onUnauthorized)
    }
  }, [])

  async function signIn(credentials) {
    const sessionUser = await api.login(credentials)
    setUser(sessionUser)
  }
  async function signUp(details) {
    const sessionUser = await api.register(details)
    setUser(sessionUser)
  }
  async function signOut() {
    try { await api.logout() } finally { setUser(null) }
  }

  const value = useMemo(() => ({ user, loading, signIn, signUp, signOut }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
