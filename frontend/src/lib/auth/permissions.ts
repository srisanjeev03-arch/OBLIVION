import type { Role, PermissionKey, User } from './types'

/**
 * Centralized Role Permission Mapping.
 *
 * NOTE: Frontend permissions are for UX visibility and workflow ergonomics only.
 * The backend remains authoritative for all authentication, authorization, and operation validation.
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

/** Check if user matches a specific role or one of multiple roles. */
export function hasRole(user: User | null | undefined, role: Role | readonly Role[]): boolean {
  if (!user) return false
  if (Array.isArray(role)) {
    return role.includes(user.role)
  }
  return user.role === role
}
