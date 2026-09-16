/**
 * Certificate deep-linking, merged onto the existing verification-expectations behaviour
 * (commit 741cbbe). These specs pin both halves so a future change to either cannot silently
 * break the other:
 *
 *     a URL certificate id seeds the lookup -> the certificate is fetched and shown
 *     a form lookup updates the URL to match -> a refresh or shared link lands on the same page
 *     verification still sends the operation/target expectations, not the certificate's own claims
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router'
import type { ReactElement } from 'react'
import { Certificates } from './Certificates'
import { setBearerToken, __resetTokenStoreForTests } from '@/lib/auth/tokenStore'

const CERT_ID = 'cert_1a2b3c4d5e6f'
const OPERATION_ID = 'op_9f8e7d6c5b4a'
const TARGET_ID = 'tgt_2b3c4d5e6f7a'
const TARGET_PATH = 'D:\\scratch\\classified.txt'

const CERTIFICATE = {
  id: CERT_ID,
  operation_id: OPERATION_ID,
  evidence_digest: 'd'.repeat(64),
  certificate_version: '1',
  signing_algorithm: 'Ed25519',
  key_id: 'key_1',
  public_key: 'ab'.repeat(32),
  signature: 'cd'.repeat(64),
  claim: 'SELECTIVE_PERMANENT erasure completed',
  issued_at: '2026-01-01T00:00:00Z',
  limitations: ['No physical media sanitization is performed.'],
}

const OPERATION = { id: OPERATION_ID, target_id: TARGET_ID }
const TARGET = { id: TARGET_ID, canonical_path: TARGET_PATH, path: TARGET_PATH }

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function stubBackend() {
  const impl = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input)
    const method = (init?.method ?? 'GET').toUpperCase()

    if (method === 'GET' && url.includes(`/api/certificates/${CERT_ID}`)) {
      return Promise.resolve(jsonResponse(CERTIFICATE))
    }
    if (method === 'GET' && url.includes(`/api/operations/${OPERATION_ID}`)) {
      return Promise.resolve(jsonResponse(OPERATION))
    }
    if (method === 'GET' && url.includes(`/api/targets/${TARGET_ID}`)) {
      return Promise.resolve(jsonResponse(TARGET))
    }
    if (method === 'POST' && url.includes(`/api/certificates/${CERT_ID}/verify`)) {
      return Promise.resolve(
        jsonResponse({
          certificate_id: CERT_ID,
          overall_status: 'VALID',
          dimensions: [],
          cannot_prove: [],
          verifier_version: '1',
          verified_at: '2026-01-02T00:00:00Z',
        }),
      )
    }
    return Promise.resolve(jsonResponse({}, 404))
  })
  vi.stubGlobal('fetch', impl)
  return impl
}

/** Rendered as a sibling of the matched route, so it reflects navigation regardless of which
 * route element is on screen - the standard way to assert a component's own `navigate()` call
 * without reaching into router internals. */
function LocationProbe() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

function renderAt(initialPath: string): ReactElement {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialPath]}>
        <LocationProbe />
        <Routes>
          <Route path="/certificates" element={<Certificates />} />
          <Route path="/certificates/:certificateId" element={<Certificates />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  __resetTokenStoreForTests()
  setBearerToken({
    accessToken: 'opaque-test-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
    source: 'backend',
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  __resetTokenStoreForTests()
})

describe('a URL certificate id seeds the lookup', () => {
  it('fetches and displays the certificate named in the route', async () => {
    stubBackend()
    render(renderAt(`/certificates/${CERT_ID}`))

    await waitFor(() => expect(screen.getByText(CERT_ID)).toBeInTheDocument())
    expect(screen.getByText(OPERATION_ID)).toBeInTheDocument()
  })

  it('seeds the search input with the route id', async () => {
    stubBackend()
    render(renderAt(`/certificates/${CERT_ID}`))

    await waitFor(() =>
      expect(screen.getByLabelText(/certificate id/i)).toHaveValue(CERT_ID),
    )
  })

  it('with no route id, shows the empty state and issues no certificate request', () => {
    const impl = stubBackend()
    render(renderAt('/certificates'))

    expect(screen.getByText(/no certificate selected/i)).toBeInTheDocument()
    expect(impl).not.toHaveBeenCalled()
  })
})

describe('a form lookup updates the URL to match', () => {
  it('navigates to /certificates/<id> after a successful submit', async () => {
    stubBackend()
    render(renderAt('/certificates'))

    await userEvent.type(screen.getByLabelText(/certificate id/i), CERT_ID)
    await userEvent.click(screen.getByRole('button', { name: /retrieve/i }))

    await waitFor(() =>
      expect(screen.getByTestId('location').textContent).toBe(`/certificates/${CERT_ID}`),
    )
    await waitFor(() => expect(screen.getByText(CERT_ID)).toBeInTheDocument())
  })
})

describe('existing verification-expectations behaviour is preserved', () => {
  it('verifying sends the expectations built from the operation and target, not the certificate itself', async () => {
    const impl = stubBackend()
    render(renderAt(`/certificates/${CERT_ID}`))

    await waitFor(() => expect(screen.getByText(CERT_ID)).toBeInTheDocument())
    // Both independent records are fetched before verifying is offered as fully checked.
    await waitFor(() =>
      expect(
        screen.getByText(/checked against the operation and target records/i),
      ).toBeInTheDocument(),
    )

    await userEvent.click(screen.getByRole('button', { name: /verify at backend/i }))

    await waitFor(() => {
      const verifyCall = impl.mock.calls.find(([input, init]) => {
        const url = requestUrl(input)
        return init?.method === 'POST' && url.includes(`/api/certificates/${CERT_ID}/verify`)
      })
      expect(verifyCall).toBeDefined()
      const rawBody = verifyCall?.[1]?.body
      expect(typeof rawBody).toBe('string')
      const body: unknown = JSON.parse(rawBody as string)
      expect(body).toEqual({
        expected_operation_id: OPERATION_ID,
        expected_target_identity: TARGET_PATH,
      })
    })
  })

  it('renders the verification result once the backend responds', async () => {
    stubBackend()
    render(renderAt(`/certificates/${CERT_ID}`))

    await waitFor(() => expect(screen.getByText(CERT_ID)).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: /verify at backend/i }))

    await waitFor(() => expect(screen.queryByText(/not verified/i)).not.toBeInTheDocument())
  })
})
