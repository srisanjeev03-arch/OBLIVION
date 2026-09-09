import { useLocation } from 'react-router'
import { Search } from 'lucide-react'
import { Kbd } from '@/components/ui/Panel'
import { BackendConnectionStatus } from './BackendConnectionStatus'
import { findNavByPath } from './nav'
import { usePrefs } from '@/lib/prefs'
import { CURATED_PRESETS, SINGLE_ACCENTS } from '@/lib/themes'
import { UserIdentityBadge } from '@/components/auth/UserIdentityBadge'

export function TopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const location = useLocation()
  const current = findNavByPath(location.pathname)
  const { presetId, singleAccent, accentMode } = usePrefs()
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

  const activePreset = CURATED_PRESETS[presetId] ?? CURATED_PRESETS.oblivion
  const singleDef = SINGLE_ACCENTS[singleAccent] ?? SINGLE_ACCENTS.violet

  return (
    <header className="flex h-11 shrink-0 items-center justify-between gap-4 border-b border-line bg-surface/80 px-4 backdrop-blur-xs">
      <nav aria-label="Breadcrumb" className="min-w-0">
        <ol className="flex items-center gap-2 text-xs text-mute">
          <li className="font-semibold text-fg">Oblivion</li>
          <li aria-hidden="true" className="text-dim">
            /
          </li>
          <li className="truncate font-medium text-fg" aria-current="page">
            {current?.label ?? 'Overview'}
          </li>
        </ol>
      </nav>

      <div className="flex items-center gap-2.5">
        {/* Workspace / Theme Indicator */}
        <div className="hidden md:flex items-center gap-1.5 px-2 py-0.5 rounded-sm border border-line bg-inset text-[0.625rem] font-mono text-dim">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <span className="uppercase tracking-wider">
            {accentMode === 'preset' ? activePreset.name : singleDef.name}
          </span>
        </div>

        <button
          type="button"
          onClick={onOpenPalette}
          className="inline-flex h-7 items-center gap-2 rounded-sm border border-line bg-elevated px-2 text-xs text-dim transition-colors duration-[var(--motion-duration)] hover:text-fg hover:border-line-strong"
          aria-keyshortcuts={isMac ? 'Meta+K' : 'Control+K'}
        >
          <Search className="h-3 w-3" aria-hidden="true" />
          <span className="hidden sm:inline text-[0.6875rem]">Command</span>
          <span className="hidden items-center gap-0.5 sm:inline-flex" aria-hidden="true">
            <Kbd>{isMac ? '⌘' : 'Ctrl'}</Kbd>
            <Kbd>K</Kbd>
          </span>
        </button>

        <BackendConnectionStatus />

        {/* User Account / Identity */}
        <div className="pl-1 border-l border-line">
          <UserIdentityBadge variant="compact" />
        </div>
      </div>
    </header>
  )
}
