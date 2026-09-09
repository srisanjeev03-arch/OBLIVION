/**
 * Authentication contract status.
 *
 * SOURCE OF TRUTH: `docs/OPENAPI.yaml`, which is itself generated from the FastAPI application by
 * `scripts/gen_openapi.py`. Nothing here is a guess about the protocol: every "published" claim
 * below is backed by a request that was made against the running backend, and every "missing"
 * claim is an operation the contract does not contain.
 *
 * HISTORY WORTH KEEPING
 * This module used to record the opposite state. `docs/OPENAPI.yaml` was hand-maintained and had
 * drifted: it listed ten paths while the application served seventeen, so the three auth
 * endpoints the backend had implemented and enforced for some time appeared to be absent. The
 * console therefore refused to attempt login and reported a contract gap. That was the correct
 * behaviour against a wrong document, and it is now superseded: the document was regenerated from
 * the application, and the console authenticates for real.
 */

/** The security scheme the backend declares, quoted from the generated contract. */
export const DECLARED_SECURITY_SCHEME = {
  name: 'bearerAuth',
  type: 'http',
  scheme: 'bearer',
  /**
   * NOT a JWT. The backend mints `secrets.token_urlsafe(32)` and stores only its SHA-256 digest,
   * so a client must never parse this token, read claims from it, or assume any structure.
   */
  bearerFormat: 'OpaqueSessionToken',
  appliedGlobally: true,
} as const

/** Server-side session lifetime. There is no refresh endpoint, so re-login is the only renewal. */
export const SESSION_TTL_HOURS = 24

/**
 * Auth operations the contract publishes AND that were observed working against the running
 * backend. `evidence` records what was actually seen, not what was assumed.
 */
export interface PublishedAuthCapability {
  readonly capability: string
  readonly method: 'GET' | 'POST'
  readonly path: string
  readonly evidence: string
}

export const PUBLISHED_AUTH_CAPABILITIES: readonly PublishedAuthCapability[] = [
  {
    capability: 'issue-access-token',
    method: 'POST',
    path: '/api/auth/login',
    evidence:
      '200 with access_token (43 opaque chars, no JWT dot structure), token_type "bearer", expires_at, and user{roles,permissions}',
  },
  {
    capability: 'resolve-current-principal',
    method: 'GET',
    path: '/api/auth/me',
    evidence:
      '200 with the caller identity and 26 backend-granted permission keys; 401 UNAUTHENTICATED without a token',
  },
  {
    capability: 'revoke-session',
    method: 'POST',
    path: '/api/auth/logout',
    evidence:
      '200 COMPLETED, after which /api/auth/me with the same token returns 401 SESSION_INVALID - the credential is genuinely dead server-side, not merely forgotten locally',
  },
  {
    capability: 'reject-bad-credentials',
    method: 'POST',
    path: '/api/auth/login',
    evidence: '401 with error_code INVALID_CREDENTIALS and no token in the body',
  },
] as const

/**
 * Authentication capabilities the console needs that the contract still does not publish.
 *
 * These stay here deliberately. They are the operations the UI must render as unavailable rather
 * than simulate, and the reason the console cannot offer a "stay signed in" option or a session
 * that survives a page reload.
 */
export interface MissingAuthContractElement {
  readonly capability: string
  readonly why: string
  readonly status: 'ABSENT_FROM_CONTRACT'
  readonly userVisibleConsequence: string
}

export const MISSING_AUTH_CONTRACT_ELEMENTS: readonly MissingAuthContractElement[] = [
  {
    capability: 'renew-access-token',
    why: 'No refresh endpoint exists, and the token is held in memory only, so it cannot be re-read after a reload.',
    status: 'ABSENT_FROM_CONTRACT',
    userVisibleConsequence:
      'Signing in is per-tab. Reloading the page returns to the sign-in screen, and a session older than 24h must re-authenticate.',
  },
  {
    capability: 'revoke-all-sessions-for-user',
    why: 'Logout revokes only the presented token; there is no endpoint to revoke a user\u2019s other sessions.',
    status: 'ABSENT_FROM_CONTRACT',
    userVisibleConsequence:
      'Logging out of this tab does not sign the operator out of any other tab or device.',
  },
  {
    capability: 'manage-users-and-roles',
    why: 'No user, role or permission administration endpoints are published.',
    status: 'ABSENT_FROM_CONTRACT',
    userVisibleConsequence:
      'Administration cannot list or edit principals. It is rendered as unavailable, never with placeholder people.',
  },
] as const

/**
 * True when the contract publishes a way to obtain a token. Verified against the running backend
 * and cross-checked by `authHygiene.test.ts`, which asserts this equals the presence of an
 * `/api/auth` path in the contract - so the flag cannot drift from the document.
 */
export const AUTH_TOKEN_ISSUANCE_PUBLISHED = true

/** Stable pseudo-code so screens can branch on a missing capability rather than on error text. */
export const AUTH_CONTRACT_NOT_PUBLISHED_CODE = 'AUTH_CONTRACT_NOT_PUBLISHED' as const

export const AUTH_CONTRACT_GAP_SUMMARY: string =
  'The contract publishes no endpoint for this operation. Credential transport and the ' +
  'login/me/logout trio are implemented; this capability is not.'
