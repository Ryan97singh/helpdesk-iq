import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../store/auth'
import type { Role } from '../lib/types'

const NAV: { to: string; label: string; roles: Role[] }[] = [
  { to: '/chat', label: 'Ask HelpdeskIQ', roles: ['employee', 'agent', 'admin'] },
  { to: '/tickets', label: 'Tickets', roles: ['employee', 'agent', 'admin'] },
  { to: '/documents', label: 'Knowledge base', roles: ['agent', 'admin'] },
  { to: '/admin', label: 'AI usage & cost', roles: ['admin'] },
]

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  if (!user) return null
  const links = NAV.filter((n) => n.roles.includes(user.role))

  const signOut = () => {
    logout()
    queryClient.clear() // don't leak one user's cached data to the next sign-in
    navigate('/login')
  }

  const nav = (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {links.map((l) => (
        <NavLink
          key={l.to}
          to={l.to}
          onClick={() => setOpen(false)}
          className={({ isActive }) =>
            `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? 'bg-indigo-50 text-indigo-700' : 'text-slate-600 hover:bg-slate-100'}`
          }
        >
          {l.label}
        </NavLink>
      ))}
    </nav>
  )

  return (
    <div className="flex min-h-dvh bg-slate-50">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white p-4 md:flex">
        <Brand />
        <div className="mt-6 flex-1">{nav}</div>
        <UserFooter name={user.name} role={user.role} onLogout={signOut} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <Brand />
          <button
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8">
              {open ? <path d="M5 5l10 10M15 5L5 15" /> : <path d="M3 6h14M3 10h14M3 14h14" />}
            </svg>
          </button>
        </header>
        {open && (
          <div className="border-b border-slate-200 bg-white p-4 md:hidden">
            {nav}
            <div className="mt-4">
              <UserFooter name={user.name} role={user.role} onLogout={signOut} />
            </div>
          </div>
        )}
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2">
      <div className="grid h-8 w-8 place-items-center rounded-lg bg-indigo-600 text-sm font-bold text-white">IQ</div>
      <span className="font-semibold text-slate-900">HelpdeskIQ</span>
    </div>
  )
}

function UserFooter({ name, role, onLogout }: { name: string; role: string; onLogout: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 border-t border-slate-200 pt-4">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-slate-800">{name}</p>
        <p className="text-xs capitalize text-slate-500">{role}</p>
      </div>
      <button onClick={onLogout} className="rounded-lg px-2 py-1 text-sm text-slate-600 hover:bg-slate-100">
        Sign out
      </button>
    </div>
  )
}
