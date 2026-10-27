import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TokenPair, User } from '../lib/types'

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  setSession: (pair: TokenPair) => void
  setTokens: (access: string, refresh: string) => void
  setUser: (user: User) => void
  logout: () => void
}

// Tokens persist in localStorage so a refresh keeps you signed in. Trade-off vs httpOnly cookies
// is discussed in docs/INFRA.md (security section).
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setSession: (pair) => set({ accessToken: pair.access_token, refreshToken: pair.refresh_token, user: pair.user }),
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      setUser: (user) => set({ user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    { name: 'helpdeskiq-auth' },
  ),
)
