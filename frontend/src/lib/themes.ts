/**
 * Oblivion Forensic Console Theme & Preset System.
 *
 * Strict Architecture:
 * 1. Interaction / Brand Colors: Primary Accent, Secondary Accent, Supporting Accent.
 * 2. Semantic Colors: Success, Warning, Danger, Info, Unavailable (Immutable across all presets).
 * 3. Data Visualization Colors: Series 1 through Series 5.
 */

export type PresetId =
  | 'oblivion'
  | 'forensic'
  | 'soc'
  | 'command'
  | 'terminal'
  | 'arctic'
  | 'graphite'
  | 'amber-terminal'
  | 'spectrum'

export type SingleAccentId =
  | 'violet'
  | 'cyan'
  | 'blue'
  | 'emerald'
  | 'amber'
  | 'rose'
  | 'magenta'
  | 'red'
  | 'orange'
  | 'lime'
  | 'monochrome'

export type AccentMode = 'preset' | 'single'

export interface AccentColorDefinition {
  readonly id: SingleAccentId
  readonly name: string
  readonly hex: string
  readonly hover: string
  readonly active: string
  readonly soft: string
  readonly border: string
  readonly fg: string
}

export const SINGLE_ACCENTS: Readonly<Record<SingleAccentId, AccentColorDefinition>> = {
  violet: {
    id: 'violet',
    name: 'Obsidian Violet',
    hex: '#9c8cff',
    hover: '#aea0ff',
    active: '#8a78f0',
    soft: 'rgba(156, 140, 255, 0.14)',
    border: 'rgba(156, 140, 255, 0.38)',
    fg: '#0b0b0d',
  },
  cyan: {
    id: 'cyan',
    name: 'Forensic Cyan',
    hex: '#00e5ff',
    hover: '#33ebff',
    active: '#00c4db',
    soft: 'rgba(0, 229, 255, 0.14)',
    border: 'rgba(0, 229, 255, 0.38)',
    fg: '#00252b',
  },
  blue: {
    id: 'blue',
    name: 'Signal Blue',
    hex: '#4d88ff',
    hover: '#709fff',
    active: '#3374f5',
    soft: 'rgba(77, 136, 255, 0.14)',
    border: 'rgba(77, 136, 255, 0.38)',
    fg: '#0b1326',
  },
  emerald: {
    id: 'emerald',
    name: 'Terminal Emerald',
    hex: '#00e676',
    hover: '#33eb91',
    active: '#00c864',
    soft: 'rgba(0, 230, 118, 0.14)',
    border: 'rgba(0, 230, 118, 0.38)',
    fg: '#002810',
  },
  amber: {
    id: 'amber',
    name: 'Security Amber',
    hex: '#ffb020',
    hover: '#ffbf4d',
    active: '#e59a0f',
    soft: 'rgba(255, 176, 32, 0.14)',
    border: 'rgba(255, 176, 32, 0.38)',
    fg: '#2a1a00',
  },
  rose: {
    id: 'rose',
    name: 'Subtle Rose',
    hex: '#ff5c8a',
    hover: '#ff7d9d',
    active: '#e64472',
    soft: 'rgba(255, 92, 138, 0.14)',
    border: 'rgba(255, 92, 138, 0.38)',
    fg: '#2a0510',
  },
  magenta: {
    id: 'magenta',
    name: 'Deep Magenta',
    hex: '#e040fb',
    hover: '#e768fc',
    active: '#c520e0',
    soft: 'rgba(224, 64, 251, 0.14)',
    border: 'rgba(224, 64, 251, 0.38)',
    fg: '#210029',
  },
  red: {
    id: 'red',
    name: 'Command Crimson',
    hex: '#ff3d57',
    hover: '#ff667a',
    active: '#e52540',
    soft: 'rgba(255, 61, 87, 0.14)',
    border: 'rgba(255, 61, 87, 0.38)',
    fg: '#2b0006',
  },
  orange: {
    id: 'orange',
    name: 'Tactical Orange',
    hex: '#ff7043',
    hover: '#ff8a65',
    active: '#e65328',
    soft: 'rgba(255, 112, 67, 0.14)',
    border: 'rgba(255, 112, 67, 0.38)',
    fg: '#2a0a00',
  },
  lime: {
    id: 'lime',
    name: 'Phosphor Lime',
    hex: '#c6ff00',
    hover: '#d2ff33',
    active: '#aee000',
    soft: 'rgba(198, 255, 0, 0.14)',
    border: 'rgba(198, 255, 0, 0.38)',
    fg: '#1f2900',
  },
  monochrome: {
    id: 'monochrome',
    name: 'Stark Monochrome',
    hex: '#e0e0e6',
    hover: '#ffffff',
    active: '#c2c2cb',
    soft: 'rgba(224, 224, 230, 0.14)',
    border: 'rgba(224, 224, 230, 0.38)',
    fg: '#08080a',
  },
}

