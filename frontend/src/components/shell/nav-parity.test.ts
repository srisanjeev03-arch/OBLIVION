import { describe, it, expect } from 'vitest'
import { NAV_ITEMS, ALL_NAV_SECTIONS, findNavByPath } from '@/components/shell/nav'
import { router } from '@/app/router'
import { ROLE_DEFAULT_PERMISSIONS } from '@/lib/auth/permissions'
import { makeUser } from '@/test/factories'
import type { User } from '@/lib/auth/types'

/**
 * Navigation and routing must agree. Previously two nav entries ('Administration' and 'Settings')
 * both declared '/settings', so the sidebar rendered two rows that highlighted together and the
 * permission-gated one could never be reached as itself.
 */

interface RouteNode {
  path?: string | null
  children?: RouteNode[]
}

function flatten(routes: RouteNode[], parent = ''): string[] {
  const out: string[] = []
  for (const route of routes) {
    const joined =
      route.path === undefined || route.path === null
        ? parent
        : route.path === '/'
          ? '/'
          : route.path === '*'
            ? `${parent}/*`
            : `${parent === '/' ? '' : parent}/${route.path}`.replace(/\/{2,}/g, '/')
    out.push(joined || '/')
    if (route.children) out.push(...flatten(route.children, joined))
  }
  return out
}

const ROUTE_PATHS = new Set(
  flatten(router.routes as unknown as RouteNode[])
    .map((p) => (p.startsWith('/') ? p : `/${p}`))
    .filter((p) => !p.includes('*')),
)

describe('navigation / route parity', () => {
  it('declares no duplicate destinations', () => {
    const paths = NAV_ITEMS.map((item) => item.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('declares no duplicate ids', () => {
    const ids = NAV_ITEMS.map((item) => item.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('every nav destination has a real route', () => {
    const missing = NAV_ITEMS.filter((item) => !ROUTE_PATHS.has(item.path)).map(
      (item) => `${item.id} -> ${item.path}`,
    )
    expect(missing).toEqual([])
  })

  it('resolves each nav item back to itself', () => {
    for (const item of NAV_ITEMS) {
      expect(findNavByPath(item.path)?.id).toBe(item.id)
    }
  })

  it('gates every non-public destination behind a permission', () => {
    // Overview and Settings are UI surface; everything else is data-bearing and must be gated.
    const ungated = NAV_ITEMS.filter(
      (item) => !item.permission && !['overview', 'settings'].includes(item.id),
    ).map((item) => item.id)
    expect(ungated).toEqual([])
  })
})

describe('administration is reachable only to managers', () => {
  const admin = (role: keyof typeof ROLE_DEFAULT_PERMISSIONS): User =>
    makeUser({ id: `u-${role}`, username: `u-${role}`, displayName: role, role })

  it('has its own path distinct from settings', () => {
    const administration = NAV_ITEMS.find((i) => i.id === 'administration')
    const settings = NAV_ITEMS.find((i) => i.id === 'settings')
    expect(administration?.path).toBe('/administration')
    expect(settings?.path).toBe('/settings')
    expect(administration?.path).not.toBe(settings?.path)
  })

  it('is hidden from every role that lacks user.manage', () => {
    for (const role of ['VIEWER', 'AUDITOR', 'OPERATOR', 'INVESTIGATOR'] as const) {
      const sections = ALL_NAV_SECTIONS.flatMap((s) => s.items).filter(
        (i) => i.id === 'administration',
      )
      expect(sections[0]?.permission).toBe('user.manage')
      expect(ROLE_DEFAULT_PERMISSIONS[role]).not.toContain('user.manage')
    }
    expect(ROLE_DEFAULT_PERMISSIONS.ADMIN).toContain('user.manage')
    expect(admin('ADMIN').role).toBe('ADMIN')
  })
})
