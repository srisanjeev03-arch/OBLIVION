'use client'

import { cn } from '@/lib/utils'
import { toneColor, type Tone } from '@/lib/labels'
import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

/* ---------- Panel ---------- */

export function Panel({
  className,
  children,
  inset,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { inset?: boolean }) {
  return (
    <div
      className={cn(
        'rounded-lg border border-line bg-surface',
        inset && 'bg-inset',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

/* ---------- Button ---------- */

type BtnVariant = 'primary' | 'default' | 'ghost' | 'outline' | 'danger' | 'subtle'
type BtnSize = 'sm' | 'md' | 'icon'

export function Button({
  variant = 'default',
  size = 'md',
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: BtnVariant
  size?: BtnSize
}) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap transition-colors duration-150',
        'disabled:pointer-events-none disabled:opacity-45',
        size === 'sm' && 'h-8 px-3 text-[0.8125rem]',
        size === 'md' && 'h-9 px-3.5 text-sm',
        size === 'icon' && 'h-9 w-9',
        variant === 'primary' &&
          'bg-accent text-accent-fg hover:opacity-90 active:opacity-80',
        variant === 'default' &&
          'border border-line-strong bg-elevated text-fg hover:bg-inset',
        variant === 'outline' &&
          'border border-line-strong text-fg hover:bg-elevated',
        variant === 'ghost' && 'text-dim hover:bg-elevated hover:text-fg',
        variant === 'subtle' && 'bg-inset text-fg hover:bg-elevated',
        variant === 'danger' &&
          'bg-danger text-white hover:opacity-90 active:opacity-80',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}

/* ---------- StatusPill ---------- */

export function StatusPill({
  tone,
  children,
  dot = true,
  className,
}: {
  tone: Tone
  children: React.ReactNode
  dot?: boolean
  className?: string
}) {
  const color = toneColor(tone)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium',
        className,
      )}
      style={{
        color: tone === 'neutral' ? 'var(--dim)' : color,
        borderColor:
          tone === 'neutral'
            ? 'var(--line-strong)'
            : `color-mix(in oklab, ${color} 35%, transparent)`,
        backgroundColor:
          tone === 'neutral'
            ? 'transparent'
            : `color-mix(in oklab, ${color} 12%, transparent)`,
      }}
    >
      {dot && (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: tone === 'neutral' ? 'var(--mute)' : color }}
        />
      )}
      {children}
    </span>
  )
}

/* ---------- Badge (quiet) ---------- */

export function Tag({
  children,
  className,
  mono,
}: {
  children: React.ReactNode
  className?: string
  mono?: boolean
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded border border-line bg-inset px-1.5 py-0.5 text-xs text-dim',
        mono && 'font-mono tabular',
        className,
      )}
    >
      {children}
    </span>
  )
}

/* ---------- Segmented control ---------- */

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  size = 'md',
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: React.ReactNode }[]
  size?: 'sm' | 'md'
  className?: string
}) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-0.5 rounded-md border border-line bg-inset p-0.5',
        className,
      )}
      role="tablist"
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'rounded-[calc(var(--radius)-4px)] font-medium transition-colors',
              size === 'sm' ? 'h-6 px-2 text-xs' : 'h-7 px-2.5 text-[0.8125rem]',
              active
                ? 'bg-elevated text-fg shadow-sm'
                : 'text-dim hover:text-fg',
            )}
            style={active ? { color: 'var(--accent)' } : undefined}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

/* ---------- Meta row (label / value) ---------- */

export function Meta({
  label,
  children,
  mono,
}: {
  label: string
  children: React.ReactNode
  mono?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="text-xs text-mute">{label}</span>
      <span
        className={cn(
          'text-right text-[0.8125rem] text-fg',
          mono && 'font-mono tabular text-dim',
        )}
      >
        {children}
      </span>
    </div>
  )
}

/* ---------- Copyable hash ---------- */

export function Hash({
  value,
  truncate = true,
  className,
}: {
  value: string
  truncate?: boolean
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const shown = truncate && value.length > 20 ? `${value.slice(0, 10)}…${value.slice(-6)}` : value
  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(value)
        setCopied(true)
        setTimeout(() => setCopied(false), 1400)
      }}
      className={cn(
        'group inline-flex items-center gap-1.5 rounded border border-line bg-inset px-1.5 py-0.5 font-mono text-xs text-dim transition-colors hover:border-line-strong hover:text-fg',
        className,
      )}
      title="Copy full value"
    >
      <span className="tabular">{shown}</span>
      {copied ? (
        <Check className="h-3 w-3" style={{ color: 'var(--success)' }} />
      ) : (
        <Copy className="h-3 w-3 opacity-50 group-hover:opacity-100" />
      )}
    </button>
  )
}

/* ---------- Section heading ---------- */

export function SectionTitle({
  children,
  action,
}: {
  children: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="text-[0.8125rem] font-semibold tracking-wide text-dim">
        {children}
      </h3>
      {action}
    </div>
  )
}

/* ---------- Empty state ---------- */

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon?: React.ComponentType<{ className?: string }>
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      {Icon && (
        <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-line bg-inset">
          <Icon className="h-5 w-5 text-mute" />
        </div>
      )}
      <div>
        <p className="text-sm font-medium text-fg">{title}</p>
        <p className="mx-auto mt-1 max-w-xs text-[0.8125rem] text-mute">
          {description}
        </p>
      </div>
      {action}
    </div>
  )
}

/* ---------- Skeleton ---------- */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn('animate-pulse rounded bg-inset', className)}
      aria-hidden
    />
  )
}

/* ---------- Progress ---------- */

export function Progress({
  value,
  tone = 'accent',
  className,
}: {
  value: number
  tone?: Tone
  className?: string
}) {
  return (
    <div
      className={cn('h-1.5 w-full overflow-hidden rounded-full bg-inset', className)}
      role="progressbar"
      aria-valuenow={Math.round(value)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full transition-[width] duration-500 ease-out"
        style={{
          width: `${Math.max(0, Math.min(100, value))}%`,
          backgroundColor: toneColor(tone),
        }}
      />
    </div>
  )
}

/* ---------- Switch ---------- */

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border transition-colors',
        checked ? 'border-transparent' : 'border-line-strong bg-inset',
      )}
      style={checked ? { backgroundColor: 'var(--accent)' } : undefined}
    >
      <span
        className={cn(
          'inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform',
          checked ? 'translate-x-4' : 'translate-x-0.5',
        )}
        style={checked ? undefined : { backgroundColor: 'var(--dim)' }}
      />
    </button>
  )
}
