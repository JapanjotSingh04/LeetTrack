import { Navigate, Route, Routes } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import { ToastProvider } from './components/Toast'
import Dashboard from './pages/Dashboard'
import Questions from './pages/Questions'
import Progress from './pages/Progress'
import Profile from './pages/Profile'
import AuthPage from './auth/AuthPage'
import RequireAuth from './auth/RequireAuth'
import { AuthProvider } from './auth/AuthContext'

function Workspace() {
  return (
    <div className="min-h-screen flex bg-base text-ink">
      <Sidebar />
      <main className="flex-1 min-w-0">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/questions" element={<Questions />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="/login" element={<AuthPage mode="login" />} />
          <Route path="/register" element={<AuthPage mode="register" />} />
          <Route element={<RequireAuth />}>
            <Route path="/*" element={<Workspace />} />
          </Route>
        </Routes>
      </ToastProvider>
    </AuthProvider>
  )
}
