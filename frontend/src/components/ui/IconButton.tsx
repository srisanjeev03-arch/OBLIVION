import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Required: icon-only controls must have an accessible name. */
  label: string
  size?: 'sm' | 'md'
  variant?: 'ghost' | 'outline'
  pressed?: boolean
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  {
    label,
    size = 'md',
    variant = 'ghost',
    pressed,
    className,
    children,
    type = 'button',
    ...props
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-md text-dim',
        'transition-colors duration-[var(--motion-duration)]',
        'hover:bg-elevated hover:text-fg active:bg-inset',
        'disabled:pointer-events-none disabled:opacity-45',
        size === 'sm' ? 'h-7 w-7' : 'h-8 w-8',
        variant === 'outline' && 'border border-line-strong',
        pressed && 'bg-inset text-fg',
        className,
      )}
      {...props}
    >
      <span className="inline-flex" aria-hidden="true">
        {children}
      </span>
    </button>
  )
})
