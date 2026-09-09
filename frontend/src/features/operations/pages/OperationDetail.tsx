import { useState } from 'react'
import { useParams, useNavigate } from 'react-router'
import { Activity, Ban, FileCheck2, AlertTriangle, RefreshCw } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { StatusBadge } from '@/components/status/StatusBadge'
import { EvidenceId } from '@/features/evidence/components/EvidenceId'
import { EvidenceChainViewer } from '@/features/evidence/components/EvidenceChainViewer'
import { ErrorState, LoadingState } from '@/components/states'
import { useOperationQuery, useOperationEventsQuery, useCancelOperationMutation } from '@/lib/api'
import { OPERATION_LIFECYCLE } from '@/lib/status'
import { cn } from '@/lib/cn'

export function OperationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [cancelModalOpen, setCancelModalOpen] = useState(false)

  // Live polling for operation state
  const { data: op, isLoading, isError, error, refetch } = useOperationQuery(id, { pollMs: 1500 })
  const { data: events } = useOperationEventsQuery(id)
  const cancelMutation = useCancelOperationMutation(id || '')

  const handleCancel = () => {
    cancelMutation.mutate(undefined, {
      onSuccess: () => {
        setCancelModalOpen(false)
        void refetch()
      },
    })
  }

  const isTerminal =
    op?.state === 'COMPLETED' ||
    op?.state === 'FAILED' ||
    op?.state === 'PARTIAL' ||
    op?.state === 'INCONCLUSIVE' ||
    op?.state === 'CANCELLED'

  const currentStageIndex = op?.state
    ? OPERATION_LIFECYCLE.indexOf(op.state as (typeof OPERATION_LIFECYCLE)[number])
    : 0

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title={`Operation: ${id || 'N/A'}`}
        icon={<Activity className="h-4 w-4 text-accent" />}
        description="Live telemetry, cryptographic stage transitions, and sequential evidence records."
        breadcrumbs={[{ label: 'Operations', href: '/operations' }, { label: id || 'Detail' }]}
        actions={
          <div className="flex items-center gap-2">
            {!isTerminal && (
              <Button
                variant="danger"
                size="sm"
                leadingIcon={<Ban className="h-3.5 w-3.5" />}
                onClick={() => setCancelModalOpen(true)}
              >
                Cancel Operation
              </Button>
            )}
            {op?.state === 'COMPLETED' && (
              <Button
                variant="primary"
                size="sm"
                leadingIcon={<FileCheck2 className="h-3.5 w-3.5" />}
                onClick={() => navigate('/certificates')}
              >
                View Certificate
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
              onClick={() => void refetch()}
            >
              Sync
            </Button>
          </div>
        }
      />

      <div className="flex-1 p-6 space-y-6 max-w-7xl">
        {isLoading && (
          <LoadingState
            title="Connecting to Forensic Stream"
            description="Observing daemon status and evidence events for operation..."
          />
        )}

        {isError && (
          <ErrorState
            title="Failed to Load Operation"
            error={error}
            onRetry={() => void refetch()}
          />
        )}

        {op && (
          <div className="space-y-6 motion-enter">
            {/* 1. Lifecycle Stepper Rail */}
            <div className="rounded-md border border-line bg-surface p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-accent" />
                  <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
                    Authoritative Lifecycle Progression
                  </h3>
                </div>
                {op.state && <StatusBadge kind="operation" value={op.state} emphasis="strong" />}
              </div>

              {/* Lifecycle Stage Pills */}
              <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-1.5 pt-1">
                {OPERATION_LIFECYCLE.map((stage, idx) => {
                  const isPassed = currentStageIndex > idx || op.state === 'COMPLETED'
                  const isCurrent = op.state === stage
                  return (
                    <div
                      key={stage}
                      className={cn(
                        'rounded-sm px-1.5 py-2 text-center font-mono text-[0.625rem] truncate border transition-colors',
                        isPassed && 'border-success/40 bg-success-soft text-success font-semibold',
                        isCurrent && 'border-accent bg-accent-soft text-accent font-bold shadow-xs',
                        currentStageIndex < idx &&
                          op.state !== 'COMPLETED' &&
                          'border-line bg-inset text-mute',
                      )}
                    >
                      <span className="block text-[0.5625rem] opacity-60">0{idx + 1}</span>
                      <span className="truncate">{stage}</span>
                    </div>
                  )
                })}
              </div>

              {/* Progress Bar */}
              {op.progress_percent !== undefined && (
                <div className="space-y-1.5 pt-2 border-t border-line/50">
                  <div className="flex justify-between text-xs">
                    <span className="text-dim">Overall Phase Completion</span>
                    <span className="font-mono text-fg font-bold tabular">
                      {Math.round(op.progress_percent)}%
                    </span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-inset overflow-hidden border border-line">
                    <div
                      className="h-full bg-accent transition-all duration-300"
                      style={{ width: `${op.progress_percent}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* 2. Parameters & Target Meta Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="rounded-md border border-line bg-surface p-4 space-y-3">
                <span className="text-xs font-bold text-fg uppercase tracking-wider block border-b border-line pb-2">
                  Operation Identifiers
                </span>
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="text-dim text-[0.6875rem] block uppercase">Operation ID</span>
                    <EvidenceId value={op.id} label="Operation ID" />
                  </div>
                  <div>
                    <span className="text-dim text-[0.6875rem] block uppercase">Target ID</span>
                    <EvidenceId value={op.target_id} label="Target ID" />
                  </div>
                </div>
              </div>

              <div className="rounded-md border border-line bg-surface p-4 space-y-3">
                <span className="text-xs font-bold text-fg uppercase tracking-wider block border-b border-line pb-2">
                  Execution Parameters
                </span>
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="text-dim text-[0.6875rem] block uppercase">Deletion Mode</span>
                    <span className="font-mono text-fg font-semibold">
                      {op.mode || 'COMPLETE_ERASURE'}
                    </span>
                  </div>
                  <div>
                    <span className="text-dim text-[0.6875rem] block uppercase">
                      Policy Standard
                    </span>
                    <span className="font-mono text-dim">
                      {op.policy_id ?? 'not recorded by the backend'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="rounded-md border border-line bg-surface p-4 space-y-3">
                <span className="text-xs font-bold text-fg uppercase tracking-wider block border-b border-line pb-2">
                  Safety & Warnings
                </span>
                <div className="space-y-1 text-xs">
                  {op.warnings && op.warnings.length > 0 ? (
                    op.warnings.map((w, i) => (
                      <div
                        key={i}
                        className="text-warning flex items-center gap-1.5 text-[0.6875rem]"
                      >
                        <AlertTriangle className="h-3 w-3 shrink-0" />
                        <span>{w}</span>
                      </div>
                    ))
                  ) : (
                    <span className="text-mute text-[0.6875rem]">No active safety warnings.</span>
                  )}
                </div>
              </div>
            </div>

            {/* 3. Evidence Chain Stream */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
                  Live Forensic Evidence Stream
                </h3>
              </div>
              <EvidenceChainViewer events={events} />
            </div>
          </div>
        )}
      </div>

      {/* Cancel Confirmation Dialog */}
      <Dialog
        open={cancelModalOpen}
        onClose={() => setCancelModalOpen(false)}
        title="Cancel Active Operation"
        description="Request cancellation of the active erasure job. If destructive writing has commenced, the operation will terminate in PARTIAL state."
        tone="danger"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setCancelModalOpen(false)}>
              Keep Running
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={cancelMutation.isPending}
              onClick={handleCancel}
            >
              Confirm Cancellation
            </Button>
          </>
        }
      >
        <p className="text-xs text-dim leading-relaxed">
          The daemon will safely dismount locks and record a <code>CANCELLED</code> event in the
          tamper-evident evidence chain.
        </p>
      </Dialog>
    </div>
  )
}
