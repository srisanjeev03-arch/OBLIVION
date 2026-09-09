import { NavLink } from 'react-router'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { cn } from '@/lib/cn'
import { usePrefs } from '@/lib/prefs'
import { useAuth } from '@/lib/auth/context'
import { IconButton } from '@/components/ui/IconButton'
import { Tooltip } from '@/components/ui/Tooltip'
import { UserIdentityBadge } from '@/components/auth/UserIdentityBadge'
import { getNavSectionsForUser } from './nav'

function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" fill="none">
      <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M6.5 6.5l11 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  const toggleSidebar = usePrefs((s) => s.toggleSidebar)
  const { user } = useAuth()
  const visibleSections = getNavSectionsForUser(user)

  return (
    <aside
      aria-label="Primary"
      className={cn(
        'flex shrink-0 flex-col border-r border-line bg-surface',
        'transition-[width] duration-[var(--motion-duration)]',
        collapsed ? 'w-12' : 'w-56',
      )}
    >
      {/* Brand Header */}
      <div
        className={cn(
          'flex h-11 items-center border-b border-line',
          collapsed ? 'justify-center' : 'gap-2.5 px-3',
        )}
      >
        <Mark className="h-5 w-5 shrink-0 text-fg" />
        {!collapsed && (
          <div className="min-w-0 leading-none">
            <div className="text-[0.8125rem] font-bold tracking-tight text-fg">OBLIVION</div>
            <div className="mt-0.5 text-[0.5625rem] tracking-[0.14em] text-mute uppercase font-mono">
              Forensic Console
            </div>
          </div>
        )}
      </div>

      {/* Dynamic Role Navigation */}
      <nav className="flex-1 overflow-y-auto py-2" aria-label="Sections">
        {visibleSections.map((section) => (
          <div key={section.label} className="mb-3">
            {!collapsed && (
              <p className="px-3 pb-1 pt-1 text-[0.5625rem] font-bold uppercase tracking-[0.14em] text-mute">
                {section.label}
              </p>
            )}
            <ul className={cn('flex flex-col gap-0.5', collapsed ? 'items-center px-1.5' : 'px-2')}>
              {section.items.map((item) => {
                const Icon = item.icon
                const link = (
                  <NavLink
                    to={item.path}
                    end={item.path === '/'}
                    aria-label={collapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'group relative flex items-center rounded-sm text-[0.8125rem] outline-offset-[-2px]',
                        'transition-colors duration-[var(--motion-duration)]',
                        collapsed ? 'h-8 w-8 justify-center' : 'h-7 gap-2.5 px-2 text-xs',
                        isActive
                          ? 'bg-inset text-fg font-medium border border-line-strong'
                          : 'text-dim hover:bg-elevated hover:text-fg',
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        {isActive && (
                          <span
                            aria-hidden="true"
                            className={cn(
                              'absolute left-0 top-1/2 h-3.5 w-0.5 -translate-y-1/2 rounded-r bg-accent',
                              collapsed && '-left-1.5',
                            )}
                          />
                        )}
                        <Icon className="h-3.5 w-3.5 shrink-0" />
                        {!collapsed && <span className="truncate">{item.label}</span>}
                        {!collapsed && item.pendingBackend && (
                          <span
                            className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full border border-line-strong"
                            title={`Awaiting backend: ${item.pendingBackend}`}
                            aria-label="awaiting backend"
                          />
                        )}
                      </>
                    )}
                  </NavLink>
                )
                return (
                  <li key={item.id}>
                    {collapsed ? (
                      <Tooltip content={item.label} side="right">
                        {link}
                      </Tooltip>
                    ) : (
                      link
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* User Account / Workspace Footer */}
      {!collapsed && user && (
        <div className="p-2 border-t border-line">
          <UserIdentityBadge variant="full" />
        </div>
      )}

      {/* Collapse Toggle */}
      <div
        className={cn(
          'flex h-9 items-center border-t border-line',
          collapsed ? 'justify-center' : 'justify-end px-2',
        )}
      >
        <IconButton
          label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          size="sm"
          onClick={toggleSidebar}
          aria-expanded={!collapsed}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-3.5 w-3.5" />
          ) : (
            <PanelLeftClose className="h-3.5 w-3.5" />
          )}
        </IconButton>
      </div>
    </aside>
  )
}
