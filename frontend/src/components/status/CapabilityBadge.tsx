import { CheckCircle2, AlertTriangle, CircleSlash, Ban, HelpCircle } from 'lucide-react'
import { cn } from '@/lib/cn'
import type { CapabilityStatus } from '@/lib/api/capabilities'

export interface CapabilityBadgeProps {
  status: CapabilityStatus
  label?: string
  className?: string
}

export function CapabilityBadge({ status, label, className }: CapabilityBadgeProps) {
  switch (status) {
    case 'AVAILABLE':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[0.6875rem] font-semibold tracking-wider uppercase',
            'border-success/40 bg-success-soft text-success',
            className,
          )}
        >
          <CheckCircle2 className="h-3 w-3" />
          <span>{label ?? 'Available'}</span>
        </span>
      )
    case 'LIMITED':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[0.6875rem] font-semibold tracking-wider uppercase',
            'border-warning/40 bg-warning-soft text-warning',
            className,
          )}
        >
          <AlertTriangle className="h-3 w-3" />
          <span>{label ?? 'Limited V1'}</span>
        </span>
      )
    case 'UNAVAILABLE':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[0.6875rem] font-semibold tracking-wider uppercase',
            'border-line-strong bg-inset text-dim',
            className,
          )}
        >
          <CircleSlash className="h-3 w-3" />
          <span>{label ?? 'Unavailable'}</span>
        </span>
      )
    case 'NOT_IMPLEMENTED':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[0.6875rem] font-semibold tracking-wider uppercase',
            'border-line-strong bg-inset text-mute',
            className,
          )}
        >
          <Ban className="h-3 w-3" />
          <span>{label ?? 'Not Implemented'}</span>
        </span>
      )
    case 'INCONCLUSIVE':
      return (
        <span
          className={cn(
            'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm border text-[0.6875rem] font-semibold tracking-wider uppercase',
            'border-warning/40 bg-warning-soft text-warning',
            className,
          )}
        >
          <HelpCircle className="h-3 w-3" />
          <span>{label ?? 'Inconclusive'}</span>
        </span>
      )
  }
}
