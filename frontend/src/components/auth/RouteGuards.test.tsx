/**
 * `RequireNavPermission` looks a permission up from `nav.ts` instead of taking one as a literal,
 * so a sidebar entry and its route guard cannot drift apart. These specs pin its three outcomes:
 * granted, denied (identical to `RequirePermission`'s existing behaviour) and unknown id (fails
 * closed with a thrown error rather than rendering an ungated route).
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { RequireNavPermission } from './RouteGuards'
import { AuthContext } from '@/lib/auth/context'
import { makeUser } from '@/test/factories'
import type { AuthContextType } from '@/lib/auth/types'
import type { NavId } from '@/components/shell/nav'

function authValue(user: AuthContextType['user']): AuthContextType {
  return {
    user,
    session: null,
    authState: user ? 'AUTHENTICATED' : 'UNAUTHENTICATED',
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
    hasPermission: (permission) => user?.permissions.includes(permission) ?? false,
    hasAnyPermission: (permissions) =>
      permissions.some((p) => user?.permissions.includes(p) ?? false),
    hasAllPermissions: (permissions) =>
      permissions.every((p) => user?.permissions.includes(p) ?? false),
    hasRole: () => false,
  }
}

function renderGuarded(navId: NavId, user: AuthContextType['user']) {
  render(
    <AuthContext.Provider value={authValue(user)}>
      <MemoryRouter>
        <RequireNavPermission navId={navId}>
          <div>protected content</div>
        </RequireNavPermission>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('RequireNavPermission', () => {
  it('renders the guarded content when the user holds the mapped permission', () => {
    // 'targets' maps to case.view (nav.ts); ADMIN holds it.
    renderGuarded('targets', makeUser({ role: 'ADMIN' }))
    expect(screen.getByText('protected content')).toBeInTheDocument()
  })

  it('falls through to the existing Unauthorized behaviour when the permission is missing', () => {
    // 'administration' maps to user.manage, which VIEWER does not hold - identical to what
    // RequirePermission has always done, since RequireNavPermission only looks the permission up
    // and then delegates.
    renderGuarded('administration', makeUser({ role: 'VIEWER' }))
    expect(screen.queryByText('protected content')).not.toBeInTheDocument()
    expect(screen.getByText(/403/)).toBeInTheDocument()
  })

  it('renders ungated nav items (no declared permission) regardless of role', () => {
    // 'settings' declares no permission in nav.ts.
    renderGuarded('settings', makeUser({ role: 'VIEWER' }))
    expect(screen.getByText('protected content')).toBeInTheDocument()
  })

  it('fails closed on an unknown navId instead of rendering an ungated route', () => {
    // Calling the guard directly: the throw happens before any hook runs, so this needs no
    // provider - it is the same fail-closed check a typo'd navId would hit at render time.
    expect(() =>
      RequireNavPermission({ navId: 'not-a-real-nav-id' as NavId, children: null }),
    ).toThrow(/not a navigation id/)
  })
})
