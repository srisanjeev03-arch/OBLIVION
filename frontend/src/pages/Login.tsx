import { useState, type FormEvent } from 'react'
import { useNavigate, useLocation } from 'react-router'
import { Lock, ShieldAlert, AlertTriangle, CircleSlash, FlaskConical } from 'lucide-react'
import { useAuth } from '@/lib/auth/context'
import {
  isDevAuthEnabled,
  DEV_PERSONAS,
  DEV_SESSION_BANNER,
  type DevPersona,
} from '@/lib/auth/devAuth'
import {
  MISSING_AUTH_CONTRACT_ELEMENTS,
  AUTH_TOKEN_ISSUANCE_PUBLISHED,
  DECLARED_SECURITY_SCHEME,
} from '@/lib/auth/authContract'
import { ROLE_METADATA } from '@/lib/auth/types'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6.5 6.5l11 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

/**
 * Sign-in screen.
 *
 * This screen does not pretend to authenticate anyone. Credential transport (bearer) is wired and
 * tested, but OPENAPI.yaml publishes no endpoint that issues a token, so submitting real
 * credentials reports the contract gap instead of showing a success state that never happened.
 * The form is rendered disabled with the reason attached - hiding it would leave an operator
 * guessing, and enabling it would promise a capability that does not exist.
 */
export function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const { login, signInWithDevPersona, authState, error: authError } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/'
  const devEnabled = isDevAuthEnabled()
  const canSubmitCredentials = AUTH_TOKEN_ISSUANCE_PUBLISHED
  const showGap = authState === 'UNAVAILABLE' && !canSubmitCredentials

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)
    if (!username.trim()) return
    setLoading(true)
    try {
      await login({ username: username.trim(), password })
      void navigate(from, { replace: true })
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setLoading(false)
    }
  }

  // Deliberately explicit: a persona is chosen by name, never inferred from a password prefix.
  const handleSelectPersona = (persona: DevPersona) => {
    setLocalError(null)
    try {
      signInWithDevPersona(persona.id)
      void navigate(from, { replace: true })
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : 'Development persona sign-in failed.')
    }
  }

  const activeError = localError || authError

  return (
    <div className="flex min-h-screen w-full flex-col items-center justify-center bg-bg p-4 text-fg select-none">
      <div className="w-full max-w-md space-y-5 rounded-lg border border-line-strong bg-surface p-7 shadow-2xl motion-enter">
        <div className="flex flex-col items-center space-y-2 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-md border border-line-strong bg-inset text-accent shadow-xs">
            <Mark className="h-7 w-7" />
          </div>
          <div className="space-y-0.5">
            <h1 className="text-lg font-bold tracking-tight text-fg">OBLIVION FORENSIC CONSOLE</h1>
            <p className="font-mono text-xs text-mute">
              {DECLARED_SECURITY_SCHEME.scheme.toUpperCase()} AUTHENTICATED OPERATOR ACCESS
            </p>
          </div>
        </div>

        {showGap && <AuthContractGap />}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-3">
            <Input
              label="Operator Username / ID"
              placeholder={canSubmitCredentials ? 'e.g. s.connor' : 'Unavailable - no token endpoint'}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={!canSubmitCredentials}
              className="font-mono text-xs"
              required
            />
            <Input
              label="Passphrase"
              type="password"
              placeholder={canSubmitCredentials ? 'Enter passphrase' : 'Unavailable - no token endpoint'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={!canSubmitCredentials}
              className="font-mono text-xs"
              required
            />
          </div>

          {activeError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-sm border border-danger/40 bg-danger-soft p-2.5 text-xs leading-relaxed text-danger"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{activeError}</span>
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            size="md"
            loading={loading}
            disabled={!canSubmitCredentials}
            className="w-full justify-center"
            leadingIcon={<Lock className="h-3.5 w-3.5" />}
          >
            {canSubmitCredentials ? 'Authenticate Session' : 'Authentication Unavailable'}
          </Button>
        </form>

        {devEnabled && (
          <div className="space-y-2.5 border-t border-line pt-4">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1 text-[0.625rem] font-bold uppercase tracking-wider text-warning">
                <FlaskConical className="h-3 w-3" />
                Development personas only
              </span>
              <span className="font-mono text-[0.5625rem] text-dim">DEV BUILD - NOT BACKEND</span>
            </div>
            <p className="rounded-sm border border-warning/40 bg-warning-soft p-2 font-mono text-[0.625rem] leading-relaxed text-warning">
              {DEV_SESSION_BANNER}
            </p>

            <div className="grid grid-cols-1 gap-1.5">
              {DEV_PERSONAS.map((p) => {
                const meta = ROLE_METADATA[p.role]
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleSelectPersona(p)}
                    disabled={loading}
                    className="flex items-center justify-between gap-2 rounded-sm border border-line bg-elevated/40 p-2 text-left text-xs transition-colors hover:border-line-strong hover:bg-elevated"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ backgroundColor: meta.color }}
                      />
                      <div className="min-w-0 truncate">
                        <span className="block truncate text-xs font-semibold text-fg">
                          {p.displayName}
                        </span>
                        <span className="block font-mono text-[0.625rem] text-dim">
                          @{p.username}
                        </span>
                      </div>
                    </div>
                    <span
                      className="shrink-0 rounded-xs border px-1.5 py-0.5 font-mono text-[0.5625rem] font-bold uppercase"
                      style={{
                        color: meta.color,
                        borderColor: `${meta.color}40`,
                        backgroundColor: `${meta.color}15`,
                      }}
                    >
                      {p.role}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        <div className="border-t border-line/40 pt-3 text-center font-mono text-[0.625rem] leading-relaxed text-dim">
          Role and permission checks in this console control visibility only. Authorization is
          enforced by the backend on every request.
        </div>
      </div>
    </div>
  )
}

/** States the missing contract elements as a fact, rather than as a login failure. */
function AuthContractGap() {
  return (
    <div
      role="status"
      className="space-y-2 rounded-md border border-warning/40 bg-warning-soft p-3"
      data-testid="auth-contract-gap"
    >
      <div className="flex items-center gap-1.5 text-warning">
        <CircleSlash className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        <span className="text-[0.6875rem] font-bold uppercase tracking-wider">
          Contract gap: no token endpoint
        </span>
      </div>
      <p className="text-[0.6875rem] leading-relaxed text-fg">
        The OpenAPI contract declares <span className="font-mono">bearerAuth</span> (
        {DECLARED_SECURITY_SCHEME.bearerFormat}) but publishes no endpoint that issues, renews or
        revokes a token. Credential transport is implemented; credential issuance is not available.
      </p>
      <ul className="space-y-0.5">
        {MISSING_AUTH_CONTRACT_ELEMENTS.map((element) => (
          <li
            key={element.capability}
            className="font-mono text-[0.625rem] leading-relaxed text-dim"
          >
            MISSING: {element.capability}
          </li>
        ))}
      </ul>
      <p className="flex items-start gap-1.5 text-[0.625rem] leading-relaxed text-mute">
        <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" />
        Development personas are the only way into the console in a development build, and are
        compiled out of production builds.
      </p>
    </div>
  )
}

