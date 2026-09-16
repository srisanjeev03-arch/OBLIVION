import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { StrictMode } from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider } from './provider'
import { useAuth } from './context'
import { useAuthStore } from './store'
import { getBearerToken, __resetTokenStoreForTests } from './tokenStore'
import {
  backendContractSessionSource,
  resolveSessionSource,
  type SessionSource,
} from './sessionSource'
import {
  DEV_TOKEN_PREFIX,
  devPersonaSessionSource,
  resolveDevPersonaSession,
} from './devAuth'
import { userFromContract } from '@/lib/api/auth'
import { publishAuthEvent } from '@/lib/api/authEvents'
import type { components } from '@/lib/api/schema'
import type { AuthContextType } from './types'

/**
 * The auth boundary, tested against the real contract.
 *
 * These specs pin the properties that matter operationally: a login is an actual HTTP request with
 * the documented body and no pre-existing credential; a rejection produces a refusal and never a
 * session; the token lives only in memory; and logout distinguishes "the backend revoked it" from
 * "we forgot about it".
 */

type UserOut = components['schemas']['UserOut']

const BASE = 'http://127.0.0.1:8000'

/** Mirrors the shape observed from the running backend, including the opaque token. */
const REAL_PRINCIPAL: UserOut = {
  id: 'usr_1a2b3c4d5e6f',
  username: 'real.operator',
  roles: ['OPERATOR', 'AUDITOR'],
  permissions: ['operation.view', 'operation.execute', 'audit.view', 'evidence.view'],
  disabled: false,
  created_at: '2026-01-01T00:00:00Z',
  last_authenticated_at: null,
}

const OPAQUE_TOKEN = 'wH2kJ9mQx1T7vB4nL6pR8sY0aC3eF5gI7kM2oQ6sU8'

interface Recorded {
  url: string
  method: string
  headers: Record<string, string>
  body: unknown
}

/** A fetch stub shaped like the subset of `Response` the transport consumes. */
function responseFor(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: () => Promise.resolve(body),
  }
}

function stubBackend(handlers: Record<string, (call: Recorded) => { status: number; body: unknown }>) {
  const calls: Recorded[] = []
  const impl = vi.fn(
    (input: unknown, init?: RequestInit): Promise<ReturnType<typeof responseFor>> => {
      const url = String(input)
      const rawBody = init?.body
      const call: Recorded = {
        url,
        method: (init?.method as string) ?? 'GET',
        headers: (init?.headers as Record<string, string>) ?? {},
        // The transport always sends a JSON string, so parse it as one rather than coercing an
        // unknown BodyInit through String(), which would flatten an object to "[object Object]".
        body: typeof rawBody === 'string' ? JSON.parse(rawBody) : undefined,
      }
      calls.push(call)
      const key = `${call.method} ${url.replace(BASE, '')}`
      const handler = handlers[key]
      if (!handler) {
        return Promise.resolve(
          responseFor(404, { error_code: 'NOT_FOUND', message: `unhandled ${key}` }),
        )
      }
      const result = handler(call)
      return Promise.resolve(responseFor(result.status, result.body))
    },
  )
  vi.stubGlobal('fetch', impl)
  return { calls, impl }
}

let captured: AuthContextType | null = null

function Harness() {
  const auth = useAuth()
  captured = auth
  return (
    <div>
      <span data-testid="state">{auth.authState}</span>
      <span data-testid="user">{auth.user?.displayName ?? 'none'}</span>
      <span data-testid="token">{auth.accessToken ?? 'none'}</span>
      <span data-testid="dev">{String(auth.isDevSession)}</span>
      <span data-testid="notice">{auth.notice?.message ?? 'none'}</span>
      <button type="button" onClick={() => auth.signInWithDevPersona('usr-dev-admin')}>
        persona
      </button>
      <button
        type="button"
        onClick={() => {
          // The provider re-throws so callers can react; the real Login page catches it too.
          auth.login({ username: 'real.operator', password: 'hunter2' }).catch(() => undefined)
        }}
      >
        login
      </button>
      <button type="button" onClick={() => void auth.logout()}>
        logout
      </button>
    </div>
  )
}

async function renderAuth(source?: SessionSource) {
  // Deliberately rendered with no QueryClientProvider ancestor: AuthProvider must not acquire a
  // React Query dependency. Cache clearing lives in app/SessionCacheBoundary instead.
  render(
    <AuthProvider sessionSource={source}>
      <Harness />
    </AuthProvider>,
  )
  // Settle the mount-time restore promise inside act() so no state update escapes into a bare
  // microtask; every test below starts from the same known resting state.
  await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAUTHENTICATED'))
}

