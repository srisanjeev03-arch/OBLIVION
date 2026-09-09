/**
 * Test-only factories.
 *
 * Centralised because `User` gained required fields when the console started consuming the
 * backend's real multi-role principal. Fixtures scattered across spec files silently drift in
 * exactly that situation; one factory means the compiler reports the drift instead.
 */
import { ROLE_DEFAULT_PERMISSIONS } from '@/lib/auth/permissions'
import type { PermissionKey, Role, User } from '@/lib/auth/types'

export function makeUser(overrides: Partial<Omit<User, 'role'>> & { role: Role }): User {
  const { role, ...rest } = overrides
  return {
    id: `usr-test-${role.toLowerCase()}`,
    username: `test-${role.toLowerCase()}`,
    displayName: `Test ${role}`,
    unrecognizedPermissions: [],
    ...rest,
    role,
    roles: rest.roles ?? [role],
    permissions: rest.permissions ?? [...ROLE_DEFAULT_PERMISSIONS[role]],
  }
}

/** Convenience: every permission a role is documented to hold, for role-scoped assertions. */
export function permissionsFor(role: Role): readonly PermissionKey[] {
  return ROLE_DEFAULT_PERMISSIONS[role]
}