import type { ReactNode } from 'react'
import { Breadcrumbs, type BreadcrumbItem } from '@/components/ui/Breadcrumbs'
import { cn } from '@/lib/cn'

export interface PageHeaderProps {
  title: ReactNode
  purpose?: string
  description?: string
  icon?: ReactNode
  badge?: ReactNode
  breadcrumbs?: BreadcrumbItem[]
  actions?: ReactNode
  statusIndicator?: ReactNode
  className?: string
}

export function PageHeader({
  title,
  purpose,
  description,
  icon,
  badge,
  breadcrumbs,
  actions,
  statusIndicator,
  className,
}: PageHeaderProps) {
  const subtitle = description || purpose

  return (
    <div
      className={cn(
        'flex flex-col gap-2.5 border-b border-line bg-surface px-6 py-4',
        className,
      )}
    >
      {breadcrumbs && <Breadcrumbs items={breadcrumbs} className="mb-0.5" />}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {icon && (
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line-strong bg-elevated text-accent">
              {icon}
            </span>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-2.5">
              <h1 className="text-[1.125rem] font-semibold text-fg tracking-tight truncate">{title}</h1>
              {badge && <div className="shrink-0">{badge}</div>}
              {statusIndicator && <div className="shrink-0">{statusIndicator}</div>}
            </div>
            {subtitle && (
              <p className="text-xs text-dim mt-0.5 truncate leading-relaxed">{subtitle}</p>
            )}
          </div>
        </div>

        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </div>
  )
}
