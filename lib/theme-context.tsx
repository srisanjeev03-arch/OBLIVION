'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'
import type { Appearance } from './types'

export const ACCENT_PRESETS: {
  name: string
  value: string
  fg: string
}[] = [
  { name: 'Oblivion Violet', value: '#8b7cff', fg: '#0b0b0d' },
  { name: 'Electric Blue', value: '#4f8dff', fg: '#0b0b0d' },
  { name: 'Cyan', value: '#3fc9d9', fg: '#04121a' },
  { name: 'Indigo', value: '#6366f1', fg: '#ffffff' },
  { name: 'Emerald', value: '#34d39a', fg: '#04140d' },
  { name: 'Amber', value: '#e6a53a', fg: '#1a1204' },
  { name: 'Rose', value: '#f4708a', fg: '#1a0810' },
  { name: 'Graphite', value: '#9aa0ac', fg: '#0b0b0d' },
]

const DEFAULT: Appearance = {
  theme: 'dark',
  accent: '#8b7cff',
  accentFg: '#0b0b0d',
  accentName: 'Oblivion Violet',
  density: 'standard',
  corner: 'balanced',
  motion: 'full',
}

const STORAGE_KEY = 'oblivion.appearance'

interface ThemeCtx {
  appearance: Appearance
  set: (patch: Partial<Appearance>) => void
  reset: () => void
}

const Ctx = createContext<ThemeCtx | null>(null)

function resolveTheme(theme: Appearance['theme']): 'dark' | 'light' {
  if (theme === 'system') {
    return typeof window !== 'undefined' &&
      window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light'
  }
  return theme
}

function apply(a: Appearance) {
  const root = document.documentElement
  const resolved = resolveTheme(a.theme)
  root.classList.remove('dark', 'light')
  root.classList.add(resolved)
  root.setAttribute('data-density', a.density)
  root.setAttribute('data-corner', a.corner)
  root.setAttribute('data-motion', a.motion)
  root.style.setProperty('--accent', a.accent)
  root.style.setProperty('--accent-fg', a.accentFg)
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [appearance, setAppearance] = useState<Appearance>(DEFAULT)

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (raw) setAppearance({ ...DEFAULT, ...JSON.parse(raw) })
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    apply(appearance)
    if (appearance.theme !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => apply(appearance)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [appearance])

  const set = useCallback((patch: Partial<Appearance>) => {
    setAppearance((prev) => {
      const next = { ...prev, ...patch }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }, [])

  const reset = useCallback(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(DEFAULT))
    } catch {
      /* ignore */
    }
    setAppearance(DEFAULT)
  }, [])

  return <Ctx.Provider value={{ appearance, set, reset }}>{children}</Ctx.Provider>
}

export function useAppearance() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAppearance must be used within ThemeProvider')
  return ctx
}
