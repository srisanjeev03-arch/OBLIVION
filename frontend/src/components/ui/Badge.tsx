import { type HTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export type BadgeVariant =
  'default' | 'neutral' | 'accent' | 'info' | 'success' | 'warning' | 'danger' | 'outline'
export type BadgeSize = 'xs' | 'sm' | 'md'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
  size?: BadgeSize
  leadingIcon?: ReactNode
  trailingIcon?: ReactNode
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'border-line-strong bg-inset text-fg',
  neutral: 'border-line bg-surface text-dim',
  accent: 'border-accent/40 bg-accent-soft text-accent',
  info: 'border-info/40 bg-info-soft text-info',
  success: 'border-success/40 bg-success-soft text-success',
  warning: 'border-warning/40 bg-warning-soft text-warning',
  danger: 'border-danger/40 bg-danger-soft text-danger',
  outline: 'border-line-strong bg-transparent text-fg',
}

const sizeStyles: Record<BadgeSize, string> = {
  xs: 'h-4 px-1 text-[0.625rem] gap-1',
  sm: 'h-5 px-1.5 text-[0.6875rem] gap-1.5',
  md: 'h-6 px-2 text-xs gap-1.5',
}

export function Badge({
  variant = 'default',
  size = 'sm',
  leadingIcon,
  trailingIcon,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-sm border font-medium whitespace-nowrap select-none',
        sizeStyles[size],
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      {leadingIcon && (
        <span className="inline-flex shrink-0" aria-hidden="true">
          {leadingIcon}
        </span>
      )}
      {children}
      {trailingIcon && (
        <span className="inline-flex shrink-0" aria-hidden="true">
          {trailingIcon}
        </span>
      )}
    </span>
  )
}
