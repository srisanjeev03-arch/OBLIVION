import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '@/lib/auth/store'

/**
 * Clears cached backend responses whenever the acting principal changes.
 *
 * React Query keys do not include the operator, so a cache that survives login, logout or a 401
 * would let the next operator read the previous one's targets, operations and evidence. That is a
 * data-leak shape, not a staleness nuisance.
 *
 * This lives in its own component rather than inside `AuthProvider` on purpose: the auth layer then
 * keeps no dependency on React Query and can be rendered on its own (tests, stories, a future
 * sub-app) without a `QueryClientProvider` ancestor. This component is mounted under both providers,
 * so it can see each.
 *
 * It renders nothing. Identity is keyed on the credential itself, so a token rotation or a re-login
 * as a different user both clear, while an unrelated re-render does not.
 */
export function SessionCacheBoundary() {
  const queryClient = useQueryClient()
  const session = useAuthStore((s) => s.session)
  const previous = useRef<string | null>(null)
  const mounted = useRef(false)

  const identity = session ? `${session.source}:${session.accessToken}` : null

  useEffect(() => {
    // The first pass only records where we started. Clearing then would be harmless but pointless.
    if (!mounted.current) {
      mounted.current = true
      previous.current = identity
      return
    }
    if (previous.current === identity) return
    previous.current = identity
    // Every transition clears, including the move back to signed-out: a cache left behind after
    // logout is exactly the leak this component exists to prevent.
    queryClient.clear()
  }, [identity, queryClient])

  return null
}
