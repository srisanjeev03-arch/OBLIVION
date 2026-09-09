import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  Flame,
  ShieldAlert,
  HardDrive,
  KeyRound,
  ArrowLeft,
  Lock,
  Layers,
  Crosshair,
} from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Checkbox } from '@/components/ui/Checkbox'
import { Dialog } from '@/components/ui/Dialog'
import { EvidenceId } from '@/components/evidence/EvidenceId'
import { EmptyState } from '@/components/states'
import { useCreateOperationMutation, useTargetQuery } from '@/lib/api'
import { useUIStore } from '@/stores/ui.store'
import { useAIPreferences } from '@/stores/ai.store'
import { formatBytes, formatCount } from '@/lib/format'
import type { OperationMode } from '@/lib/api/types'
import { ALLOWLISTED_POLICIES } from '@/lib/api/contract-policies'
import { isAvailable } from '@/lib/api/capabilities'
import { AIPanel } from '@/components/ai/AIPanel'
import { cn } from '@/lib/cn'

/**
 * The lifecycle rail mirrors the backend's real approval-gated state machine, not a marketing
 * sequence. `operations.create` leaves an operation in PENDING_APPROVAL; a *different* principal
 * must approve it (separation of duties) before `operations.execute` performs the erasure.
 */
const WORKFLOW_STEPS = [
  '1. Analyze target',
  '2. Configure mode & policy',
  '3. Request operation',
  '4. Pending approval',
  '5. Approved (separate principal)',
  '6. Execute erasure',
  '7. Verify',
  '8. Recovery test',
  '9. Residual scan',
  '10. Certify',
]

/**
 * Policies come from `contract-policies.ts`, which is generated from the backend's
 * `POLICY_REGISTRY`. They are not editable here on purpose: the backend allowlist-checks
 * `policy_id` and rejects anything else, so an invented identifier would only produce a 400 that
 * reads like operator error. Each mode maps to exactly one policy, so the mode selection determines
 * the policy rather than offering a free choice.
 */
function policyForMode(mode: OperationMode) {
  return ALLOWLISTED_POLICIES.find((p) => p.allowed_modes.includes(mode))
}

