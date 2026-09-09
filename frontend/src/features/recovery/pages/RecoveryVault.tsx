import { useState } from 'react'
import { KeyRound, Lock, RotateCcw, Clock, CheckCircle2 } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { Dialog } from '@/components/ui/Dialog'
import { DataTable, type ColumnDef } from '@/components/ui/DataTable'
import { EvidenceId } from '@/features/evidence/components/EvidenceId'
import { EmptyState, LoadingState, UnavailableState } from '@/components/states'
import { useRecoveryObjectsQuery, useRestoreRecoveryObjectMutation } from '@/lib/api'
import { isAvailable } from '@/lib/api/capabilities'
import { formatIso } from '@/lib/format'
import type { RecoveryObject } from '@/lib/api/types'
import { AIPanel } from '@/components/ai/AIPanel'
import { useAIPreferences } from '@/stores/ai.store'

export function RecoveryVault() {
  const { data: objects, isLoading, refetch } = useRecoveryObjectsQuery()
  const aiEnabled = useAIPreferences((s) => s.enabled)

  const [selectedObject, setSelectedObject] = useState<RecoveryObject | null>(null)
  const [restoreModalOpen, setRestoreModalOpen] = useState(false)
  const [destinationPath, setDestinationPath] = useState(
    'C:\\Oblivion\\Restored\\recovered_payload.dat',
  )
  const [restoreSuccess, setRestoreSuccess] = useState(false)

  const restoreMutation = useRestoreRecoveryObjectMutation(selectedObject?.id || '')
  const isVaultAvailable = isAvailable('recovery.list')

  const handleOpenRestore = (obj: RecoveryObject) => {
    setSelectedObject(obj)
    setRestoreSuccess(false)
    setRestoreModalOpen(true)
  }

  const handleExecuteRestore = () => {
    if (!selectedObject?.id || !destinationPath.trim()) return

    restoreMutation.mutate(
      { destination: destinationPath.trim() },
      {
        onSuccess: () => {
          setRestoreSuccess(true)
          void refetch()
        },
      },
    )
  }

  const columns: ColumnDef<RecoveryObject>[] = [
    {
      key: 'id',
      header: 'Vault ID',
      width: '150px',
      cell: (r) => <EvidenceId value={r.id} label="Vault Object ID" size="sm" />,
    },
    {
      key: 'operation_id',
      header: 'Source Operation',
      width: '150px',
      cell: (r) => <EvidenceId value={r.operation_id} label="Operation ID" size="sm" />,
    },
    {
      key: 'status',
      header: 'Vault Escrow State',
      width: '150px',
      cell: (r) => (
        <Badge
          variant={
            r.status === 'RESTORED'
              ? 'success'
              : r.status === 'AVAILABLE'
                ? 'accent'
                : r.status === 'EXPIRED'
                  ? 'danger'
                  : 'warning'
          }
        >
          {r.status || 'PROTECTED'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: 'Quarantined At',
      width: '160px',
      cell: (r) => (
        <span className="font-mono text-[0.6875rem] text-dim">{formatIso(r.created_at)}</span>
      ),
    },
    {
      key: 'expires_at',
      header: 'Retention Expiry',
      width: '160px',
      cell: (r) => (
        <span className="font-mono text-[0.6875rem] text-warning flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span>{formatIso(r.expires_at)}</span>
        </span>
      ),
    },
    {
      key: 'original_sha256',
      header: 'Original Hash (SHA-256)',
      width: '160px',
      cell: (r) => <EvidenceId value={r.original_sha256} label="Original SHA-256" size="sm" />,
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      width: '120px',
      cell: (r) => (
        <Button
          variant="outline"
          size="sm"
          leadingIcon={<RotateCcw className="h-3 w-3" />}
          disabled={r.status === 'EXPIRED' || r.status === 'RESTORED'}
          onClick={() => handleOpenRestore(r)}
        >
          Restore
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Quarantined Recovery Vault"
        icon={<KeyRound className="h-4 w-4 text-warning" />}
        description="Controlled recoverable escrow objects under cryptographic retention locks. Cryptographic keys are never exposed."
      />

      <div className="flex-1 p-6 space-y-6 max-w-7xl">
        {/* AI Advisory â€” Recovery Risk Prediction */}
        {aiEnabled && (
          <AIPanel
            title="Recovery Risk Prediction"
            state="UNAVAILABLE"
            summary="The AI advisory layer is not yet integrated for recovery risk prediction. Recovery authorization is operator-controlled via the authoritative backend vault."
            drawerSubtitle="AI ADVISORY â€” Recovery Risk Prediction"
          />
        )}

        {/* Security Boundary Notice */}
        <div className="rounded-md border border-line bg-surface p-4 flex items-start gap-3">
          <Lock className="h-4 w-4 text-accent shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <span className="font-semibold text-fg block">
              Cryptographic Zero-Knowledge Retention Boundary
            </span>
            <p className="text-dim leading-relaxed text-[0.6875rem]">
              Encrypted escrow objects are held in low-level quarantine. Decryption and restoration
              occur exclusively inside the authoritative backend daemon. Client browser code never
              receives plaintext keys or unencrypted payload buffers.
            </p>
          </div>
        </div>

        {/* Vault Table */}
        {!isVaultAvailable ? (
          <UnavailableState
            title="Recovery Vault Awaiting Backend Phase 10"
            reason="Listing and restoring quarantined objects requires GET /api/recovery-objects and POST /api/recovery-objects/{id}/restore (Milestone B)."
          />
        ) : isLoading ? (
          <LoadingState
            title="Querying Recovery Vault"
            description="Checking escrow object integrity and expiration timers..."
          />
        ) : (
          <DataTable<RecoveryObject>
            columns={columns}
            rows={objects || []}
            rowKey={(r) => r.id ?? ''}
            caption="Recovery Objects"
            emptyContent={
              <EmptyState
                title="Vault is Empty"
                description="No controlled recoverable deletion objects are currently in escrow."
              />
            }
          />
        )}
      </div>

      {/* Restore Modal */}
      <Dialog
        open={restoreModalOpen}
        onClose={() => setRestoreModalOpen(false)}
        title="Authorize Object Restoration"
        description="Decrypt and restore the quarantined object to a verified destination path."
        tone="default"
        footer={
          <>
            <Button variant="outline" size="sm" onClick={() => setRestoreModalOpen(false)}>
              {restoreSuccess ? 'Close' : 'Cancel'}
            </Button>
            {!restoreSuccess && (
              <Button
                variant="primary"
                size="sm"
                loading={restoreMutation.isPending}
                onClick={handleExecuteRestore}
              >
                Execute Restore
              </Button>
            )}
          </>
        }
      >
        <div className="space-y-4 text-xs">
          {restoreSuccess ? (
            <div className="rounded-sm border border-success/40 bg-success-soft p-3 space-y-2 text-success">
              <div className="flex items-center gap-2 font-bold">
                <CheckCircle2 className="h-4 w-4" />
                <span>RESTORE COMPLETED & VERIFIED</span>
              </div>
              <p className="text-[0.6875rem] text-fg leading-relaxed">
                The backend restored the payload to <code>{destinationPath}</code> and verified that
                its post-restoration SHA-256 matches the original escrow digest.
              </p>
            </div>
          ) : (
            <>
              <div className="rounded-sm border border-line bg-inset p-3 space-y-2">
                <span className="text-dim uppercase text-[0.6875rem] block font-medium">
                  Escrow Record Details
                </span>
                <div className="grid grid-cols-2 gap-2 text-[0.6875rem] font-mono">
                  <div>
                    <span className="text-dim block">Vault ID:</span>
                    <span className="text-fg font-semibold">{selectedObject?.id}</span>
                  </div>
                  <div>
                    <span className="text-dim block">Original Hash:</span>
                    <EvidenceId value={selectedObject?.original_sha256} label="SHA-256" />
                  </div>
                </div>
              </div>

              <div className="space-y-1.5">
                <span className="text-dim text-[0.6875rem] uppercase font-medium block">
                  Restoration Destination Path
                </span>
                <Input
                  value={destinationPath}
                  onChange={(e) => setDestinationPath(e.target.value)}
                  placeholder="C:\Restored\target_file.dat"
                  className="font-mono text-xs"
                />
                <span className="text-[0.625rem] text-mute block">
                  The backend daemon will verify write permissions before decrypting.
                </span>
              </div>
            </>
          )}
        </div>
      </Dialog>
    </div>
  )
}
