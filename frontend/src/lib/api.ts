import { useAuth } from '../store/auth'
import type { ChatEvent, TokenPair } from './types'

const BASE = import.meta.env.VITE_API_URL ?? ''

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let refreshing: Promise<boolean> | null = null

/** Exchange the refresh token once, even if several requests hit a 401 at the same time. */
async function refreshSession(): Promise<boolean> {
  const { refreshToken, setSession, logout } = useAuth.getState()
  if (!refreshToken) return false
  refreshing ??= (async () => {
    try {
      const res = await fetch(`${BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) throw new Error('refresh failed')
      setSession((await res.json()) as TokenPair)
      return true
    } catch {
      logout()
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

async function authedFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = useAuth.getState().accessToken
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const res = await fetch(`${BASE}${path}`, { ...init, headers })
  if (res.status === 401 && retry && (await refreshSession())) return authedFetch(path, init, false)
  return res
}

async function errorFrom(res: Response): Promise<ApiError> {
  let message = res.statusText || 'Request failed'
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') message = body.detail
    else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join(', ')
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, message)
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await authedFetch(path, init)
  if (!res.ok) throw await errorFrom(res)
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const post = <T>(path: string, body: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(body) })

/** POST + Server-Sent Events over fetch (EventSource can't send a body or auth header). */
export async function streamChat(message: string, onEvent: (e: ChatEvent) => void, signal?: AbortSignal) {
  const res = await authedFetch('/api/chat/stream', { method: 'POST', body: JSON.stringify({ message }), signal })
  if (!res.ok || !res.body) throw await errorFrom(res)
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''
    for (const frame of frames) {
      const line = frame.split('\n').find((l) => l.startsWith('data: '))
      if (line) onEvent(JSON.parse(line.slice(6)) as ChatEvent)
    }
  }
}
