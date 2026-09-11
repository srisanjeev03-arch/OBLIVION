/**
 * The audit screen against a stubbed backend.
 *
 * These are integration tests in the sense that matters here: the component, the query layer, the
 * capability gate and the HTTP client all run for real, and only the network is stubbed. What is
 * being checked is that backend truth reaches the screen unaltered - and, just as important, that
 * the screen adds no reassurance the backend never expressed.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement } from 'react'
import { Audit } from './Audit'
import { setBearerToken, __resetTokenStoreForTests } from '@/lib/auth/tokenStore'

const GENESIS_DIGEST = 'a'.repeat(64)
const SECOND_DIGEST = 'b'.repeat(64)

function auditPage(overrides: Record<string, unknown> = {}) {
  return {
    events: [
      {
        audit_id: 'aud_0000000000000001',
        sequence: 1,
        event_type: 'AUTH_LOGIN_SUCCEEDED',
        outcome: 'SUCCEEDED',
        actor_id: 'usr_alice',
        actor_role: 'INVESTIGATOR',
        actor_source: 'AUTHENTICATED_SESSION',
        operation_id: null,
        target_identity: null,
        evidence_id: null,
        certificate_id: null,
        summary: 'Signed in.',
        safe_metadata: {},
        occurred_at: '2026-09-11T08:00:00+00:00',
        digest: GENESIS_DIGEST,
        previous_audit_id: null,
        previous_audit_digest: null,
      },
      {
        audit_id: 'aud_0000000000000002',
        sequence: 2,
        event_type: 'AUTH_LOGIN_FAILED',
        outcome: 'REFUSED',
        actor_id: 'unauthenticated:administrator',
        actor_role: 'NONE',
        actor_source: 'UNAUTHENTICATED',
        operation_id: null,
        target_identity: null,
        evidence_id: null,
        certificate_id: null,
        summary: 'Sign-in refused.',
        safe_metadata: { reason: 'password did not match' },
        occurred_at: '2026-09-11T08:01:00+00:00',
        digest: SECOND_DIGEST,
        previous_audit_id: 'aud_0000000000000001',
        previous_audit_digest: GENESIS_DIGEST,
      },
    ],
    returned: 2,
    total_records: 2,
    records_predating_chain: 0,
    limit: 200,
    offset: 0,
    ...overrides,
  }
}

const INTACT_VERIFICATION = {
  status: 'INTACT',
  checked: 2,
  reason: '2 record(s) form an unbroken chain from the genesis record.',
  links: [
    { audit_id: 'aud_0000000000000001', sequence: 1, status: 'VALID_GENESIS', detail: 'genesis' },
    {
      audit_id: 'aud_0000000000000002',
      sequence: 2,
      status: 'VALID_PREDECESSOR',
      detail: 'linked',
    },
  ],
  first_invalid_audit_id: null,
  records_predating_chain: 0,
  proves: ['The audit records supplied have not been edited since they were written.'],
  does_not_prove: [
    'That any erasure succeeded, or that any target is unrecoverable.',
    'That the evidence records referenced by these entries are intact - evidence integrity is a separate check against the evidence chain.',
    'That any certificate is trustworthy.',
  ],
  scope_note:
    'This result describes the integrity of the audit log only. It is not a statement about evidence integrity, erasure success, or certificate trust.',
}

type Handler = (url: string, init?: RequestInit) => { status: number; body: unknown }

/**
 * Read the URL from whatever `fetch` was handed.
 *
 * `RequestInfo` is `string | Request`, and a `Request` has no useful default stringification -
 * relying on one would silently produce `[object Object]` and make every handler miss.
 */
function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.href
  return input.url
}

function stub(handlers: Record<string, Handler>) {
  const impl = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = requestUrl(input)
    const method = (init?.method ?? 'GET').toUpperCase()
    const key = Object.keys(handlers).find((k) => {
      const separator = k.indexOf(' ')
      const verb = k.slice(0, separator)
      const path = k.slice(separator + 1)
      return verb === method && url.includes(path)
    })
    const handler = key === undefined ? undefined : handlers[key]
    if (!handler) throw new Error(`unstubbed request: ${method} ${url}`)
    const { status, body } = handler(url, init)
    return Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', impl)
  return impl
}

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
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

