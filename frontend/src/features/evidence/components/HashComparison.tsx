import { CheckCircle2, XCircle, HelpCircle } from 'lucide-react'
import { cn } from '@/lib/cn'
import { EvidenceHash } from './EvidenceId'

export interface HashComparisonProps {
  baselineHash?: string | null
  verificationHash?: string | null
  expectedMatch?: boolean
  label?: string
  className?: string
}

export function HashComparison({
  baselineHash,
  verificationHash,
  expectedMatch = false,
  label = 'Forensic Cryptographic Hash Comparison',
  className,
}: HashComparisonProps) {
  const isCompared = Boolean(baselineHash && verificationHash)
  const isMatch = isCompared && baselineHash === verificationHash

  return (
    <div className={cn('rounded-md border border-line bg-surface p-3 space-y-2.5', className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-fg">{label}</span>
        {isCompared ? (
          <span
            className={cn(
              'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-xs text-[0.6875rem] font-semibold uppercase tracking-wider border',
              isMatch
                ? 'bg-warning-soft border-warning/40 text-warning'
                : 'bg-success-soft border-success/40 text-success',
            )}
          >
            {isMatch ? (
              <>
                <XCircle className="h-3 w-3" />
                <span>Payload Identical (Post-Erasure Failure)</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-3 w-3" />
                <span>Hash Inverted / Non-Matching (Erased)</span>
              </>
            )}
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-[0.6875rem] text-mute">
            <HelpCircle className="h-3 w-3" />
            <span>Comparison Pending</span>
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div className="space-y-1">
          <div className="text-[0.6875rem] text-dim font-medium uppercase tracking-wider">
            Baseline SHA-256 (Pre-Erasure)
          </div>
          <EvidenceHash value={baselineHash} label="Baseline SHA-256" />
        </div>

        <div className="space-y-1">
          <div className="text-[0.6875rem] text-dim font-medium uppercase tracking-wider">
            Verification SHA-256 (Post-Erasure)
          </div>
          <EvidenceHash value={verificationHash} label="Verification SHA-256" />
        </div>
      </div>

      {isCompared && (
        <div className="text-[0.6875rem] text-dim leading-relaxed pt-1 border-t border-line/50">
          {expectedMatch ? (
            <span>
              Controlled recovery expects identical hashes to prove complete mathematical
              restoration.
            </span>
          ) : (
            <span>
              Permanent erasure requires post-verification hash inversion or cluster vacancy,
              proving raw payload destruction.
            </span>
          )}
        </div>
      )}
    </div>
  )
}
