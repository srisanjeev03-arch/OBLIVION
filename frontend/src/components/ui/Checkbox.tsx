import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: ReactNode
  description?: ReactNode
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, description, className, disabled, checked, onChange, id, ...props },
  ref,
) {
  const inputId =
    id || (typeof label === 'string' ? label.toLowerCase().replace(/\s+/g, '-') : undefined)

  return (
    <label
      htmlFor={inputId}
      className={cn(
        'inline-flex items-start gap-2.5 select-none cursor-pointer',
        disabled && 'cursor-not-allowed opacity-50',
        className,
      )}
    >
      <span className="relative flex items-center justify-center mt-0.5">
        <input
          ref={ref}
          id={inputId}
          type="checkbox"
          checked={checked}
          onChange={onChange}
          disabled={disabled}
          className="peer sr-only"
          {...props}
        />
        <span
          className={cn(
            'flex h-4 w-4 items-center justify-center rounded-xs border border-line-strong bg-inset',
            'transition-colors duration-[var(--motion-duration)]',
            'peer-checked:bg-accent peer-checked:border-accent/60',
            'peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-focus-visible:ring-offset-1',
          )}
        >
          {checked && <Check className="h-3 w-3 text-accent-fg stroke-[3]" aria-hidden="true" />}
        </span>
      </span>
      {(label || description) && (
        <span className="flex flex-col text-left">
          {label && <span className="text-xs font-medium text-fg">{label}</span>}
          {description && <span className="text-[0.6875rem] text-dim">{description}</span>}
        </span>
      )}
    </label>
  )
})
