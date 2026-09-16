import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/cn'

/* ---------- Panel: the basic bordered surface ---------- */

export interface PanelProps extends HTMLAttributes<HTMLElement> {
  inset?: boolean
  as?: 'div' | 'section' | 'article' | 'aside'
}

export function Panel({ inset, as: Tag = 'div', className, children, ...props }: PanelProps) {
  return (
    <Tag
      className={cn(
        'rounded-md border bg-surface',
        inset ? 'border-line bg-inset' : 'border-line',
        className,
      )}
      {...props}
    >
      {children}
    </Tag>
  )
}

/* ---------- PanelHeader: title row with optional status/action slot ---------- */

export function PanelHeader({
  title,
  description,
  aside,
  className,
  headingLevel = 2,
}: {
  title: ReactNode
  description?: ReactNode
  aside?: ReactNode
  className?: string
  headingLevel?: 2 | 3 | 4
}) {
  const Heading = `h${headingLevel}` as const
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-4 border-b border-line px-4 py-2.5',
        className,
      )}
    >
      <div className="min-w-0">
        <Heading className="truncate text-xs font-semibold uppercase tracking-[0.08em] text-dim">
          {title}
        </Heading>
        {description && <p className="mt-0.5 text-[0.6875rem] text-mute leading-relaxed">{description}</p>}
      </div>
      {aside && <div className="flex shrink-0 items-center gap-2">{aside}</div>}
    </div>
  )
}

/* ---------- Meta: label / value row (use inside <MetaList>) ---------- */

export function Meta({
  label,
  children,
  mono,
  className,
}: {
  label: string
  children: ReactNode
  mono?: boolean
  className?: string
}) {
  return (
    <div className={cn('flex items-baseline justify-between gap-4 py-1.5', className)}>
      <dt className="shrink-0 text-xs text-mute">{label}</dt>
      <dd
        className={cn(
          'min-w-0 text-right text-[0.8125rem] text-fg break-words',
          mono && 'font-mono tabular text-dim',
        )}
      >
        {children}
      </dd>
    </div>
  )
}

export function MetaList({ children, className }: { children: ReactNode; className?: string }) {
  return <dl className={cn('divide-y divide-line', className)}>{children}</dl>
}

/* ---------- Kbd ---------- */

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        'inline-flex h-5 min-w-5 items-center justify-center rounded-sm border border-line bg-inset px-1 font-mono text-[0.625rem] text-mute',
        className,
      )}
    >
      {children}
    </kbd>
  )
}

/* ---------- Tag: quiet inline label ---------- */

export function Tag({
  children,
  mono,
  className,
}: {
  children: ReactNode
  mono?: boolean
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border border-line bg-inset px-1.5 py-0.5 text-xs text-dim',
        mono && 'font-mono tabular',
        className,
      )}
    >
      {children}
    </span>
  )
}

/* ---------- Skeleton ---------- */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-sm bg-inset', className)} aria-hidden="true" />
}
