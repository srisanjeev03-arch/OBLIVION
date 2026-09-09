/**
 * The session-source seam.
 *
 * `AuthProvider` never talks to an auth endpoint directly and never knows whether it is real or
 * simulated. It talks to a `SessionSource`. Swapping the temporary dev persona for the real
 * backend login flow is therefore a one-object change in `resolveSessionSource()` — no provider,
 * guard, route or component redesign.
 *
 * The backend source below deliberately issues NO network request. OPENAPI.yaml publishes no
 * token endpoint (see `@/lib/auth/authContract`), so calling `POST /api/auth/login` would be
 * inventing a protocol and would produce a 404 that looks like a backend fault rather than a
 * missing contract. It fails fast with a stable, self-explanatory code instead.
 */
import { ApiError } from '@/lib/api/errors'
import { AUTH_CONTRACT_GAP_SUMMARY, AUTH_CONTRACT_NOT_PUBLISHED_CODE } from './authContract'
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

function notPublished(): ApiError {
  return new ApiError({
    kind: 'not_implemented',
    code: AUTH_CONTRACT_NOT_PUBLISHED_CODE,
    message: AUTH_CONTRACT_GAP_SUMMARY,
  })
}

/**
 * The real backend source. It is a correct, complete implementation of the interface whose
 * authenticate/revoke methods report that the contract has not published those operations.
 *
 * Methods return promises directly rather than being declared `async`: there is nothing to await,
 * because there is nothing to call.
 */
export const backendContractSessionSource: SessionSource = {
  id: 'backend-contract',
  label: 'Backend bearer session',
  isDevelopmentOnly: false,
  // Sessions are in-memory only, so a fresh document can never have anything to resume.
  restore: () => Promise.resolve(null),
  authenticate: () => Promise.reject(notPublished()),
  revoke: () => Promise.reject(notPublished()),
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