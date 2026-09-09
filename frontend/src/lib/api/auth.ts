/**
 * Auth API boundary.
 *
 * Talks to the three auth operations the backend publishes and was observed serving:
 * `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`.
 *
 * Everything here is transport and mapping. No request is constructed by hand: the shared
 * `request()` client owns the base URL, bearer attachment, timeout, error normalisation and the
 * 401/403 event publication, so this module cannot accidentally create a second auth mechanism.
 *
 * The token is opaque. It is never parsed, and no claim is read from it - the backend stores only
 * its SHA-256 digest, so anything that looked like a JWT here would be a bug waiting to misfire.
 */
import { request } from './client'
import { ApiError } from './errors'
import type { components } from './schema'
import { isPermissionKey, isRole, ROLE_METADATA } from '@/lib/auth/types'
import type { PermissionKey, Role, Session, User } from '@/lib/auth/types'

type LoginResponse = components['schemas']['LoginResponse']
type UserOut = components['schemas']['UserOut']

export interface AuthenticatedSession {
  user: User
  session: Session
}

/**
 * Map the backend principal onto the console's `User`.
 *
 * Unknown strings are preserved in `unrecognizedPermissions` rather than dropped, so a backend that
 * widens its enum produces a visible gap instead of a silently reduced capability set. Roles are
 * ordered by privilege so `role` is the highest one, which is what badges and level ordering expect.
 */
export function userFromContract(out: UserOut): User {
  const grantedRoles: Role[] = (out.roles ?? []).filter(isRole)
  const fallback: Role[] = ['VIEWER']
  const roles: Role[] = (grantedRoles.length > 0 ? grantedRoles : fallback)
    .slice()
    .sort((a, b) => ROLE_METADATA[b].level - ROLE_METADATA[a].level)

  const rawPermissions: string[] = out.permissions ?? []
  const permissions: PermissionKey[] = rawPermissions.filter(isPermissionKey)
  const unrecognizedPermissions = rawPermissions.filter((p) => !isPermissionKey(p))

  return {
    id: out.id,
    username: out.username,
    displayName: out.username,
    role: roles[0] ?? 'VIEWER',
    roles,
    permissions,
    unrecognizedPermissions,
    disabled: out.disabled,
  }
}

/**
 * Exchange credentials for a bearer session.
 *
 * `requiresAuth: false` because this is the request that *produces* a credential - attaching a
 * previous one would be wrong, and the contract marks the path unsecured for exactly that reason.
 */
export async function login(credentials: {
  username: string
  password: string
}): Promise<AuthenticatedSession> {
  const body = await request<LoginResponse>('/api/auth/login', {
    method: 'POST',
    body: credentials,
    requiresAuth: false,
  })

  // Refuse a credential we cannot transport correctly rather than store it and fail later with a
  // confusing 401. The contract fixes the scheme to bearer; anything else means the backend changed
  // underneath us and the operator deserves a clear message.
  if (body.token_type.toLowerCase() !== 'bearer') {
    throw new ApiError({
      kind: 'parse',
      code: 'UNEXPECTED_TOKEN_TYPE',
      message:
        `Backend issued a credential of type "${body.token_type}", but this console only transports ` +
        'HTTP bearer tokens. Refusing to start a session that could not be authenticated.',
    })
  }

  if (!body.access_token) {
    throw new ApiError({
      kind: 'parse',
      code: 'EMPTY_ACCESS_TOKEN',
      message: 'Backend returned a successful login with no access token.',
    })
  }

  const issuedAt = new Date().toISOString()
  const session: Session = {
    accessToken: body.access_token,
    tokenType: 'Bearer',
    expiresAt: body.expires_at ?? null,
    issuedAt,
    source: 'backend',
  }

  return { user: userFromContract(body.user), session }
}

/**
 * Re-resolve the principal behind the credential already held.
 *
 * Returns the user only: the bearer token is the caller's existing in-memory credential and this
 * request must not mint or replace one.
 */
export function fetchCurrentUser(): Promise<User> {
  return request<UserOut>('/api/auth/me').then(userFromContract)
}

/**
 * Revoke the active session server-side.
 *
 * This genuinely invalidates the credential at the backend - verified: after a 200 logout, the same
 * token yields 401 SESSION_INVALID on `/api/auth/me`. Clearing local state is not a logout, which
 * is why the provider treats a rejection here as a real failure rather than swallowing it.
 */
export async function logout(): Promise<void> {
  await request<components['schemas']['LogoutResponse']>('/api/auth/logout', {
    method: 'POST',
  })
}
