import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { renderHook } from '@testing-library/react'
import { Providers } from './providers'
import { App } from './App'
import { AuthProvider } from '@/lib/auth/provider'
import { useAuth } from '@/lib/auth/context'
import { useAuthStore } from '@/lib/auth/store'
import { DEV_TOKEN_PREFIX, devPersonaSessionSource } from '@/lib/auth/devAuth'

/**
 * Boot tests.
 *
 * The released build shipped `<App />` without `AuthProvider`, so the first component that called
 * `useAuth()` threw and the console never rendered - while typecheck, lint, unit tests and the
 * production build all passed. These tests exist so that class of failure is caught by `npm test`
 * instead of by the operator.
 */

function renderWholeApp() {
  return render(
    <Providers>
      <App />
    </Providers>,
  )
}

beforeEach(() => {
  useAuthStore.getState().reset()
  vi.stubGlobal('fetch', vi.fn())
})

describe('application boot', () => {
  it('renders the full tree without a missing-provider error', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    expect(() => renderWholeApp()).not.toThrow()
    await waitFor(() =>
      expect(screen.getByText('OBLIVION FORENSIC CONSOLE')).toBeInTheDocument(),
    )

    const fatal = consoleError.mock.calls.flat().join(' ')
    expect(fatal).not.toMatch(/must be used within an AuthProvider/)
    consoleError.mockRestore()
  })

  it('exposes a working useAuth() to anything under the router', async () => {
    renderWholeApp()
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /authenticate session/i })).toBeInTheDocument(),
    )

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider sessionSource={devPersonaSessionSource}>{children}</AuthProvider>
      ),
    })
    await waitFor(() => expect(result.current.authState).toBe('UNAUTHENTICATED'))
    expect(result.current.isDevSession).toBe(false)
    expect(result.current.sessionSourceId).toBe('dev-persona')
  })

  it('renders a working login form wired to the published auth endpoint', async () => {
    renderWholeApp()
    // Settle the mount-time session restore before asserting, so the form is inspected at rest
    // rather than mid-resolution.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /authenticate session/i })).toBeEnabled(),
    )

    const submit = screen.getByRole('button', { name: /authenticate session/i })
    expect(submit).toBeEnabled()
    expect(screen.getByLabelText(/operator username/i)).toBeEnabled()
    expect(screen.getByLabelText(/passphrase/i)).toBeEnabled()

    // The gap that used to dominate this screen is gone; the honest limits are still stated.
    expect(screen.queryByTestId('auth-contract-gap')).not.toBeInTheDocument()
    expect(screen.getByText(/session posture/i)).toBeInTheDocument()
    expect(screen.getByText(/memory only/i)).toBeInTheDocument()
    expect(screen.getByText(/no refresh endpoint/i)).toBeInTheDocument()

    // No fabricated success language anywhere on the sign-in screen.
    expect(document.body.textContent).not.toMatch(/authenticated successfully/i)
    expect(document.body.textContent).not.toMatch(/welcome back/i)
  })

  it('offers dev personas in a dev/test build and labels them as non-backend', () => {
    renderWholeApp()
    expect(screen.getByText(/development personas only/i)).toBeInTheDocument()
    expect(screen.getByText(/DEV BUILD - NOT BACKEND/i)).toBeInTheDocument()
    expect(screen.getAllByText('ADMIN').length).toBeGreaterThan(0)
  })
})

describe('provider wiring is load-bearing', () => {
  it('useAuth() outside AuthProvider throws, proving the guard above is real', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    expect(() => renderHook(() => useAuth())).toThrow(/AuthProvider/)
    spy.mockRestore()
  })
})

describe('dev credential shape', () => {
  it('is prefixed so a dev token can never be mistaken for a backend JWT in a trace', () => {
    expect(DEV_TOKEN_PREFIX).toBe('dev-persona:')
  })
})
