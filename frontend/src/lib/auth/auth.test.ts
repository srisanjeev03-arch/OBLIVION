import { describe, it, expect, beforeEach } from 'vitest'
import { ROLES, ROLE_METADATA, type User } from './types'
import {
  ROLE_DEFAULT_PERMISSIONS,
  hasPermission,
  hasAnyPermission,
  hasAllPermissions,
  hasRole,
} from './permissions'
import { useAuthStore } from './store'
import { DEV_PERSONAS, devLogin, devLogout, isDevAuthEnabled } from './devAuth'
import { getNavSectionsForUser } from '@/components/shell/nav'

describe('5-Role RBAC Model & Metadata', () => {
  it('defines exactly the 5 primary application roles', () => {
    expect(ROLES).toHaveLength(5)
    expect(ROLES).toEqual(['ADMIN', 'INVESTIGATOR', 'OPERATOR', 'AUDITOR', 'VIEWER'])
  })

  it('maps conceptual access levels (Levels 5 to 1) as metadata', () => {
    expect(ROLE_METADATA.ADMIN.level).toBe(5)
    expect(ROLE_METADATA.INVESTIGATOR.level).toBe(4)
    expect(ROLE_METADATA.OPERATOR.level).toBe(3)
    expect(ROLE_METADATA.AUDITOR.level).toBe(2)
    expect(ROLE_METADATA.VIEWER.level).toBe(1)
  })

  it('provides distinctive role color indicators', () => {
    expect(ROLE_METADATA.ADMIN.color).toBe('#ff3d57') // Red
    expect(ROLE_METADATA.INVESTIGATOR.color).toBe('#ff7043') // Orange
    expect(ROLE_METADATA.OPERATOR.color).toBe('#ffb020') // Amber
    expect(ROLE_METADATA.AUDITOR.color).toBe('#35c88f') // Green
    expect(ROLE_METADATA.VIEWER.color).toBe('#5b9dff') // Blue
  })
})

describe('Permission Helpers', () => {
  const sampleUser: User = {
    id: 'user-test-1',
    username: 'test.investigator',
    displayName: 'Test Investigator',
    role: 'INVESTIGATOR',
    permissions: ['case.create', 'case.view', 'file_erasure.request', 'evidence.view'],
  }

  it('evaluates hasPermission correctly', () => {
    expect(hasPermission(sampleUser, 'case.create')).toBe(true)
    expect(hasPermission(sampleUser, 'file_erasure.request')).toBe(true)
    expect(hasPermission(sampleUser, 'file_erasure.execute')).toBe(false)
    expect(hasPermission(sampleUser, 'operation.approve')).toBe(false)
    expect(hasPermission(null, 'case.create')).toBe(false)
  })

  it('evaluates hasAnyPermission correctly', () => {
    expect(hasAnyPermission(sampleUser, ['case.create', 'operation.approve'])).toBe(true)
    expect(hasAnyPermission(sampleUser, ['operation.approve', 'user.manage'])).toBe(false)
    expect(hasAnyPermission(null, ['case.create'])).toBe(false)
    expect(hasAnyPermission(sampleUser, [])).toBe(false)
  })

  it('evaluates hasAllPermissions correctly', () => {
    expect(hasAllPermissions(sampleUser, ['case.create', 'evidence.view'])).toBe(true)
    expect(hasAllPermissions(sampleUser, ['case.create', 'operation.approve'])).toBe(false)
    expect(hasAllPermissions(null, ['case.create'])).toBe(false)
    expect(hasAllPermissions(sampleUser, [])).toBe(true)
  })

  it('evaluates hasRole correctly for single and multiple roles', () => {
    expect(hasRole(sampleUser, 'INVESTIGATOR')).toBe(true)
    expect(hasRole(sampleUser, 'ADMIN')).toBe(false)
    expect(hasRole(sampleUser, ['ADMIN', 'INVESTIGATOR'])).toBe(true)
    expect(hasRole(sampleUser, ['OPERATOR', 'AUDITOR'])).toBe(false)
    expect(hasRole(null, 'INVESTIGATOR')).toBe(false)
  })
})

