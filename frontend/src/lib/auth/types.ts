/**
 * Oblivion Role-Based Access Control (RBAC) & Authentication Types.
 *
 * The 5-role model and conceptual access levels:
 * - ADMIN (Level 5): System administration, security control, policy configuration, sensitive operation approval.
 * - INVESTIGATOR (Level 4): Case management, evidence investigation, recovery workflows.
 * - OPERATOR (Level 3): Approved sanitization and erasure execution.
 * - AUDITOR (Level 2): Independent audit and evidence verification.
 * - VIEWER (Level 1): Read-only case, operation, assurance, and certificate viewing.
 */

export type Role = 'ADMIN' | 'INVESTIGATOR' | 'OPERATOR' | 'AUDITOR' | 'VIEWER'

/**
 * Provenance of a bearer credential. Kept in the type module (no imports) so both the token
 * store and the session-source seam can reference it without a dependency cycle.
 */
export type AccessTokenSource = 'backend' | 'dev-persona'

/**
 * Which session source is active. `backend-contract` is the slot a real login API occupies;
 * `dev-persona` exists only under `import.meta.env.DEV`.
 */
export type SessionSourceId = 'backend-contract' | 'dev-persona'

export const ROLES: readonly Role[] = [
  'ADMIN',
  'INVESTIGATOR',
  'OPERATOR',
  'AUDITOR',
  'VIEWER',
] as const

export interface RoleMetadata {
  readonly role: Role
  readonly label: string
  readonly level: number
  readonly description: string
  readonly color: string
  readonly badgeVariant: 'danger' | 'warning' | 'info' | 'success' | 'neutral'
}

export const ROLE_METADATA: Readonly<Record<Role, RoleMetadata>> = {
  ADMIN: {
    role: 'ADMIN',
    label: 'ADMIN',
    level: 5,
    description: 'System administration and security control',
    color: '#ff3d57', // High-privilege indicator
    badgeVariant: 'danger',
  },
  INVESTIGATOR: {
    role: 'INVESTIGATOR',
    label: 'INVESTIGATOR',
    level: 4,
    description: 'Case and evidence investigation',
    color: '#ff7043', // Investigation indicator
    badgeVariant: 'warning',
  },
  OPERATOR: {
    role: 'OPERATOR',
    label: 'OPERATOR',
    level: 3,
    description: 'Approved sanitization and erasure execution',
    color: '#ffb020', // Execution indicator
    badgeVariant: 'warning',
  },
  AUDITOR: {
    role: 'AUDITOR',
    label: 'AUDITOR',
    level: 2,
    description: 'Independent audit and evidence verification',
    color: '#35c88f', // Verification indicator
    badgeVariant: 'success',
  },
  VIEWER: {
    role: 'VIEWER',
    label: 'VIEWER',
    level: 1,
    description: 'Read-only case and report viewing',
    color: '#5b9dff', // Read-only indicator
    badgeVariant: 'neutral',
  },
}

export type PermissionKey =
  // Case permissions
  | 'case.create'
  | 'case.view'
  | 'case.update'
  | 'case.close'
  // Evidence permissions
  | 'evidence.import'
  | 'evidence.view'
  | 'evidence.hash'
  | 'evidence.verify'
  // File erasure permissions
  | 'file_erasure.request'
  | 'file_erasure.execute'
  // Drive sanitization permissions
  | 'drive_sanitization.request'
  | 'drive_sanitization.execute'
  // Recovery permissions
  | 'recovery.view'
  | 'recovery.execute'
  // Operations permissions
  | 'operation.view'
  | 'operation.request'
  | 'operation.approve'
  | 'operation.execute'
  | 'operation.verify'
  // Audit permissions
  | 'audit.view'
  | 'audit.verify'
  // Reporting permissions
  | 'report.export'
  // Administration permissions
  | 'user.manage'
  | 'role.manage'
  | 'permission.manage'
  | 'system.configure'

export type AuthState =
  /** Nothing resolved yet; the provider is about to attempt it. */
  | 'UNKNOWN'
  /** A resolution is in flight. */
  | 'AUTHENTICATING'
  /** A real, backend-issued (or explicitly dev-issued) bearer credential is held. */
  | 'AUTHENTICATED'
  /** No credential held, or the held one was rejected by a backend 401. */
  | 'UNAUTHENTICATED'
  /** The last attempt failed for a reason other than a clean "no session". */
  | 'ERROR'
  /**
   * Authentication cannot be attempted at all: the OpenAPI contract publishes no token-issuing
   * endpoint. Distinct from UNAUTHENTICATED on purpose — "we are not logged in" and "there is
   * nowhere to log in to" are different facts and must not share a screen.
   */
  | 'UNAVAILABLE'

export interface User {
  id: string
  username: string
  displayName: string
  role: Role
  permissions: PermissionKey[]
  email?: string
}

/**
 * A bearer credential. `tokenType` is fixed to 'Bearer' because that is the only scheme
 * OPENAPI.yaml declares (`components.securitySchemes.bearerAuth: { type: http, scheme: bearer }`).
 * There is deliberately no cookie/session field: this console does not use cookie auth.
 */
export interface Session {
  readonly accessToken: string
  readonly tokenType: 'Bearer'
  /** ISO-8601 expiry, or null when the issuer did not report one. */
  readonly expiresAt: string | null
  readonly issuedAt: string
  /** Provenance. 'dev-persona' credentials are never valid against a real backend. */
  readonly source: AccessTokenSource
}

/** A non-fatal, dismissible notice about the current session. */
export interface AuthNotice {
  /**
   * 'permission_denied' - the backend refused one action with 403; the session is still valid.
   * 'revocation_incomplete' - local state was cleared but the backend could not be told.
   */
  readonly kind: 'permission_denied' | 'revocation_incomplete'
  readonly message: string
  readonly path: string
  readonly at: string
}

export interface AuthContextType {
  user: User | null
  session: Session | null
  authState: AuthState
  error: string | null
  notice: AuthNotice | null
  /** The bearer credential currently attached to protected requests, or null. */
  accessToken: string | null
  /** True when the session is a development persona, not a backend-issued credential. */
  isDevSession: boolean
  /** Which session source is active — the seam a real login API replaces. */
  sessionSourceId: SessionSourceId
  /**
   * Real sign-in. While the contract publishes no token endpoint this always rejects with
   * `AUTH_CONTRACT_NOT_PUBLISHED`; it never falls back to a dev persona.
   */
  login: (credentials: { username: string; password: string }) => Promise<void>
  /** Explicit, labelled development-only persona sign-in. Throws unless `import.meta.env.DEV`. */
  signInWithDevPersona: (personaId: string) => User
  logout: () => Promise<void>
  dismissNotice: () => void
  hasPermission: (permission: PermissionKey) => boolean
  hasAnyPermission: (permissions: readonly PermissionKey[]) => boolean
  hasAllPermissions: (permissions: readonly PermissionKey[]) => boolean
  hasRole: (role: Role | readonly Role[]) => boolean
}
