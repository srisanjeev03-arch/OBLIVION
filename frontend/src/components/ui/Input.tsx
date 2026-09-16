import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string
  /** Visually hidden label; still announced. Use when the layout already labels the field. */
  hideLabel?: boolean
  hint?: string
  error?: string
  mono?: boolean
  leadingIcon?: ReactNode
  size?: 'sm' | 'md'
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hideLabel, hint, error, mono, leadingIcon, size = 'md', className, id, ...props },
  ref,
) {
  const autoId = useId()
  const inputId = id ?? autoId
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {label && (
        <label
          htmlFor={inputId}
          className={cn('text-xs font-medium text-dim', hideLabel && 'sr-only')}
        >
          {label}
        </label>
      )}
      <div className="relative">
        {leadingIcon && (
          <span
            className="pointer-events-none absolute inset-y-0 left-2.5 inline-flex items-center text-mute"
            aria-hidden="true"
          >
            {leadingIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
          className={cn(
            'w-full rounded-md border bg-elevated text-fg placeholder:text-mute',
            'transition-colors duration-[var(--motion-duration)]',
            'hover:border-line-active focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25',
            'disabled:cursor-not-allowed disabled:opacity-45',
            size === 'sm' ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-[0.8125rem]',
            leadingIcon && (size === 'sm' ? 'pl-7' : 'pl-8'),
            mono && 'font-mono tabular',
            error ? 'border-danger' : 'border-line-strong',
          )}
          {...props}
        />
      </div>
      {hint && !error && (
        <p id={hintId} className="text-xs text-mute">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  )
})
