import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface PageToolbarProps {
  children: ReactNode
  className?: string
}

export function PageToolbar({ children, className }: PageToolbarProps) {
  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface/30 px-6 py-2.5 text-xs',
        className,
      )}
    >
      {children}
    </div>
  )
}