const auth = () => {
  if (!captured) throw new Error('AuthProvider has not rendered')
  return captured
}

/**
 * A session expiry that is always in the future.
 *
 * This was previously the literal `'2026-09-10T12:00:00Z'`, which made the suite a time bomb: the
 * transport deliberately refuses to attach a credential it already knows is expired, so once that
 * timestamp passed, the logout test began failing against a *correct* transport. The date, not the
 * code, was wrong. Anchoring the fixture to the clock keeps the test asserting the property it
 * means - a live credential is attached - rather than asserting what day it is.
 */
const FUTURE_EXPIRY = new Date(Date.now() + 60 * 60 * 1000).toISOString()

const loginHandler = {
  'POST /api/auth/login': () => ({
    status: 200,
    body: {
      access_token: OPAQUE_TOKEN,
      token_type: 'bearer',
      expires_at: FUTURE_EXPIRY,
      user: REAL_PRINCIPAL,
    },
  }),
  'POST /api/auth/logout': () => ({
    status: 200,
    body: { status: 'COMPLETED', message: 'Session successfully terminated' },
  }),
  'GET /api/auth/me': () => ({ status: 200, body: REAL_PRINCIPAL }),
}

beforeEach(() => {
  captured = null
  useAuthStore.getState().reset()
  __resetTokenStoreForTests()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('session source seam', () => {
  it('resolves to the backend contract source when no dev source is offered', () => {
    expect(resolveSessionSource(null)).toBe(backendContractSessionSource)
  })

  it('accepts a source that declares itself development-only', () => {
    expect(resolveSessionSource(devPersonaSessionSource)).toBe(devPersonaSessionSource)
  })

  it('refuses to substitute a non-development source for the backend', () => {
    const impostor: SessionSource = {
      id: 'backend-contract',
      label: 'impostor',
      isDevelopmentOnly: false,
      restore: () => Promise.resolve(null),
      authenticate: () => Promise.reject(new Error('nope')),
      revoke: () => Promise.resolve(),
    }
    expect(() => resolveSessionSource(impostor)).toThrow(/isDevelopmentOnly/)
  })

  it('authenticate issues a real login request carrying no prior credential', async () => {
    const { calls } = stubBackend(loginHandler)

    const resolved = await backendContractSessionSource.authenticate({
      username: 'real.operator',
      password: 'hunter2',
    })

    const call = calls.find((c) => c.url.endsWith('/api/auth/login'))
    expect(call).toBeDefined()
    expect(call?.method).toBe('POST')
    // The request that mints a credential must not attach one.
    expect(call?.headers.Authorization).toBeUndefined()
    expect(call?.body).toEqual({ username: 'real.operator', password: 'hunter2' })

    expect(resolved.session.accessToken).toBe(OPAQUE_TOKEN)
    expect(resolved.session.source).toBe('backend')
    expect(resolved.session.tokenType).toBe('Bearer')
  })

  it('maps the backend principal, including every granted role', async () => {
    stubBackend(loginHandler)
    const resolved = await backendContractSessionSource.authenticate({
      username: 'real.operator',
      password: 'hunter2',
    })

    // Roles are ordered by privilege, so the primary role is the highest one held, while the full
    // set survives for permission checks.
    expect(resolved.user.role).toBe('OPERATOR')
    expect(resolved.user.roles).toEqual(['OPERATOR', 'AUDITOR'])
    expect(resolved.user.permissions).toContain('operation.execute')
    expect(resolved.user.unrecognizedPermissions).toEqual([])
  })

  it('carries the server-set expiry rather than inventing one', async () => {
    stubBackend(loginHandler)
    const resolved = await backendContractSessionSource.authenticate({
      username: 'real.operator',
      password: 'hunter2',
    })
    expect(resolved.session.expiresAt).toBe(FUTURE_EXPIRY)
  })

  it('does not attach a credential it already knows has expired', async () => {
    // The complement of the test below, and the property that made the stale
    // fixture look like a transport bug. Sending a dead token would turn a
    // clear "no session" into a confusing 401 from the server.
    const { calls } = stubBackend(loginHandler)
    const { session } = await backendContractSessionSource.authenticate({
      username: 'real.operator',
      password: 'hunter2',
    })
    useAuthStore.getState().setSession({
      ...session,
      expiresAt: new Date(Date.now() - 1000).toISOString(),
    })

    await backendContractSessionSource.revoke()

    const call = calls.find((c) => c.url.endsWith('/api/auth/logout'))
    expect(call?.headers.Authorization).toBeUndefined()
  })

  it('revoke posts to the logout endpoint with the bearer credential attached', async () => {
    const { calls } = stubBackend(loginHandler)
    const { session } = await backendContractSessionSource.authenticate({
      username: 'real.operator',
      password: 'hunter2',
    })
    // The transport reads the credential from the token store, so it must be published first.
    useAuthStore.getState().setSession(session)

    await backendContractSessionSource.revoke()

    const call = calls.find((c) => c.url.endsWith('/api/auth/logout'))
    expect(call?.method).toBe('POST')
    expect(call?.headers.Authorization).toBe(`Bearer ${OPAQUE_TOKEN}`)
  })

  it('restore issues no request: a memory-only credential cannot survive a reload', async () => {
    const { impl } = stubBackend(loginHandler)
    await expect(backendContractSessionSource.restore()).resolves.toBeNull()
    expect(impl).not.toHaveBeenCalled()
  })

  it('refuses a credential the transport cannot carry', async () => {
    stubBackend({
      ...loginHandler,
      'POST /api/auth/login': () => ({
        status: 200,
        body: {
          access_token: OPAQUE_TOKEN,
          token_type: 'cookie',
          expires_at: '2026-09-10T12:00:00Z',
          user: REAL_PRINCIPAL,
        },
      }),
    })

    await expect(
      backendContractSessionSource.authenticate({ username: 'a', password: 'b' }),
    ).rejects.toThrow(/only transports HTTP bearer tokens/)
  })
})

describe('principal mapping is defensive about backend strings', () => {
  it('preserves an unrecognised permission instead of dropping it silently', () => {
    const user = userFromContract({
      ...REAL_PRINCIPAL,
      permissions: ['operation.view', 'quantum.erase'],
    })
    expect(user.permissions).toEqual(['operation.view'])
    expect(user.unrecognizedPermissions).toEqual(['quantum.erase'])
  })

  it('falls back to VIEWER when the backend grants no known role', () => {
    const user = userFromContract({ ...REAL_PRINCIPAL, roles: [] })
    expect(user.role).toBe('VIEWER')
    expect(user.roles).toEqual(['VIEWER'])
  })

  it('ignores a role string this build does not model', () => {
    const user = userFromContract({ ...REAL_PRINCIPAL, roles: ['SUPERUSER', 'AUDITOR'] })
    expect(user.roles).toEqual(['AUDITOR'])
  })
})

describe('dev persona isolation', () => {
  it('produces a token that cannot be mistaken for a backend credential', () => {
    const { session } = resolveDevPersonaSession('usr-dev-admin')
    expect(session.accessToken.startsWith(DEV_TOKEN_PREFIX)).toBe(true)
    expect(session.source).toBe('dev-persona')
  })
})


describe('provider auth boundary', () => {
  it('settles the mount-time restore under StrictMode instead of hanging', async () => {
    // StrictMode mounts, unmounts and re-mounts. A once-only guard kept in a ref skipped the
    // second restore while the first was discarded as cancelled, so the console never left
    // AUTHENTICATING.
    const restore = vi.fn(() => Promise.resolve(null))
    render(
      <StrictMode>
        <AuthProvider sessionSource={{ ...backendContractSessionSource, restore }}>
          <Harness />
        </AuthProvider>
      </StrictMode>,
    )
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAUTHENTICATED'))
    expect(restore).toHaveBeenCalled()
    expect(getBearerToken()).toBeNull()
  })

  it('starts unauthenticated without calling any auth endpoint', async () => {
    const { calls } = stubBackend(loginHandler)
    await renderAuth(backendContractSessionSource)

    expect(calls).toHaveLength(0)
    expect(getBearerToken()).toBeNull()
  })

  it('a successful login authenticates with the backend principal', async () => {
    stubBackend(loginHandler)
    await renderAuth(backendContractSessionSource)

    await userEvent.click(screen.getByText('login'))

    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))
    expect(screen.getByTestId('token').textContent).toBe(OPAQUE_TOKEN)
    expect(screen.getByTestId('dev').textContent).toBe('false')
    expect(getBearerToken()?.source).toBe('backend')
    expect(auth().user?.roles).toEqual(['OPERATOR', 'AUDITOR'])
  })

  it('never persists the credential to browser storage', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    stubBackend(loginHandler)
    await renderAuth(backendContractSessionSource)
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    expect(setItem).not.toHaveBeenCalled()
    setItem.mockRestore()
  })

  it('a rejected credential is a refusal, not a session', async () => {
    stubBackend({
      ...loginHandler,
      'POST /api/auth/login': () => ({
        status: 401,
        body: { error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password' },
      }),
    })
    await renderAuth(backendContractSessionSource)

    await userEvent.click(screen.getByText('login'))

    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('ERROR'))
    expect(auth().error).toContain('Invalid username or password')
    expect(auth().user).toBeNull()
    expect(auth().accessToken).toBeNull()
    expect(getBearerToken()).toBeNull()
  })

  it('a rejected login never falls back to a fake authenticated session', async () => {
    stubBackend({
      ...loginHandler,
      'POST /api/auth/login': () => ({
        status: 401,
        body: { error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password' },
      }),
    })
    await renderAuth(backendContractSessionSource)

    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('ERROR'))

    expect(screen.getByTestId('dev').textContent).toBe('false')
    expect(screen.getByTestId('token').textContent).toBe('none')
  })

  it('a dev persona yields a bearer token visible to the transport, flagged as dev', async () => {
    stubBackend(loginHandler)
    await renderAuth()

    await userEvent.click(screen.getByText('persona'))

    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))
    expect(screen.getByTestId('dev').textContent).toBe('true')
    expect(screen.getByTestId('token').textContent?.startsWith(DEV_TOKEN_PREFIX)).toBe(true)
    expect(getBearerToken()?.source).toBe('dev-persona')
  })

  it('401 clears the session and the credential', async () => {
    stubBackend(loginHandler)
    await renderAuth()
    await userEvent.click(screen.getByText('persona'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    act(() => publishAuthEvent({ kind: 'unauthenticated', path: '/api/operations', status: 401 }))

    expect(screen.getByTestId('token').textContent).toBe('none')
    expect(getBearerToken()).toBeNull()
    // A 401 is an error, not a notice: the session is gone, so there is nothing to dismiss.
    expect(auth().notice).toBeNull()
  })

  it('403 keeps the session and surfaces a dismissible notice instead', async () => {
    stubBackend(loginHandler)
    await renderAuth()
    await userEvent.click(screen.getByText('persona'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    act(() =>
      publishAuthEvent({
        kind: 'forbidden',
        path: '/api/operations',
        status: 403,
        method: 'POST',
      }),
    )

    await waitFor(() => expect(screen.getByTestId('notice').textContent).toContain('(403)'))
    // The distinguishing assertion: a 403 must not log the operator out.
    expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED')
    expect(screen.getByTestId('token').textContent?.startsWith(DEV_TOKEN_PREFIX)).toBe(true)

    auth().dismissNotice()
    await waitFor(() => expect(screen.getByTestId('notice').textContent).toBe('none'))
    expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED')
  })

  it('logout revokes at the backend and clears the local credential', async () => {
    const { calls } = stubBackend(loginHandler)
    await renderAuth(backendContractSessionSource)
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    await userEvent.click(screen.getByText('logout'))

    await waitFor(() => expect(screen.getByTestId('token').textContent).toBe('none'))
    expect(getBearerToken()).toBeNull()
    expect(screen.getByTestId('user').textContent).toBe('none')
    expect(calls.some((c) => c.url.endsWith('/api/auth/logout'))).toBe(true)
    // Revocation succeeded, so there is nothing to warn about.
    expect(screen.getByTestId('notice').textContent).toBe('none')
  })

  it('when revocation fails the operator is told the token may still be live', async () => {
    stubBackend({
      ...loginHandler,
      'POST /api/auth/logout': () => ({ status: 500, body: { error_code: 'INTERNAL_ERROR' } }),
    })
    await renderAuth(backendContractSessionSource)
    await userEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    await userEvent.click(screen.getByText('logout'))

    // Local state is still cleared - but only clearing is exactly what must not be called a logout.
    await waitFor(() => expect(screen.getByTestId('token').textContent).toBe('none'))
    await waitFor(() =>
      expect(screen.getByTestId('notice').textContent).toContain('may still be accepted'),
    )
    expect(auth().notice?.kind).toBe('revocation_incomplete')
  })
})



