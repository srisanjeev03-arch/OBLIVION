import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AuthProvider } from './provider'
import { useAuth } from './context'
import { useAuthStore } from './store'
import { getBearerToken } from './tokenStore'
import {
  backendContractSessionSource,
  resolveSessionSource,
  type SessionSource,
} from './sessionSource'
import {
  DEV_PERSONAS,
  DEV_TOKEN_PREFIX,
  devPersonaSessionSource,
  isDevAuthEnabled,
  resolveDevPersonaSession,
} from './devAuth'
import { AUTH_CONTRACT_NOT_PUBLISHED_CODE, MISSING_AUTH_CONTRACT_ELEMENTS } from './authContract'
import { publishAuthEvent } from '@/lib/api/authEvents'
import { ApiError } from '@/lib/api/errors'
import type { AuthContextType } from './types'

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

function renderAuth(source?: SessionSource) {
  return render(
    <AuthProvider sessionSource={source}>
      <Harness />
    </AuthProvider>,
  )
}

const auth = () => {
  if (!captured) throw new Error('AuthProvider has not rendered')
  return captured
}

let fetchSpy: ReturnType<typeof vi.fn>

beforeEach(() => {
  captured = null
  useAuthStore.getState().reset()
  fetchSpy = vi.fn()
  vi.stubGlobal('fetch', fetchSpy)
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

  it('never issues a request for an unpublished auth endpoint', async () => {
    await expect(
      backendContractSessionSource.authenticate({ username: 'a', password: 'b' }),
    ).rejects.toBeInstanceOf(ApiError)
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('reports the contract gap with a stable code rather than a 404', async () => {
    let error: ApiError | null = null
    try {
      await backendContractSessionSource.authenticate({ username: 'a', password: 'b' })
    } catch (caught: unknown) {
      error = caught as ApiError
    }
    expect(error).not.toBeNull()
    expect(error?.code).toBe(AUTH_CONTRACT_NOT_PUBLISHED_CODE)
    expect(error?.kind).toBe('not_implemented')
    expect(error?.isUnavailable).toBe(true)
  })

  it('documents every missing contract element', () => {
    expect(MISSING_AUTH_CONTRACT_ELEMENTS.map((e) => e.capability)).toEqual([
      'issue-access-token',
      'resolve-current-principal',
      'revoke-session',
      'renew-access-token',
      'error-envelope-for-auth',
    ])
    for (const element of MISSING_AUTH_CONTRACT_ELEMENTS) {
      expect(element.status).toBe('ABSENT_FROM_CONTRACT')
      expect(element.requiredFields.length).toBeGreaterThan(0)
    }
  })
})

describe('development persona isolation', () => {
  it('is enabled under the test/dev gate', () => {
    expect(isDevAuthEnabled()).toBe(true)
  })

  it('mints a clearly-marked dev credential, never a JWT look-alike', () => {
    const { session } = resolveDevPersonaSession('mock-admin')
    expect(session.accessToken.startsWith(DEV_TOKEN_PREFIX)).toBe(true)
    expect(session.source).toBe('dev-persona')
    expect(session.tokenType).toBe('Bearer')
    expect(session.accessToken).not.toMatch(/^eyJ/)
  })

  it('offers exactly the five documented personas', () => {
    expect(DEV_PERSONAS).toHaveLength(5)
  })

  it('switches off entirely when the build is not DEV and not the test runner', async () => {
    // The same substitution Vite performs at build time: import.meta.env.DEV -> false.
    vi.stubEnv('DEV', false)
    vi.stubEnv('MODE', 'production')
    try {
      expect(isDevAuthEnabled()).toBe(false)
      expect(() => resolveDevPersonaSession('mock-admin')).toThrow(
        /compiled out of production builds/,
      )
      await expect(
        devPersonaSessionSource.authenticate({ username: 'mock-admin', password: '' }),
      ).rejects.toThrow(/compiled out of production builds/)
      // With no dev source available, resolution can only ever reach the backend contract.
      expect(resolveSessionSource(null)).toBe(backendContractSessionSource)
    } finally {
      vi.unstubAllEnvs()
    }
  })

  it('restores the gate after the production simulation', () => {
    expect(isDevAuthEnabled()).toBe(true)
  })
})
describe('AuthProvider', () => {
  it('mounts without an invented session and reports the contract gap', async () => {
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))
    expect(screen.getByTestId('user').textContent).toBe('none')
    expect(screen.getByTestId('token').textContent).toBe('none')
    expect(getBearerToken()).toBeNull()
  })

  it('a rejected login never falls back to a fake authenticated session', async () => {
    renderAuth(backendContractSessionSource)
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))

    await userEvent.click(screen.getByText('login'))

    await waitFor(() => expect(auth().error).toContain('no endpoint that issues'))
    expect(auth().authState).toBe('UNAVAILABLE')
    expect(auth().user).toBeNull()
    expect(auth().accessToken).toBeNull()
    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('a dev persona yields a bearer token visible to the transport, flagged as dev', async () => {
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))

    await userEvent.click(screen.getByText('persona'))

    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))
    expect(screen.getByTestId('dev').textContent).toBe('true')
    expect(screen.getByTestId('token').textContent?.startsWith(DEV_TOKEN_PREFIX)).toBe(true)
    expect(getBearerToken()?.source).toBe('dev-persona')
  })

  it('401 clears the session and the credential', async () => {
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))
    await userEvent.click(screen.getByText('persona'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    publishAuthEvent({ kind: 'unauthenticated', path: '/api/operations', status: 401 })

    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))
    expect(screen.getByTestId('token').textContent).toBe('none')
    expect(getBearerToken()).toBeNull()
    // A 401 is an error, not a notice: the session is gone, so there is nothing to dismiss.
    expect(auth().notice).toBeNull()
  })

  it('403 keeps the session and surfaces a dismissible notice instead', async () => {
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))
    await userEvent.click(screen.getByText('persona'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    publishAuthEvent({
      kind: 'forbidden',
      path: '/api/operations',
      status: 403,
      method: 'POST',
    })

    await waitFor(() => expect(screen.getByTestId('notice').textContent).toContain('(403)'))
    // The distinguishing assertion: a 403 must not log the operator out.
    expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED')
    expect(screen.getByTestId('token').textContent?.startsWith(DEV_TOKEN_PREFIX)).toBe(true)

    // Dismissing is available precisely because the session survived.
    auth().dismissNotice()
    await waitFor(() => expect(screen.getByTestId('notice').textContent).toBe('none'))
    expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED')
  })

  it('logout clears the local credential', async () => {
    renderAuth()
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('UNAVAILABLE'))
    await userEvent.click(screen.getByText('persona'))
    await waitFor(() => expect(screen.getByTestId('state').textContent).toBe('AUTHENTICATED'))

    await userEvent.click(screen.getByText('logout'))

    await waitFor(() => expect(screen.getByTestId('token').textContent).toBe('none'))
    expect(getBearerToken()).toBeNull()
    expect(screen.getByTestId('user').textContent).toBe('none')
  })
})

