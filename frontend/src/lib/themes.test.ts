import { describe, it, expect } from 'vitest'
import {
  resolveThemeVariables,
  CURATED_PRESETS,
  SINGLE_ACCENTS,
  SEMANTIC_COLORS,
  type PresetId,
  type SingleAccentId,
} from './themes'

describe('Curated Presets Architecture', () => {
  it('contains exactly 9 curated multi-color presets', () => {
    const presetKeys = Object.keys(CURATED_PRESETS)
    expect(presetKeys).toHaveLength(9)
    expect(presetKeys).toContain('oblivion')
    expect(presetKeys).toContain('forensic')
    expect(presetKeys).toContain('soc')
    expect(presetKeys).toContain('command')
    expect(presetKeys).toContain('terminal')
    expect(presetKeys).toContain('arctic')
    expect(presetKeys).toContain('graphite')
    expect(presetKeys).toContain('amber-terminal')
    expect(presetKeys).toContain('spectrum')
  })

  it('contains exactly 11 single accent definitions', () => {
    const accentKeys = Object.keys(SINGLE_ACCENTS)
    expect(accentKeys).toHaveLength(11)
    expect(accentKeys).toContain('violet')
    expect(accentKeys).toContain('cyan')
    expect(accentKeys).toContain('blue')
    expect(accentKeys).toContain('emerald')
    expect(accentKeys).toContain('amber')
    expect(accentKeys).toContain('rose')
    expect(accentKeys).toContain('magenta')
    expect(accentKeys).toContain('red')
    expect(accentKeys).toContain('orange')
    expect(accentKeys).toContain('lime')
    expect(accentKeys).toContain('monochrome')
  })

  it('correctly resolves variables for default Oblivion preset', () => {
    const vars = resolveThemeVariables('preset', 'oblivion', 'violet')
    expect(vars.accent).toBe(SINGLE_ACCENTS.violet.hex)
    expect(vars.accentSecondary).toBe(SINGLE_ACCENTS.cyan.hex)
    expect(vars.accentSupporting).toBe(SINGLE_ACCENTS.blue.hex)
    expect(vars.viz1).toBeDefined()
    expect(vars.viz5).toBeDefined()
  })

  it('correctly resolves variables for Forensic preset', () => {
    const vars = resolveThemeVariables('preset', 'forensic', 'cyan')
    expect(vars.accent).toBe(SINGLE_ACCENTS.cyan.hex)
    expect(vars.accentSecondary).toBe(SINGLE_ACCENTS.violet.hex)
    expect(vars.accentSupporting).toBe(SINGLE_ACCENTS.blue.hex)
  })

  it('correctly resolves variables for single accent mode', () => {
    const vars = resolveThemeVariables('single', 'oblivion', 'emerald')
    expect(vars.accent).toBe(SINGLE_ACCENTS.emerald.hex)
    expect(vars.accentHover).toBe(SINGLE_ACCENTS.emerald.hover)
    expect(vars.accentActive).toBe(SINGLE_ACCENTS.emerald.active)
    expect(vars.accentSoft).toBe(SINGLE_ACCENTS.emerald.soft)
  })

  it('preserves immutable semantic tokens across dark and light palettes', () => {
    expect(SEMANTIC_COLORS.dark.success).toBe('#35c88f')
    expect(SEMANTIC_COLORS.dark.danger).toBe('#ec5b6a')
    expect(SEMANTIC_COLORS.dark.warning).toBe('#e6a53a')
    expect(SEMANTIC_COLORS.dark.info).toBe('#5b9dff')

    expect(SEMANTIC_COLORS.light.success).toBe('#12a06a')
    expect(SEMANTIC_COLORS.light.danger).toBe('#d23b4b')
  })

  it('resolves all 9 presets without throwing errors', () => {
    const presetKeys = Object.keys(CURATED_PRESETS) as PresetId[]
    for (const pid of presetKeys) {
      const vars = resolveThemeVariables('preset', pid, 'violet')
      expect(vars.accent).toMatch(/^#[0-9a-fA-F]{6}$/)
      expect(vars.accentSecondary).toMatch(/^#[0-9a-fA-F]{6}$/)
    }
  })

  it('resolves all 11 single accents without throwing errors', () => {
    const accentKeys = Object.keys(SINGLE_ACCENTS) as SingleAccentId[]
    for (const aid of accentKeys) {
      const vars = resolveThemeVariables('single', 'oblivion', aid)
      expect(vars.accent).toMatch(/^#[0-9a-fA-F]{6}$/)
    }
  })
})