describe('Critical Separation of Duties (SoD) Rules', () => {
  it('INVESTIGATOR can request but cannot execute or approve', () => {
    const perms = ROLE_DEFAULT_PERMISSIONS.INVESTIGATOR
    expect(perms).toContain('file_erasure.request')
    expect(perms).toContain('operation.request')
    expect(perms).not.toContain('file_erasure.execute')
    expect(perms).not.toContain('operation.approve')
    expect(perms).not.toContain('operation.execute')
    expect(perms).not.toContain('audit.verify')
  })

  it('OPERATOR can execute approved operations but cannot approve or request independent audit verify', () => {
    const perms = ROLE_DEFAULT_PERMISSIONS.OPERATOR
    expect(perms).toContain('file_erasure.execute')
    expect(perms).toContain('operation.execute')
    expect(perms).not.toContain('operation.approve')
    expect(perms).not.toContain('audit.verify')
    expect(perms).not.toContain('user.manage')
  })

  it('AUDITOR can independently verify but cannot execute operations or manage users', () => {
    const perms = ROLE_DEFAULT_PERMISSIONS.AUDITOR
    expect(perms).toContain('audit.verify')
    expect(perms).toContain('evidence.verify')
    expect(perms).toContain('operation.verify')
    expect(perms).not.toContain('file_erasure.execute')
    expect(perms).not.toContain('operation.approve')
    expect(perms).not.toContain('operation.execute')
    expect(perms).not.toContain('user.manage')
  })

  it('VIEWER has read-only viewing permissions with all operational controls hidden', () => {
    const perms = ROLE_DEFAULT_PERMISSIONS.VIEWER
    expect(perms).toContain('case.view')
    expect(perms).toContain('evidence.view')
    expect(perms).toContain('operation.view')
    expect(perms).not.toContain('file_erasure.request')
    expect(perms).not.toContain('file_erasure.execute')
    expect(perms).not.toContain('operation.approve')
    expect(perms).not.toContain('recovery.execute')
    expect(perms).not.toContain('audit.verify')
  })

  it('ADMIN has approval and system administration authority', () => {
    const perms = ROLE_DEFAULT_PERMISSIONS.ADMIN
    expect(perms).toContain('operation.approve')
    expect(perms).toContain('user.manage')
    expect(perms).toContain('role.manage')
    expect(perms).toContain('system.configure')
  })
})

describe('Role-Aware Navigation & Workspaces', () => {
  it('filters navigation sections appropriately for VIEWER (read-only)', () => {
    const viewerUser: User = {
      id: 'v1',
      username: 'viewer',
      displayName: 'Viewer',
      role: 'VIEWER',
      permissions: [...ROLE_DEFAULT_PERMISSIONS.VIEWER],
    }

    const sections = getNavSectionsForUser(viewerUser)
    const allItems = sections.flatMap((s) => s.items)

    // Viewer should have Overview, Operations, Certificates, Assurance
    expect(allItems.some((i) => i.id === 'overview')).toBe(true)
    expect(allItems.some((i) => i.id === 'operations')).toBe(true)
    expect(allItems.some((i) => i.id === 'certificates')).toBe(true)
    expect(allItems.some((i) => i.id === 'assurance')).toBe(true)

    // Viewer should NOT have Sanitization/Erasure request or Admin
    expect(allItems.some((i) => i.id === 'erasure')).toBe(false)
    expect(allItems.some((i) => i.id === 'administration')).toBe(false)
  })

  it('filters navigation sections appropriately for INVESTIGATOR', () => {
    const invUser: User = {
      id: 'i1',
      username: 'investigator',
      displayName: 'Investigator',
      role: 'INVESTIGATOR',
      permissions: [...ROLE_DEFAULT_PERMISSIONS.INVESTIGATOR],
    }

    const sections = getNavSectionsForUser(invUser)
    const allItems = sections.flatMap((s) => s.items)

    expect(allItems.some((i) => i.id === 'targets')).toBe(true)
    expect(allItems.some((i) => i.id === 'erasure')).toBe(true)
    expect(allItems.some((i) => i.id === 'recovery')).toBe(true)
    expect(allItems.some((i) => i.id === 'residuals')).toBe(true)
    expect(allItems.some((i) => i.id === 'administration')).toBe(false)
  })

  it('returns safe fallback navigation when unauthenticated', () => {
    const sections = getNavSectionsForUser(null)
    expect(sections).toHaveLength(1)
    expect(sections[0]?.items[0]?.id).toBe('overview')
  })
})

describe('Isolated Development Auth Adapter', () => {
  beforeEach(() => {
    devLogout()
  })

  it('provides exactly 5 development personas', () => {
    expect(DEV_PERSONAS).toHaveLength(5)
    expect(DEV_PERSONAS.map((p) => p.role)).toEqual([
      'ADMIN',
      'INVESTIGATOR',
      'OPERATOR',
      'AUDITOR',
      'VIEWER',
    ])
  })

  it('authenticates mock-admin correctly in development mode', () => {
    expect(isDevAuthEnabled()).toBe(true)
    const user = devLogin('mock-admin')
    expect(user.role).toBe('ADMIN')
    expect(user.permissions).toContain('user.manage')
    expect(useAuthStore.getState().authState).toBe('AUTHENTICATED')
    expect(useAuthStore.getState().user?.role).toBe('ADMIN')
  })

  it('authenticates mock-operator correctly', () => {
    const user = devLogin('mock-operator')
    expect(user.role).toBe('OPERATOR')
    expect(user.permissions).toContain('file_erasure.execute')
    expect(user.permissions).not.toContain('operation.approve')
  })

  it('resets state on devLogout', () => {
    devLogin('mock-auditor')
    expect(useAuthStore.getState().authState).toBe('AUTHENTICATED')

    devLogout()
    expect(useAuthStore.getState().authState).toBe('UNAUTHENTICATED')
    expect(useAuthStore.getState().user).toBeNull()
  })
})
