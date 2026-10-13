import { useCallback, useEffect, useState } from 'react'
import Navbar from '../components/Navbar'
import StatCard from '../components/StatCard'
import LoadingSpinner from '../components/LoadingSpinner'
import * as api from '../api/api'

export default function Profile() {
  const [user, setUser] = useState(null)
  const [progress, setProgress] = useState(null)
  const [solved, setSolved] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [userData, progressData, solvedData] = await Promise.all([
        api.getUser(),
        api.getProgress(),
        api.getSolvedQuestions(),
      ])
      setUser(userData)
      setProgress(progressData)
      setSolved(solvedData)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const platforms = [...new Set(solved.map((s) => s.platform))]

  return (
    <>
      <Navbar title="Profile" subtitle="Your account and progress summary" />
      <div className="px-8 py-6 max-w-3xl">
        {error && (
          <div className="rounded-card border border-hard/30 bg-hard-bg p-4 mb-6 text-sm text-hard">
            Unable to load profile. ({error})
          </div>
        )}

        {loading && !error && <LoadingSpinner label="Loading profile…" />}

        {user && progress && !error && (
          <>
            <div className="rounded-card border border-base-border bg-base-card p-6 shadow-card mb-6 flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-accent-muted text-accent flex items-center justify-center font-mono font-semibold text-lg">
                {user.username?.slice(0, 2).toUpperCase()}
              </div>
              <div>
                <h2 className="text-lg font-semibold text-ink">{user.username}</h2>
                <p className="text-sm text-ink-muted">User ID {user.user_id}</p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <StatCard label="Total solved" value={progress.total_solved} />
              <StatCard label="Revisions completed" value={progress.revisions_completed} accentClass="text-accent" />
              <StatCard label="Platforms used" value={platforms.length || '—'} />
            </div>

            <div className="rounded-card border border-base-border bg-base-card p-5 shadow-card">
              <h3 className="text-sm font-medium text-ink mb-3">Platforms</h3>
              {platforms.length === 0 ? (
                <p className="text-sm text-ink-faint">No solved questions yet.</p>
              ) : (
                <div className="flex gap-2 flex-wrap">
                  {platforms.map((p) => (
                    <span
                      key={p}
                      className="text-xs px-2.5 py-1 rounded-full border border-base-border text-ink-muted capitalize"
                    >
                      {p}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </>
  )
}
