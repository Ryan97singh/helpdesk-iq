import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import type { User } from '../lib/types'
import { useAuth } from '../store/auth'
import { ErrorBanner, Spinner } from '../components/ui'

function readTokens() {
  const params = new URLSearchParams(window.location.hash.slice(1))
  return { access: params.get('access_token'), refresh: params.get('refresh_token') }
}

/** Landing page for the Google SSO redirect: tokens arrive in the URL fragment. */
export function AuthCallback() {
  const navigate = useNavigate()
  const { setTokens, setUser } = useAuth()
  const [{ access, refresh }] = useState(readTokens)
  const [error, setError] = useState<string | null>(access && refresh ? null : 'Sign-in failed: no tokens returned.')

  useEffect(() => {
    window.history.replaceState(null, '', window.location.pathname) // scrub tokens from the address bar
    if (!access || !refresh) return
    setTokens(access, refresh)
    api<User>('/api/auth/me')
      .then((user) => {
        setUser(user)
        navigate('/chat', { replace: true })
      })
      .catch(() => setError('Sign-in failed. Please try again.'))
  }, [access, refresh, navigate, setTokens, setUser])

  return (
    <div className="grid min-h-dvh place-items-center px-4">
      {error ? <ErrorBanner message={error} /> : <Spinner className="h-8 w-8 text-indigo-600" />}
    </div>
  )
}
