import { useEffect, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/cn'
import { IconButton } from '@/components/ui/IconButton'

export interface InspectorDrawerProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  subtitle?: ReactNode
  badge?: ReactNode
  icon?: ReactNode
  actions?: ReactNode
  children: ReactNode
  footer?: ReactNode
  width?: 'md' | 'lg' | 'xl'
  className?: string
}

const widthClasses = {
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
} as const

export function InspectorDrawer({
  open,
  onClose,
  title,
  subtitle,
  badge,
  icon,
  actions,
  children,
  footer,
  width = 'lg',
  className,
}: InspectorDrawerProps) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <>
      {/* Backdrop for overlay widths */}
      <div
        className="fixed inset-0 z-40 bg-bg/60 backdrop-blur-xs transition-opacity lg:hidden"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Inspector"
        className={cn(
          'fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-line-strong bg-surface shadow-2xl motion-drawer',
          widthClasses[width],
          className,
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-line-strong px-5">
          <div className="flex min-w-0 items-center gap-2.5">
            {icon && <span className="text-accent shrink-0">{icon}</span>}
            <div className="flex min-w-0 flex-col gap-0.5">
              <div className="flex items-center gap-2">
                <h2 className="truncate text-sm font-semibold tracking-tight text-fg">{title}</h2>
                {badge && <div className="shrink-0">{badge}</div>}
              </div>
              {subtitle && (
                <p className="truncate font-mono text-[0.6875rem] text-mute">{subtitle}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {actions}
            <IconButton label="Close inspector" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </IconButton>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 text-xs">{children}</div>

        {footer && (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-line bg-inset/50 px-5 py-3">
            {footer}
          </div>
        )}
      </aside>
    </>
  )
}
