import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { useAuth } from '@/lib/auth/context'
import { Unauthorized } from '@/pages/Unauthorized'
import type { PermissionKey } from '@/lib/auth/types'

/**
 * Route guard for authenticated sessions.
 *
 * Redirecting here is a *usability* measure, never a security measure: the bearer token is what
 * authenticates, and the backend independently rejects every unauthenticated request with 401.
 * Removing this guard would not make a single protected resource reachable.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { authState, user } = useAuth()
  const location = useLocation()

  if (authState === 'AUTHENTICATING' || authState === 'UNKNOWN') {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-bg text-fg">
        <div className="flex flex-col items-center gap-2">
          <span className="h-6 w-6 rounded-full border-2 border-accent border-t-transparent motion-spin" />
          <span className="font-mono text-xs text-mute">RESOLVING SESSION...</span>
        </div>
      </div>
    )
  }

  // UNAVAILABLE (no published token endpoint) and UNAUTHENTICATED (credential rejected/absent)
  // both land on /login, which renders a different explanation for each. They are kept as
  // separate states in the store so that screen can tell the truth.
  if (authState === 'UNAVAILABLE' || authState === 'ERROR') {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (authState === 'UNAUTHENTICATED' || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}

/**
 * Route guard for a required permission.
 *
 * This mirrors the backend's RBAC so an operator is not offered actions they cannot perform. It is
 * presentation only — a hidden button is not a security control, and the authoritative decision is
 * the backend's 403, which `AuthProvider` handles separately by surfacing a notice while keeping
 * the session alive.
 */
export function RequirePermission({
  permission,
  children,
}: {
  permission: PermissionKey
  children: ReactNode
}) {
  const { hasPermission, user } = useAuth()

  if (!user || !hasPermission(permission)) {
    return <Unauthorized />
  }

  return <>{children}</>
}
