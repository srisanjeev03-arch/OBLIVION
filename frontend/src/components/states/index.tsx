import type { ReactNode } from 'react'
import { CircleSlash, Inbox, Loader2, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import { describeApiError } from '@/lib/api/errors'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/status/StatusBadge'

/**
 * The four screen-state primitives every backend-driven surface must be able to render.
 * They are deliberately plain: no illustrations, no motion beyond the loading spinner.
 */

interface BaseProps {
  title?: string
  description?: ReactNode
  action?: ReactNode
  className?: string
  /** Compact variant for table cells and small panels. */
  compact?: boolean
}

function Frame({
  icon,
  badge,
  title,
  description,
  action,
  className,
  compact,
  role,
}: BaseProps & { icon: ReactNode; badge: ReactNode; role?: 'status' | 'alert' }) {
  return (
    <div
      role={role}
      className={cn(
        'flex flex-col items-center justify-center gap-2 text-center',
        compact ? 'px-4 py-6' : 'px-6 py-12',
        className,
      )}
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-inset text-mute">
        {icon}
      </div>
      <div className="flex flex-col items-center gap-1">
        {badge}
        {title && <p className="text-sm font-medium text-fg">{title}</p>}
        {description && (
          <div className="max-w-md text-xs leading-relaxed text-mute">{description}</div>
        )}
      </div>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

export function LoadingState({ title = 'Loading', description, className, compact }: BaseProps) {
  return (
    <Frame
      role="status"
      icon={<Loader2 className="h-4 w-4 motion-spin" aria-hidden="true" />}
      badge={<StatusBadge kind="screen" value="LOADING" />}
      title={title}
      description={description ?? 'Waiting for the backend.'}
      className={className}
      compact={compact}
    />
  )
}

export function EmptyState({
  title = 'Nothing to show',
  description,
  action,
  className,
  compact,
}: BaseProps) {
  return (
    <Frame
      icon={<Inbox className="h-4 w-4" aria-hidden="true" />}
      badge={<StatusBadge kind="screen" value="EMPTY" />}
      title={title}
      description={description ?? 'The backend returned no records for this view.'}
      action={action}
      className={className}
      compact={compact}
    />
  )
}

export interface ErrorStateProps extends BaseProps {
  error: unknown
  onRetry?: () => void
  retrying?: boolean
}

export function ErrorState({
  error,
  onRetry,
  retrying,
  title,
  description,
  className,
  compact,
}: ErrorStateProps) {
  const summary = describeApiError(error)
  return (
    <Frame
      role="alert"
      icon={<TriangleAlert className="h-4 w-4 text-danger" aria-hidden="true" />}
      badge={<StatusBadge kind="screen" value="FAILED" />}
      title={title ?? summary.title}
      description={
        <div className="flex flex-col gap-1">
          <span>{description ?? summary.detail}</span>
          <span className="font-mono text-[0.6875rem] text-mute">
            {summary.code}
            {summary.requestId ? ` · request ${summary.requestId}` : ''}
          </span>
        </div>
      }
      action={
        onRetry && summary.retryable ? (
          <Button size="sm" onClick={onRetry} loading={retrying}>
            Retry
          </Button>
        ) : undefined
      }
      className={className}
      compact={compact}
    />
  )
}

export interface UnavailableStateProps extends BaseProps {
  /** Why the capability is unavailable — sourced from the capability registry, never invented. */
  reason?: string
}

export function UnavailableState({
  title = 'Not available from the backend',
  reason,
  description,
  action,
  className,
  compact,
}: UnavailableStateProps) {
  return (
    <Frame
      icon={<CircleSlash className="h-4 w-4" aria-hidden="true" />}
      badge={<StatusBadge kind="screen" value="UNAVAILABLE" />}
      title={title}
      description={
        <div className="flex flex-col gap-1">
          {description && <span>{description}</span>}
          {reason && <span className="text-dim">{reason}</span>}
          {!description && !reason && (
            <span>This capability is not provided by the backend yet.</span>
          )}
        </div>
      }
      action={action}
      className={className}
      compact={compact}
    />
  )
}
