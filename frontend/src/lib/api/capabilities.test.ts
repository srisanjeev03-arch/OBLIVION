import { describe, it, expect } from 'vitest'
import { isAvailable, unavailableReason, buildPath, FORENSIC_CAPABILITIES } from './capabilities'

describe('Capability Gating', () => {
  it('identifies available capabilities correctly', () => {
    expect(isAvailable('targets.analyze')).toBe(true)
    expect(unavailableReason('targets.analyze')).toBeNull()
  })

  it('identifies unavailable/unimplemented capabilities correctly', () => {
    expect(isAvailable('operations.create')).toBe(false)
    expect(unavailableReason('operations.create')).toContain('Awaiting backend: Phase 2')
  })

  it('correctly substitutes path parameters in buildPath', () => {
    const path = buildPath('targets.get', { target_id: 'tgt-123' })
    expect(path).toBe('/api/targets/tgt-123')
  })

  it('throws when required path parameters are missing', () => {
    expect(() => buildPath('targets.get', {})).toThrowError('Missing path parameter "target_id"')
  })

  it('provides honest forensic detector capabilities', () => {
    const unallocated = FORENSIC_CAPABILITIES.find((c) => c.id === 'fs.unallocated_clusters')
    expect(unallocated).toBeDefined()
    expect(unallocated?.status).toBe('UNAVAILABLE')
    expect(unallocated?.limitation).toContain('Not assessed')
  })
})
