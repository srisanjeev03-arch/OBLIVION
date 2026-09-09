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

/**
 * Every permission key the backend's `Permission` enum can grant, as a runtime value.
 *
 * The union above is erased at compile time, so validating what `/api/auth/me` actually returned
 * needs the list itself. Keeping it here rather than re-deriving it means the type and the
 * validator cannot silently disagree: `auth.test.ts` asserts this array covers the union exactly.
 */
export const PERMISSION_KEYS: readonly PermissionKey[] = [
  'case.create',
  'case.view',
  'case.update',
  'case.close',
  'evidence.import',
  'evidence.view',
  'evidence.hash',
  'evidence.verify',
  'file_erasure.request',
  'file_erasure.execute',
  'drive_sanitization.request',
  'drive_sanitization.execute',
  'recovery.view',
  'recovery.execute',
  'operation.view',
  'operation.request',
  'operation.approve',
  'operation.execute',
  'operation.verify',
  'audit.view',
  'audit.verify',
  'report.export',
  'user.manage',
  'role.manage',
  'permission.manage',
  'system.configure',
] as const

export function isRole(value: string): value is Role {
  return (ROLES as readonly string[]).includes(value)
}

export function isPermissionKey(value: string): value is PermissionKey {
  return (PERMISSION_KEYS as readonly string[]).includes(value)
}

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

export interface User {
  id: string
  username: string
  displayName: string
  /**
   * Primary role, used for badge colouring and level ordering. The backend grants a SET of roles,
   * so this is the highest-privilege one rather than the only one.
   */
  role: Role
  /** Every role the backend actually granted, in descending privilege order. */
  roles: Role[]
  permissions: PermissionKey[]
  /**
   * Permission strings the backend granted that this build does not know about. Surfaced instead
   * of dropped so a backend that widens its enum shows up as a visible gap rather than a silent
   * loss of capability.
   */
  unrecognizedPermissions: string[]
  email?: string
  /** True when the backend reports the account disabled. Kept for honest display. */
  disabled?: boolean
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
