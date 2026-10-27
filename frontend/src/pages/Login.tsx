import { useState, type FormEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate, useNavigate } from 'react-router-dom'
import { api, ApiError, post } from '../lib/api'
import type { TokenPair } from '../lib/types'
import { useAuth } from '../store/auth'
import { Button, ErrorBanner } from '../components/ui'

const DEMO = [
  { label: 'Employee', email: 'employee@helpdesk.io' },
  { label: 'Agent', email: 'agent@helpdesk.io' },
  { label: 'Admin', email: 'admin@helpdesk.io' },
]

export function Login() {
  const { accessToken, setSession } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const providers = useQuery({
    queryKey: ['auth-providers'],
    queryFn: () => api<{ google: boolean }>('/api/auth/providers'),
  })

  if (accessToken) return <Navigate to="/chat" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const pair =
        mode === 'login'
          ? await post<TokenPair>('/api/auth/login', { email, password })
          : await post<TokenPair>('/api/auth/register', { email, password, name })
      setSession(pair)
      navigate('/chat')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto grid h-11 w-11 place-items-center rounded-xl bg-indigo-600 font-bold text-white">IQ</div>
          <h1 className="mt-4 text-2xl font-semibold text-slate-900">HelpdeskIQ</h1>
          <p className="mt-1 text-sm text-slate-500">AI copilot for your IT & HR helpdesk</p>
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          {error && <ErrorBanner message={error} />}
          {mode === 'register' && (
            <Field label="Full name" value={name} onChange={setName} autoComplete="name" />
          )}
          <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            minLength={mode === 'register' ? 8 : undefined}
          />
          <Button type="submit" className="w-full" loading={loading}>
            {mode === 'login' ? 'Sign in' : 'Create account'}
          </Button>
          {providers.data?.google && (
            <a
              href="/api/auth/google/login"
              className="flex w-full items-center justify-center rounded-lg px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
            >
              Continue with Google (SSO)
            </a>
          )}
          <p className="text-center text-sm text-slate-500">
            {mode === 'login' ? 'New here? ' : 'Already have an account? '}
            <button
              type="button"
              className="font-medium text-indigo-600 hover:underline"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login')
                setError(null)
              }}
            >
              {mode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </form>

        {mode === 'login' && (
          <div className="mt-6 rounded-xl bg-white p-4 text-sm ring-1 ring-slate-200">
            <p className="font-medium text-slate-700">Demo accounts (password: Password123!)</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {DEMO.map((d) => (
                <button
                  key={d.email}
                  type="button"
                  onClick={() => {
                    setEmail(d.email)
                    setPassword('Password123!')
                  }}
                  className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-200"
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function Field(props: {
  label: string
  value: string
  onChange: (v: string) => void
  type?: string
  autoComplete?: string
  minLength?: number
}) {
  const id = props.label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
        {props.label}
      </label>
      <input
        id={id}
        required
        type={props.type ?? 'text'}
        value={props.value}
        autoComplete={props.autoComplete}
        minLength={props.minLength}
        onChange={(e) => props.onChange(e.target.value)}
        className="w-full rounded-lg border-0 px-3 py-2 text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-indigo-600 focus:outline-none"
      />
    </div>
  )
}