export function ErasureWorkflow() {
  const navigate = useNavigate()
  const { selectedTargetId, setActiveOperationId } = useUIStore()
  const aiEnabled = useAIPreferences((s) => s.enabled)

  // Target query
  const { data: target } = useTargetQuery(selectedTargetId ?? undefined)
  const createMutation = useCreateOperationMutation()

  // Workflow state
  const [currentStep] = useState<number>(4) // Start at Configure step
  const [selectedMode, setSelectedMode] = useState<OperationMode>('COMPLETE_ERASURE')
  const [retentionDays, setRetentionDays] = useState<number>(30)

  // The policy is determined by the mode, because that is how the backend allowlist is built: each
  // mode has exactly one compatible policy. Holding it in state would let the UI present a
  // combination the server is guaranteed to reject.
  const selectedPolicy = policyForMode(selectedMode)

  // Confirmation modal state
  const [confirmModalOpen, setConfirmModalOpen] = useState(false)
  const [acknowledgedRisk, setAcknowledgedRisk] = useState(false)

  const isCreateAvailable = isAvailable('operations.create')

  const handleExecuteOperation = () => {
    if (!acknowledgedRisk || !target?.id || !selectedPolicy) return

    createMutation.mutate(
      {
        target_id: target.id,
        mode: selectedMode,
        policy_id: selectedPolicy.policy_id,
        confirmation: {
          acknowledged_risk: true,
        },
        ...(selectedMode === 'CONTROLLED_RECOVERABLE'
          ? { recovery: { retention_seconds: retentionDays * 86400 } }
          : {}),
      },
      {
        onSuccess: (op) => {
          if (op.id) {
            setActiveOperationId(op.id)
            setConfirmModalOpen(false)
            void navigate(`/operations/${op.id}`)
          }
        },
      },
    )
  }

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Forensic Erasure & Destruction Wizard"
        icon={<Flame className="h-4 w-4 text-danger" />}
        description="Configure deterministic erasure policies, review controlled scopes, and execute cryptographic destruction."
      />

      <div className="flex-1 p-6 space-y-6 max-w-5xl mx-auto w-full">
        {/* 10-Step Progress Stepper Rail */}
        <div className="rounded-md border border-line bg-surface p-4 space-y-2 select-none">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-fg">
              Forensic Erasure Lifecycle Rail (Step 4 of 10: Policy Configuration)
            </span>
            <Badge variant="accent">GOVERNED WORKFLOW</Badge>
          </div>

          <div className="grid grid-cols-5 md:grid-cols-10 gap-1.5 pt-1">
            {WORKFLOW_STEPS.map((step, idx) => {
              const stepNum = idx + 1
              const isPast = stepNum < currentStep
              const isCurrent = stepNum === currentStep
              return (
                <div
                  key={idx}
                  className={cn(
                    'rounded-sm px-2 py-1 text-center font-mono text-[0.625rem] truncate border transition-colors',
                    isPast && 'border-success/40 bg-success-soft text-success font-semibold',
                    isCurrent && 'border-accent bg-accent-soft text-accent font-bold shadow-xs',
                    stepNum > currentStep && 'border-line bg-inset text-mute',
                  )}
                >
                  {step}
                </div>
              )
            })}
          </div>
        </div>

        {/* Target Context Card or Empty Prompt */}
        {!target ? (
          <div className="rounded-md border border-line bg-surface p-6">
            <EmptyState
              title="No Target Selected for Erasure"
              description="A validated filesystem target profile is required prior to configuring deletion policies."
              action={
                <Button
                  variant="primary"
                  size="md"
                  leadingIcon={<Crosshair className="h-3.5 w-3.5" />}
                  onClick={() => void navigate('/targets')}
                >
                  Discover & Profile Target First
                </Button>
              }
            />
          </div>
        ) : (
          <>
            {/* Target Scope Card */}
            <div className="rounded-md border border-line bg-surface p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-line pb-2.5">
                <div className="flex items-center gap-2">
                  <HardDrive className="h-4 w-4 text-accent" />
                  <span className="text-xs font-bold uppercase tracking-wider text-fg">
                    Target Under Scope
                  </span>
                </div>
                <Badge variant="info">AUTHORITATIVE SCOPE</Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-dim text-[0.6875rem] block uppercase">Target ID</span>
                  <EvidenceId value={target.id} label="Target ID" />
                </div>
                <div className="sm:col-span-2">
                  <span className="text-dim text-[0.6875rem] block uppercase">Filesystem Path</span>
                  <span className="font-mono text-fg font-semibold truncate block">
                    {target.path}
                  </span>
                </div>
                <div>
                  <span className="text-dim text-[0.6875rem] block uppercase">Size & Items</span>
                  <span className="font-mono text-fg">
                    {formatBytes(target.size_bytes)} ({formatCount(target.file_count, 'file')})
                  </span>
                </div>
              </div>
            </div>

            {/* Step 4: Deletion Mode Selection */}
            <div className="rounded-md border border-line bg-surface p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
                  1. Select Controlled Deletion Mode
                </h3>
                <span className="text-[0.6875rem] text-dim font-mono">
                  CreateOperationRequest.mode
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Mode 1: Complete Erasure */}
                <button
                  type="button"
                  onClick={() => setSelectedMode('COMPLETE_ERASURE')}
                  className={cn(
                    'rounded-md border p-3.5 text-left transition-all space-y-2 relative',
                    selectedMode === 'COMPLETE_ERASURE'
                      ? 'border-danger/60 bg-danger-soft/30 shadow-xs'
                      : 'border-line bg-elevated/40 hover:bg-elevated',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <Flame className="h-4 w-4 text-danger" />
                    <Badge variant={selectedMode === 'COMPLETE_ERASURE' ? 'danger' : 'neutral'}>
                      PERMANENT
                    </Badge>
                  </div>
                  <div className="font-bold text-xs text-fg">Complete Erasure</div>
                  <p className="text-[0.6875rem] text-dim leading-relaxed">
                    Cryptographic key destruction and raw cluster overwrite. Data is mathematically
                    unrecoverable within tested scope.
                  </p>
                </button>

                {/* Mode 2: Selective Permanent */}
                <button
                  type="button"
                  onClick={() => setSelectedMode('SELECTIVE_PERMANENT')}
                  className={cn(
                    'rounded-md border p-3.5 text-left transition-all space-y-2 relative',
                    selectedMode === 'SELECTIVE_PERMANENT'
                      ? 'border-accent/60 bg-accent-soft/30 shadow-xs'
                      : 'border-line bg-elevated/40 hover:bg-elevated',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <Layers className="h-4 w-4 text-accent" />
                    <Badge variant={selectedMode === 'SELECTIVE_PERMANENT' ? 'accent' : 'neutral'}>
                      SELECTIVE
                    </Badge>
                  </div>
                  <div className="font-bold text-xs text-fg">Selective Permanent</div>
                  <p className="text-[0.6875rem] text-dim leading-relaxed">
                    Purges targeted files, alternate data streams, and journal references without
                    destroying surrounding container.
                  </p>
                </button>

                {/* Mode 3: Controlled Recoverable */}
                <button
                  type="button"
                  onClick={() => setSelectedMode('CONTROLLED_RECOVERABLE')}
                  className={cn(
                    'rounded-md border p-3.5 text-left transition-all space-y-2 relative',
                    selectedMode === 'CONTROLLED_RECOVERABLE'
                      ? 'border-warning/60 bg-warning-soft/30 shadow-xs'
                      : 'border-line bg-elevated/40 hover:bg-elevated',
                  )}
                >
                  <div className="flex items-center justify-between">
                    <KeyRound className="h-4 w-4 text-warning" />
                    <Badge
                      variant={selectedMode === 'CONTROLLED_RECOVERABLE' ? 'warning' : 'neutral'}
                    >
                      ESCROW VAULT
                    </Badge>
                  </div>
                  <div className="font-bold text-xs text-fg">Controlled Recoverable</div>
                  <p className="text-[0.6875rem] text-dim leading-relaxed">
                    Quarantines encrypted payload in the Recovery Vault with timed retention and
                    dual-operator authorization.
                  </p>
                </button>
              </div>

              {/* Retention configuration if Recoverable */}
              {selectedMode === 'CONTROLLED_RECOVERABLE' && (
                <div className="rounded-sm border border-warning/40 bg-warning-soft p-3 space-y-2 text-xs">
                  <div className="font-semibold text-fg flex items-center gap-1.5">
                    <Lock className="h-3.5 w-3.5 text-warning" />
                    Recovery Vault Retention Policy
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-dim text-[0.6875rem]">Retention Duration (Days):</span>
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={retentionDays}
                      onChange={(e) => setRetentionDays(Number(e.target.value))}
                      className="h-7 w-20 rounded-xs border border-line bg-inset px-2 font-mono text-xs text-fg"
                    />
                    <span className="text-[0.6875rem] text-mute">
                      Vault expires in {retentionDays} days, triggering automated irreversible
                      purge.
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Step 4B: Erasure Policy (backend-allowlisted, determined by mode) */}
            <div className="rounded-md border border-line bg-surface p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
                  2. Erasure policy (allowlisted by the backend)
                </h3>
                <span className="text-[0.6875rem] text-dim font-mono">
                  CreateOperationRequest.policy_id
                </span>
              </div>

              {selectedPolicy ? (
                <div className="rounded-md border border-accent/40 bg-accent-soft/20 p-3 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-fg">{selectedPolicy.name}</span>
                    <Badge variant="accent">{selectedPolicy.policy_id}</Badge>
                  </div>
                  <p className="text-[0.6875rem] leading-relaxed text-dim">
                    {selectedPolicy.description}
                  </p>
                  <dl className="grid grid-cols-1 gap-x-6 gap-y-1 pt-1 font-mono text-[0.625rem] text-mute sm:grid-cols-2">
                    <div>
                      <dt className="inline">Applies to: </dt>
                      <dd className="inline text-fg">
                        {selectedPolicy.allowed_target_types.join(', ')}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline">Approval required: </dt>
                      <dd className="inline text-fg">
                        {selectedPolicy.requires_approval ? 'yes — separate principal' : 'no'}
                      </dd>
                    </div>
                  </dl>
                </div>
              ) : (
                <div className="rounded-md border border-warning/40 bg-warning-soft p-3 text-[0.6875rem] leading-relaxed text-warning">
                  The backend registry contains no policy for mode{' '}
                  <span className="font-mono">{selectedMode}</span>. The operation cannot be
                  requested until one is allowlisted.
                </div>
              )}

              <p className="text-[0.625rem] leading-relaxed text-mute">
                This list is generated from the backend policy registry, so it cannot offer a
                technique the server would refuse. The backend also enforces mode and target-type
                compatibility; a mismatch is rejected before any filesystem action.
              </p>
            </div>

            {/* AI Advisory — Sanitization Strategy Recommendation */}
            {aiEnabled && (
              <AIPanel
                title="Sanitization Strategy Recommendation"
                state="UNAVAILABLE"
                summary="The AI advisory layer is not yet integrated for sanitization strategy recommendation. Authoritative policy selection is operator-controlled based on backend media profile and forensic standards."
                drawerSubtitle="AI ADVISORY — Sanitization Strategy Recommendation"
              />
            )}

            {/* Bottom Bar: Action Trigger */}
            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="md"
                leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
                onClick={() => void navigate('/targets')}
              >
                Back to Target Analysis
              </Button>

              <Button
                variant="danger"
                size="md"
                leadingIcon={<Flame className="h-3.5 w-3.5" />}
                onClick={() => {
                  setAcknowledgedRisk(false)
                  setConfirmModalOpen(true)
                }}
              >
                Review & Authorize Erasure
              </Button>
            </div>
          </>
        )}
      </div>

      {/* High-Consequence Confirmation Dialog */}
      <Dialog
        open={confirmModalOpen}
        onClose={() => setConfirmModalOpen(false)}
        title="High-Consequence Destructive Deletion Confirmation"
        description="Verify the exact target scope, byte size, and policy before dispatching destruction."
        tone="danger"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setConfirmModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={createMutation.isPending}
              disabled={!acknowledgedRisk}
              onClick={handleExecuteOperation}
            >
              {selectedMode === 'CONTROLLED_RECOVERABLE'
                ? 'Execute Vault Quarantine'
                : 'Delete Permanently'}
            </Button>
          </>
        }
      >
        <div className="space-y-4 text-xs">
          {/* Exact Backend Scope Card */}
          <div className="rounded-sm border border-danger/40 bg-danger-soft p-3 space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-danger">
              <ShieldAlert className="h-4 w-4" />
              <span>
                {selectedMode === 'CONTROLLED_RECOVERABLE'
                  ? 'RECOVERY ESCROW QUARANTINE'
                  : 'IRREVERSIBLE DESTRUCTION CONFIRMATION'}
              </span>
            </div>
            <p className="text-[0.6875rem] text-fg leading-relaxed">
              You are authorizing an operational deletion request. The backend forensic daemon will
              execute block-level destruction on the designated target.
            </p>

            <div className="grid grid-cols-2 gap-2 pt-2 font-mono text-[0.6875rem] border-t border-danger/20">
              <div>
                <span className="text-dim block">Target:</span>
                <span className="text-fg font-semibold truncate block">{target?.path}</span>
              </div>
              <div>
                <span className="text-dim block">Scope / Size:</span>
                <span className="text-fg font-semibold">
                  {formatBytes(target?.size_bytes)} / {formatCount(target?.file_count, 'file')}
                </span>
              </div>
              <div>
                <span className="text-dim block">Mode:</span>
                <span className="text-fg font-semibold">{selectedMode}</span>
              </div>
              <div>
                <span className="text-dim block">Reversibility:</span>
                <span className="text-danger font-bold">
                  {selectedMode === 'CONTROLLED_RECOVERABLE'
                    ? 'RECOVERABLE VIA RETENTION'
                    : 'IRREVERSIBLE'}
                </span>
              </div>
            </div>
          </div>

          {!isCreateAvailable && (
            <div className="rounded-sm border border-warning/40 bg-warning-soft p-2 text-[0.6875rem] text-warning">
              Notice: Backend capability <code>operations.create</code> is currently marked awaiting
              Phase 2. This request will return an integration-ready unavailable state.
            </div>
          )}

          {/* Explicit Risk Checkbox */}
          <div className="pt-2">
            <Checkbox
              checked={acknowledgedRisk}
              onChange={(e) => setAcknowledgedRisk(e.target.checked)}
              label="I have verified the exact target scope and authorize irreversible erasure."
              description="This confirmation is cryptographically timestamped in the audit log."
            />
          </div>
        </div>
      </Dialog>
    </div>
  )
}
