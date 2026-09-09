import { useEffect, useState, type ReactNode } from 'react'
import { Outlet, useLocation } from 'react-router'
import { cn } from '@/lib/cn'
import { usePrefs } from '@/lib/prefs'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { CommandPalette } from './CommandPalette'
import { SessionProvenanceBanner } from '@/components/auth/SessionProvenanceBanner'

/**
 * Fixed-height operator console frame: sidebar | (topbar / workspace). The inspector drawer is
 * rendered by pages inside the workspace so it can overlay at narrow widths.
 */
export function AppShell({ children }: { children?: ReactNode }) {
  const sidebarCollapsed = usePrefs((s) => s.sidebarCollapsed)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Close the palette on navigation so a stale dialog never sits over a new page.
  useEffect(() => {
    setPaletteOpen(false)
  }, [location.pathname])

  return (
    <div className="flex h-full w-full overflow-hidden bg-bg text-fg">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-sm focus:bg-elevated focus:px-2 focus:py-1 focus:text-xs"
      >
        Skip to main content
      </a>
      <Sidebar collapsed={sidebarCollapsed} />
      <div className={cn('flex min-w-0 flex-1 flex-col')}>
        <SessionProvenanceBanner />
        <TopBar onOpenPalette={() => setPaletteOpen(true)} />
        <main id="main" className="relative min-h-0 flex-1 overflow-y-auto" tabIndex={-1}>
          {children ?? <Outlet />}
        </main>
      </div>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </div>
  )
}
