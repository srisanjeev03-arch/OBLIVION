import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

export interface SwitchProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange'> {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  label?: string
  description?: string
  size?: 'sm' | 'md'
}

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(function Switch(
  {
    checked,
    onCheckedChange,
    label,
    description,
    size = 'md',
    disabled = false,
    className,
    ...props
  },
  ref,
) {
  return (
    <label
      className={cn(
        'inline-flex items-center gap-2.5 select-none cursor-pointer',
        disabled && 'cursor-not-allowed opacity-50',
        className,
      )}
    >
      <button
        ref={ref}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          'relative inline-flex shrink-0 items-center rounded-full transition-colors duration-[var(--motion-duration)] border border-line-strong',
          size === 'sm' ? 'h-4 w-7' : 'h-5 w-9',
          checked ? 'bg-accent border-accent/60' : 'bg-inset hover:bg-elevated',
        )}
        {...props}
      >
        <span
          className={cn(
            'inline-block rounded-full bg-white shadow-xs transition-transform duration-[var(--motion-duration)]',
            size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5',
            checked
              ? size === 'sm'
                ? 'translate-x-3.5 bg-accent-fg'
                : 'translate-x-4.5 bg-accent-fg'
              : 'translate-x-0.5 bg-mute',
          )}
        />
      </button>
      {(label || description) && (
        <span className="flex flex-col text-left">
          {label && <span className="text-xs font-medium text-fg">{label}</span>}
          {description && <span className="text-[0.6875rem] text-dim">{description}</span>}
        </span>
      )}
    </label>
  )
})
