/**
 * The operation workflow's integration shape.
 *
 * The interesting assertions here are about what the console does *not* send. Approval and the
 * closed-loop pipeline both carry no request body: the approving identity comes from the
 * authenticated session, and the target, mode, policy and approval come from the persisted
 * operation. A "convenient" body on either would reintroduce the two attacks the backend's
 * body-less design removes - naming a different approver, and redirecting an approved erasure at
 * another path.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactElement, ReactNode } from 'react'
import { useApproveOperationMutation, useRunPipelineMutation } from '@/lib/api/mutations'
import { PipelineResultPanel } from './PipelineResultPanel'
import { setBearerToken, __resetTokenStoreForTests } from '@/lib/auth/tokenStore'
import type { PipelineResultOut } from '@/lib/api/queries'

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>
}

function renderWithClient(ui: ReactElement) {
  return render(<QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>)
}

function stubOk(body: unknown) {
  const impl = vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', impl)
  return impl
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

describe('approval carries no caller-chosen identity', () => {
  it('posts to the operation it was given, with no body', async () => {
    const impl = stubOk({ id: 'op_1', state: 'READY' })
    const { result } = renderHook(() => useApproveOperationMutation('op_1'), { wrapper })

    await act(async () => {
      await result.current.mutateAsync()
    })

    const call = impl.mock.calls[0] as unknown as [string, RequestInit]
    expect(String(call[0])).toContain('/api/operations/op_1/approve')
    expect(call[1].method).toBe('POST')
    // No approver field, because there is no field at all.
    expect(call[1].body ?? null).toBeNull()
  })
})

describe('the pipeline is invoked without a target', () => {
  it('posts to the operation it was given, with no body', async () => {
    const impl = stubOk({
      operation_id: 'op_1',
      target_identity: 'C:/scratch/x.txt',
      final_state: 'COMPLETED',
      stages: [],
      limitations: [],
      coverage: {},
    })
    const { result } = renderHook(() => useRunPipelineMutation('op_1'), { wrapper })

    await act(async () => {
      await result.current.mutateAsync()
    })

    const call = impl.mock.calls[0] as unknown as [string, RequestInit]
    expect(String(call[0])).toContain('/api/operations/op_1/pipeline')
    expect(call[1].method).toBe('POST')
    // No target_path field: an approved erasure cannot be redirected from here.
    expect(call[1].body ?? null).toBeNull()
  })
})

describe('the pipeline result is rendered without rounding', () => {
  const result = {
    operation_id: 'op_1',
    target_identity: 'C:/scratch/x.txt',
    final_state: 'PARTIAL',
    stages: [
      { stage: 'ERASE', status: 'COMPLETED', detail: '' },
      { stage: 'TEST_RECOVERY', status: 'UNAVAILABLE', detail: 'no baseline' },
    ],
    assurance_status: 'INCONCLUSIVE',
    verification_status: null,
    evidence_id: 'ev_1',
    certificate_id: null,
    evidence_digest: null,
    limitations: ['MFT record inspection (needs raw volume access)'],
    coverage: {
      recovery_test: 'UNAVAILABLE',
      residual_analysis: 'PARTIAL',
      recovery_methods: {
        supported: ['filesystem_enumeration'],
        attempted: [],
        successful: [],
        failed: [],
        unavailable: ['mft_record', 'usn_journal'],
      },
      residual_scanners: {
        supported: ['path_existence'],
        ran: ['path_existence'],
        inconclusive: [],
        unavailable: [],
      },
    },
  } as unknown as PipelineResultOut

  it('shows INCONCLUSIVE as itself, never as success or failure', async () => {
    renderWithClient(<PipelineResultPanel result={result} />)
    await waitFor(() => expect(screen.getByText('INCONCLUSIVE')).toBeInTheDocument())
  })

  it('lists every stage, including the one that could not run', () => {
    renderWithClient(<PipelineResultPanel result={result} />)
    expect(screen.getByText('ERASE')).toBeInTheDocument()
    expect(screen.getByText('TEST_RECOVERY')).toBeInTheDocument()
  })

  it('names the recovery methods that were never attempted', () => {
    renderWithClient(<PipelineResultPanel result={result} />)
    // The claim "recovery testing was performed" is not checkable; naming the
    // methods is. The permanently-unavailable ones must stay visible.
    expect(screen.getByText(/mft_record, usn_journal/)).toBeInTheDocument()
    expect(screen.getByText('Never attempted')).toBeInTheDocument()
  })

  it('states that a method finding nothing is not proof of irrecoverability', () => {
    renderWithClient(<PipelineResultPanel result={result} />)
    expect(screen.getByText(/not a finding that the data is unrecoverable/i)).toBeInTheDocument()
  })

  it('says no certificate was issued rather than implying one was', () => {
    renderWithClient(<PipelineResultPanel result={result} />)
    expect(screen.getByText(/No certificate was issued/i)).toBeInTheDocument()
  })

  it('warns that a successful request is not a successful erasure', () => {
    renderWithClient(<PipelineResultPanel result={result} />)
    expect(screen.getByText(/neither is implied by the request succeeding/i)).toBeInTheDocument()
  })
})
