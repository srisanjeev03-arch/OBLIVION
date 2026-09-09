import { describe, it, expect } from 'vitest'
import { formatBytes, formatCount, truncateMiddle, formatIso, PLACEHOLDER } from './format'

describe('formatBytes', () => {
  it('handles null/undefined gracefully', () => {
    expect(formatBytes(null)).toBe(PLACEHOLDER)
    expect(formatBytes(undefined)).toBe(PLACEHOLDER)
  })

  it('formats byte boundaries correctly', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(1024 * 1024 * 1024)).toBe('1.0 GB')
  })
})

describe('formatCount', () => {
  it('handles null/undefined', () => {
    expect(formatCount(null, 'item')).toBe(PLACEHOLDER)
    expect(formatCount(undefined, 'item')).toBe(PLACEHOLDER)
  })

  it('pluralizes correctly', () => {
    expect(formatCount(1, 'file')).toBe('1 file')
    expect(formatCount(2, 'file')).toBe('2 files')
    expect(formatCount(0, 'file')).toBe('0 files')
  })
})

describe('formatIso', () => {
  it('handles null/undefined', () => {
    expect(formatIso(null)).toBe(PLACEHOLDER)
    expect(formatIso(undefined)).toBe(PLACEHOLDER)
  })
})

describe('truncateMiddle', () => {
  it('does not truncate short strings', () => {
    expect(truncateMiddle('short', 10, 10)).toBe('short')
  })

  it('truncates long strings with ellipsis', () => {
    const long = 'abcdefghijklmnopqrstuvwxyz0123456789'
    const truncated = truncateMiddle(long, 4, 4)
    expect(truncated).toBe('abcd…6789')
  })
})
