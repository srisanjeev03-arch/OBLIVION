/**
 * Objective Selection only navigates. These specs pin that it offers exactly the destinations the
 * role can reach (the permission comes from `nav.ts`, the same source as the route guards) and
 * that the recoverable objective hands its mode to the erasure screen without performing anything.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router'
import { ObjectiveSelection } from './ObjectiveSelection'
import { AuthContext } from '@/lib/auth/context'
import { makeUser } from '@/test/factories'
import type { AuthContextType, PermissionKey } from '@/lib/auth/types'

function authValue(user: AuthContextType['user']): AuthContextType {
  const has = (p: PermissionKey) => user?.permissions.includes(p) ?? false
  return {
    user,
    session: null,
    authState: 'AUTHENTICATED',
    error: null,
    notice: null,
    accessToken: null,
    isDevSession: false,
    sessionSourceId: 'backend-contract',
    login: () => Promise.reject(new Error('not used in this test')),
    signInWithDevPersona: () => {
      throw new Error('not used in this test')
    },
    logout: () => Promise.resolve(),
    dismissNotice: () => {},
    hasPermission: has,
    hasAnyPermission: (ps) => ps.some(has),
    hasAllPermissions: (ps) => ps.every(has),
    hasRole: () => false,
  }
}

function Destination() {
  const location = useLocation()
  return <div data-testid="destination">{`${location.pathname} ${JSON.stringify(location.state)}`}</div>
}

function renderPage(user: AuthContextType['user']) {
  render(
    <AuthContext.Provider value={authValue(user)}>
      <MemoryRouter initialEntries={['/objective']}>
        <Routes>
          <Route path="/objective" element={<ObjectiveSelection />} />
          <Route path="*" element={<Destination />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

const objectiveButton = (name: RegExp) => screen.getByRole('button', { name })

describe('ObjectiveSelection', () => {
  it('disables objectives whose destination the role cannot open', () => {
    const viewer = makeUser({ role: 'VIEWER' })
    renderPage(viewer)

    const erase = objectiveButton(/^Remove data/)
    expect(erase).toBeDisabled()
    expect(viewer.permissions).not.toContain('file_erasure.request')
  })

  it('enables every objective for a role that can open every destination', () => {
    renderPage(makeUser({ role: 'ADMIN' }))
    for (const name of [
      /^Remove data/,
      /^Remove with controlled recovery/,
      /^Check for remaining traces/,
      /^Review an operation/,
      /^Review evidence and the audit trail/,
    ]) {
      expect(objectiveButton(name)).toBeEnabled()
    }
  })

  it('hands the recoverable mode to the erasure screen and performs nothing itself', async () => {
    const user = userEvent.setup()
    renderPage(makeUser({ role: 'ADMIN' }))

    await user.click(objectiveButton(/^Remove with controlled recovery/))
    await user.click(screen.getByRole('button', { name: /^Continue to/ }))

    const destination = screen.getByTestId('destination').textContent ?? ''
    expect(destination).toContain('/erasure')
    expect(destination).toContain('"mode":"CONTROLLED_RECOVERABLE"')
  })

  it('shows the real required permission in expert mode', async () => {
    const user = userEvent.setup()
    renderPage(makeUser({ role: 'ADMIN' }))

    await user.click(screen.getByRole('button', { name: 'EXPERT' }))
    await user.click(objectiveButton(/^Review evidence and the audit trail/))

    expect(screen.getByText('audit.view')).toBeInTheDocument()
    expect(screen.getByText('/audit')).toBeInTheDocument()
  })

  it('makes no irrecoverability or physical-sanitization claim', () => {
    renderPage(makeUser({ role: 'ADMIN' }))
    const text = document.body.textContent ?? ''
    expect(text).not.toMatch(/irrecoverabl/i)
    expect(text).not.toMatch(/entire volumes/i)
  })
})
