import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import type { Role } from './lib/types'
import { Admin } from './pages/Admin'
import { AuthCallback } from './pages/AuthCallback'
import { Chat } from './pages/Chat'
import { Documents } from './pages/Documents'
import { Login } from './pages/Login'
import { Tickets } from './pages/Tickets'
import { useAuth } from './store/auth'

/** Route guard: unauthenticated -> login; wrong role -> chat. The API enforces the same rules. */
function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const user = useAuth((s) => s.user)
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/chat" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/chat" element={<Chat />} />
        <Route path="/tickets" element={<Tickets />} />
        <Route
          path="/documents"
          element={
            <RequireAuth roles={['agent', 'admin']}>
              <Documents />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth roles={['admin']}>
              <Admin />
            </RequireAuth>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  )
}
