import { describe, it, expect } from 'vitest'
import {
  CAPABILITIES,
  buildPath,
  contractDrift,
  getCapability,
  isAvailable,
  isInContract,
  unavailableReason,
  type CapabilityId,
} from './capabilities'
import { CONTRACT_OPERATIONS, isContractOperation } from './contract-paths'

/**
 * The registry's availability is derived from the generated contract, so these specs are mostly
 * about the *relationship* rather than about individual flags: nothing in the registry may claim an
 * operation the application does not route, and nothing the application routes may be suppressed.
 */

const ALL_IDS = Object.keys(CAPABILITIES) as CapabilityId[]

describe('availability is derived, not asserted', () => {
  it('agrees with the contract for every registered capability', () => {
    for (const id of ALL_IDS) {
      const c = CAPABILITIES[id]
      expect(isAvailable(id)).toBe(isContractOperation(c.method, c.path))
    }
  })

  it('has no drift between registry intent and the running application', () => {
    // A non-empty result means either a capability was added without the backend routing it, or the
    // backend shipped an operation the registry still describes as a gap.
    expect(contractDrift()).toEqual([])
  })

  it('marks the auth trio available, since the backend routes and serves it', () => {
    for (const id of ['auth.login', 'auth.me', 'auth.logout'] as const) {
      expect(isInContract(id)).toBe(true)
      expect(unavailableReason(id)).toBeNull()
    }
  })

  it('marks certificate verification available', () => {
    // Previously pinned to implemented: false, which made the console refuse a shipped capability.
    expect(isAvailable('certificates.verify')).toBe(true)
    expect(isAvailable('certificates.get')).toBe(true)
  })

  it('treats /health as contracted and reachable without a credential', () => {
    expect(isAvailable('health')).toBe(true)
    expect(getCapability('health').path).toBe('/health')
  })
})

describe('gaps are named, not hidden', () => {
  // `audit.events` used to be listed here. The backend now publishes
  // `GET /api/audit/events` and `POST /api/audit/verify`, so the gap is closed
  // and the capability is contracted like any other - keeping it in this list
  // would assert a limitation that no longer exists.
  // `operations.list` was removed from this list when F-D shipped
  // `GET /api/operations`. The entry asserted a limitation that no longer
  // exists, and leaving it would have kept the console refusing a capability
  // the backend actually serves - which is the exact failure mode this file's
  // header describes as the more dangerous direction.
  const GAPPED: CapabilityId[] = [
    'targets.list',
    'assurance.get',
    'certificates.list',
    'residual.findings',
  ]

  it('every gap capability is unavailable AND carries an explanation', () => {
    for (const id of GAPPED) {
      expect(isAvailable(id)).toBe(false)
      // The point of the registry: an unavailable capability must say what happens instead.
      expect(unavailableReason(id)).toBeTruthy()
      expect(CAPABILITIES[id].gapNote).toBeTruthy()
    }
  })

  it('no capability without a gapNote is missing from the contract', () => {
    const missing = ALL_IDS.filter((id) => CAPABILITIES[id].gapNote === undefined && !isInContract(id))
    expect(missing).toEqual([])
  })
})

describe('registry integrity', () => {
  it('keys match the ids they hold', () => {
    for (const id of ALL_IDS) {
      expect(CAPABILITIES[id].id).toBe(id)
    }
  })

  it('every path is absolute', () => {
    for (const id of ALL_IDS) {
      expect(CAPABILITIES[id].path.startsWith('/')).toBe(true)
    }
  })

  it('registers no duplicate method+path among callable capabilities', () => {
    const seen = new Map<string, CapabilityId>()
    const duplicates: string[] = []
    for (const id of ALL_IDS) {
      if (CAPABILITIES[id].gapNote) continue
      const key = `${CAPABILITIES[id].method} ${CAPABILITIES[id].path}`
      if (seen.has(key)) duplicates.push(`${key} (${String(seen.get(key))} vs ${id})`)
      seen.set(key, id)
    }
    expect(duplicates).toEqual([])
  })

  it('covers every operation the contract publishes', () => {
    const registered = new Set(
      ALL_IDS.filter((id) => !CAPABILITIES[id].gapNote).map(
        (id) => `${CAPABILITIES[id].method} ${CAPABILITIES[id].path}`,
      ),
    )
    const uncovered = CONTRACT_OPERATIONS.filter((op) => !registered.has(op))
    expect(uncovered).toEqual([])
  })

  it('flags exactly the destructive operations for confirmation handling', () => {
    // `operations.pipeline` runs the real erasure as one of its twelve stages,
    // so it must be flagged destructive and carry the same confirmation
    // handling as `operations.execute`. A destructive call the console treats
    // as ordinary is the one that gets fired by accident.
    const destructive = ALL_IDS.filter((id) => CAPABILITIES[id].destructive)
    expect(destructive.sort()).toEqual(
      [
        'operations.create',
        'operations.execute',
        'operations.pipeline',
        'recovery.restore',
      ].sort(),
    )
  })
})

describe('buildPath', () => {
  it('substitutes and encodes parameters', () => {
    expect(
      buildPath('certificates.verify', { certificate_id: 'cert 1/2' }),
    ).toBe('/api/certificates/cert%201%2F2/verify')
  })

  it('refuses to build a path with a missing parameter instead of sending a broken URL', () => {
    expect(() => buildPath('operations.get', {})).toThrow(/Missing path parameter/)
  })
})
