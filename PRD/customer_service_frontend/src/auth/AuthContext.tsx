import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import type { AuthProfile, DemoTokenResponse } from '../api/types'

const STORAGE_KEY = 'edu-cs-auth'

export interface AuthSession {
  token: string
  profile: AuthProfile
}

interface AuthContextValue {
  session: AuthSession | null
  login: (tenantCode: string, externalId: string) => Promise<DemoTokenResponse>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as AuthSession
    if (!parsed?.token || !parsed?.profile?.user_id) return null
    return parsed
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(readStoredSession)

  const login = useCallback(async (tenantCode: string, externalId: string) => {
    const result = await api.demoToken(tenantCode, externalId)
    const profile: AuthProfile = {
      user_id: result.user_id,
      tenant_id: result.tenant_id,
      tenant_code: result.tenant_code,
      tenant_type: result.tenant_type,
      role: result.role,
      name: result.name,
    }
    const next = { token: result.access_token, profile }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    setSession(next)
    return result
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setSession(null)
  }, [])

  const value = useMemo(
    () => ({ session, login, logout }),
    [session, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

export function useSessionToken(): string {
  const { session } = useAuth()
  if (!session) throw new Error('missing session')
  return session.token
}
