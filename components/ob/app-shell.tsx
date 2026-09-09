'use client'

import {
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
  Search,
  Bell,
  Check,
  X,
  AlertTriangle,
  ChevronRight,
} from 'lucide-react'
import { useShell, ShellProvider, type View } from './shell-context'
import { CommandPalette } from './command-palette'
import { OblivionMark } from './mark'
import { cn } from '@/lib/utils'
import { currentUser, systemComponents } from '@/lib/mock-data'
import { OverviewView } from './views/overview'
import { OperationsView } from './views/operations'
import { TargetsView } from './views/targets'
import { RecoveryView } from './views/recovery'
import { ResidualView } from './views/residual'
import { AssuranceView } from './views/assurance'
import { CertificatesView } from './views/certificates'
import { AuditView } from './views/audit'
import { SystemView } from './views/system'
import { SettingsView } from './views/settings'
import { WorkflowView } from './views/workflow'

const NAV: {
  section: string
  items: { view: View; label: string; icon: React.ComponentType<{ className?: string }> }[]
}[] = [
  {
    section: 'Workspace',
    items: [
      { view: 'overview', label: 'Overview', icon: LayoutGrid },
      { view: 'operations', label: 'Operations', icon: Activity },
      { view: 'targets', label: 'Targets', icon: Crosshair },
    ],
  },
  {
    section: 'Forensics',
    items: [
      { view: 'recovery', label: 'Recovery Vault', icon: Archive },
      { view: 'residual', label: 'Residual Analysis', icon: ScanSearch },
      { view: 'assurance', label: 'Assurance', icon: ShieldCheck },
    ],
  },
  {
    section: 'Evidence',
    items: [
      { view: 'certificates', label: 'Certificates', icon: FileCheck },
      { view: 'audit', label: 'Audit', icon: ScrollText },
      { view: 'system', label: 'System', icon: Server },
    ],
  },
]

const VIEW_TITLES: Record<View, string> = {
  overview: 'Overview',
  operations: 'Operations',
  targets: 'Targets',
  recovery: 'Recovery Vault',
  residual: 'Residual Analysis',
  assurance: 'Assurance',
  certificates: 'Certificates',
  audit: 'Audit',
  system: 'System Health',
  settings: 'Settings',
  workflow: 'Erasure Workflow',
}

function Sidebar() {
  const { view, navigate } = useShell()
  const degraded = systemComponents.some((c) => c.status !== 'OPERATIONAL')
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-surface">
      <div className="flex h-14 items-center gap-2.5 px-4">
        <OblivionMark className="h-6 w-6" />
        <div className="leading-none">
          <div className="text-sm font-semibold tracking-tight text-fg">
            OBLIVION
          </div>
          <div className="mt-0.5 text-[0.625rem] tracking-[0.14em] text-mute">
            ERASE · VERIFY · PROVE
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2.5 py-2">
        {NAV.map((group) => (
          <div key={group.section} className="mb-4">
            <p className="px-2 py-1.5 text-[0.6875rem] font-medium tracking-wide text-mute">
              {group.section}
            </p>
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const active = view === item.view
                const Icon = item.icon
                return (
                  <li key={item.view}>
                    <button
                      onClick={() => navigate(item.view)}
                      className={cn(
                        'group relative flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-[0.8125rem] transition-colors',
                        active
                          ? 'bg-inset text-fg'
                          : 'text-dim hover:bg-elevated hover:text-fg',
                      )}
                      aria-current={active ? 'page' : undefined}
                    >
                      {active && (
                        <span
                          className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full"
                          style={{ backgroundColor: 'var(--accent)' }}
                        />
                      )}
                      <Icon
                        className="h-4 w-4 shrink-0"
                        style={active ? { color: 'var(--accent)' } : undefined}
                      />
                      {item.label}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-line p-2.5">
        <button
          onClick={() => navigate('system')}
          className="mb-1 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[0.75rem] text-dim hover:bg-elevated"
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{
              backgroundColor: degraded ? 'var(--warning)' : 'var(--success)',
            }}
          />
          {degraded ? 'System degraded' : 'All systems operational'}
        </button>
        <button
          onClick={() => navigate('settings')}
          className="flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left hover:bg-elevated"
        >
          <div
            className="flex h-7 w-7 items-center justify-center rounded-full text-[0.6875rem] font-semibold"
            style={{ backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }}
          >
            AR
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-[0.8125rem] font-medium text-fg">
              {currentUser.name}
            </div>
            <div className="truncate text-[0.6875rem] text-mute">
              {currentUser.role}
            </div>
          </div>
          <Settings className="h-3.5 w-3.5 text-mute" />
        </button>
      </div>
    </aside>
  )
}

function Topbar() {
  const { view, setCommandOpen } = useShell()
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-surface/80 px-5 backdrop-blur">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-mute">OBLIVION</span>
        <ChevronRight className="h-3.5 w-3.5 text-mute" />
        <span className="font-medium text-fg">{VIEW_TITLES[view]}</span>
      </div>
      <div className="flex-1" />
      <button
        onClick={() => setCommandOpen(true)}
        className="flex h-8 items-center gap-2 rounded-md border border-line bg-inset px-2.5 text-[0.8125rem] text-mute transition-colors hover:border-line-strong hover:text-dim"
      >
        <Search className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Search or run command</span>
        <kbd className="ml-1 rounded border border-line bg-surface px-1 py-0.5 font-mono text-[0.625rem]">
          ⌘K
        </kbd>
      </button>
      <button
        className="relative flex h-8 w-8 items-center justify-center rounded-md text-dim hover:bg-inset hover:text-fg"
        aria-label="Notifications"
      >
        <Bell className="h-4 w-4" />
        <span
          className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: 'var(--warning)' }}
        />
      </button>
    </header>
  )
}

