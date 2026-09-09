'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Search,
  CornerDownLeft,
  LayoutGrid,
  Activity,
  Crosshair,
  Archive,
  ScanSearch,
  ShieldCheck,
  FileCheck,
  ScrollText,
  Server,
  Settings,
  Palette,
  Play,
} from 'lucide-react'
import { useShell, type View, type NavParams } from './shell-context'
import { operations, certificates } from '@/lib/mock-data'
import { cn } from '@/lib/utils'

interface Cmd {
  id: string
  group: string
  label: string
  hint?: string
  icon: React.ComponentType<{ className?: string }>
  run: () => void
}

export function CommandPalette() {
  const { commandOpen, setCommandOpen, navigate } = useShell()
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandOpen(true)
      }
      if (e.key === 'Escape') setCommandOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setCommandOpen])

  useEffect(() => {
    if (commandOpen) {
      setQ('')
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 20)
    }
  }, [commandOpen])

  const commands = useMemo<Cmd[]>(() => {
    const go = (v: View, p?: NavParams): (() => void) => () => navigate(v, p)
    const nav: Cmd[] = [
      { id: 'n-overview', group: 'Navigate', label: 'Overview', icon: LayoutGrid, run: go('overview') },
      { id: 'n-ops', group: 'Navigate', label: 'Operations', icon: Activity, run: go('operations') },
      { id: 'n-targets', group: 'Navigate', label: 'Targets', icon: Crosshair, run: go('targets') },
      { id: 'n-recovery', group: 'Navigate', label: 'Recovery Vault', icon: Archive, run: go('recovery') },
      { id: 'n-residual', group: 'Navigate', label: 'Residual Analysis', icon: ScanSearch, run: go('residual') },
      { id: 'n-assurance', group: 'Navigate', label: 'Assurance', icon: ShieldCheck, run: go('assurance') },
      { id: 'n-cert', group: 'Navigate', label: 'Certificates', icon: FileCheck, run: go('certificates') },
      { id: 'n-audit', group: 'Navigate', label: 'Audit', icon: ScrollText, run: go('audit') },
      { id: 'n-system', group: 'Navigate', label: 'System Health', icon: Server, run: go('system') },
      { id: 'n-settings', group: 'Navigate', label: 'Settings', icon: Settings, run: go('settings') },
    ]
    const actions: Cmd[] = [
      { id: 'a-analyze', group: 'Actions', label: 'Analyze a target', hint: 'Start erasure workflow', icon: Play, run: go('workflow') },
      { id: 'a-appearance', group: 'Actions', label: 'Change appearance', hint: 'Theme, accent, density', icon: Palette, run: go('settings', { settingsSection: 'appearance' }) },
    ]
    const ops: Cmd[] = operations.map((o) => ({
      id: `op-${o.id}`,
      group: 'Operations',
      label: o.target,
      hint: o.id,
      icon: Activity,
      run: go('operations', { operationId: o.id }),
    }))
    const certs: Cmd[] = certificates.map((c) => ({
      id: `c-${c.id}`,
      group: 'Certificates',
      label: c.id,
      hint: c.target,
      icon: FileCheck,
      run: go('certificates', { certificateId: c.id }),
    }))
    return [...actions, ...nav, ...ops, ...certs]
  }, [navigate])

  const filtered = useMemo(() => {
    if (!q.trim()) return commands
    const s = q.toLowerCase()
    return commands.filter(
      (c) =>
        c.label.toLowerCase().includes(s) ||
        c.hint?.toLowerCase().includes(s) ||
        c.group.toLowerCase().includes(s),
    )
  }, [q, commands])

  const groups = useMemo(() => {
    const m = new Map<string, Cmd[]>()
    filtered.forEach((c) => {
      if (!m.has(c.group)) m.set(c.group, [])
      m.get(c.group)!.push(c)
    })
    return Array.from(m.entries())
  }, [filtered])

  if (!commandOpen) return null

  const flat = filtered

  return (
    <div
      className="fixed inset-0 z-100 flex items-start justify-center px-4 pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onMouseDown={() => setCommandOpen(false)}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" />
      <div
        className="animate-scale-in relative w-full max-w-xl overflow-hidden rounded-xl border border-line-strong bg-elevated shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2.5 border-b border-line px-3.5">
          <Search className="h-4 w-4 text-mute" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setActive(0)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setActive((a) => Math.min(a + 1, flat.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setActive((a) => Math.max(a - 1, 0))
              } else if (e.key === 'Enter') {
                e.preventDefault()
                flat[active]?.run()
              }
            }}
            placeholder="Search targets, operations, certificates, settings…"
            className="h-12 flex-1 bg-transparent text-sm text-fg outline-none placeholder:text-mute"
          />
          <kbd className="rounded border border-line bg-inset px-1.5 py-0.5 font-mono text-[0.625rem] text-mute">
            ESC
          </kbd>
        </div>
        <div className="max-h-[52vh] overflow-y-auto p-1.5">
          {flat.length === 0 && (
            <p className="px-3 py-8 text-center text-sm text-mute">
              No matches for “{q}”.
            </p>
          )}
          {groups.map(([group, items]) => (
            <div key={group} className="mb-1">
              <p className="px-2.5 py-1.5 text-[0.6875rem] font-medium tracking-wide text-mute">
                {group}
              </p>
              {items.map((c) => {
                const idx = flat.indexOf(c)
                const isActive = idx === active
                const Icon = c.icon
                return (
                  <button
                    key={c.id}
                    onMouseMove={() => setActive(idx)}
                    onClick={() => c.run()}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors',
                      isActive ? 'bg-inset text-fg' : 'text-dim',
                    )}
                  >
                    <Icon
                      className="h-4 w-4 shrink-0"
                      style={{ color: isActive ? 'var(--accent)' : 'var(--mute)' }}
                    />
                    <span className="flex-1 truncate">{c.label}</span>
                    {c.hint && (
                      <span className="truncate font-mono text-[0.6875rem] text-mute">
                        {c.hint}
                      </span>
                    )}
                    {isActive && (
                      <CornerDownLeft className="h-3.5 w-3.5 text-mute" />
                    )}
                  </button>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
