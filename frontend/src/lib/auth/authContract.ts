/**
 * Authentication contract status.
 *
 * SOURCE OF TRUTH: `contract/OPENAPI.yaml` (regenerated into `src/lib/api/schema.d.ts` via
 * `npm run gen:api`). Nothing in this file is a guess about the protocol — every claim below is
 * either quoted from the contract or explicitly marked as ABSENT from it.
 *
 * WHAT THE CONTRACT DOES PUBLISH
 *   openapi: 3.0.3
 *   servers:  http://127.0.0.1:8000
 *   security: [{ bearerAuth: [] }]            <- applied globally
 *   components.securitySchemes.bearerAuth:
 *     type: http, scheme: bearer, bearerFormat: JWT
 *
 * WHAT THE CONTRACT DOES NOT PUBLISH
 *   No token-issuing endpoint of any kind. All 10 contract paths assume a bearer JWT is already
 *   present; none of them can supply one. Token issuance is therefore an undocumented dependency,
 *   and the console must not invent it.
 *
 * This module exists so that "we cannot log in" is a *stated, machine-checkable* condition rather
 *   than a silent failure or a fake success.
 */

/** The security scheme the backend actually declares. Quoted from OPENAPI.yaml. */
export const DECLARED_SECURITY_SCHEME = {
  name: 'bearerAuth',
  type: 'http',
  scheme: 'bearer',
  bearerFormat: 'JWT',
  appliedGlobally: true,
} as const

/**
 * Authentication capabilities the console needs, that OPENAPI.yaml does not publish.
 *
 * `candidatePath` is NOT authoritative — it is only the path the pre-consolidation frontend
 * happened to call. The backend team must confirm the real path, verb, request body and response
 * schema before any of this is wired up. Do not implement against `candidatePath`.
 */
export interface MissingAuthContractElement {
  readonly capability: string
  readonly why: string
  readonly candidatePath: string
  readonly status: 'ABSENT_FROM_CONTRACT'
  readonly requiredFields: readonly string[]
}

export const MISSING_AUTH_CONTRACT_ELEMENTS: readonly MissingAuthContractElement[] = [
  {
    capability: 'issue-access-token',
    why: 'Without it there is no way to obtain the bearer JWT that every published path requires.',
    candidatePath: 'POST /api/auth/login',
    status: 'ABSENT_FROM_CONTRACT',
    requiredFields: [
      'request credential shape (username/password? OAuth2 grant? OIDC code exchange?)',
      'response access token field name',
      'token TTL / expires_in semantics',
      'refresh token presence and rotation policy',
      'failure status codes distinguishing bad credentials (401) from locked/disabled (403/423)',
    ],
  },
  {
    capability: 'resolve-current-principal',
    why: 'The console needs user id, role and permission set derived from the token, not asserted by the client.',
    candidatePath: 'GET /api/auth/me',
    status: 'ABSENT_FROM_CONTRACT',
    requiredFields: [
      'user schema (id, username, display name, email)',
      'authoritative role enum (the frontend 5-role model is unratified)',
      'authoritative permission key enum (the frontend 24-key list is unratified)',
      'whether role/permissions are embedded in JWT claims or returned as a body',
    ],
  },
  {
    capability: 'revoke-session',
    why: 'Logout must invalidate server-side state; clearing the token locally is not a logout.',
    candidatePath: 'POST /api/auth/logout',
    status: 'ABSENT_FROM_CONTRACT',
    requiredFields: ['revocation semantics', 'whether a refresh token must also be revoked'],
  },
  {
    capability: 'renew-access-token',
    why: 'Required for long forensic operations that outlive a short JWT TTL.',
    candidatePath: 'POST /api/auth/refresh',
    status: 'ABSENT_FROM_CONTRACT',
    requiredFields: ['grant shape', 'rotation behaviour on reuse'],
  },
  {
    capability: 'error-envelope-for-auth',
    why: 'The console must render 401 and 403 distinctly; it cannot know the codes exist until specified.',
    candidatePath: '(applies to every protected path)',
    status: 'ABSENT_FROM_CONTRACT',
    requiredFields: [
      '401 body shape and code',
      '403 body shape and code',
      'whether WWW-Authenticate is returned',
    ],
  },
]

/** Paths the pre-consolidation frontend called that are not in OPENAPI.yaml. */
export const UNPUBLISHED_PATHS_PREVIOUSLY_CALLED: readonly string[] = [
  'POST /api/auth/login',
  'POST /api/auth/logout',
  'GET /api/auth/me',
]

/**
 * True when the contract publishes no way to obtain a token. This is the honest current state and
 * it is what the UI renders, rather than a login form that cannot succeed.
 */
export const AUTH_TOKEN_ISSUANCE_PUBLISHED = false

export const AUTH_CONTRACT_GAP_SUMMARY: string =
  'OPENAPI.yaml declares bearerAuth (JWT) as the security scheme but publishes no endpoint that ' +
  'issues, renews or revokes a token. Credential transport is implemented; credential issuance is ' +
  'an undocumented backend dependency.'

/** Stable pseudo-code so screens can branch on the gap instead of on a caught exception's text. */
export const AUTH_CONTRACT_NOT_PUBLISHED_CODE = 'AUTH_CONTRACT_NOT_PUBLISHED' as const