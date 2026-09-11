import { Badge } from '@/components/ui/Badge'
import type { PipelineResultOut } from '@/lib/api/queries'

/**
 * What the closed loop actually reported.
 *
 * Three rules shape this panel, and each exists because the obvious alternative would be a lie:
 *
 * **Every stage is listed, including the ones that did not run.** A stage that was skipped,
 * refused or unavailable is a fact about the operation. Hiding it would leave the reader assuming
 * the whole loop ran.
 *
 * **Assurance is not the HTTP status.** A 200 means the pipeline ran and reported; it does not mean
 * the erasure was sound. `assurance_status` is rendered as its own field, and INCONCLUSIVE and
 * PARTIAL are shown as themselves rather than rounded to failure or success.
 *
 * **Coverage is named, not counted.** "Recovery testing was performed" is not checkable.
 * "`filesystem_enumeration` ran; five other methods were never attempted" is - so the method and
 * scanner lists are rendered by name, and the permanently-unavailable forensic methods are shown
 * as limitations rather than folded into a coverage percentage.
 */

const STAGE_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  COMPLETED: 'success',
  SKIPPED: 'neutral',
  REFUSED: 'warning',
  UNAVAILABLE: 'warning',
  FAILED: 'danger',
  NOT_RUN: 'neutral',
}

const ASSURANCE_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  PASSED: 'success',
  PARTIAL: 'warning',
  INCONCLUSIVE: 'warning',
  FAILED: 'danger',
}

const COVERAGE_VARIANT: Record<string, 'success' | 'warning' | 'neutral'> = {
  PERFORMED: 'success',
  PARTIAL: 'warning',
  INCONCLUSIVE: 'warning',
  UNAVAILABLE: 'warning',
  NOT_PERFORMED: 'neutral',
}

function NamedList({ label, values }: { label: string; values: readonly string[] | undefined }) {
  return (
    <div className="space-y-0.5">
      <span className="text-dim text-[0.625rem] uppercase block">{label}</span>
      <span className="font-mono text-[0.6875rem] text-fg break-words">
        {values && values.length > 0 ? values.join(', ') : 'none'}
      </span>
    </div>
  )
}

export function PipelineResultPanel({ result }: { result: PipelineResultOut }) {
  const coverage = (result.coverage ?? {}) as Record<string, unknown>
  const recoveryMethods = coverage.recovery_methods as Record<string, string[]> | undefined
  const residualScanners = coverage.residual_scanners as Record<string, string[]> | undefined

  return (
    <div className="rounded-md border border-line bg-surface p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-line pb-3">
        <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
          Closed-Loop Pipeline Result
        </h3>
        <div className="flex items-center gap-1.5">
          <span className="text-[0.625rem] text-dim uppercase">Final state</span>
          <Badge variant={STAGE_VARIANT[result.final_state] ?? 'neutral'}>
            {result.final_state}
          </Badge>
        </div>
      </div>

      {/* A 200 is not a success claim. State it, rather than letting the badge imply it. */}
      <p className="text-[0.6875rem] text-dim">
        The pipeline ran and reported what happened, which may include refusals. Read the stage
        statuses and the assurance verdict below; neither is implied by the request succeeding.
      </p>

      {/* Every stage, including those that did not run. */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
        {result.stages.map((stage) => (
          <div
            key={String(stage.stage)}
            className="rounded-sm border border-line bg-inset px-2 py-1.5 space-y-0.5"
          >
            <span className="block font-mono text-[0.625rem] text-dim truncate">
              {String(stage.stage)}
            </span>
            <Badge variant={STAGE_VARIANT[String(stage.status)] ?? 'neutral'} size="xs">
              {String(stage.status)}
            </Badge>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 border-t border-line">
        <div className="space-y-1">
          <span className="text-dim text-[0.625rem] uppercase block">Assurance verdict</span>
          {result.assurance_status ? (
            <Badge variant={ASSURANCE_VARIANT[result.assurance_status] ?? 'neutral'}>
              {result.assurance_status}
            </Badge>
          ) : (
            <span className="text-[0.6875rem] text-mute">
              Not reached — the pipeline stopped before assurance was assessed.
            </span>
          )}
        </div>
        <div className="space-y-1">
          <span className="text-dim text-[0.625rem] uppercase block">
            Independent certificate verification
          </span>
          {result.verification_status ? (
            <Badge variant={result.verification_status === 'VALID' ? 'success' : 'warning'}>
              {result.verification_status}
            </Badge>
          ) : (
            <span className="text-[0.6875rem] text-mute">
              No certificate was issued, so there was nothing to verify.
            </span>
          )}
        </div>
      </div>

      {/* Coverage by name. A boolean here would be exactly the conflation the
          backend's coverage model was rebuilt to remove. */}
      {(recoveryMethods ?? residualScanners) && (
        <div className="rounded-sm border border-line bg-inset p-3 space-y-3">
          <span className="text-[0.625rem] uppercase font-medium text-dim block">
            What was actually searched
          </span>

          {recoveryMethods && (
            <div className="space-y-1">
              <div className="flex items-center gap-1.5">
                <span className="text-[0.6875rem] font-semibold text-fg">Recovery testing</span>
                {typeof coverage.recovery_test === 'string' && (
                  <Badge variant={COVERAGE_VARIANT[coverage.recovery_test] ?? 'neutral'} size="xs">
                    {coverage.recovery_test}
                  </Badge>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                <NamedList label="Attempted" values={recoveryMethods.attempted} />
                <NamedList label="Recovered data" values={recoveryMethods.successful} />
                <NamedList label="Found nothing" values={recoveryMethods.failed} />
                <NamedList label="Never attempted" values={recoveryMethods.unavailable} />
              </div>
              <p className="text-[0.625rem] text-mute pt-1">
                A method that found nothing is evidence about that method. It is not a finding that
                the data is unrecoverable.
              </p>
            </div>
          )}

          {residualScanners && (
            <div className="space-y-1 pt-2 border-t border-line/60">
              <div className="flex items-center gap-1.5">
                <span className="text-[0.6875rem] font-semibold text-fg">Residual analysis</span>
                {typeof coverage.residual_analysis === 'string' && (
                  <Badge
                    variant={COVERAGE_VARIANT[coverage.residual_analysis] ?? 'neutral'}
                    size="xs"
                  >
                    {coverage.residual_analysis}
                  </Badge>
                )}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                <NamedList label="Ran" values={residualScanners.ran} />
                <NamedList label="Inconclusive" values={residualScanners.inconclusive} />
                <NamedList label="Could not run" values={residualScanners.unavailable} />
              </div>
            </div>
          )}
        </div>
      )}

      {result.limitations && result.limitations.length > 0 && (
        <div className="space-y-1">
          <span className="text-[0.625rem] uppercase font-medium text-dim block">
            Stated limitations of this build
          </span>
          <ul className="space-y-0.5">
            {result.limitations.map((limitation) => (
              <li key={limitation} className="text-[0.6875rem] text-mute flex gap-2">
                <span aria-hidden="true">·</span>
                <span>{limitation}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
