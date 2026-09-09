import { ShieldQuestion, Scale, Info } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { UnavailableState } from '@/components/states'
import { getCapability, unavailableReason } from '@/lib/api/capabilities'

/**
 * Assurance.
 *
 * This screen used to present a hand-written "10-vector assurance framework" with standards
 * citations â€” NIST SP 800-88 Rev. 1, DoD 5220.22-M, ISO/IEC 27040:2015 â€” and badges reading
 * "ISO 27040 COMPLIANT" and "NIST SP 800-88". None of it came from the backend, none of it was
 * evaluated, and the vector list described capabilities the product does not have (physical cluster
 * readback, NAND out-of-band inspection). Compliance is an assertion about a process and an
 * auditor's judgement; it is not a field an API returns, so a console cannot award it.
 *
 * What remains is the honest position: the backend runs an assurance engine, its result is embedded
 * in signed evidence, and no assurance read endpoint is published. So assurance cannot be displayed
 * here yet, and the two places where it *can* be read are named instead.
 */

const READABLE_EVIDENCE = [
  {
    title: 'Per-operation evidence events',
    path: 'GET /api/operations/{operation_id}/events',
    detail:
      'The tamper-evident event chain for one operation, including the states it passed through ' +
      'and the digest recorded for each event.',
    where: 'Operations â†’ open an operation by ID',
  },
  {
    title: 'Certificate verification dimensions',
    path: 'POST /api/certificates/{certificate_id}/verify',
    detail:
      'Ten dimension-level results (structure, evidence digest, signature validity, signer trust, ' +
      'chain integrity, operation and target consistency) plus an overall status and an explicit ' +
      'list of what the certificate cannot prove.',
    where: 'Certificates â†’ retrieve and verify',
  },
] as const

export function Assurance() {
  const capability = getCapability('assurance.get')
  const reason = unavailableReason('assurance.get')

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Assurance"
        icon={<ShieldQuestion className="h-4 w-4 text-accent" />}
        description="How confident the backend's verification stages permit us to be that a target is unrecoverable within the supported scope."
      />

      <div className="mx-auto w-full max-w-4xl space-y-4 p-4 sm:p-5">
        <div className="flex items-start gap-2.5 rounded-md border border-info/40 bg-info-soft p-4 text-xs">
          <Scale className="mt-0.5 h-4 w-4 shrink-0 text-info" aria-hidden="true" />
          <div className="space-y-1.5">
            <div className="font-bold text-fg">
              NOT DETECTED is not the same as PROVABLY UNRECOVERABLE
            </div>
            <p className="leading-relaxed text-dim">
              Oblivion reports assurance within a stated scope: a filesystem, a media class, a set of
              supported recovery techniques. The absence of detected remnants in a tested scope does
              not establish that unmapped NAND blocks, hardware shadow sectors or out-of-scope
              snapshots contain nothing. Any screen in this console that shows a result is reporting
              what a backend stage observed, and any stage that has not run says so.
            </p>
          </div>
        </div>

        <Panel>
          <PanelHeader title="Assurance assessment" />
          <UnavailableState
            title="Assurance is not retrievable from the published contract"
            reason={reason ?? undefined}
            description={
              <>
                Backend operation: <span className="font-mono">{capability.method} {capability.path}</span>{' '}
                â€” not routed. No assurance value is shown here, and none is estimated.
              </>
            }
          />
        </Panel>

        <Panel>
          <PanelHeader title="Where verification results can be read today" />
          <div className="space-y-3">
            {READABLE_EVIDENCE.map((item) => (
              <div key={item.path} className="rounded-sm border border-line bg-inset p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-xs font-semibold text-fg">{item.title}</span>
                  <span className="font-mono text-[0.625rem] text-mute">{item.path}</span>
                </div>
                <p className="mt-1 text-[0.6875rem] leading-relaxed text-dim">{item.detail}</p>
                <p className="mt-1.5 font-mono text-[0.625rem] text-mute">{item.where}</p>
              </div>
            ))}
          </div>
        </Panel>

        <div className="flex items-start gap-2 rounded-md border border-line bg-surface p-3 text-[0.6875rem] leading-relaxed text-mute">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>
            When the backend publishes an assurance read endpoint, this screen renders its result and
            nothing else changes: the capability registry derives availability from the generated
            contract, so the screen begins reporting real data the moment the route exists.
          </span>
        </div>
      </div>
    </div>
  )
}

