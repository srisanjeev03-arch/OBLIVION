import { type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface TabItem<T extends string = string> {
  id: T
  label: string
  icon?: ReactNode
  count?: number | string
  disabled?: boolean
}

export interface TabsProps<T extends string = string> {
  items: TabItem<T>[]
  value: T
  onChange: (value: T) => void
  size?: 'sm' | 'md'
  className?: string
}

export function Tabs<T extends string = string>({
  items,
  value,
  onChange,
  size = 'md',
  className,
}: TabsProps<T>) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-line bg-surface p-0.5',
        className,
      )}
    >
      {items.map((tab) => {
        const isSelected = tab.id === value
        return (
          <button
            key={tab.id}
            role="tab"
            type="button"
            aria-selected={isSelected}
            disabled={tab.disabled}
            onClick={() => onChange(tab.id)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-sm font-medium whitespace-nowrap select-none transition-colors duration-[var(--motion-duration)]',
              'disabled:pointer-events-none disabled:opacity-40',
              size === 'sm' ? 'h-6 px-2 text-xs' : 'h-7 px-2.5 text-xs',
              isSelected
                ? 'bg-elevated text-fg shadow-xs border border-line-strong'
                : 'text-dim hover:bg-inset hover:text-fg border border-transparent',
            )}
          >
            {tab.icon && (
              <span className="inline-flex shrink-0 opacity-80" aria-hidden="true">
                {tab.icon}
              </span>
            )}
            <span>{tab.label}</span>
            {tab.count !== undefined && (
              <span
                className={cn(
                  'rounded-xs px-1 text-[0.625rem] font-mono tabular',
                  isSelected ? 'bg-inset text-fg' : 'bg-surface text-mute',
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
