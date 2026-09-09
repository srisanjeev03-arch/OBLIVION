import { useId, type SelectHTMLAttributes } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/cn'

export interface SelectOption<T extends string = string> {
  value: T
  label: string
  disabled?: boolean
}

export interface SelectProps<T extends string = string> extends Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  'size' | 'onChange' | 'value'
> {
  label: string
  hideLabel?: boolean
  options: readonly SelectOption<T>[]
  value: T | ''
  onChange: (value: T) => void
  placeholder?: string
  size?: 'sm' | 'md'
  hint?: string
}

export function Select<T extends string = string>({
  label,
  hideLabel,
  options,
  value,
  onChange,
  placeholder,
  size = 'md',
  hint,
  className,
  id,
  disabled,
  required,
  ...props
}: SelectProps<T>) {
  const autoId = useId()
  const selectId = id ?? autoId
  const hintId = hint ? `${selectId}-hint` : undefined
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label
        htmlFor={selectId}
        className={cn('text-xs font-medium text-dim', hideLabel && 'sr-only')}
      >
        {label}
      </label>
      <div className="relative">
        <select
          id={selectId}
          value={value}
          disabled={disabled}
          required={required}
          aria-describedby={hintId}
          onChange={(e) => onChange(e.target.value as T)}
          className={cn(
            'w-full appearance-none rounded-md border border-line-strong bg-surface pr-8 text-fg',
            'transition-colors duration-[var(--motion-duration)]',
            'focus:border-accent focus:outline-none',
            'disabled:cursor-not-allowed disabled:opacity-45',
            size === 'sm' ? 'h-7 pl-2.5 text-xs' : 'h-8 pl-3 text-[0.8125rem]',
            value === '' && 'text-mute',
          )}
          {...props}
        >
          {placeholder !== undefined && (
            <option value="" disabled={required}>
              {placeholder}
            </option>
          )}
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-mute"
          aria-hidden="true"
        />
      </div>
      {hint && (
        <p id={hintId} className="text-xs text-mute">
          {hint}
        </p>
      )}
    </div>
  )
}