export interface CuratedThemePreset {
  readonly id: PresetId
  readonly name: string
  readonly subtitle: string
  readonly description: string
  readonly primary: SingleAccentId
  readonly secondary: SingleAccentId
  readonly supporting: SingleAccentId
  readonly viz: readonly [string, string, string, string, string]
}

export const CURATED_PRESETS: Readonly<Record<PresetId, CuratedThemePreset>> = {
  oblivion: {
    id: 'oblivion',
    name: 'Oblivion',
    subtitle: 'Signature Console',
    description: 'Violet primary interaction, Cyan technical highlights, Blue supporting metadata.',
    primary: 'violet',
    secondary: 'cyan',
    supporting: 'blue',
    viz: ['#9c8cff', '#00e5ff', '#4d88ff', '#00e676', '#ffb020'],
  },
  forensic: {
    id: 'forensic',
    name: 'Forensic',
    subtitle: 'Evidence Workstation',
    description: 'Cyan primary interaction, Violet analytical intelligence, Blue data metadata.',
    primary: 'cyan',
    secondary: 'violet',
    supporting: 'blue',
    viz: ['#00e5ff', '#9c8cff', '#4d88ff', '#35c88f', '#ffb020'],
  },
  soc: {
    id: 'soc',
    name: 'SOC',
    subtitle: 'Security Operations',
    description: 'Signal Blue primary interaction, Cyan live telemetry, Violet analysis.',
    primary: 'blue',
    secondary: 'cyan',
    supporting: 'violet',
    viz: ['#4d88ff', '#00e5ff', '#9c8cff', '#35c88f', '#ff7043'],
  },
  command: {
    id: 'command',
    name: 'Command',
    subtitle: 'Tactical Console',
    description: 'Command Crimson primary, Orange tactical highlights, Amber indicators.',
    primary: 'red',
    secondary: 'orange',
    supporting: 'amber',
    viz: ['#ff3d57', '#ff7043', '#ffb020', '#4d88ff', '#00e5ff'],
  },
  terminal: {
    id: 'terminal',
    name: 'Terminal',
    subtitle: 'Phosphor Green',
    description: 'Emerald interaction, Cyan highlights, Phosphor Lime indicators.',
    primary: 'emerald',
    secondary: 'cyan',
    supporting: 'lime',
    viz: ['#00e676', '#00e5ff', '#c6ff00', '#4d88ff', '#ffb020'],
  },
  arctic: {
    id: 'arctic',
    name: 'Arctic',
    subtitle: 'Cool Spectrum',
    description: 'Restrained Cyan primary, Blue secondary, Violet supporting tones.',
    primary: 'cyan',
    secondary: 'blue',
    supporting: 'violet',
    viz: ['#00e5ff', '#4d88ff', '#9c8cff', '#00e676', '#e0e0e6'],
  },
  graphite: {
    id: 'graphite',
    name: 'Graphite',
    subtitle: 'Minimal Monochrome',
    description: 'Strict monochrome with neutral gray highlights. Ideal for conservative audits.',
    primary: 'monochrome',
    secondary: 'blue',
    supporting: 'violet',
    viz: ['#f0f0f3', '#b8b8c2', '#848492', '#555562', '#33333d'],
  },
  'amber-terminal': {
    id: 'amber-terminal',
    name: 'Amber Terminal',
    subtitle: 'Vintage Security',
    description: 'Amber primary interaction, Orange secondary, Red supporting indicators.',
    primary: 'amber',
    secondary: 'orange',
    supporting: 'red',
    viz: ['#ffb020', '#ff7043', '#ff3d57', '#4d88ff', '#00e5ff'],
  },
  spectrum: {
    id: 'spectrum',
    name: 'Spectrum',
    subtitle: 'Categorical Analysis',
    description: 'Structured multi-accent allocation for high-bandwidth data visualization.',
    primary: 'violet',
    secondary: 'cyan',
    supporting: 'blue',
    viz: ['#9c8cff', '#00e5ff', '#4d88ff', '#00e676', '#ffb020'],
  },
}

