import { useState } from 'react'
import { FileSearch, AlertTriangle, Info, Layers } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { DataTable, type ColumnDef } from '@/components/ui/DataTable'
import { EvidenceId } from '@/features/evidence/components/EvidenceId'
import { InspectorDrawer } from '@/components/shell/InspectorDrawer'
import { UnavailableState, EmptyState } from '@/components/states'
import { CapabilityBadge } from '@/components/status/CapabilityBadge'
import { isAvailable } from '@/lib/api/capabilities'
import { AIPanel } from '@/components/ai/AIPanel'
import { useAIPreferences } from '@/stores/ai.store'
import { cn } from '@/lib/cn'

export type ResidualClassification =
  'DIRECT_MATCH' | 'LIKELY_RELATED' | 'POSSIBLY_RELATED' | 'UNRELATED' | 'INCONCLUSIVE'

export interface ResidualFinding {
  id: string
  artifact_type: string
  location_offset: string
  classification: ResidualClassification
  similarity_percent: number
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'NEGLIGIBLE'
  explanation: string
  remediation_advice: string
  evidence_ref?: string
}

const FORENSIC_SCAN_CAPABILITIES = [
  {
    category: 'OBSERVED',
    name: 'Live Namespace & ADS Scans',
    status: 'AVAILABLE' as const,
    description:
      'Scans live directory entries, Alternate Data Streams, and visible filesystem nodes.',
  },
  {
    category: 'NOT ASSESSED',
    name: 'Unallocated Cluster Remnant Analysis',
    status: 'UNAVAILABLE' as const,
    description: 'Low-level carving over free cluster pools requires backend scanner plugin.',
  },
  {
    category: 'UNAVAILABLE',
    name: 'Deleted NTFS $MFT Record Parsing',
    status: 'UNAVAILABLE' as const,
    description: 'Raw Master File Table record reconstruction is unsupported in V1 build.',
  },
  {
    category: 'UNAVAILABLE',
    name: 'Flash Controller NAND Out-of-Band Inspection',
    status: 'UNAVAILABLE' as const,
    description: 'Wear-leveling physical silicon inspection is physically unsupported in software.',
  },
]

