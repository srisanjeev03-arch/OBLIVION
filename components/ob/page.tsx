'use client'

import { cn } from '@/lib/utils'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-fg text-balance">
          {title}
        </h1>
        {description && (
          <p className="mt-1 max-w-2xl text-[0.8125rem] text-dim text-pretty">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Page({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return <div className={cn('mx-auto max-w-[1400px] p-5 lg:p-6', className)}>{children}</div>
}
