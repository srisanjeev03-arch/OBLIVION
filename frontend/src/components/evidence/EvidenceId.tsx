import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '@/lib/cn'
import { PLACEHOLDER, truncateMiddle } from '@/lib/format'

export interface EvidenceIdProps {
  /** Backend-provided identifier or hash. `undefined` renders the placeholder, never a fake. */
  value: string | null | undefined
  /** Accessible description, e.g. "Operation ID", "SHA-256". */
  label: string
  truncate?: boolean
  size?: 'sm' | 'md'
  className?: string
}

/**
 * Monospace identifier with copy-to-clipboard and visible + announced feedback. Used for every
 * ID and hash the console renders so technical values are always distinguishable and copyable.
 */
export function EvidenceId({
  value,
  label,
  truncate = true,
  size = 'sm',
  className,
}: EvidenceIdProps) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => () => window.clearTimeout(timer.current), [])

  if (!value) {
    return (
      <span
        className={cn(
          'font-mono tabular text-mute',
          size === 'sm' ? 'text-xs' : 'text-sm',
          className,
        )}
        aria-label={`${label}: not provided`}
      >
        {PLACEHOLDER}
      </span>
    )
  }

  const shown = truncate ? truncateMiddle(value) : value

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access denied — leave the value selectable instead of failing loudly.
      setCopied(false)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void copy()}
      title={`Copy ${label}: ${value}`}
      aria-label={`Copy ${label} ${value}`}
      className={cn(
        'group inline-flex max-w-full items-center gap-1.5 rounded-sm border border-line bg-inset font-mono tabular text-dim',
        'transition-colors duration-[var(--motion-duration)] hover:border-line-strong hover:text-fg',
        size === 'sm' ? 'h-5 px-1.5 text-[0.6875rem]' : 'h-6 px-2 text-xs',
        className,
      )}
    >
      <span className="truncate">{shown}</span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0 text-success" aria-hidden="true" />
      ) : (
        <Copy className="h-3 w-3 shrink-0 opacity-50 group-hover:opacity-100" aria-hidden="true" />
      )}
      <span className="sr-only" role="status" aria-live="polite">
        {copied ? `${label} copied` : ''}
      </span>
    </button>
  )
}

/** SHA-256 and other digests: same control, full-width by default so hashes are auditable. */
export function EvidenceHash({
  value,
  label = 'SHA-256',
  className,
}: Omit<EvidenceIdProps, 'label'> & { label?: string }) {
  return (
    <EvidenceId
      value={value}
      label={label}
      truncate={false}
      className={cn('break-all', className)}
    />
  )
}
