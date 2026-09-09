import { ShieldCheck, Link2, ShieldAlert } from 'lucide-react'
import { cn } from '@/lib/cn'
import { formatIso } from '@/lib/format'
import type { EvidenceEvent } from '@/lib/api/types'
import { EvidenceId } from './EvidenceId'

export interface EvidenceChainViewerProps {
  events?: EvidenceEvent[] | null
  className?: string
}

export function EvidenceChainViewer({ events, className }: EvidenceChainViewerProps) {
  if (!events || events.length === 0) {
    return (
      <div
        className={cn(
          'rounded-md border border-line bg-surface p-4 text-center text-xs text-mute',
          className,
        )}
      >
        No evidence events recorded in the chain yet.
      </div>
    )
  }

  // Validate chain integrity: sequence consecutive and each event's previous_event_hash matches predecessor's payload_hash
  const integrity = events.every((event, idx) => {
    if (idx === 0) return true
    const prev = events[idx - 1]
    if (!prev?.payload_hash || !event.previous_event_hash) return true
    return event.previous_event_hash === prev.payload_hash
  })

  return (
    <div className={cn('rounded-md border border-line bg-surface p-3 space-y-3', className)}>
      <div className="flex items-center justify-between border-b border-line pb-2 text-xs">
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-accent" />
          <span className="font-semibold text-fg">Tamper-Evident Evidence Chain</span>
          <span className="text-[0.6875rem] font-mono text-mute">({events.length} events)</span>
        </div>

        <div className="flex items-center gap-1.5">
          {integrity ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[0.625rem] font-semibold text-success bg-success-soft border border-success/40 uppercase tracking-wider">
              <ShieldCheck className="h-3 w-3" />
              <span>Chain Integrity Verified</span>
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs text-[0.625rem] font-semibold text-danger bg-danger-soft border border-danger/40 uppercase tracking-wider">
              <ShieldAlert className="h-3 w-3" />
              <span>Chain Hash Mismatch</span>
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
        {events.map((event, idx) => {
          return (
            <div
              key={event.sequence ?? idx}
              className="relative rounded-sm border border-line bg-elevated/60 p-2.5 space-y-1.5 text-xs transition-colors hover:border-line-strong"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center justify-center h-4 w-4 rounded-xs bg-inset font-mono text-[0.625rem] font-bold text-accent">
                    #{event.sequence ?? idx + 1}
                  </span>
                  <span className="font-mono font-semibold text-fg text-xs">
                    {event.event_type || 'EVIDENCE_EVENT'}
                  </span>
                </div>
                <span className="text-[0.6875rem] text-mute font-mono">
                  {formatIso(event.timestamp)}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[0.6875rem] pt-1">
                <div>
                  <span className="text-dim mr-1.5">Payload Hash:</span>
                  <EvidenceId value={event.payload_hash} label="Payload Hash" />
                </div>
                <div>
                  <span className="text-dim mr-1.5">Prev Hash:</span>
                  <EvidenceId value={event.previous_event_hash} label="Previous Hash" />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
