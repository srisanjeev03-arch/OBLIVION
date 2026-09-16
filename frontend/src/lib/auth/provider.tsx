import { useCallback, useEffect, useMemo, type ReactNode } from 'react'
import { useAuthStore } from './store'
import {
  backendContractSessionSource,
  resolveSessionSource,
  type SessionSource,
} from './sessionSource'
import { devLogin, devPersonaSessionSource, isDevAuthEnabled } from './devAuth'
import { subscribeToAuthEvents } from '@/lib/api/authEvents'
import { ApiError, describeApiError } from '@/lib/api/errors'
import { AuthContext } from './context'
import type { AuthContextType, PermissionKey, Role, User } from './types'

/**
 * What "no session" means right now. The contract publishes a token endpoint, so the honest
 * answer is simply UNAUTHENTICATED.
 */

export function AuthProvider({
  children,
  sessionSource,
}: {
  children: ReactNode
  /** Test seam. Defaults to the DEV persona source under `import.meta.env.DEV`, else the backend. */
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
  // No "already attempted" ref: StrictMode mounts, unmounts and re-mounts in development, and a
  // ref survives that, so the second mount would skip restore() while the first mount's result is
  // discarded as cancelled - leaving the console stuck on AUTHENTICATING. Each mount restores; the
  // `cancelled` flag keeps a stale first-mount result from winning.
  useEffect(() => {
    let cancelled = false

    const opening = useAuthStore.getState()
    if (opening.authState === 'UNKNOWN') {
      opening.setAuthState('AUTHENTICATING')
    }

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
        // Nothing to resume: the bearer token is memory-only, so a fresh document starts
        // unauthenticated. That is the documented posture, not a failure.
        s.setUser(null)
        s.setSession(null)
        s.setAuthState('UNAUTHENTICATED')
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
          s.setAuthState('UNAUTHENTICATED')
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
   * Real sign-in.
   *
   * Always routed at `backendContractSessionSource`, never at the resolved `source`, so a rejected
   * credential can never quietly resolve into a simulated dev session. A failure is surfaced as a
   * failure; nothing here falls back.
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
        // A new principal may hold different permissions and may only be entitled to a subset of
        // what the previous one cached.
      } catch (err: unknown) {
        const after = useAuthStore.getState()
        after.setUser(null)
        after.setSession(null)
        const summary = describeApiError(err)
        after.setError(`${summary.title}: ${summary.detail}`)
        after.setAuthState('ERROR')
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
      s.setAuthState('UNAUTHENTICATED')
      s.setError('Development personas are not available in this build.')
      throw new Error('Development personas are not available in this build.')
    }
    // Asserts the DEV gate and the persona lookup, then commits to the store.
    return devLogin(personaId)
  }, [])

  /**
   * Logout.
   *
   * The local credential is always cleared â€” leaving it behind would be worse than any reporting
   * failure. What must not be papered over is the difference between "the backend revoked this
   * session" and "we forgot about it". If the revocation call fails the operator is told the
   * credential may still be live server-side, because a forgotten token is not a revoked one.
   */
  const logout = useCallback(async () => {
    const before = useAuthStore.getState().session
    let revocationFailed: string | null = null
    try {
      if (before?.source === 'dev-persona') {
        await devPersonaSessionSource.revoke()
      } else {
        await backendContractSessionSource.revoke()
      }
    } catch (err: unknown) {
      revocationFailed =
        err instanceof ApiError
          ? `${err.kind}${err.status ? ` ${err.status}` : ''}`
          : err instanceof Error
            ? err.message
            : 'unknown error'
    } finally {
      useAuthStore.getState().reset()
      useAuthStore.getState().setAuthState('UNAUTHENTICATED')
    }
    if (revocationFailed !== null) {
      useAuthStore.getState().setNotice({
        kind: 'revocation_incomplete',
        message:
          `Local session cleared, but server-side revocation failed (${revocationFailed}). ` +
          'The bearer token may still be accepted by the backend until it expires.',
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