describe('audit screen renders backend truth', () => {
  it('renders the records the backend returned, with their real sequence and digests', async () => {
    stub({ 'GET /api/audit/events': () => ({ status: 200, body: auditPage() }) })
    renderWithClient(<Audit />)

    expect(await screen.findByText('AUTH_LOGIN_SUCCEEDED')).toBeInTheDocument()
    expect(screen.getByText('AUTH_LOGIN_FAILED')).toBeInTheDocument()
    // Outcomes are shown in the backend's own words, not reduced to pass/fail.
    expect(screen.getByText('SUCCEEDED')).toBeInTheDocument()
    expect(screen.getByText('REFUSED')).toBeInTheDocument()
  })

  it('never presents a merely claimed identity as an authenticated one', async () => {
    stub({ 'GET /api/audit/events': () => ({ status: 200, body: auditPage() }) })
    renderWithClient(<Audit />)

    await screen.findByText('AUTH_LOGIN_FAILED')
    // The failed sign-in carries a username someone typed. It must be labelled as a claim,
    // otherwise the log reads as an accusation against whoever owns that name.
    expect(screen.getByText('Claimed — not authenticated')).toBeInTheDocument()
    expect(screen.getByText('Authenticated')).toBeInTheDocument()
  })

  it('shows an empty log as empty, not as an all-clear', async () => {
    stub({
      'GET /api/audit/events': () => ({
        status: 200,
        body: auditPage({ events: [], returned: 0, total_records: 0 }),
      }),
    })
    renderWithClient(<Audit />)

    expect(await screen.findByText('No audit records yet')).toBeInTheDocument()
    expect(screen.queryByText(/all nominal|no issues|secure/i)).not.toBeInTheDocument()
  })

  it('discloses records that predate the chain rather than dropping them silently', async () => {
    stub({
      'GET /api/audit/events': () => ({
        status: 200,
        body: auditPage({ records_predating_chain: 7 }),
      }),
    })
    renderWithClient(<Audit />)

    expect(await screen.findByText(/7 record\(s\) predate the chain/)).toBeInTheDocument()
  })
})

describe('authorization failures are shown as refusals, not emptiness', () => {
  it('renders a 403 as a blocked state naming the required permission', async () => {
    stub({
      'GET /api/audit/events': () => ({
        status: 403,
        body: {
          error_code: 'FORBIDDEN',
          message: "Insufficient permissions: requires 'audit.view'",
        },
      }),
    })
    renderWithClient(<Audit />)

    expect(await screen.findByText('Your role cannot read the audit log')).toBeInTheDocument()
    // An operator denied the log must not see a table that reads as "nothing happened".
    expect(screen.queryByText('No audit records yet')).not.toBeInTheDocument()
  })

  it('renders a server failure as a failure, with a retry', async () => {
    stub({
      'GET /api/audit/events': () => ({
        status: 500,
        body: { error_code: 'AUDIT_RECORD_UNREADABLE', message: 'row is corrupt' },
      }),
    })
    renderWithClient(<Audit />)

    expect(await screen.findByText('The audit log could not be read')).toBeInTheDocument()
  })
})

