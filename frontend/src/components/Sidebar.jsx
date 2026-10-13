import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const LINKS = [
  { to: '/', label: 'Dashboard', icon: GridIcon },
  { to: '/questions', label: 'Questions', icon: ListIcon },
  { to: '/progress', label: 'Progress', icon: ChartIcon },
  { to: '/profile', label: 'Profile', icon: UserIcon },
]

export default function Sidebar() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  async function handleLogout() { await signOut(); navigate('/login', { replace: true }) }
  return (
    <aside className="w-56 shrink-0 border-r border-base-border bg-base-raised flex flex-col">
      <div className="px-5 py-5 flex items-center gap-2">
        <span className="w-7 h-7 rounded-md bg-accent flex items-center justify-center text-white font-mono font-bold text-sm">
          {'{}'}
        </span>
        <span className="text-ink font-semibold tracking-tight">LeetTrack</span>
      </div>

      <nav className="flex-1 px-3 py-2 flex flex-col gap-1">
        {LINKS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-accent-muted text-accent'
                  : 'text-ink-muted hover:text-ink hover:bg-base-card'
              }`
            }
          >
            <Icon />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-4 border-t border-base-border">
        <p className="text-xs text-ink-muted truncate mb-3" title={user?.email}>{user?.username}</p>
        <button onClick={handleLogout} className="w-full text-left text-sm text-ink-muted hover:text-hard transition-colors">Log out</button>
      </div>
    </aside>
  )
}

function GridIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="9" y="1.5" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="1.5" y="9" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="9" y="9" width="5.5" height="5.5" rx="1" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}
function ListIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M5 3.5h9M5 8h9M5 12.5h9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="2" cy="3.5" r="1" fill="currentColor" />
      <circle cx="2" cy="8" r="1" fill="currentColor" />
      <circle cx="2" cy="12.5" r="1" fill="currentColor" />
    </svg>
  )
}
function ChartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M2 14V2M2 14h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M4.5 11V8M8 11V5M11.5 11V6.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}
function UserIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="5.5" r="2.75" stroke="currentColor" strokeWidth="1.3" />
      <path d="M2.5 14c.8-2.8 3-4.2 5.5-4.2s4.7 1.4 5.5 4.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}
