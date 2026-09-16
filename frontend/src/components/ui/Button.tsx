import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'

export type ButtonVariant = 'primary' | 'default' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  /** Shows a spinner, disables the control and announces busy state. */
  loading?: boolean
  leadingIcon?: ReactNode
  trailingIcon?: ReactNode
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-accent-fg hover:brightness-110 active:brightness-95 shadow-sm',
  default: 'border border-line-strong bg-elevated text-fg hover:bg-inset hover:border-line-active active:bg-inset',
  outline: 'border border-line-strong text-fg hover:bg-elevated hover:border-line-active active:bg-inset',
  ghost: 'text-dim hover:bg-elevated hover:text-fg active:bg-inset',
  danger: 'border border-danger/40 bg-danger-soft text-danger hover:bg-danger hover:text-white',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-[0.8125rem] gap-2',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'default',
    size = 'md',
    loading = false,
    leadingIcon,
    trailingIcon,
    className,
    children,
    disabled,
    type = 'button',
    ...props
  },
  ref,
) {
  const isDisabled = disabled || loading
  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center rounded-md font-medium whitespace-nowrap select-none',
        'transition-colors duration-[var(--motion-duration)]',
        'disabled:pointer-events-none disabled:opacity-45',
        sizeClasses[size],
        variantClasses[variant],
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 motion-spin" aria-hidden="true" />
      ) : (
        leadingIcon && (
          <span className="inline-flex shrink-0" aria-hidden="true">
            {leadingIcon}
          </span>
        )
      )}
      {children}
      {trailingIcon && !loading && (
        <span className="inline-flex shrink-0" aria-hidden="true">
          {trailingIcon}
        </span>
      )}
    </button>
  )
})
