import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/cn'
import { IconButton } from './IconButton'

export interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  /** Destructive dialogs use a stronger frame so the operator cannot mistake them. */
  tone?: 'default' | 'danger'
  className?: string
}

const sizeClasses = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl' } as const

/**
 * Modal dialog built on the native <dialog> element: focus trapping, Escape handling and inert
 * background come from the platform. The console never renders "Are you sure?" alone — callers
 * must pass concrete backend facts into `children`.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  tone = 'default',
  className,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descId = useId()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()

    const handleBackdropClick = (e: MouseEvent) => {
      if (e.target === el) onClose()
    }
    el.addEventListener('click', handleBackdropClick)
    return () => el.removeEventListener('click', handleBackdropClick)
  }, [open, onClose])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onCancel={(e) => {
        e.preventDefault()
        onClose()
      }}
      className={cn(
        'm-auto w-[calc(100%-2rem)] rounded-lg border bg-elevated p-0 text-fg shadow-2xl',
        'backdrop:bg-black/60 open:motion-enter',
        tone === 'danger' ? 'border-danger/50' : 'border-line-strong',
        sizeClasses[size],
        className,
      )}
    >
      <div className="flex items-start justify-between gap-4 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 id={titleId} className="text-sm font-semibold">
            {title}
          </h2>
          {description && (
            <p id={descId} className="mt-0.5 text-xs text-dim">
              {description}
            </p>
          )}
        </div>
        <IconButton label="Close dialog" size="sm" onClick={onClose}>
          <X className="h-4 w-4" />
        </IconButton>
      </div>
      {children && <div className="px-4 py-3">{children}</div>}
      {footer && (
        <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
          {footer}
        </div>
      )}
    </dialog>
  )
}
