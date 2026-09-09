import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { PresetId, SingleAccentId, AccentMode } from './themes'

/**
 * UI preferences only. This store must never hold backend data, tokens, keys or any
 * security-relevant state — it is persisted to localStorage.
 */

export type ThemeMode = 'dark' | 'light' | 'system'
export type Density = 'comfortable' | 'standard' | 'compact'
export type Corner = 'sharp' | 'balanced' | 'soft'
export type Motion = 'full' | 'minimal'

export const THEME_MODES: readonly ThemeMode[] = ['dark', 'light', 'system']
export const DENSITIES: readonly Density[] = ['comfortable', 'standard', 'compact']
export const CORNERS: readonly Corner[] = ['sharp', 'balanced', 'soft']
export const MOTIONS: readonly Motion[] = ['full', 'minimal']

interface PrefsState {
  theme: ThemeMode
  presetId: PresetId
  singleAccent: SingleAccentId
  accentMode: AccentMode
  density: Density
  corner: Corner
  motion: Motion
  sidebarCollapsed: boolean
  setTheme: (theme: ThemeMode) => void
  setPreset: (presetId: PresetId) => void
  setSingleAccent: (singleAccent: SingleAccentId) => void
  setAccentMode: (accentMode: AccentMode) => void
  setDensity: (density: Density) => void
  setCorner: (corner: Corner) => void
  setMotion: (motion: Motion) => void
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleSidebar: () => void
}

export const PREFS_STORAGE_KEY = 'oblivion.prefs.v1'

export const usePrefs = create<PrefsState>()(
  persist(
    (set) => ({
      theme: 'dark',
      presetId: 'oblivion',
      singleAccent: 'violet',
      accentMode: 'preset',
      density: 'standard',
      corner: 'balanced',
      motion: 'full',
      sidebarCollapsed: false,
      setTheme: (theme) => set({ theme }),
      setPreset: (presetId) => set({ presetId, accentMode: 'preset' }),
      setSingleAccent: (singleAccent) => set({ singleAccent, accentMode: 'single' }),
      setAccentMode: (accentMode) => set({ accentMode }),
      setDensity: (density) => set({ density }),
      setCorner: (corner) => set({ corner }),
      setMotion: (motion) => set({ motion }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: PREFS_STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        theme: s.theme,
        presetId: s.presetId,
        singleAccent: s.singleAccent,
        accentMode: s.accentMode,
        density: s.density,
        corner: s.corner,
        motion: s.motion,
        sidebarCollapsed: s.sidebarCollapsed,
      }),
    },
  ),
)

/** Resolves 'system' to the concrete scheme using the OS preference. */
export function resolveTheme(theme: ThemeMode): 'dark' | 'light' {
  if (theme !== 'system') return theme
  if (typeof window === 'undefined' || !window.matchMedia) return 'dark'
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}
