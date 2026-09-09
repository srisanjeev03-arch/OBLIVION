import { create } from 'zustand'
import type {
  User,
  Session,
  AuthState,
  AuthNotice,
  PermissionKey,
  Role,
} from './types'
import { hasPermission, hasAnyPermission, hasAllPermissions, hasRole } from './permissions'
import { setBearerToken } from './tokenStore'

interface AuthStore {
  user: User | null
  session: Session | null
  authState: AuthState
  error: string | null
  notice: AuthNotice | null
  setUser: (user: User | null) => void
  /**
   * Setting a session is the only way a bearer token enters the transport. The token store mirror
   * is unconditional here so a credential can never diverge from the session it belongs to, and
   * so `setSession(null)` is always simultaneously a token clear.
   */
  setSession: (session: Session | null) => void
  setAuthState: (state: AuthState) => void
  setError: (error: string | null) => void
  setNotice: (notice: AuthNotice | null) => void
  hasPermission: (permission: PermissionKey) => boolean
  hasAnyPermission: (permissions: readonly PermissionKey[]) => boolean
  hasAllPermissions: (permissions: readonly PermissionKey[]) => boolean
  hasRole: (role: Role | readonly Role[]) => boolean
  reset: () => void
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  session: null,
  authState: 'UNKNOWN',
  error: null,
  notice: null,
  setUser: (user) => set({ user }),
  setSession: (session) => {
    set({ session })
    setBearerToken(
      session
        ? { accessToken: session.accessToken, expiresAt: session.expiresAt, source: session.source }
        : null,
    )
  },
  setAuthState: (authState) => set({ authState }),
  setError: (error) => set({ error }),
  setNotice: (notice) => set({ notice }),
  hasPermission: (permission) => hasPermission(get().user, permission),
  hasAnyPermission: (permissions) => hasAnyPermission(get().user, permissions),
  hasAllPermissions: (permissions) => hasAllPermissions(get().user, permissions),
  hasRole: (role) => hasRole(get().user, role),
  reset: () => {
    set({
      user: null,
      session: null,
      authState: 'UNAUTHENTICATED',
      error: null,
      notice: null,
    })
    setBearerToken(null)
  },
}))
