import { useState } from 'react'
import { ScrollText } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { DataTable, type ColumnDef } from '@/components/ui/DataTable'
import { EvidenceId } from '@/components/evidence/EvidenceId'
import { InspectorDrawer } from '@/components/shell/InspectorDrawer'
import { EmptyState, UnavailableState } from '@/components/states'
import { isAvailable } from '@/lib/api/capabilities'
import { formatIso } from '@/lib/format'

export interface AuditLogEntry {
  id: string
  timestamp: string
  actor: string
  role: string
  eventType:
    'OPERATOR_ACTION' | 'SYSTEM_EVENT' | 'SECURITY_EVENT' | 'OPERATION_EVENT' | 'VERIFICATION_EVENT'
  action: string
  target_path: string
  operation_id?: string
  result: 'SUCCESS' | 'WARNING' | 'FAILURE'
  correlation_id: string
  details?: Record<string, unknown>
}

export function Audit() {
  const isAuditAvailable = isAvailable('audit.events')

  const [searchQuery, setSearchQuery] = useState('')
  const [resultFilter, setResultFilter] = useState('ALL')
  const [selectedEntry, setSelectedEntry] = useState<AuditLogEntry | null>(null)

  const columns: ColumnDef<AuditLogEntry>[] = [
    {
      key: 'timestamp',
      header: 'Timestamp (UTC)',
      width: '160px',
      cell: (l) => (
        <span className="font-mono text-[0.6875rem] text-dim">{formatIso(l.timestamp)}</span>
      ),
    },
    {
      key: 'actor',
      header: 'Operator / Role',
      width: '160px',
      cell: (l) => (
        <div className="truncate">
          <div className="font-semibold text-xs text-fg">{l.actor}</div>
          <div className="text-[0.625rem] text-dim font-mono">{l.role}</div>
        </div>
      ),
    },
    {
      key: 'action',
      header: 'Forensic Event Action',
      width: '200px',
      cell: (l) => (
        <div className="truncate">
          <span className="font-mono text-xs font-semibold text-fg block truncate">{l.action}</span>
          <span className="text-[0.625rem] text-mute block truncate">{l.target_path}</span>
        </div>
      ),
    },
    {
      key: 'operation_id',
      header: 'Operation ID',
      width: '140px',
      cell: (l) => <EvidenceId value={l.operation_id} label="Operation ID" size="sm" />,
    },
    {
      key: 'result',
      header: 'Result',
      width: '110px',
      cell: (l) => (
        <Badge
          variant={
            l.result === 'SUCCESS' ? 'success' : l.result === 'WARNING' ? 'warning' : 'danger'
          }
        >
          {l.result}
        </Badge>
      ),
    },
    {
      key: 'correlation_id',
      header: 'Correlation ID',
      width: '140px',
      cell: (l) => <EvidenceId value={l.correlation_id} label="Correlation ID" size="sm" />,
    },
  ]

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Recorded Forensic Audit Events"
        icon={<ScrollText className="h-4 w-4" />}
        description="Chronological event record capturing operator authorizations, destructive dispatches, and verification telemetry."
      />

      <div className="flex-1 p-6 space-y-4 max-w-7xl">
        {/* Search & Filter Bar */}
        <div className="rounded-md border border-line bg-surface p-3 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto flex-1 max-w-md">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by actor, action, target, or correlation ID..."
              className="font-mono text-xs"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select<string>
              label="Filter results"
              hideLabel
              value={resultFilter}
              onChange={(val) => setResultFilter(val)}
              options={[
                { value: 'ALL', label: 'All Results' },
                { value: 'SUCCESS', label: 'Success' },
                { value: 'WARNING', label: 'Warning' },
                { value: 'FAILURE', label: 'Failure' },
              ]}
              size="sm"
            />
          </div>
        </div>

        {/* Table Content */}
        {!isAuditAvailable ? (
          <UnavailableState
            title="Audit Stream Ingestion Awaiting Backend Delivery"
            reason="Centralized audit event collection requires GET /api/audit/events (scheduled for Milestone A delivery)."
          />
        ) : (
          <DataTable<AuditLogEntry>
            columns={columns}
            rows={[]}
            rowKey={(l) => l.id}
            caption="Audit Records"
            emptyContent={
              <EmptyState
                title="No Audit Records Found"
                description="No security or operator events match the active filters."
              />
            }
            onRowSelect={(entry) => setSelectedEntry(entry)}
          />
        )}
      </div>

      {/* Audit Event Detail Inspector */}
      <InspectorDrawer
        open={Boolean(selectedEntry)}
        onClose={() => setSelectedEntry(null)}
        title={`Audit Event Record: ${selectedEntry?.id || ''}`}
        subtitle="Forensic operator action log"
      >
        {selectedEntry && (
          <div className="space-y-4 text-xs">
            <div className="rounded-md border border-line bg-elevated/40 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-dim uppercase text-[0.6875rem] font-medium">Outcome</span>
                <Badge variant={selectedEntry.result === 'SUCCESS' ? 'success' : 'danger'}>
                  {selectedEntry.result}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-2 font-mono text-[0.6875rem]">
                <div>
                  <span className="text-dim block">Actor / Role:</span>
                  <span className="text-fg font-semibold">
                    {selectedEntry.actor} ({selectedEntry.role})
                  </span>
                </div>
                <div>
                  <span className="text-dim block">Timestamp:</span>
                  <span className="text-fg">{formatIso(selectedEntry.timestamp)}</span>
                </div>
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] block uppercase font-medium">
                Action Performed
              </span>
              <div className="rounded-sm border border-line bg-inset p-3 font-mono text-fg text-xs">
                {selectedEntry.action}
              </div>
            </div>

            <div className="space-y-1">
              <span className="text-dim text-[0.6875rem] block uppercase font-medium">
                Correlation Identifiers
              </span>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-dim text-[0.625rem] block">Operation ID:</span>
                  <EvidenceId value={selectedEntry.operation_id} label="Operation ID" />
                </div>
                <div>
                  <span className="text-dim text-[0.625rem] block">Correlation ID:</span>
                  <EvidenceId value={selectedEntry.correlation_id} label="Correlation ID" />
                </div>
              </div>
            </div>
          </div>
        )}
      </InspectorDrawer>
    </div>
  )
}
