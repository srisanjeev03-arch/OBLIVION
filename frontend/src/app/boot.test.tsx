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
    await waitFor(() => expect(screen.getByTestId('auth-contract-gap')).toBeInTheDocument())

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider sessionSource={devPersonaSessionSource}>{children}</AuthProvider>
      ),
    })
    await waitFor(() => expect(result.current.authState).toBe('UNAVAILABLE'))
    expect(result.current.isDevSession).toBe(false)
    expect(result.current.sessionSourceId).toBe('dev-persona')
  })

  it('shows the auth contract gap rather than a working login form', async () => {
    renderWholeApp()
    const gap = await screen.findByTestId('auth-contract-gap')
    expect(gap.textContent).toMatch(/no endpoint that issues/)
    expect(gap.textContent).toMatch(/bearerAuth/)

    const submit = screen.getByRole('button', { name: /authentication unavailable/i })
    expect(submit).toBeDisabled()

    const disabledFields = screen.getAllByPlaceholderText(/unavailable - no token endpoint/i)
    expect(disabledFields).toHaveLength(2)
    for (const field of disabledFields) {
      expect(field).toBeDisabled()
    }

    // No fabricated success language anywhere on the sign-in screen.
    expect(gap.textContent).not.toMatch(/authenticated successfully/i)
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
