import type { User, Role, PermissionKey, Session } from './types'
import { ROLE_DEFAULT_PERMISSIONS } from './permissions'
import { useAuthStore } from './store'
import type { ResolvedSession, SessionSource } from './sessionSource'
import { ApiError } from '@/lib/api/errors'

/**
 * Isolated Development Persona Adapter.
 *
 * SAFETY PROPERTIES (all enforced, none configurable):
 *   1. Gated exclusively on `import.meta.env.DEV` (or the vitest MODE). Vite statically replaces
 *      `import.meta.env.DEV` with `false` in production builds, so every branch below is
 *      dead-code-eliminated from the shipped bundle. There is deliberately NO `VITE_MOCK_AUTH`
 *      escape hatch: a build-time env var can be set by whoever controls the build environment,
 *      which would turn a "development only" door into a production backdoor.
 *   2. Personas are reachable ONLY through `signInWithDevPersona()` — an explicit action on a
 *      labelled control. `login()` never routes here, so a failed real authentication request can
 *      never silently become a fake authenticated session.
 *   3. Tokens are prefixed `dev-persona:` and are structurally unlike a JWT, so they cannot be
 *      mistaken for a real credential in logs or network traces.
 *   4. Nothing is persisted. The session dies with the document.
 *   5. `DEV_SESSION_BANNER` must be rendered while such a session is live.
 */

export const DEV_SESSION_BANNER =
  'DEVELOPMENT PERSONA — this session was created in the browser and was never authenticated by the backend.' as const

/** Marks a token as unambiguously non-production and non-reusable. */
export const DEV_TOKEN_PREFIX = 'dev-persona:'

export interface DevPersona {
  readonly id: string
  readonly username: string
  readonly displayName: string
  readonly role: Role
  readonly level: number
  readonly description: string
  readonly permissions: readonly PermissionKey[]
}

export const DEV_PERSONAS: readonly DevPersona[] = [
  {
    id: 'usr-dev-admin',
    username: 'mock-admin',
    displayName: 'Dr. Sarah Connor (SecAdmin)',
    role: 'ADMIN',
    level: 5,
    description: 'Level 5 — System administration, security governance & approval authority',
    permissions: ROLE_DEFAULT_PERMISSIONS.ADMIN,
  },
  {
    id: 'usr-dev-investigator',
    username: 'mock-investigator',
    displayName: 'Alex Morgan (Investigator)',
    role: 'INVESTIGATOR',
    level: 4,
    description: 'Level 4 — Evidence discovery, case profiling & deletion requests',
    permissions: ROLE_DEFAULT_PERMISSIONS.INVESTIGATOR,
  },
  {
    id: 'usr-dev-operator',
    username: 'mock-operator',
    displayName: 'David Kim (Operator)',
    role: 'OPERATOR',
    level: 3,
    description: 'Level 3 — Execution of approved forensic erasure operations',
    permissions: ROLE_DEFAULT_PERMISSIONS.OPERATOR,
  },
  {
    id: 'usr-dev-auditor',
    username: 'mock-auditor',
    displayName: 'Elena Rostova (Auditor)',
    role: 'AUDITOR',
    level: 2,
    description: 'Level 2 — Independent audit log verification & certificate proof review',
    permissions: ROLE_DEFAULT_PERMISSIONS.AUDITOR,
  },
  {
    id: 'usr-dev-viewer',
    username: 'mock-viewer',
    displayName: 'Public Stakeholder (Viewer)',
    role: 'VIEWER',
    level: 1,
    description: 'Level 1 — Read-only assurance and certificate viewing',
    permissions: ROLE_DEFAULT_PERMISSIONS.VIEWER,
  },
] as const

/**
 * Whether the development persona adapter is available.
 * Driven by `import.meta.env.DEV` alone — plus the test mode so unit tests can exercise the
 * adapter. There is no production configuration that enables this.
 */
export function isDevAuthEnabled(): boolean {
  return import.meta.env.DEV || import.meta.env.MODE === 'test'
}

/** Throws a stable error when called from a production build. */
function assertDevAuthEnabled(): void {
  if (!isDevAuthEnabled()) {
    throw new ApiError({
      kind: 'not_implemented',
      code: 'DEV_AUTH_DISABLED_IN_PRODUCTION',
      message: 'Development personas are compiled out of production builds.',
    })
  }
}

function findPersona(usernameOrId: string): DevPersona | undefined {
  const clean = usernameOrId.trim().toLowerCase()
  return DEV_PERSONAS.find(
    (p) =>
      p.username.toLowerCase() === clean ||
      p.id.toLowerCase() === clean ||
      p.role.toLowerCase() === clean,
  )
}

function toUser(persona: DevPersona): User {
  return {
    id: persona.id,
    username: persona.username,
    displayName: persona.displayName,
    role: persona.role,
    roles: [persona.role],
    permissions: [...persona.permissions],
    // Dev personas are assembled from this file's own table, never from the backend, so there is
    // nothing unrecognised to report. The field stays to keep the dev and real shapes identical.
    unrecognizedPermissions: [],
    email: `${persona.username}@oblivion.local`,
  }
}

function toDevSession(persona: DevPersona): Session {
  const now = Date.now()
  return {
    accessToken: `${DEV_TOKEN_PREFIX}${persona.role.toLowerCase()}-${now}`,
    tokenType: 'Bearer',
    issuedAt: new Date(now).toISOString(),
    expiresAt: new Date(now + 8 * 3600 * 1000).toISOString(),
    source: 'dev-persona',
  }
}

/** Builds a dev persona session without touching the store — used by the session source. */
export function resolveDevPersonaSession(usernameOrId: string): ResolvedSession {
  assertDevAuthEnabled()
  const persona = findPersona(usernameOrId)
  if (!persona) {
    throw new Error(`Development persona not found: ${usernameOrId}`)
  }
  return { user: toUser(persona), session: toDevSession(persona) }
}

/** Converts a synchronous failure into a rejection so the interface contract holds. */
function attempt<T>(run: () => T): Promise<T> {
  try {
    return Promise.resolve(run())
  } catch (reason) {
    return Promise.reject(
      reason instanceof Error ? reason : new Error(`Dev persona resolution failed: ${String(reason)}`),
    )
  }
}

/**
 * The `SessionSource` the dev personas occupy. `restore()` returns null: even in development a
 * reload must be an explicit re-selection, never an implicit resume of a fake identity.
 */
export const devPersonaSessionSource: SessionSource = {
  id: 'dev-persona',
  label: 'DEV persona (browser-local)',
  isDevelopmentOnly: true,
  restore: () => Promise.resolve(null),
  authenticate: (credentials) => attempt(() => resolveDevPersonaSession(credentials.username)),
  // Nothing server-side exists to revoke; clearing local state is the whole operation.
  revoke: () => Promise.resolve(),
}

/** Authenticates a development persona directly into the store. */
export function devLogin(usernameOrId: string): User {
  const { user, session } = resolveDevPersonaSession(usernameOrId)
  const store = useAuthStore.getState()
  store.setUser(user)
  store.setSession(session)
  store.setAuthState('AUTHENTICATED')
  store.setError(null)
  return user
}

/** Clears simulated session state. */
export function devLogout(): void {
  useAuthStore.getState().reset()
}

/** Returns available development personas. */
export function getDevPersonas(): readonly DevPersona[] {
  return DEV_PERSONAS
}
