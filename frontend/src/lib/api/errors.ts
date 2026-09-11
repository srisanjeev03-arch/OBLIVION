import { normaliseApiErrorBody } from './types'

export type ApiErrorKind =
  /** Backend capability is not implemented / not in the contract. No request was made. */
  | 'not_implemented'
  /** fetch() rejected: DNS, refused connection, CORS, offline. */
  | 'network'
  /** Our own timeout fired. */
  | 'timeout'
  /** Caller cancelled via AbortSignal. Never shown to the operator as an error. */
  | 'aborted'
  /** Backend answered with a non-2xx status. */
  | 'http'
  /** Backend answered 2xx but the body was not valid JSON. */
  | 'parse'

export interface ApiErrorInit {
  kind: ApiErrorKind
  message: string
  code?: string
  status?: number
  retryable?: boolean
  requestId?: string
  cause?: unknown
}

export class ApiError extends Error {
  readonly kind: ApiErrorKind
  /** Stable backend error code (docs/OBLIVION_DOCUMENTATION.md §10) or a client-side pseudo-code. */
  readonly code: string
  readonly status: number | undefined
  readonly retryable: boolean
  readonly requestId: string | undefined

  constructor(init: ApiErrorInit) {
    super(init.message, init.cause !== undefined ? { cause: init.cause } : undefined)
    this.name = 'ApiError'
    this.kind = init.kind
    this.code = init.code ?? defaultCodeFor(init.kind)
    this.status = init.status
    this.retryable = init.retryable ?? defaultRetryableFor(init.kind, init.status)
    this.requestId = init.requestId
  }

  /** 404/501 from an endpoint we expected means the backend has not shipped it yet. */
  get isUnavailable(): boolean {
    return this.kind === 'not_implemented' || this.status === 404 || this.status === 501
  }

  /**
   * 401 — the credential is missing, malformed or expired. The session must be cleared and the
   * operator must sign in again.
   */
  get isUnauthenticated(): boolean {
    return this.status === 401
  }

  /**
   * 403 — the credential was accepted but the backend refused this specific action. The session
   * stays valid; only the action is denied. Never redirect to sign-in on this.
   */
  get isForbidden(): boolean {
    return this.status === 403
  }

  /**
   * Aggregate of the two. Kept for callers that genuinely treat both alike (e.g. screen-state
   * mapping), but new code should prefer `isUnauthenticated` / `isForbidden` because they require
   * different handling.
   */
  get isAuthorization(): boolean {
    return this.status === 401 || this.status === 403
  }
}

function defaultCodeFor(kind: ApiErrorKind): string {
  switch (kind) {
    case 'not_implemented':
      return 'CLIENT_NOT_IMPLEMENTED'
    case 'network':
      return 'CLIENT_NETWORK'
    case 'timeout':
      return 'CLIENT_TIMEOUT'
    case 'aborted':
      return 'CLIENT_ABORTED'
    case 'http':
      return 'HTTP_ERROR'
    case 'parse':
      return 'CLIENT_PARSE'
  }
}

function defaultRetryableFor(kind: ApiErrorKind, status: number | undefined): boolean {
  if (kind === 'network' || kind === 'timeout') return true
  if (kind === 'http' && status !== undefined) return status === 429 || status >= 500
  return false
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

/** Builds an ApiError from a non-2xx Response, honouring either documented error envelope. */
export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  let body: unknown = undefined
  try {
    body = await response.json()
  } catch {
    body = undefined
  }
  const envelope = normaliseApiErrorBody(body)
  if (envelope) {
    return new ApiError({
      kind: 'http',
      status: response.status,
      code: envelope.code,
      message: envelope.message,
      retryable: envelope.retryable,
      requestId: envelope.requestId ?? response.headers.get('x-request-id') ?? undefined,
    })
  }
  return new ApiError({
    kind: 'http',
    status: response.status,
    message: response.statusText || `HTTP ${response.status}`,
    requestId: response.headers.get('x-request-id') ?? undefined,
  })
}

export interface ApiErrorSummary {
  title: string
  detail: string
  code: string
  retryable: boolean
  requestId?: string
}

/** Operator-safe summary: never leaks stack traces or raw bodies. */
export function describeApiError(error: unknown): ApiErrorSummary {
  if (isApiError(error)) {
    switch (error.kind) {
      case 'not_implemented':
        return {
          title: 'Capability unavailable',
          detail: error.message,
          code: error.code,
          retryable: false,
        }
      case 'network':
        return {
          title: 'Backend unreachable',
          detail: 'The console could not reach the backend. Check that the API is running.',
          code: error.code,
          retryable: true,
        }
      case 'timeout':
        return {
          title: 'Request timed out',
          detail: 'The backend did not respond in time.',
          code: error.code,
          retryable: true,
        }
      case 'aborted':
        return {
          title: 'Cancelled',
          detail: 'The request was cancelled.',
          code: error.code,
          retryable: false,
        }
      case 'parse':
        return {
          title: 'Unexpected response',
          detail: 'The backend returned a response the console could not read.',
          code: error.code,
          retryable: false,
        }
      case 'http':
        if (error.isUnauthenticated) {
          return {
            title: 'Session not authenticated',
            // The backend's own wording is more useful than a generic sentence, and on a login
            // attempt the generic one is simply wrong: there was no bearer credential to reject.
            detail:
              error.message?.trim() ||
              'The backend did not accept a credential for this request (401). Sign in again to obtain a new one.',
            code: error.code,
            retryable: false,
            requestId: error.requestId,
          }
        }
        if (error.isForbidden) {
          return {
            title: 'Permission denied',
            detail:
              error.message?.trim() ||
              'The backend accepted your session but refused this action (403). Your session remains valid.',
            code: error.code,
            retryable: false,
            requestId: error.requestId,
          }
        }
        return {
          title: error.isUnavailable ? 'Endpoint unavailable' : 'Backend error',
          detail: error.message,
          code: error.code,
          retryable: error.retryable,
          requestId: error.requestId,
        }
    }
  }
  return {
    title: 'Unexpected error',
    detail: 'Something went wrong in the console.',
    code: 'CLIENT_UNKNOWN',
    retryable: false,
  }
}
