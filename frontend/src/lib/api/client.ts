import { env } from '@/lib/env'
import { ApiError, apiErrorFromResponse } from './errors'
import { useConnection } from './connection'
import { publishAuthEvent } from './authEvents'
import { authorizationHeaderValue } from '@/lib/auth/tokenStore'

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  /** Milliseconds. Long-running work is observed by polling, never by long requests. */
  timeoutMs?: number
  headers?: Record<string, string>
  /**
   * Defaults to true: OPENAPI.yaml applies `bearerAuth` globally, so every published path is a
   * protected path. Set false only for a genuinely public route once one is contracted.
   * Note this controls whether we ATTACH a credential, never whether we trust a response — the
   * backend remains the sole authority on who is authenticated.
   */
  requiresAuth?: boolean
}

export const DEFAULT_TIMEOUT_MS = 15_000

function mergeSignals(signals: AbortSignal[]): AbortSignal {
  const controller = new AbortController()
  for (const s of signals) {
    if (s.aborted) {
      controller.abort(s.reason)
      break
    }
    s.addEventListener('abort', () => controller.abort(s.reason), { once: true })
  }
  return controller.signal
}

/**
 * Single transport for every backend call. Normalises all failures to ApiError, never throws raw
 * fetch errors, and feeds the passive connection tracker. Aborts initiated by the caller surface
 * as `kind: 'aborted'` so callers can ignore them.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const {
    method = 'GET',
    body,
    signal,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    headers = {},
    requiresAuth = true,
  } = options

  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => timeoutController.abort('timeout'), timeoutMs)
  const combined = signal
    ? mergeSignals([signal, timeoutController.signal])
    : timeoutController.signal

  const url = `${env.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
  const connection = useConnection.getState()

  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
  }

  // Bearer transport per OPENAPI.yaml `securitySchemes.bearerAuth`. When no usable token is
  // held we still send the request rather than short-circuiting it: the backend is the authority
  // on authentication, and a real 401 is a better record than a frontend assertion. What we never
  // do is synthesise a success.
  if (requiresAuth) {
    const authorization = authorizationHeaderValue()
    if (authorization) requestHeaders.Authorization = authorization
  }

  Object.assign(requestHeaders, headers)

  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: requestHeaders,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: combined,
      // Explicit, not incidental: this console authenticates with bearer tokens only. 'omit'
      // guarantees no cookie or other ambient credential is ever attached, including on the
      // same-origin requests a Vite dev server would otherwise make credentialed.
      credentials: 'omit',
      mode: 'cors',
    })
  } catch (cause) {
    clearTimeout(timeoutId)
    if (signal?.aborted) {
      throw new ApiError({ kind: 'aborted', message: 'Request cancelled', cause })
    }
    if (timeoutController.signal.aborted) {
      const err = new ApiError({
        kind: 'timeout',
        message: `No response within ${timeoutMs} ms`,
        cause,
      })
      connection.reportFailure('request', { kind: err.kind, code: err.code })
      throw err
    }
    const err = new ApiError({ kind: 'network', message: 'Backend unreachable', cause })
    connection.reportFailure('request', { kind: err.kind, code: err.code })
    throw err
  }
  clearTimeout(timeoutId)

  if (!response.ok) {
    const err = await apiErrorFromResponse(response)
    connection.reportFailure('request', { kind: err.kind, code: err.code, status: err.status })

    // 401 and 403 are published as different events and are never collapsed into one another.
    // A 401 invalidates the credential; a 403 does not, because the operator *is* authenticated
    // and merely lacks permission for this one action.
    if (requiresAuth && err.status === 401) {
      publishAuthEvent({ kind: 'unauthenticated', path, status: 401 })
    } else if (err.status === 403) {
      publishAuthEvent({ kind: 'forbidden', path, status: 403, method })
    }

    throw err
  }

  connection.reportSuccess('request')

  if (response.status === 204 || response.headers.get('content-length') === '0') {
    return undefined as T
  }

  try {
    return (await response.json()) as T
  } catch (cause) {
    throw new ApiError({ kind: 'parse', message: 'Response body was not valid JSON', cause })
  }
}

/**
 * Optional health probe. Only runs when VITE_API_HEALTH_PATH is configured — the contract has
 * no health endpoint and the console must not invent one.
 */
export async function probeHealth(signal?: AbortSignal): Promise<boolean> {
  if (!env.apiHealthPath) return false
  const connection = useConnection.getState()
  try {
    // A health probe is conventionally public; never attach a bearer credential to it.
    await request<unknown>(env.apiHealthPath, { signal, timeoutMs: 5_000, requiresAuth: false })
    connection.reportSuccess('probe')
    return true
  } catch (error) {
    if (error instanceof ApiError && error.kind !== 'aborted') {
      connection.reportFailure('probe', {
        kind: error.kind,
        code: error.code,
        status: error.status,
      })
    }
    return false
  }
}
