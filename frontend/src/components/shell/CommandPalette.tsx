import { useEffect, useMemo, useRef, useState, type ComponentType } from 'react'
import { useNavigate } from 'react-router'
import { ArrowRight, Moon, PanelLeft, RotateCw, Search, Sun } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { cn } from '@/lib/cn'
import { usePrefs } from '@/lib/prefs'
import { NAV_ITEMS, type NavItem } from './nav'
import { Dialog } from '@/components/ui/Dialog'
import { Kbd } from '@/components/ui/Panel'

interface ActionItem {
  id: string
  label: string
  category: string
  icon: ComponentType<{ className?: string }>
  perform: () => void
  hint?: string
}

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const theme = usePrefs((s) => s.theme)
  const setTheme = usePrefs((s) => s.setTheme)
  const toggleSidebar = usePrefs((s) => s.toggleSidebar)

  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)

  const actionItems: ActionItem[] = useMemo(() => {
    const navActions: ActionItem[] = NAV_ITEMS.map((item: NavItem) => ({
      id: `nav-${item.id}`,
      label: item.label,
      category: 'Navigation',
      icon: item.icon,
      perform: () => {
        void navigate(item.path)
        onOpenChange(false)
      },
      hint: item.purpose,
    }))

    const utilityActions: ActionItem[] = [
      {
        id: 'toggle-sidebar',
        label: 'Toggle Sidebar',
        category: 'View',
        icon: PanelLeft,
        perform: () => {
          toggleSidebar()
          onOpenChange(false)
        },
      },
      {
        id: 'toggle-theme',
        label: theme === 'dark' ? 'Switch to Light Theme' : 'Switch to Dark Theme',
        category: 'Preferences',
        icon: theme === 'dark' ? Sun : Moon,
        perform: () => {
          setTheme(theme === 'dark' ? 'light' : 'dark')
          onOpenChange(false)
        },
      },
      {
        id: 'refresh-cache',
        label: 'Refresh All Queries',
        category: 'System',
        icon: RotateCw,
        perform: () => {
          void queryClient.invalidateQueries()
          onOpenChange(false)
        },
      },
    ]

    return [...navActions, ...utilityActions]
  }, [navigate, onOpenChange, queryClient, setTheme, theme, toggleSidebar])

  const filteredItems = useMemo(() => {
    const clean = query.trim().toLowerCase()
    if (!clean) return actionItems
    return actionItems.filter(
      (item) =>
        item.label.toLowerCase().includes(clean) ||
        item.category.toLowerCase().includes(clean) ||
        (item.hint && item.hint.toLowerCase().includes(clean)),
    )
  }, [actionItems, query])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 20)
    }
  }, [open])

  useEffect(() => {
    setSelectedIndex(0)
  }, [filteredItems])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => (i + 1) % (filteredItems.length || 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => (i - 1 + filteredItems.length) % (filteredItems.length || 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const current = filteredItems[selectedIndex]
      if (current) {
        current.perform()
      }
    }
  }

  // Scroll active item into view
  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const activeEl = list.children[selectedIndex] as HTMLElement | undefined
    if (activeEl) {
      activeEl.scrollIntoView({ block: 'nearest' })
    }
  }, [selectedIndex])

  return (
    <Dialog open={open} onClose={() => onOpenChange(false)} title="Command Palette" size="lg">
      <div className="flex flex-col overflow-hidden">
        <div className="flex h-12 items-center gap-3 border-b border-line px-3">
          <Search className="h-4 w-4 shrink-0 text-mute" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-list"
            aria-autocomplete="list"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or navigate to a view..."
            className="flex-1 bg-transparent text-sm text-fg placeholder:text-mute focus:outline-none"
          />
          <Kbd>ESC</Kbd>
        </div>

        <ul id="command-list" ref={listRef} role="listbox" className="max-h-72 overflow-y-auto p-2">
          {filteredItems.length === 0 ? (
            <li className="px-3 py-6 text-center text-xs text-mute">
              No commands matching &ldquo;{query}&rdquo;
            </li>
          ) : (
            filteredItems.map((item, idx) => {
              const Icon = item.icon
              const isSelected = idx === selectedIndex
              return (
                <li
                  key={item.id}
                  id={`command-option-${idx}`}
                  role="option"
                  aria-selected={isSelected}
                  className="list-none"
                >
                  <button
                    type="button"
                    onClick={() => item.perform()}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={cn(
                      'flex w-full cursor-pointer items-center justify-between gap-3 rounded-md px-2.5 py-2 text-xs text-left',
                      'transition-colors duration-[var(--motion-duration)]',
                      isSelected ? 'bg-elevated text-fg' : 'text-dim hover:text-fg',
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <Icon
                        className={cn('h-4 w-4 shrink-0', isSelected ? 'text-accent' : 'text-mute')}
                      />
                      <span className="truncate font-medium">{item.label}</span>
                      {item.hint && (
                        <span className="hidden truncate text-[0.6875rem] text-mute sm:inline">
                          {item.hint}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-sm border border-line-strong bg-inset px-1.5 py-0.5 text-[0.625rem] text-dim uppercase">
                        {item.category}
                      </span>
                      {isSelected && <ArrowRight className="h-3 w-3 text-dim" aria-hidden="true" />}
                    </div>
                  </button>
                </li>
              )
            })
          )}
        </ul>

        <div className="flex items-center justify-between border-t border-line bg-inset px-3 py-1.5 text-[0.6875rem] text-mute">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <Kbd>↑</Kbd>
              <Kbd>↓</Kbd>
              Navigate
            </span>
            <span className="inline-flex items-center gap-1">
              <Kbd>↵</Kbd>
              Select
            </span>
          </div>
          <span>Oblivion Forensic Console</span>
        </div>
      </div>
    </Dialog>
  )
}
