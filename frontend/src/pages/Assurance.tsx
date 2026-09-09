import { ShieldCheck, Info } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Badge } from '@/components/ui/Badge'
import { StatusBadge } from '@/components/status/StatusBadge'
import { CapabilityBadge } from '@/components/status/CapabilityBadge'
import { AIPanel } from '@/components/ai/AIPanel'
import { useAIPreferences } from '@/stores/ai.store'
import type { AssuranceState } from '@/lib/status'

export interface AssuranceVector {
  id: string
  title: string
  description: string
  status: AssuranceState
  capabilityStatus: 'AVAILABLE' | 'LIMITED' | 'UNAVAILABLE'
  standard: string
  limitations?: string
}

const ASSURANCE_FRAMEWORK_VECTORS: AssuranceVector[] = [
  {
    id: 'vec-01',
    title: '1. Target Identification & Cluster Geometry Mapping',
    description:
      'Volume mount point, physical geometry, LCN cluster runs, and sector alignment mapped.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'AVAILABLE',
    standard: 'NTFS Filesystem Standard',
  },
  {
    id: 'vec-02',
    title: '2. Scope Boundary & Alternate Data Streams (ADS)',
    description: 'Named data streams, reparse points, hardlinks, and shadow copy links identified.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'AVAILABLE',
    standard: 'NTFS ADS Specification',
  },
  {
    id: 'vec-03',
    title: '3. Pre-Erasure Cryptographic Baseline Capture',
    description: 'Deterministic SHA-256 payload digest captured prior to destructive overwriting.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'AVAILABLE',
    standard: 'FIPS 180-4 (SHA-256)',
  },
  {
    id: 'vec-04',
    title: '4. Block-Level Sanitization Execution',
    description: 'Execution of NIST SP 800-88 Rev. 1 Cryptographic Purge or multi-pass overwrite.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'LIMITED',
    standard: 'NIST SP 800-88 Rev. 1 / DoD 5220.22-M',
    limitations: 'Requires elevated daemon execution on host OS.',
  },
  {
    id: 'vec-05',
    title: '5. Low-Level Post-Verification Readback',
    description:
      'Immediate readback of targeted physical clusters to verify byte inversion and zero vacancy.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'LIMITED',
    standard: 'ISO/IEC 27040:2015',
  },
  {
    id: 'vec-06',
    title: '6. Negative Forensic Carving Test',
    description:
      'Forensic carvers and file-table parsers evaluate whether deleted headers remain discoverable.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'UNAVAILABLE',
    standard: 'Digital Forensics Carving Standard',
    limitations: 'Negative recovery detector awaiting backend Phase 8 integration.',
  },
  {
    id: 'vec-07',
    title: '7. Unallocated Space & Slack Remnant Analysis',
    description: 'Deep scan of cluster slack bytes and adjacent unallocated sectors.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'UNAVAILABLE',
    standard: 'Forensic Remnant Verification',
    limitations: 'Not assessed — unallocated cluster detector unavailable in current V1 build.',
  },
  {
    id: 'vec-08',
    title: '8. SSD/NVMe Out-of-Band Remnant Evaluation',
    description:
      'Verification that flash wear-leveling did not retain stale copies in unmapped blocks.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'UNAVAILABLE',
    standard: 'NAND Wear-Leveling Boundary',
    limitations:
      'Physical NAND silicon inspection is technically impossible via software without controller testbench.',
  },
  {
    id: 'vec-09',
    title: '9. Tamper-Evident Evidence Chain Integrity',
    description: 'Cryptographic hash-chain of all lifecycle events sealed with zero sequence gaps.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'LIMITED',
    standard: 'Merkle Audit Log Chain',
    limitations: 'Evidence chain persists in memory; permanent ledger delivered in Phase 6.',
  },
  {
    id: 'vec-10',
    title: '10. Ed25519 Root Authority Attestation',
    description: 'Digitally signed cryptographic certificate issued by root certificate authority.',
    status: 'NOT_EVALUATED',
    capabilityStatus: 'LIMITED',
    standard: 'Ed25519 / RFC 8032',
    limitations: 'Awaiting Milestone A certificate issuance backend.',
  },
]

export function Assurance() {
  const aiEnabled = useAIPreferences((s) => s.enabled)
  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Multi-Vector Assurance Framework"
        icon={<ShieldCheck className="h-4 w-4 text-success" />}
        description="Evidence-based forensic verification scorecard. Distinguishes verified scope from physical irrecoverability."
      />

      <div className="flex-1 p-6 space-y-6 max-w-5xl mx-auto w-full">
        {/* AI Advisory — Assurance Explanation */}
        {aiEnabled && (
          <AIPanel
            title="Assurance Explanation"
            state="UNAVAILABLE"
            summary="The AI advisory layer is not yet integrated for assurance explanation. The deterministic multi-vector framework below is the authoritative measure of operational confidence."
            drawerSubtitle="AI ADVISORY — Assurance Explanation"
          />
        )}

        {/* Core Forensic Truth Axiom Banner */}
        <div className="rounded-md border border-info/40 bg-info-soft p-4 space-y-2 text-xs text-info">
          <div className="flex items-center gap-2 font-bold text-fg">
            <Info className="h-4 w-4 text-info shrink-0" />
            <span>Forensic Axiom: NOT DETECTED ≠ PROVABLY UNRECOVERABLE</span>
          </div>
          <p className="text-[0.6875rem] text-dim leading-relaxed">
            Oblivion adheres to strict forensic standards. The absence of detected file remnants in
            a tested filesystem scope does not prove that unallocated NAND wear blocks or hardware
            shadow sectors contain zero residual data. The console guarantees high assurance
            strictly within validated boundaries.
          </p>
        </div>

        {/* Aggregate Status Card */}
        <div className="rounded-md border border-line bg-surface p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="text-dim uppercase text-[0.6875rem] font-bold tracking-wider">
              Assurance Evaluation State
            </span>
            <div className="flex items-center gap-2.5">
              <StatusBadge kind="assurance" value="NOT_EVALUATED" emphasis="strong" size="md" />
              <span className="text-xs text-dim">
                Evaluation executes automatically upon operation completion.
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="neutral">ISO 27040 COMPLIANT</Badge>
            <Badge variant="neutral">NIST SP 800-88</Badge>
          </div>
        </div>

        {/* 10-Point Vector Framework List */}
        <div className="rounded-md border border-line bg-surface overflow-hidden">
          <div className="border-b border-line bg-elevated/60 px-5 py-3 flex items-center justify-between">
            <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
              Multi-Vector Assurance Verification Criteria
            </h3>
            <span className="text-[0.6875rem] text-dim font-mono">10 VERIFICATION VECTORS</span>
          </div>

          <div className="divide-y divide-line">
            {ASSURANCE_FRAMEWORK_VECTORS.map((vec) => (
              <div key={vec.id} className="p-4 space-y-2 hover:bg-elevated/30 transition-colors">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-fg">{vec.title}</span>
                  </div>
                  <div className="flex items-center gap-2.5 shrink-0">
                    <span className="font-mono text-[0.625rem] text-mute">{vec.standard}</span>
                    <CapabilityBadge status={vec.capabilityStatus} />
                  </div>
                </div>

                <p className="text-[0.6875rem] text-dim leading-relaxed">{vec.description}</p>

                {vec.limitations && (
                  <div className="rounded-xs border border-line bg-inset p-2 text-[0.6875rem] text-dim space-y-0.5">
                    <span className="font-semibold text-fg block text-[0.625rem] uppercase">
                      Physical Boundary / Limitation:
                    </span>
                    <span className="opacity-90">{vec.limitations}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
