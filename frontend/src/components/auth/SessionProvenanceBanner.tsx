import { FlaskConical, ShieldX, CircleSlash, X } from 'lucide-react'
import { useAuth } from '@/lib/auth/context'
import { DEV_SESSION_BANNER } from '@/lib/auth/devAuth'

/**
 * Persistent session-provenance strip.
 *
 * Two things must never be ambiguous while the console is on screen: who the operator is believed
 * to be, and whether that belief came from the backend or from a development shortcut. A dev
 * persona grants real UI power in this build, so it is announced on every screen rather than only
 * on the sign-in page - otherwise a developer can demo an "ADMIN session" that has never touched
 * an authenticator, and mistake the resulting behaviour for production behaviour.
 *
 * The 403 notice is rendered here too, and is deliberately separate from the 401 path: a denied
 * action keeps the session, so the message is dismissible instead of redirecting.
 */
export function SessionProvenanceBanner() {
  const { isDevSession, user, notice, dismissNotice } = useAuth()

  // Note: there is deliberately no "auth unavailable" strip here. `RequireAuth` redirects an
  // UNAVAILABLE session to /login, which renders the full contract-gap explanation, so a strip
  // in the shell would be unreachable dead UI.
  if (!isDevSession && !notice) return null

  return (
    <div className="flex flex-col" role="status" aria-live="polite">
      {isDevSession && (
        <div
          className="flex items-center gap-2 border-b border-warning/40 bg-warning-soft px-4 py-1.5 text-[0.6875rem] text-warning"
          data-testid="dev-session-banner"
        >
          <FlaskConical className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span className="font-mono font-bold uppercase tracking-wider">DEV</span>
          <span className="truncate leading-relaxed">
            {DEV_SESSION_BANNER}
            {user ? ` Active persona: ${user.displayName} (${user.role}).` : ''}
          </span>
        </div>
      )}

      {notice && (
        <div className="flex items-center gap-2 border-b border-danger/40 bg-danger-soft px-4 py-1.5 text-[0.6875rem] text-danger">
          {notice.kind === 'permission_denied' ? (
            <ShieldX className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <CircleSlash className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          )}
          <span className="min-w-0 flex-1 truncate leading-relaxed">{notice.message}</span>
          <button
            type="button"
            onClick={dismissNotice}
            aria-label="Dismiss authorization notice"
            className="shrink-0 rounded-xs p-0.5 hover:bg-danger/10"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  )
}
