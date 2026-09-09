/**
 * Auth event bus.
 *
 * The HTTP transport is the only place that observes real 401/403 responses, but it must not
 * import the auth provider (circular dependency). Instead the transport publishes and the
 * auth provider subscribes.
 *
 * 401 and 403 are deliberately different events because they demand different handling:
 *   - 401 UNAUTHENTICATED  -> the credential is missing/invalid/expired. The session is dead;
 *                             it must be cleared and the operator returned to sign-in.
 *   - 403 FORBIDDEN        -> the credential is valid but the backend refused this action.
 *                             The session stays intact. Clearing it here would be a bug: it
 *                             would punish a correctly-authenticated operator for one denied
 *                             action, and would disguise an authorization decision as a
 *                             login failure.
 */

export type AuthEvent =
  | { readonly kind: 'unauthenticated'; readonly path: string; readonly status: 401 }
  | { readonly kind: 'forbidden'; readonly path: string; readonly status: 403; readonly method: string }

type Listener = (event: AuthEvent) => void

const listeners = new Set<Listener>()

export function publishAuthEvent(event: AuthEvent): void {
  for (const listener of listeners) listener(event)
}

export function subscribeToAuthEvents(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Test-only: prevents listeners leaking between specs. */
export function __resetAuthEventsForTests(): void {
  listeners.clear()
}