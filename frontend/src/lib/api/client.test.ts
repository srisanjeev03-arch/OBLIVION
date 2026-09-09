import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { request } from './client'
import { ApiError } from './errors'
import { publishAuthEvent, subscribeToAuthEvents, type AuthEvent } from './authEvents'
import { clearBearerToken, setBearerToken } from '@/lib/auth/tokenStore'

interface FakeResponse {
  ok: boolean
  status: number
  statusText: string
  headers: { get: (name: string) => string | null }
  json: () => Promise<unknown>
}

function httpOk(body: unknown): FakeResponse {
  return {
    ok: true,
    status: 200,
    statusText: 'OK',
    headers: { get: () => null },
    json: () => Promise.resolve(body),
  }
}

function httpStatus(status: number, body: unknown = {}): FakeResponse {
  return {
    ok: false,
    status,
    statusText: String(status),
    headers: { get: () => null },
    json: () => Promise.resolve(body),
  }
}

let fetchMock: ReturnType<typeof vi.fn>
let originalFetch: typeof globalThis.fetch
let events: AuthEvent[]
let unsubscribe: (() => void) | null = null

beforeEach(() => {
  clearBearerToken()
  events = []
  unsubscribe = subscribeToAuthEvents((e) => events.push(e))

  originalFetch = globalThis.fetch
  fetchMock = vi.fn()
  globalThis.fetch = fetchMock as unknown as typeof globalThis.fetch
})

afterEach(() => {
  unsubscribe?.()
  unsubscribe = null
  globalThis.fetch = originalFetch
  clearBearerToken()
})

function sentInit(): {
  headers: Record<string, string>
  credentials: string
  mode: string
} {
  const call = fetchMock.mock.calls[0]
  if (!call) throw new Error('fetch was never called')
  return call[1] as never
}

describe('bearer transport', () => {
  it('attaches Authorization: Bearer <token> to a protected request', async () => {
    setBearerToken({ accessToken: 'real.jwt.token', expiresAt: null, source: 'backend' })
    fetchMock.mockResolvedValue(httpOk({ ok: true }))

    await request('/api/operations')

    const init = sentInit()
    expect(init.headers.Authorization).toBe('Bearer real.jwt.token')
  })

  it('sends no Authorization header when no session is held', async () => {
    fetchMock.mockResolvedValue(httpOk({ ok: true }))

    await request('/api/operations')

    expect(sentInit().headers.Authorization).toBeUndefined()
  })

  it('never attaches a credential to a request marked requiresAuth: false', async () => {
    setBearerToken({ accessToken: 'secret-token', expiresAt: null, source: 'backend' })
    fetchMock.mockResolvedValue(httpOk({ ok: true }))

    await request('/api/health', { requiresAuth: false })

    expect(sentInit().headers.Authorization).toBeUndefined()
  })

  it('treats an expired token as absent rather than sending a known-dead credential', async () => {
    setBearerToken({
      accessToken: 'expired',
      expiresAt: new Date(Date.now() - 60_000).toISOString(),
      source: 'backend',
    })
    fetchMock.mockResolvedValue(httpOk({ ok: true }))

    await request('/api/operations')

    expect(sentInit().headers.Authorization).toBeUndefined()
  })

  it('uses credentials: "omit" so no cookie is ever sent as an ambient credential', async () => {
    setBearerToken({ accessToken: 't', expiresAt: null, source: 'backend' })
    fetchMock.mockResolvedValue(httpOk({ ok: true }))

    await request('/api/operations')

    const init = sentInit()
    expect(init.credentials).toBe('omit')
    expect(init.mode).toBe('cors')
  })
})

describe('401 and 403 are handled distinctly', () => {
  it('401 reports an unauthenticated error and publishes an unauthenticated event', async () => {
    setBearerToken({ accessToken: 'rejected', expiresAt: null, source: 'backend' })
    fetchMock.mockResolvedValue(httpStatus(401, { error: { code: 'AUTH_INVALID', message: 'bad' } }))

    const error = await request('/api/operations').catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.isUnauthenticated).toBe(true)
    expect(apiError.isForbidden).toBe(false)
    expect(events.map((e) => e.kind)).toEqual(['unauthenticated'])
  })

  it('403 reports a forbidden error and publishes a forbidden event', async () => {
    setBearerToken({ accessToken: 'valid', expiresAt: null, source: 'backend' })
    fetchMock.mockResolvedValue(httpStatus(403, { error: { code: 'FORBIDDEN', message: 'no' } }))

    const error = await request('/api/operations', { method: 'POST' }).catch((e: unknown) => e)

    const apiError = error as ApiError
    expect(apiError.isForbidden).toBe(true)
    expect(apiError.isUnauthenticated).toBe(false)
    expect(events).toHaveLength(1)
    expect(events[0]?.kind).toBe('forbidden')
  })

  it('a 401 on a requiresAuth: false request does not invalidate the session', async () => {
    setBearerToken({ accessToken: 'valid', expiresAt: null, source: 'backend' })
    fetchMock.mockResolvedValue(httpStatus(401))

    await request('/api/health', { requiresAuth: false }).catch(() => undefined)

    expect(events).toHaveLength(0)
  })

  it('a failed request always rejects - no successful response is ever synthesised', async () => {
    fetchMock.mockResolvedValue(httpStatus(500))
    await expect(request('/api/operations')).rejects.toBeInstanceOf(ApiError)
  })
})

describe('auth event bus', () => {
  it('delivers published events to subscribers and unsubscribes cleanly', () => {
    const seen: AuthEvent[] = []
    const unsubscribe = subscribeToAuthEvents((e) => seen.push(e))
    publishAuthEvent({ kind: 'unauthenticated', path: '/api/x', status: 401 })
    unsubscribe()
    publishAuthEvent({ kind: 'unauthenticated', path: '/api/y', status: 401 })
    expect(seen).toHaveLength(1)
  })
})
