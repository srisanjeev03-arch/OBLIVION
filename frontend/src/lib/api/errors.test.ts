import { describe, it, expect } from 'vitest'
import { ApiError, apiErrorFromResponse, describeApiError, isApiError } from './errors'

describe('ApiError', () => {
  it('creates an ApiError with standard envelope properties', () => {
    const err = new ApiError({
      kind: 'http',
      message: 'Resource not found',
      status: 404,
      code: 'ERR_NOT_FOUND',
      requestId: 'req-1234',
    })

    expect(err.message).toBe('Resource not found')
    expect(err.status).toBe(404)
    expect(err.code).toBe('ERR_NOT_FOUND')
    expect(err.requestId).toBe('req-1234')
    expect(err.isUnavailable).toBe(true)
    expect(isApiError(err)).toBe(true)
  })

  it('identifies authorization errors correctly', () => {
    const err = new ApiError({
      kind: 'http',
      message: 'Forbidden',
      status: 403,
      code: 'ERR_FORBIDDEN',
    })

    expect(err.isAuthorization).toBe(true)
  })
})

describe('error envelope handling', () => {
  // The backend answers with a flat {error_code, message}; docs/API.md documents a nested
  // {error: {code, message}}. Reading only the documented one silently discarded every backend
  // error code, so an operator typing a wrong password was told "Unauthorized" instead of
  // "Invalid username or password".
  function responseWith(status: number, body: unknown) {
    return {
      ok: false,
      status,
      statusText: 'Unauthorized',
      headers: { get: () => null },
      json: () => Promise.resolve(body),
    } as unknown as Response
  }

  it('reads the flat envelope the backend actually sends', async () => {
    const err = await apiErrorFromResponse(
      responseWith(401, { error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password' }),
    )
    expect(err.code).toBe('INVALID_CREDENTIALS')
    expect(err.message).toBe('Invalid username or password')
    expect(err.status).toBe(401)
  })

  it('still reads the nested envelope from docs/API.md', async () => {
    const err = await apiErrorFromResponse(
      responseWith(403, {
        error: { code: 'TARGET_REVALIDATION_FAILED', message: 'The target changed.', retryable: false },
      }),
    )
    expect(err.code).toBe('TARGET_REVALIDATION_FAILED')
    expect(err.message).toBe('The target changed.')
  })

  it('invents no code when the body matches neither envelope', async () => {
    const err = await apiErrorFromResponse(responseWith(500, { detail: 'boom' }))
    expect(err.code).toBe('HTTP_ERROR')
    expect(err.message).toBe('Unauthorized')
  })

  it('surfaces the backend message for a 401 rather than a generic one', async () => {
    const err = await apiErrorFromResponse(
      responseWith(401, { error_code: 'INVALID_CREDENTIALS', message: 'Invalid username or password' }),
    )
    const summary = describeApiError(err)
    expect(summary.detail).toBe('Invalid username or password')
    expect(summary.code).toBe('INVALID_CREDENTIALS')
  })
})
