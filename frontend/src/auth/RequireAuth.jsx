import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function RequireAuth() {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center text-sm text-ink-muted bg-base">Loading LeetTrack…</div>
  return user ? <Outlet /> : <Navigate to="/login" replace />
}
