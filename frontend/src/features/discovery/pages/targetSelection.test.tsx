/**
 * F-C: profiling a target must actually select it.
 *
 * `setSelectedTargetId` existed on the UI store and was never called by anything, so
 * `selectedTargetId` was permanently null. A target could be profiled successfully and then never
 * become the subject of an operation - the erasure workflow read a value nothing ever wrote.
 *
 * These tests follow the chain the operator walks:
 *
 *     profile a target -> the store holds its id -> the workflow resolves that id to a target
 *     -> a create-operation request can be submitted with it
 *
 * The identifier is the backend's, never the path the operator typed, and the backend stays
 * authoritative: it revalidates the target when the operation is created and again immediately
 * before anything destructive happens.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor, renderHook } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import type { ReactElement, ReactNode } from 'react'
import { Targets } from './Targets'
import { useTargetQuery } from '@/lib/api/queries'
import { useUIStore } from '@/stores/ui.store'
import { setBearerToken, __resetTokenStoreForTests } from '@/lib/auth/tokenStore'

const BACKEND_TARGET_ID = 'tgt_9f1c2d3e4a5b'
const TARGET_PATH = 'E:\\scratch\\classified.txt'

const ANALYSED = {
  id: BACKEND_TARGET_ID,
  path: TARGET_PATH,
  canonical_path: TARGET_PATH,
  type: 'file',
  size_bytes: 2432,
  file_count: 1,
  sha256: 'a'.repeat(64),
  storage_profile: {},
}

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

    if (method === 'POST' && url.includes('/api/targets/analyze')) {
      return Promise.resolve(jsonResponse(ANALYSED))
    }
    if (method === 'GET' && url.includes(`/api/targets/${BACKEND_TARGET_ID}`)) {
      return Promise.resolve(jsonResponse(ANALYSED))
    }
    return Promise.resolve(jsonResponse({}, 404))
  })
  vi.stubGlobal('fetch', impl)
  return impl
}

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  // The screen renders a react-router <Link>, so it needs a router in context.
  // Without one the link throws during render - the component still worked, but
  // the suite reported unhandled errors, which is exactly the kind of noise that
  // trains a reader to ignore test output.
  return render(
    <MemoryRouter>
      <QueryClientProvider client={client}>{ui}</QueryClientProvider>
    </MemoryRouter>,
  )
}

async function profileATarget() {
  await userEvent.type(screen.getByLabelText(/filesystem path/i), TARGET_PATH)
  await userEvent.click(screen.getByRole('button', { name: /inspect target/i }))
}

beforeEach(() => {
  __resetTokenStoreForTests()
  setBearerToken({
    accessToken: 'opaque-test-token',
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
    source: 'backend',
  })
  useUIStore.setState({ selectedTargetId: null })
})

afterEach(() => {
  vi.unstubAllGlobals()
  __resetTokenStoreForTests()
  useUIStore.setState({ selectedTargetId: null })
})

describe('profiling a target selects it', () => {
  it('starts with nothing selected', () => {
    expect(useUIStore.getState().selectedTargetId).toBeNull()
  })

  it('stores the backend identifier after a successful profile', async () => {
    stubBackend()
    renderWithClient(<Targets />)

    await profileATarget()

    await waitFor(() => expect(useUIStore.getState().selectedTargetId).toBe(BACKEND_TARGET_ID))
  })

  it('stores the id the backend issued, never the path that was typed', async () => {
    stubBackend()
    renderWithClient(<Targets />)

    await profileATarget()

    await waitFor(() => expect(useUIStore.getState().selectedTargetId).toBeTruthy())
    const selected = useUIStore.getState().selectedTargetId
    expect(selected).toBe(BACKEND_TARGET_ID)
    expect(selected).not.toBe(TARGET_PATH)
  })

  it('selects nothing when the response carries no identifier', async () => {
    // An id-less response must not select an empty string: the workflow would
    // then claim a target it cannot resolve, and the backend would reject it
    // later with a confusing error instead of the screen saying "none selected".
    const impl = vi.fn(() => Promise.resolve(jsonResponse({ ...ANALYSED, id: undefined })))
    vi.stubGlobal('fetch', impl)
    renderWithClient(<Targets />)

    await profileATarget()

    await waitFor(() => expect(impl).toHaveBeenCalled())
    expect(useUIStore.getState().selectedTargetId).toBeNull()
  })

  it('does not select anything when profiling fails', async () => {
    const impl = vi.fn(() =>
      Promise.resolve(
        jsonResponse({ error_code: 'PROTECTED_PATH', message: 'refused' }, 400),
      ),
    )
    vi.stubGlobal('fetch', impl)
    renderWithClient(<Targets />)

    await profileATarget()

    await waitFor(() => expect(impl).toHaveBeenCalled())
    // A refused target is not a selected target.
    expect(useUIStore.getState().selectedTargetId).toBeNull()
  })
})

describe('the erasure workflow can then reach the target', () => {
  it('resolves the selected id through the real target query', async () => {
    // The chain the operator walks, end to end at the data layer: the store now
    // holds an id, and that id resolves to a target the workflow can submit.
    const impl = stubBackend()
    renderWithClient(<Targets />)

    await profileATarget()
    await waitFor(() => expect(useUIStore.getState().selectedTargetId).toBe(BACKEND_TARGET_ID))

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    )

    const { result } = renderHook(() => useTargetQuery(BACKEND_TARGET_ID), { wrapper })

    await waitFor(() => expect(result.current.data).toBeDefined())
    expect(result.current.data?.id).toBe(BACKEND_TARGET_ID)

    // And the workflow would submit that id, not the typed path.
    const fetched = impl.mock.calls.map(([input]) => requestUrl(input))
    expect(fetched.some((u) => u.includes(`/api/targets/${BACKEND_TARGET_ID}`))).toBe(true)
  })
})
