import type { Role, PermissionKey, User } from './types'

/**
 * Reference role → permission mapping.
 *
 * THIS TABLE GRANTS NOTHING. It exists for exactly two purposes:
 *   1. to give the development personas in `devAuth.ts` a realistic permission set without a
 *      backend, and
 *   2. to let the tests reason about role shape.
 *
 * A real session's permissions come from `/api/auth/me` and nowhere else. The backend computes
 * them from its own `ROLE_PERMISSIONS` map and enforces them on every request; this copy is
 * allowed to disagree with it and the backend still wins. That is the point of keeping them
 * separate: hiding a control is a usability affordance, never a security boundary.
 */
export const ROLE_DEFAULT_PERMISSIONS: Readonly<Record<Role, readonly PermissionKey[]>> = {
  ADMIN: [
    // Case
    'case.create',
    'case.view',
    'case.update',
    'case.close',
    // Evidence
    'evidence.import',
    'evidence.view',
    'evidence.hash',
    'evidence.verify',
    // File erasure
    'file_erasure.request',
    'file_erasure.execute',
    // Drive sanitization
    'drive_sanitization.request',
    'drive_sanitization.execute',
    // Recovery
    'recovery.view',
    'recovery.execute',
    // Operations
    'operation.view',
    'operation.request',
    'operation.approve',
    'operation.execute',
    // Audit
    'audit.view',
    'audit.verify',
    // Reporting
    'report.export',
    // Administration
    'user.manage',
    'role.manage',
    'permission.manage',
    'system.configure',
  ],
  INVESTIGATOR: [
    // Case
    'case.create',
    'case.view',
    'case.update',
    // Evidence
    'evidence.import',
    'evidence.view',
    'evidence.hash',
    // File erasure & drive sanitization requests only (cannot approve or execute)
    'file_erasure.request',
    'drive_sanitization.request',
    // Recovery inspection
    'recovery.view',
    // Operations view & request
    'operation.view',
    'operation.request',
    // Reporting
    'report.export',
  ],
  OPERATOR: [
    // Case & Evidence view
    'case.view',
    'evidence.view',
    // Operations execution (only after approval)
    'operation.view',
    'operation.execute',
    'file_erasure.execute',
    'drive_sanitization.execute',
    // Recovery execution if authorized
    'recovery.view',
    'recovery.execute',
  ],
  AUDITOR: [
    // Independent inspection & verification
    'case.view',
    'evidence.view',
    'evidence.verify',
    'operation.view',
    'operation.verify',
    'audit.view',
    'audit.verify',
    'report.export',
  ],
  VIEWER: [
    // Read-only viewing
    'case.view',
    'evidence.view',
    'operation.view',
  ],
}

/** Check if user has a specific permission. */
export function hasPermission(user: User | null | undefined, permission: PermissionKey): boolean {
  if (!user) return false
  return user.permissions.includes(permission)
}

/** Check if user has at least one of the provided permissions. */
export function hasAnyPermission(
  user: User | null | undefined,
  permissions: readonly PermissionKey[],
): boolean {
  if (!user || permissions.length === 0) return false
  return permissions.some((p) => user.permissions.includes(p))
}

/** Check if user has all of the provided permissions. */
export function hasAllPermissions(
  user: User | null | undefined,
  permissions: readonly PermissionKey[],
): boolean {
  if (!user) return false
  if (permissions.length === 0) return true
  return permissions.every((p) => user.permissions.includes(p))
}

/**
 * Check if a user holds a role.
 *
 * Tests the full granted set, not just `user.role`: the backend can issue several roles at once,
 * and a check that looked only at the primary role would deny an action the operator is entitled
 * to. Denying on a frontend check is at least fail-closed, but it is still a bug the operator sees.
 */
export function hasRole(user: User | null | undefined, role: Role | readonly Role[]): boolean {
  if (!user) return false
  const granted: readonly Role[] = user.roles?.length ? user.roles : [user.role]
  const wanted: readonly Role[] = typeof role === 'string' ? [role] : role
  return wanted.some((r) => granted.includes(r))
}
