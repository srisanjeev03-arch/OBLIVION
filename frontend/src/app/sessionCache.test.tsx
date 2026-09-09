import { describe, it, expect, beforeEach } from 'vitest'
import { act, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SessionCacheBoundary } from './SessionCacheBoundary'
import { AuthProvider } from '@/lib/auth/provider'
import { devPersonaSessionSource } from '@/lib/auth/devAuth'
import { useAuthStore } from '@/lib/auth/store'
import type { Session } from '@/lib/auth/types'

/**
 * The guard that stops one operator reading another's cached backend responses.
 *
 * React Query keys are not principal-scoped, so without this boundary a logout leaves targets,
 * operations and evidence in the cache for whoever signs in next.
 */

function sessionFor(token: string): Session {
  return {
    accessToken: token,
    tokenType: 'Bearer',
    issuedAt: new Date().toISOString(),
    expiresAt: null,
    source: 'backend',
  }
}

async function renderBoundary(queryClient: QueryClient) {
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider sessionSource={devPersonaSessionSource}>
        <SessionCacheBoundary />
      </AuthProvider>
    </QueryClientProvider>,
  )
  // Let AuthProvider's mount-time restore promise settle inside act() before the test drives any
  // state change, so React is not updated from an unwrapped microtask.
  await waitFor(() => expect(useAuthStore.getState().authState).toBe('UNAUTHENTICATED'))
}

let queryClient: QueryClient

beforeEach(() => {
  useAuthStore.getState().reset()
  queryClient = new QueryClient()
})

describe('SessionCacheBoundary', () => {
  it('clears cached backend data when a principal signs in', async () => {
    queryClient.setQueryData(['operations'], [{ id: 'op_previous' }])
    await renderBoundary(queryClient)

    expect(queryClient.getQueryData(['operations'])).toBeDefined()

    act(() => useAuthStore.getState().setSession(sessionFor('token-a')))
    expect(queryClient.getQueryData(['operations'])).toBeUndefined()
  })

  it('clears on logout, which is the transition that leaks if missed', async () => {
    await renderBoundary(queryClient)
    act(() => useAuthStore.getState().setSession(sessionFor('token-a')))
    queryClient.setQueryData(['evidence'], [{ id: 'ev_1' }])

    act(() => useAuthStore.getState().setSession(null))
    expect(queryClient.getQueryData(['evidence'])).toBeUndefined()
  })

  it('clears when a different operator takes over the same document', async () => {
    await renderBoundary(queryClient)
    act(() => useAuthStore.getState().setSession(sessionFor('token-a')))
    queryClient.setQueryData(['operations'], [{ id: 'op_for_a' }])

    act(() => useAuthStore.getState().setSession(sessionFor('token-b')))
    expect(queryClient.getQueryData(['operations'])).toBeUndefined()
  })

  it('leaves the cache alone while the session is unchanged', async () => {
    await renderBoundary(queryClient)
    act(() => useAuthStore.getState().setSession(sessionFor('token-a')))

    queryClient.setQueryData(['operations'], [{ id: 'op_1' }])
    // A re-render with the same credential must not discard data the screens are using.
    act(() => useAuthStore.getState().setSession(sessionFor('token-a')))
    expect(queryClient.getQueryData(['operations'])).toBeDefined()
  })

  it('does not clear on a cold mount with no session', async () => {
    queryClient.setQueryData(['operations'], [{ id: 'prefetched' }])
    await renderBoundary(queryClient)
    expect(queryClient.getQueryData(['operations'])).toBeDefined()
  })
})

