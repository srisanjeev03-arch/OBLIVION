import { Check, Minus, TriangleAlert, X } from 'lucide-react'
import { cn } from '@/lib/cn'
import { alignDimensions, DIMENSION_LABEL } from '@/lib/certificate'
import type { CertificateVerificationOut, DimensionResult } from '@/lib/api/queries'

/**
 * Dimension-level certificate verification (Â§14).
 *
 * Rendered only from a `POST /api/certificates/{id}/verify` response. There is no default, no
 * placeholder row and no optimistic state: before the backend answers, this component is not shown
 * at all, because a dimension with no result is a different fact from a dimension that passed.
 */

interface ResultMeta {
  label: string
  className: string
  Icon: typeof Check
  iconClass: string
}

const RESULT_META: Readonly<Record<DimensionResult, ResultMeta>> = {
  PASS: {
    label: 'PASS',
    className: 'border-success/40 bg-success-soft text-success',
    Icon: Check,
    iconClass: 'text-success',
  },
  FAIL: {
    label: 'FAIL',
    className: 'border-danger/40 bg-danger-soft text-danger',
    Icon: X,
    iconClass: 'text-danger',
  },
  NOT_CHECKED: {
    label: 'NOT CHECKED',
    className: 'border-line bg-inset text-mute',
    Icon: Minus,
    iconClass: 'text-mute',
  },
  INCONCLUSIVE: {
    label: 'INCONCLUSIVE',
    className: 'border-warning/40 bg-warning-soft text-warning',
    Icon: TriangleAlert,
    iconClass: 'text-warning',
  },
}

const OVERALL_META: Readonly<Record<CertificateVerificationOut['overall_status'], ResultMeta>> = {
  VALID: RESULT_META.PASS,
  INVALID: RESULT_META.FAIL,
  INCONCLUSIVE: RESULT_META.INCONCLUSIVE,
}

function ResultChip({ result }: { result: DimensionResult }) {
  const meta = RESULT_META[result]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-xs border px-1.5 py-0.5 font-mono text-[0.5625rem] font-bold uppercase tracking-wide',
        meta.className,
      )}
    >
      <meta.Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {meta.label}
    </span>
  )
}

export function CertificateVerificationPanel({
  verification,
}: {
  verification: CertificateVerificationOut
}) {
  const overall = OVERALL_META[verification.overall_status]
  const rows = alignDimensions(verification.dimensions ?? [])
  const cannotProve = verification.cannot_prove ?? []

  return (
    <div className="space-y-4">
      <div
        className={cn(
          'flex flex-col gap-2 rounded-md border p-4 sm:flex-row sm:items-center sm:justify-between',
          overall.className,
        )}
        data-testid="overall-status"
      >
        <div className="space-y-0.5">
          <span className="block text-[0.625rem] font-bold uppercase tracking-wider opacity-80">
            Overall verification status
          </span>
          <span className="block font-mono text-lg font-bold">
            {verification.overall_status}
          </span>
        </div>
        <div className="max-w-sm text-[0.6875rem] leading-relaxed opacity-90">
          Overall validity is decided by this field alone. A PASS on signature validity does not by
          itself make a certificate valid.
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-line">
        <div className="border-b border-line bg-elevated/60 px-4 py-2.5">
          <h3 className="text-[0.6875rem] font-bold uppercase tracking-wider text-fg">
            Verification dimensions
          </h3>
        </div>
        <div className="divide-y divide-line">
          {rows.map((row) => (
            <div
              key={row.dimension}
              className="flex flex-col gap-1.5 p-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
            >
              <div className="min-w-0">
                <div className="text-xs font-semibold text-fg">
                  {DIMENSION_LABEL[row.dimension] ?? row.dimension}
                </div>
                <div className="font-mono text-[0.625rem] text-mute">{row.dimension}</div>
                {row.detail && (
                  <p className="mt-1 text-[0.6875rem] leading-relaxed text-dim">{row.detail}</p>
                )}
                {row.evidence_ref && (
                  <p className="mt-1 font-mono text-[0.625rem] break-all text-mute">
                    evidence_ref: {row.evidence_ref}
                  </p>
                )}
              </div>
              <div className="shrink-0">
                <ResultChip result={row.result} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {cannotProve.length > 0 && (
        <div className="rounded-md border border-info/40 bg-info-soft p-3.5">
          <span className="block text-[0.625rem] font-bold uppercase tracking-wider text-info">
            What this certificate cannot prove
          </span>
          <ul className="mt-1.5 space-y-1">
            {cannotProve.map((item) => (
              <li key={item} className="text-[0.6875rem] leading-relaxed text-fg">
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