export function ResidualAnalysis() {
  const isResidualAvailable = isAvailable('residual.findings')
  const aiEnabled = useAIPreferences((s) => s.enabled)
  const [selectedFinding, setSelectedFinding] = useState<ResidualFinding | null>(null)

  const columns: ColumnDef<ResidualFinding>[] = [
    {
      key: 'id',
      header: 'Finding ID',
      width: '140px',
      cell: (f) => <EvidenceId value={f.id} label="Finding ID" size="sm" />,
    },
    {
      key: 'artifact_type',
      header: 'Artifact Type',
      width: '160px',
      cell: (f) => (
        <span className="font-mono text-xs font-semibold text-fg">{f.artifact_type}</span>
      ),
    },
    {
      key: 'location_offset',
      header: 'Cluster / MFT Offset',
      width: '180px',
      cell: (f) => (
        <span className="font-mono text-xs text-dim truncate block" title={f.location_offset}>
          {f.location_offset}
        </span>
      ),
    },
    {
      key: 'classification',
      header: 'Classification',
      width: '160px',
      cell: (f) => (
        <Badge
          variant={
            f.classification === 'DIRECT_MATCH'
              ? 'danger'
              : f.classification === 'LIKELY_RELATED'
                ? 'warning'
                : f.classification === 'INCONCLUSIVE'
                  ? 'neutral'
                  : 'success'
          }
        >
          {f.classification}
        </Badge>
      ),
    },
    {
      key: 'similarity_percent',
      header: 'Similarity',
      width: '110px',
      cell: (f) => (
        <span
          className={cn(
            'font-mono text-xs font-bold tabular',
            f.similarity_percent > 40 ? 'text-danger' : 'text-success',
          )}
        >
          {f.similarity_percent}%
        </span>
      ),
    },
    {
      key: 'risk_level',
      header: 'Remnant Risk',
      width: '130px',
      cell: (f) => (
        <Badge
          variant={
            f.risk_level === 'CRITICAL' || f.risk_level === 'HIGH'
              ? 'danger'
              : f.risk_level === 'MEDIUM'
                ? 'warning'
                : 'neutral'
          }
        >
          {f.risk_level}
        </Badge>
      ),
    },
  ]

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Residual & Remnant Forensics"
        icon={<FileSearch className="h-4 w-4" />}
        description="Forensic examination of post-erasure remnants, cluster slack, and unallocated sector boundaries."
      />

      <div className="flex-1 p-6 space-y-6 max-w-7xl">
        {/* AI Advisory â€” Residual Finding Classification */}
        {aiEnabled && (
          <AIPanel
            title="Residual Finding Classification"
            state="UNAVAILABLE"
            summary="The AI advisory layer is not yet integrated for residual finding classification. Authoritative forensic classification is derived from backend deterministic cluster and MFT analysis."
            drawerSubtitle="AI ADVISORY â€” Residual Finding Classification"
          />
        )}

        {/* Core Forensic Question Banner */}
        <div className="rounded-md border border-line bg-surface p-4 flex items-start gap-3">
          <Info className="h-4 w-4 text-accent shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <span className="font-semibold text-fg block">
              Forensic Inquiry: &ldquo;What remains, and why?&rdquo;
            </span>
            <p className="text-dim leading-relaxed text-[0.6875rem]">
              Oblivion distinguishes between live namespace unlinking and true physical remnant
              eradication. Detectors are explicitly categorized so operators understand what was
              assessed versus what remains unassessed by hardware limitations.
            </p>
          </div>
        </div>

        {/* Forensic Detector Capability Status Grid */}
        <div className="rounded-md border border-line bg-surface p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-line pb-2.5">
            <span className="text-xs font-bold uppercase tracking-wider text-fg flex items-center gap-2">
              <Layers className="h-4 w-4 text-info" />
              Forensic Scanner Detectors & Coverage Boundary
            </span>
            <span className="text-[0.6875rem] text-dim font-mono">STANDALONE AUDIT</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 text-xs">
            {FORENSIC_SCAN_CAPABILITIES.map((cap, idx) => (
              <div
                key={idx}
                className="rounded-sm border border-line bg-elevated/40 p-3 space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-fg">{cap.name}</span>
                  <CapabilityBadge status={cap.status} />
                </div>
                <p className="text-[0.6875rem] text-dim leading-relaxed">{cap.description}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        {!isResidualAvailable ? (
          <UnavailableState
            title="Residual Analysis Awaiting Backend Scanner Integration"
            reason="Sector-level residual analysis requires GET /api/operations/{id}/residuals (scheduled for post-Milestone A delivery)."
          />
        ) : (
          <DataTable<ResidualFinding>
            columns={columns}
            rows={[]}
            rowKey={(f) => f.id}
            caption="Residual Findings"
            emptyContent={
              <EmptyState
                title="Not Assessed â€” Capability Unavailable in Current V1"
                description="Deep unallocated cluster and MFT carving was not performed as the detector is unavailable."
              />
            }
            onRowSelect={(finding) => setSelectedFinding(finding)}
          />
        )}
      </div>

      {/* Residual Finding Inspector Drawer */}
      <InspectorDrawer
        open={Boolean(selectedFinding)}
        onClose={() => setSelectedFinding(null)}
        title={`Residual Artifact: ${selectedFinding?.id || ''}`}
        subtitle="Forensic cluster remnant inspection"
      >
        {selectedFinding && (
          <div className="space-y-4 text-xs">
            <div className="rounded-md border border-line bg-elevated/40 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-dim uppercase text-[0.6875rem] font-medium">
                  Classification
                </span>
                <Badge variant="danger">{selectedFinding.classification}</Badge>
              </div>

              <div className="space-y-1">
                <span className="text-dim text-[0.6875rem] block uppercase">Physical Offset</span>
                <span className="font-mono text-fg font-semibold">
                  {selectedFinding.location_offset}
                </span>
              </div>
            </div>

            {/* Why is this still here? */}
            <div className="rounded-md border border-warning/40 bg-warning-soft p-4 space-y-2 text-warning">
              <div className="flex items-center gap-1.5 font-bold">
                <AlertTriangle className="h-4 w-4" />
                <span>Why is this still here?</span>
              </div>
              <p className="text-[0.6875rem] text-fg leading-relaxed">
                {selectedFinding.explanation}
              </p>
            </div>

            {/* Recommended Remediation */}
            <div className="rounded-md border border-line bg-surface p-4 space-y-2">
              <span className="font-semibold text-fg block text-[0.6875rem] uppercase tracking-wider">
                Remediation Guidance
              </span>
              <p className="text-[0.6875rem] text-dim leading-relaxed">
                {selectedFinding.remediation_advice}
              </p>
            </div>
          </div>
        )}
      </InspectorDrawer>
    </div>
  )
}
