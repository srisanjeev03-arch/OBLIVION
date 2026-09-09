/**
 * Auth API boundary — NOT IMPLEMENTED, BY CONTRACT.
 *
 * This module is the single place a published auth endpoint gets wired in. It currently makes no
 * network request whatsoever, because `contract/OPENAPI.yaml` does not publish one. See
 * `@/lib/auth/authContract` for the exact list of missing elements.
 *
 * The pre-consolidation frontend called `POST /api/auth/login`, `POST /api/auth/logout` and
 * `GET /api/auth/me` here. None of those paths exist in the contract, so each call produced a 404
 * that the provider swallowed and reported as "not logged in" — disguising a missing contract as
 * an operator-facing authentication failure. That is the behaviour this file replaces.
 *
 * WHEN THE BACKEND PUBLISHES AUTH:
 *   1. Add the paths to `contract/OPENAPI.yaml` and run `npm run gen:api`.
 *   2. Implement the bodies below against the generated types, returning `ResolvedSession`.
 *   3. Flip `AUTH_TOKEN_ISSUANCE_PUBLISHED` in `authContract.ts`.
 *   4. Point `backendContractSessionSource` at these functions.
 * Nothing else in the app changes: no provider, guard, route or component redesign.
 */
import { ApiError } from './errors'
import { AUTH_CONTRACT_GAP_SUMMARY, AUTH_CONTRACT_NOT_PUBLISHED_CODE } from '@/lib/auth/authContract'
import type { ResolvedSession } from '@/lib/auth/sessionSource'

function notPublishedError(): ApiError {
  return new ApiError({
    kind: 'not_implemented',
    code: AUTH_CONTRACT_NOT_PUBLISHED_CODE,
    message: AUTH_CONTRACT_GAP_SUMMARY,
  })
}

/** Contract gap. Performs no request and fabricates no session. */
export function login(
  _credentials: { username: string; password: string },
): Promise<ResolvedSession> {
  return Promise.reject(notPublishedError())
}

/** Contract gap. Performs no request; local state clearing is handled by the provider. */
export function logout(): Promise<void> {
  return Promise.reject(notPublishedError())
}

/** Contract gap. Performs no request and never returns a guessed principal. */
export function me(): Promise<ResolvedSession> {
  return Promise.reject(notPublishedError())
}
