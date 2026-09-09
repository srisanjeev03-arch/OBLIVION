import { describe, it, expect } from 'vitest'
import { ApiError, isApiError } from './errors'

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
