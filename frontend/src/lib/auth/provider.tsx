import { useCallback, useEffect, useMemo, useRef, type ReactNode } from 'react'
import { useAuthStore } from './store'
import {
  backendContractSessionSource,
  resolveSessionSource,
  type SessionSource,
} from './sessionSource'
import { devLogin, devPersonaSessionSource, isDevAuthEnabled } from './devAuth'
import { AUTH_CONTRACT_NOT_PUBLISHED_CODE, AUTH_TOKEN_ISSUANCE_PUBLISHED } from './authContract'
import { subscribeToAuthEvents } from '@/lib/api/authEvents'
import { describeApiError } from '@/lib/api/errors'
import { AuthContext } from './context'
import type { AuthContextType, PermissionKey, Role, User } from './types'

/**
 * What "no session" means right now. With no published token endpoint the client is not merely
 * logged out, it is unable to log in — a materially different fact that deserves its own state.
 */
function noSessionState(): 'UNAVAILABLE' | 'UNAUTHENTICATED' {
  return AUTH_TOKEN_ISSUANCE_PUBLISHED ? 'UNAUTHENTICATED' : 'UNAVAILABLE'
}

export function AuthProvider({
  children,
  sessionSource,
}: {
  children: ReactNode
  /** Test seam. Defaults to the DEV persona source under `import.meta.env.DEV`, else the contract. */
  sessionSource?: SessionSource
}) {
  const user = useAuthStore((s) => s.user)
  const session = useAuthStore((s) => s.session)
  const authState = useAuthStore((s) => s.authState)
  const error = useAuthStore((s) => s.error)
  const notice = useAuthStore((s) => s.notice)

  const source = useMemo(
    () =>
      sessionSource ??
      resolveSessionSource(isDevAuthEnabled() ? devPersonaSessionSource : null),
    [sessionSource],
  )

  // --- mount: restore only, never authenticate ------------------------------------------
  const restoreAttempted = useRef(false)
  useEffect(() => {
    if (restoreAttempted.current) return
    restoreAttempted.current = true

    const opening = useAuthStore.getState()
    opening.setAuthState('AUTHENTICATING')

    let cancelled = false
    void source
      .restore()
      .then((resolved) => {
        if (cancelled) return
        const s = useAuthStore.getState()
        if (resolved) {
          s.setUser(resolved.user)
          s.setSession(resolved.session)
          s.setAuthState('AUTHENTICATED')
          s.setError(null)
          return
        }
        s.setUser(null)
        s.setSession(null)
        s.setAuthState(noSessionState())
        s.setError(null)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const s = useAuthStore.getState()
        // A failed restore NEVER yields an authenticated session.
        s.setUser(null)
        s.setSession(null)
        s.setAuthState('ERROR')
        const summary = describeApiError(err)
        s.setError(`${summary.title}: ${summary.detail}`)
      })

    return () => {
      cancelled = true
    }
  }, [source])

  // --- live transport feedback: 401 and 403 handled apart -------------------------------
  useEffect(
    () =>
      subscribeToAuthEvents((event) => {
        const s = useAuthStore.getState()
        if (event.kind === 'unauthenticated') {
          s.setSession(null)
          s.setUser(null)
          s.setAuthState(noSessionState())
          s.setError(
            'The backend rejected the bearer credential (401). A new session is required.',
          )
          return
        }
        // 403 preserves the session: the operator IS authenticated, this one action is denied.
        s.setNotice({
          kind: 'permission_denied',
          message: `The backend refused ${event.method} ${event.path} (403). Your session is still valid.`,
          path: event.path,
          at: new Date().toISOString(),
        })
      }),
    [],
  )

  /**
   * Real sign-in. Always routed at `backendContractSessionSource`, never at the dev persona
   * source, so a rejected credential can never quietly resolve into a simulated session. While
   * the contract publishes no token endpoint this rejects with AUTH_CONTRACT_NOT_PUBLISHED and
   * the UI renders the gap.
   */
  const login = useCallback(
    async (credentials: { username: string; password: string }) => {
      const s = useAuthStore.getState()
      s.setAuthState('AUTHENTICATING')
      s.setError(null)
      s.setNotice(null)

      try {
        const resolved = await backendContractSessionSource.authenticate(credentials)
        const after = useAuthStore.getState()
        after.setUser(resolved.user)
        after.setSession(resolved.session)
        after.setAuthState('AUTHENTICATED')
        after.setError(null)
      } catch (err: unknown) {
        const after = useAuthStore.getState()
        after.setUser(null)
        after.setSession(null)
        const summary = describeApiError(err)
        after.setError(`${summary.title}: ${summary.detail}`)
        after.setAuthState(
          err instanceof Error && 'code' in err && err.code === AUTH_CONTRACT_NOT_PUBLISHED_CODE
            ? 'UNAVAILABLE'
            : 'ERROR',
        )
        throw err
      }
    },
    [],
  )

  /**
   * Explicit development persona sign-in. Unavailable unless `import.meta.env.DEV`, and the
   * resulting session is tagged `source: 'dev-persona'` for the lifetime of the tab.
   */
  const signInWithDevPersona = useCallback((personaId: string): User => {
    if (!isDevAuthEnabled()) {
      const s = useAuthStore.getState()
      s.setAuthState(noSessionState())
      s.setError('Development personas are not available in this build.')
      throw new Error('Development personas are not available in this build.')
    }
    // Asserts the DEV gate and the persona lookup, then commits to the store.
    return devLogin(personaId)
  }, [])

  const logout = useCallback(async () => {
    const before = useAuthStore.getState().session
    let revocationUnavailable = false
    try {
      if (before?.source === 'dev-persona') {
        await devPersonaSessionSource.revoke()
      } else {
        await backendContractSessionSource.revoke()
      }
    } catch (err: unknown) {
      revocationUnavailable =
        err instanceof Error && 'code' in err && err.code === AUTH_CONTRACT_NOT_PUBLISHED_CODE
    } finally {
      useAuthStore.getState().reset()
      useAuthStore.getState().setAuthState(noSessionState())
    }
    if (revocationUnavailable) {
      // Honest bookkeeping: the local credential is gone but the backend was never told,
      // because no revocation endpoint is published. Clearing local state is not a logout.
      useAuthStore.getState().setNotice({
        kind: 'revocation_incomplete',
        message:
          'Local session cleared. Server-side revocation is not published in the contract, so the credential may remain valid at the backend.',
        path: '/api/auth/logout',
        at: new Date().toISOString(),
      })
    }
  }, [])

  const dismissNotice = useCallback(() => useAuthStore.getState().setNotice(null), [])

  const hasPerm = useCallback(
    (permission: PermissionKey) => useAuthStore.getState().hasPermission(permission),
    [],
  )

  const hasAnyPerm = useCallback(
    (permissions: readonly PermissionKey[]) =>
      useAuthStore.getState().hasAnyPermission(permissions),
    [],
  )

  const hasAllPerms = useCallback(
    (permissions: readonly PermissionKey[]) =>
      useAuthStore.getState().hasAllPermissions(permissions),
    [],
  )

  const hasUserRole = useCallback(
    (role: Role | readonly Role[]) => useAuthStore.getState().hasRole(role),
    [],
  )

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      session,
      authState,
      error,
      notice,
      accessToken: session?.accessToken ?? null,
      isDevSession: session?.source === 'dev-persona',
      sessionSourceId: source.id,
      login,
      signInWithDevPersona,
      logout,
      dismissNotice,
      hasPermission: hasPerm,
      hasAnyPermission: hasAnyPerm,
      hasAllPermissions: hasAllPerms,
      hasRole: hasUserRole,
    }),
    [
      user,
      session,
      authState,
      error,
      notice,
      source.id,
      login,
      signInWithDevPersona,
      logout,
      dismissNotice,
      hasPerm,
      hasAnyPerm,
      hasAllPerms,
      hasUserRole,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