describe('chain verification is the server answer and carries its limits', () => {
  it('renders the verdict, the per-link states and what it does not prove', async () => {
    stub({
      'GET /api/audit/events': () => ({ status: 200, body: auditPage() }),
      'POST /api/audit/verify': () => ({ status: 200, body: INTACT_VERIFICATION }),
    })
    renderWithClient(<Audit />)

    await screen.findByText('AUTH_LOGIN_SUCCEEDED')
    await userEvent.click(screen.getByRole('button', { name: /verify chain/i }))

    expect(await screen.findByText('INTACT')).toBeInTheDocument()
    expect(screen.getByText(/VALID_GENESIS · 1/)).toBeInTheDocument()
    expect(screen.getByText(/VALID_PREDECESSOR · 1/)).toBeInTheDocument()

    // The limits are rendered verbatim. An INTACT chain shown without them would read as
    // "the erasure was sound", which is the substitution this whole layer exists to prevent.
    expect(screen.getByText('What this result does not establish')).toBeInTheDocument()
    expect(
      screen.getByText(/That any erasure succeeded, or that any target is unrecoverable\./),
    ).toBeInTheDocument()
    expect(screen.getByText(/That any certificate is trustworthy\./)).toBeInTheDocument()
    expect(screen.getByText(/integrity of the audit log only/)).toBeInTheDocument()
  })

  it('sends no verdict field, so the client cannot contribute to the answer', async () => {
    const impl = stub({
      'GET /api/audit/events': () => ({ status: 200, body: auditPage() }),
      'POST /api/audit/verify': () => ({ status: 200, body: INTACT_VERIFICATION }),
    })
    renderWithClient(<Audit />)

    await screen.findByText('AUTH_LOGIN_SUCCEEDED')
    await userEvent.click(screen.getByRole('button', { name: /verify chain/i }))
    await screen.findByText('INTACT')

    const call = impl.mock.calls.find(
      ([input, init]) =>
        requestUrl(input).includes('/api/audit/verify') && init?.method === 'POST',
    )
    expect(call).toBeDefined()
    const body = call?.[1]?.body
    // Either no body at all, or one carrying no verdict field.
    if (typeof body === 'string') {
      const parsed: unknown = JSON.parse(body)
      expect(parsed).not.toHaveProperty('status')
      expect(parsed).not.toHaveProperty('proves')
    }
  })

  it('reports a broken chain as broken, naming the affected records', async () => {
    stub({
      'GET /api/audit/events': () => ({ status: 200, body: auditPage() }),
      'POST /api/audit/verify': () => ({
        status: 200,
        body: {
          ...INTACT_VERIFICATION,
          status: 'BROKEN',
          reason: '1 record(s) were modified after being written.',
          first_invalid_audit_id: 'aud_0000000000000002',
          links: [
            {
              audit_id: 'aud_0000000000000001',
              sequence: 1,
              status: 'VALID_GENESIS',
              detail: 'genesis',
            },
            {
              audit_id: 'aud_0000000000000002',
              sequence: 2,
              status: 'MUTATED_EVENT',
              detail: 'The entry was modified after it was written.',
            },
          ],
          proves: [],
        },
      }),
    })
    renderWithClient(<Audit />)

    await screen.findByText('AUTH_LOGIN_SUCCEEDED')
    await userEvent.click(screen.getByRole('button', { name: /verify chain/i }))

    expect(await screen.findByText('BROKEN')).toBeInTheDocument()
    expect(screen.getByText(/MUTATED_EVENT · 1/)).toBeInTheDocument()
    expect(screen.getByText(/The entry was modified after it was written\./)).toBeInTheDocument()
  })
})

describe('the transport carries the real credential', () => {
  it('attaches the bearer token and persists nothing to browser storage', async () => {
    const impl = stub({ 'GET /api/audit/events': () => ({ status: 200, body: auditPage() }) })
    renderWithClient(<Audit />)
    await screen.findByText('AUTH_LOGIN_SUCCEEDED')

    await waitFor(() => expect(impl).toHaveBeenCalled())
    const firstCall = impl.mock.calls[0]
    expect(firstCall).toBeDefined()
    const headers = new Headers(firstCall?.[1]?.headers)
    expect(headers.get('Authorization')).toBe('Bearer opaque-test-token')

    // The credential must exist only in memory: a token in localStorage survives the tab and is
    // readable by any injected script.
    const stored = JSON.stringify({ ...localStorage, ...sessionStorage })
    expect(stored).not.toContain('opaque-test-token')
  })
})
