import { useState } from 'react'
import { useNavigate } from 'react-router'
import { Activity, Flame, ArrowUpRight } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { DataTable, type ColumnDef } from '@/components/ui/DataTable'
import { StatusBadge } from '@/components/status/StatusBadge'
import { EvidenceId } from '@/components/evidence/EvidenceId'
import { EmptyState, UnavailableState } from '@/components/states'
import { InspectorDrawer } from '@/components/shell/InspectorDrawer'
import { EvidenceChainViewer } from '@/components/evidence/EvidenceChainViewer'
import { useOperationEventsQuery, useOperationQuery } from '@/lib/api'
import { useUIStore } from '@/stores/ui.store'
import { isAvailable } from '@/lib/api/capabilities'
import type { Operation } from '@/lib/api/types'

export function Operations() {
  const navigate = useNavigate()
  const { openDrawer, closeDrawer, activeDrawer } = useUIStore()

  const [stateFilter, setStateFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [inspectedOpId, setInspectedOpId] = useState<string | null>(null)

  const isOpsListAvailable = isAvailable('operations.list')

  // Query inspected operation details if selected
  const { data: inspectedOp } = useOperationQuery(inspectedOpId ?? undefined)
  const { data: inspectedEvents } = useOperationEventsQuery(inspectedOpId ?? undefined)

  // Columns definition
  const columns: ColumnDef<Operation>[] = [
    {
      key: 'id',
      header: 'Operation ID',
      width: '160px',
      cell: (op) => <EvidenceId value={op.id} label="Operation ID" size="sm" />,
    },
    {
      key: 'target_id',
      header: 'Target ID',
      width: '140px',
      cell: (op) => <EvidenceId value={op.target_id} label="Target ID" size="sm" />,
    },
    {
      key: 'mode',
      header: 'Mode',
      width: '160px',
      cell: (op) => (
        <span className="font-mono text-xs font-semibold text-fg">{op.mode || 'N/A'}</span>
      ),
    },
    {
      key: 'state',
      header: 'Lifecycle State',
      width: '150px',
      cell: (op) => (op.state ? <StatusBadge kind="operation" value={op.state} /> : null),
    },
    {
      key: 'progress_percent',
      header: 'Progress',
      width: '120px',
      cell: (op) => (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-16 rounded-full bg-inset overflow-hidden border border-line">
            <div className="h-full bg-accent" style={{ width: `${op.progress_percent ?? 0}%` }} />
          </div>
          <span className="font-mono text-[0.6875rem] tabular text-dim">
            {Math.round(op.progress_percent ?? 0)}%
          </span>
        </div>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      align: 'right',
      width: '100px',
      cell: (op) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            if (op.id) void navigate(`/operations/${op.id}`)
          }}
          trailingIcon={<ArrowUpRight className="h-3 w-3" />}
        >
          Monitor
        </Button>
      ),
    },
  ]

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Operations Monitor & Job Ledger"
        icon={<Activity className="h-4 w-4" />}
        description="Filterable ledger of all active, completed, and quarantined erasure operations."
        actions={
          <Button
            variant="primary"
            size="sm"
            leadingIcon={<Flame className="h-3.5 w-3.5" />}
            onClick={() => void navigate('/erasure')}
          >
            New Erasure Job
          </Button>
        }
      />

      <div className="flex-1 p-6 space-y-4 max-w-7xl">
        {/* Filter Bar */}
        <div className="rounded-md border border-line bg-surface p-3 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto flex-1 max-w-md">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by operation ID or target..."
              className="font-mono text-xs"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select<string>
              label="Filter state"
              hideLabel
              value={stateFilter}
              onChange={(val) => setStateFilter(val)}
              options={[
                { value: 'ALL', label: 'All Lifecycle States' },
                { value: 'CREATED', label: 'Created' },
                { value: 'RUNNING', label: 'Running / Erasing' },
                { value: 'COMPLETED', label: 'Completed' },
                { value: 'FAILED', label: 'Failed' },
                { value: 'PARTIAL', label: 'Partial' },
                { value: 'INCONCLUSIVE', label: 'Inconclusive' },
              ]}
              size="sm"
            />
          </div>
        </div>

        {/* Table Content */}
        {!isOpsListAvailable ? (
          <UnavailableState
            title="Operations Listing Awaiting Backend Phase 2"
            reason="The backend contract currently supports querying individual operations by ID (GET /api/operations/{id}). Listing all operations via GET /api/operations is planned for Phase 2."
            action={
              <div className="flex gap-2">
                <Button variant="default" size="sm" onClick={() => navigate('/targets')}>
                  Analyze Target
                </Button>
                <Button variant="primary" size="sm" onClick={() => navigate('/erasure')}>
                  Create New Operation
                </Button>
              </div>
            }
          />
        ) : (
          <DataTable<Operation>
            columns={columns}
            rows={[]}
            rowKey={(op) => op.id ?? ''}
            caption="Operations"
            emptyContent={
              <EmptyState
                title="No Operations in Ledger"
                description="No forensic erasure jobs match the active filters."
              />
            }
            onRowSelect={(op) => {
              if (op.id) {
                setInspectedOpId(op.id)
                openDrawer('operation', op)
              }
            }}
          />
        )}
      </div>

      {/* Operation Inspector Drawer */}
      <InspectorDrawer
        open={activeDrawer === 'operation' && Boolean(inspectedOpId)}
        onClose={closeDrawer}
        title={`Operation Inspector: ${inspectedOpId || ''}`}
        subtitle="Forensic evidence events and lifecycle state"
        actions={
          inspectedOpId && (
            <Button
              variant="outline"
              size="sm"
              trailingIcon={<ArrowUpRight className="h-3 w-3" />}
              onClick={() => {
                closeDrawer()
                void navigate(`/operations/${inspectedOpId}`)
              }}
            >
              Full Monitor
            </Button>
          )
        }
      >
        <div className="space-y-4">
          <div className="rounded-md border border-line bg-elevated/40 p-3 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-dim uppercase text-[0.6875rem]">Lifecycle State</span>
              {inspectedOp?.state && <StatusBadge kind="operation" value={inspectedOp.state} />}
            </div>
            <div className="grid grid-cols-2 gap-2 pt-1 font-mono text-[0.6875rem]">
              <div>
                <span className="text-dim block">Mode:</span>
                <span className="text-fg font-semibold">
                  {inspectedOp?.mode || 'COMPLETE_ERASURE'}
                </span>
              </div>
              <div>
                <span className="text-dim block">Policy:</span>
                <span className="text-fg font-semibold">
                  {inspectedOp?.policy_id || 'pol-nist-800-88-purge'}
                </span>
              </div>
            </div>
          </div>

          {/* Evidence Chain Events */}
          <div className="space-y-2">
            <span className="text-xs font-bold text-fg uppercase tracking-wider block">
              Evidence Event Sequence
            </span>
            <EvidenceChainViewer events={inspectedEvents} />
          </div>
        </div>
      </InspectorDrawer>
    </div>
  )
}
