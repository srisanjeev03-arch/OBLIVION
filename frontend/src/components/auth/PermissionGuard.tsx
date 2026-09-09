import type { ReactNode } from 'react'
import { useAuth } from '@/lib/auth/context'
import type { PermissionKey, Role } from '@/lib/auth/types'

export interface PermissionGuardProps {
  permission?: PermissionKey
  anyPermission?: readonly PermissionKey[]
  allPermissions?: readonly PermissionKey[]
  role?: Role | readonly Role[]
  fallback?: ReactNode
  children: ReactNode
}

/**
 * Declarative component to conditionally render children based on active user permissions or role.
 *
 * NOTE: This is for UX visibility only. The backend independently enforces authorization on all requests.
 */
export function PermissionGuard({
  permission,
  anyPermission,
  allPermissions,
  role,
  fallback = null,
  children,
}: PermissionGuardProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions, hasRole, user } = useAuth()

  if (!user) {
    return <>{fallback}</>
  }

  if (role && !hasRole(role)) {
    return <>{fallback}</>
  }

  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>
  }

  if (anyPermission && !hasAnyPermission(anyPermission)) {
    return <>{fallback}</>
  }

  if (allPermissions && !hasAllPermissions(allPermissions)) {
    return <>{fallback}</>
  }

  return <>{children}</>
}
