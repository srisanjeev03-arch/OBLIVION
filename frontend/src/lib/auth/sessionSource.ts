/**
 * The session-source seam.
 *
 * `AuthProvider` never talks to an auth endpoint directly and never knows whether it is real or
 * simulated. It talks to a `SessionSource`. Swapping the backend login flow for a development
 * substitute is therefore a one-object change in `resolveSessionSource()` — no provider, guard,
 * route or component redesign.
 *
 * `backendContractSessionSource` below is the real one: it calls the auth endpoints that
 * `docs/OPENAPI.yaml` publishes and that were verified against the running backend.
 */
import * as authApi from '@/lib/api/auth'
import type { SessionSourceId, Session, User } from './types'

export interface ResolvedSession {
  user: User
  session: Session
}

export interface SessionSource {
  readonly id: SessionSourceId
  /** Shown verbatim in the UI so the operator always knows which source granted the session. */
  readonly label: string
  readonly isDevelopmentOnly: boolean
  /** Resume an existing session. Null means "nothing to resume" — not an error. */
  restore(): Promise<ResolvedSession | null>
  /** Exchange credentials for a bearer session. Rejects if issuance is unavailable. */
  authenticate(credentials: { username: string; password: string }): Promise<ResolvedSession>
  /** Server-side revocation. Local clearing happens regardless. */
  revoke(): Promise<void>
}

/**
 * The real backend source.
 *
 * `restore()` resolves to null rather than attempting anything: the bearer token lives in module
 * memory only and is deliberately never written to localStorage, sessionStorage or a cookie, so a
 * fresh document genuinely has no credential to resume. That is a privacy and XSS-surface choice,
 * not an oversight, and it is why a page reload signs the operator out. The contract publishes no
 * refresh endpoint that could re-establish a session either (see
 * `MISSING_AUTH_CONTRACT_ELEMENTS`), so there is nothing honest to restore.
 */
export const backendContractSessionSource: SessionSource = {
  id: 'backend-contract',
  label: 'Backend bearer session',
  isDevelopmentOnly: false,
  restore: () => Promise.resolve(null),
  authenticate: (credentials) => authApi.login(credentials),
  revoke: () => authApi.logout(),
}

/**
 * Selects the active source.
 *
 * `devSource` is supplied by the caller only when `isDevAuthEnabled()` is true, and must itself
 * declare `isDevelopmentOnly`. That invariant check means a development substitute can never be
 * smuggled in as if it were the backend: production resolves to
 * `backendContractSessionSource` unconditionally, and `import.meta.env.DEV` is statically replaced
 * with `false` at build time so the dev branch is dead-code-eliminated from the shipped bundle.
 */
export function resolveSessionSource(devSource: SessionSource | null): SessionSource {
  if (devSource === null) return backendContractSessionSource
  if (!devSource.isDevelopmentOnly) {
    throw new Error(
      'resolveSessionSource: only a source marked isDevelopmentOnly may replace the backend contract source.',
    )
  }
  return devSource
}