/** Immutable semantic colors — never altered by user accent choices. */
export const SEMANTIC_COLORS = {
  dark: {
    success: '#35c88f',
    successSoft: 'rgba(53, 200, 143, 0.14)',
    warning: '#e6a53a',
    warningSoft: 'rgba(230, 165, 58, 0.14)',
    danger: '#ec5b6a',
    dangerSoft: 'rgba(236, 91, 106, 0.14)',
    info: '#5b9dff',
    infoSoft: 'rgba(91, 157, 255, 0.14)',
  },
  light: {
    success: '#12a06a',
    successSoft: 'rgba(18, 160, 106, 0.14)',
    warning: '#b3761a',
    warningSoft: 'rgba(179, 118, 26, 0.14)',
    danger: '#d23b4b',
    dangerSoft: 'rgba(210, 59, 75, 0.14)',
    info: '#2f6fe0',
    infoSoft: 'rgba(47, 111, 224, 0.14)',
  },
} as const

export interface ResolvedThemeVars {
  accent: string
  accentHover: string
  accentActive: string
  accentSoft: string
  accentBorder: string
  accentFg: string
  accentSecondary: string
  accentSecondarySoft: string
  accentSupporting: string
  accentSupportingSoft: string
  viz1: string
  viz2: string
  viz3: string
  viz4: string
  viz5: string
}

export function resolveThemeVariables(
  mode: AccentMode,
  presetId: PresetId,
  singleAccentId: SingleAccentId,
): ResolvedThemeVars {
  if (mode === 'single') {
    const acc = SINGLE_ACCENTS[singleAccentId] ?? SINGLE_ACCENTS.violet
    return {
      accent: acc.hex,
      accentHover: acc.hover,
      accentActive: acc.active,
      accentSoft: acc.soft,
      accentBorder: acc.border,
      accentFg: acc.fg,
      accentSecondary: acc.hover,
      accentSecondarySoft: acc.soft,
      accentSupporting: acc.hex,
      accentSupportingSoft: acc.soft,
      viz1: acc.hex,
      viz2: acc.hover,
      viz3: '#4d88ff',
      viz4: '#35c88f',
      viz5: '#ffb020',
    }
  }

  const preset = CURATED_PRESETS[presetId] ?? CURATED_PRESETS.oblivion
  const p = SINGLE_ACCENTS[preset.primary] ?? SINGLE_ACCENTS.violet
  const s = SINGLE_ACCENTS[preset.secondary] ?? SINGLE_ACCENTS.cyan
  const sup = SINGLE_ACCENTS[preset.supporting] ?? SINGLE_ACCENTS.blue

  return {
    accent: p.hex,
    accentHover: p.hover,
    accentActive: p.active,
    accentSoft: p.soft,
    accentBorder: p.border,
    accentFg: p.fg,
    accentSecondary: s.hex,
    accentSecondarySoft: s.soft,
    accentSupporting: sup.hex,
    accentSupportingSoft: sup.soft,
    viz1: preset.viz[0],
    viz2: preset.viz[1],
    viz3: preset.viz[2],
    viz4: preset.viz[3],
    viz5: preset.viz[4],
  }
}