function ToastViewport() {
  const { toasts, dismissToast } = useShell()
  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-100 flex w-80 flex-col gap-2">
      {toasts.map((t) => {
        const color =
          t.tone === 'success'
            ? 'var(--success)'
            : t.tone === 'danger'
              ? 'var(--danger)'
              : t.tone === 'warning'
                ? 'var(--warning)'
                : 'var(--accent)'
        const Icon =
          t.tone === 'danger'
            ? X
            : t.tone === 'warning'
              ? AlertTriangle
              : Check
        return (
          <div
            key={t.id}
            className="animate-fade-up pointer-events-auto flex items-start gap-2.5 rounded-lg border border-line-strong bg-elevated p-3 shadow-xl"
          >
            <div
              className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full"
              style={{ backgroundColor: `color-mix(in oklab, ${color} 18%, transparent)` }}
            >
              <Icon className="h-3 w-3" style={{ color }} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[0.8125rem] font-medium text-fg">{t.title}</p>
              {t.description && (
                <p className="mt-0.5 text-xs text-dim">{t.description}</p>
              )}
            </div>
            <button
              onClick={() => dismissToast(t.id)}
              className="text-mute hover:text-fg"
              aria-label="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}

function ViewRouter() {
  const { view } = useShell()
  switch (view) {
    case 'overview':
      return <OverviewView />
    case 'operations':
      return <OperationsView />
    case 'targets':
      return <TargetsView />
    case 'recovery':
      return <RecoveryView />
    case 'residual':
      return <ResidualView />
    case 'assurance':
      return <AssuranceView />
    case 'certificates':
      return <CertificatesView />
    case 'audit':
      return <AuditView />
    case 'system':
      return <SystemView />
    case 'settings':
      return <SettingsView />
    case 'workflow':
      return <WorkflowView />
    default:
      return <OverviewView />
  }
}

function ShellInner() {
  const { view } = useShell()
  return (
    <div className="flex h-dvh overflow-hidden bg-bg text-fg">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main key={view} className="animate-fade-up min-h-0 flex-1 overflow-y-auto">
          <ViewRouter />
        </main>
      </div>
      <CommandPalette />
      <ToastViewport />
    </div>
  )
}

export function AppShell() {
  return (
    <ShellProvider>
      <ShellInner />
    </ShellProvider>
  )
}
