/**
 * Capability registry — the only place that decides whether the console may call a backend
 * endpoint. Two independent facts are recorded per capability:
 *
 *   inContract   the route exists in contract/OPENAPI.yaml
 *   implemented  the backend has shipped it (source: context/IMPLEMENTATION_PROGRESS.md,
 *                last updated 2026-09-05 — Phase 1 in progress, only target analysis planned)
 *
 * A capability that is not implemented short-circuits to UNAVAILABLE *before* any network call.
 * Flip `implemented` here — and only here — as the backend ships phases.
 */

export type CapabilityStatus =
  'AVAILABLE' | 'LIMITED' | 'UNAVAILABLE' | 'NOT_IMPLEMENTED' | 'INCONCLUSIVE'

export interface ForensicCapability {
  readonly id: string
  readonly name: string
  readonly status: CapabilityStatus
  readonly explanation: string
  readonly limitation?: string
  readonly versionPhase?: string
}

export const FORENSIC_CAPABILITIES: readonly ForensicCapability[] = [
  {
    id: 'fs.ntfs_live_analysis',
    name: 'NTFS Live Namespace & ADS Analysis',
    status: 'AVAILABLE',
    explanation: 'Live filesystem path inspection, Alternate Data Streams, and cluster geometry.',
    versionPhase: 'Phase 1',
  },
  {
    id: 'fs.baseline_sha256',
    name: 'Pre-Erasure Baseline SHA-256 Capture',
    status: 'AVAILABLE',
    explanation: 'Captures raw payload digest prior to destructive operations.',
    versionPhase: 'Phase 1',
  },
  {
    id: 'erasure.controlled_execution',
    name: 'Validated Deletion Operations',
    status: 'LIMITED',
    explanation: 'Destructive block-level zeroing and cryptographic key eradication.',
    limitation:
      'Requires running backend daemon with admin elevation; client execution is strictly blocked.',
    versionPhase: 'Phase 2',
  },
  {
    id: 'fs.ntfs_mft_carving',
    name: 'NTFS Deleted $MFT Record Analysis',
    status: 'UNAVAILABLE',
    explanation:
      'Low-level NTFS Master File Table deleted record parsing is not available in current V1 build.',
    limitation: 'Not assessed — detector unavailable in current V1.',
    versionPhase: 'Post-Milestone A',
  },
  {
    id: 'fs.unallocated_clusters',
    name: 'Unallocated Cluster Remnant Scanning',
    status: 'UNAVAILABLE',
    explanation:
      'Raw volume cluster carving in unallocated space is not supported by current target provider.',
    limitation: 'Not assessed — raw volume acquisition unavailable.',
    versionPhase: 'Post-Milestone A',
  },
  {
    id: 'hardware.nand_inspection',
    name: 'SSD / NVMe Controller Out-of-Band Inspection',
    status: 'UNAVAILABLE',
    explanation:
      'Hardware controller wear-leveling NAND inspection is physically unsupported in software-only console.',
    limitation: 'Physical silicon inspection requires hardware testbench.',
    versionPhase: 'Out of Scope',
  },
  {
    id: 'crypto.ed25519_attestation',
    name: 'Ed25519 Cryptographic Attestation Certificates',
    status: 'LIMITED',
    explanation: 'Digital evidence signatures and Merkle root verification.',
    limitation: 'Awaiting Milestone A certificate issuance backend integration.',
    versionPhase: 'Phase 7 (Milestone A)',
  },
] as const

export type CapabilityId =
  | 'targets.analyze'
  | 'targets.get'
  | 'operations.create'
  | 'operations.get'
  | 'operations.cancel'
  | 'operations.events'
  | 'recovery.list'
  | 'recovery.restore'
  | 'certificates.get'
  | 'certificates.verify'
  // Needed by the UI but absent from the contract. Kept so the gaps are explicit and reviewable.
  | 'health'
  | 'operations.list'
  | 'targets.list'
  | 'audit.events'
  | 'assurance.get'
  | 'certificates.list'
  | 'residual.findings'

export interface Capability {
  readonly id: CapabilityId
  readonly method: 'GET' | 'POST'
  /** Path template using `{param}` placeholders exactly as in the contract. */
  readonly path: string
  readonly inContract: boolean
  readonly implemented: boolean
  /** Backend phase from IMPLEMENTATION_PROGRESS.md that delivers this capability. */
  readonly backendPhase: string
  readonly destructive: boolean
  readonly summary: string
}

export const CAPABILITIES: Readonly<Record<CapabilityId, Capability>> = {
  'targets.analyze': {
    id: 'targets.analyze',
    method: 'POST',
    path: '/api/targets/analyze',
    inContract: true,
    implemented: true,
    backendPhase: 'Phase 1 — Discovery + Profiling + Dry-run',
    destructive: false,
    summary: 'Analyze a filesystem target (read-only).',
  },
  'targets.get': {
    id: 'targets.get',
    method: 'GET',
    path: '/api/targets/{target_id}',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 1 — Discovery + Profiling + Dry-run',
    destructive: false,
    summary: 'Fetch a previously analyzed target.',
  },
  'operations.create': {
    id: 'operations.create',
    method: 'POST',
    path: '/api/operations',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 2 — Selective Permanent Deletion',
    destructive: true,
    summary: 'Create a validated erasure operation.',
  },
  'operations.get': {
    id: 'operations.get',
    method: 'GET',
    path: '/api/operations/{operation_id}',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 2 — Selective Permanent Deletion',
    destructive: false,
    summary: 'Observe an operation by ID.',
  },
  'operations.cancel': {
    id: 'operations.cancel',
    method: 'POST',
    path: '/api/operations/{operation_id}/cancel',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 2 — Selective Permanent Deletion',
    destructive: false,
    summary: 'Request cancellation of an operation.',
  },
  'operations.events': {
    id: 'operations.events',
    method: 'GET',
    path: '/api/operations/{operation_id}/events',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 6 — Evidence Chain',
    destructive: false,
    summary: 'Evidence events for an operation.',
  },
  'recovery.list': {
    id: 'recovery.list',
    method: 'GET',
    path: '/api/recovery-objects',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 10 — Vault (Milestone B)',
    destructive: false,
    summary: 'List authorized recovery objects.',
  },
  'recovery.restore': {
    id: 'recovery.restore',
    method: 'POST',
    path: '/api/recovery-objects/{recovery_id}/restore',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 10 — Vault (Milestone B)',
    destructive: true,
    summary: 'Restore a controlled-recoverable object.',
  },
  'certificates.get': {
    id: 'certificates.get',
    method: 'GET',
    path: '/api/certificates/{certificate_id}',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 7 — Certificates (Milestone A)',
    destructive: false,
    summary: 'Fetch a certificate.',
  },
  'certificates.verify': {
    id: 'certificates.verify',
    method: 'POST',
    path: '/api/certificates/{certificate_id}/verify',
    inContract: true,
    implemented: false,
    backendPhase: 'Phase 7 — Certificates (Milestone A)',
    destructive: false,
    summary: 'Verify certificate integrity and signature.',
  },
  health: {
    id: 'health',
    method: 'GET',
    path: '/api/health',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract (docs/API.md gap API-003)',
    destructive: false,
    summary: 'Backend health.',
  },
  'operations.list': {
    id: 'operations.list',
    method: 'GET',
    path: '/api/operations',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract',
    destructive: false,
    summary: 'List operations.',
  },
  'targets.list': {
    id: 'targets.list',
    method: 'GET',
    path: '/api/targets',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract',
    destructive: false,
    summary: 'List analyzed targets.',
  },
  'audit.events': {
    id: 'audit.events',
    method: 'GET',
    path: '/api/audit/events',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract (docs/API.md gap API-003)',
    destructive: false,
    summary: 'Audit timeline.',
  },
  'assurance.get': {
    id: 'assurance.get',
    method: 'GET',
    path: '/api/assurance/{operation_id}',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract (docs/API.md gap API-003)',
    destructive: false,
    summary: 'Assurance assessment for an operation.',
  },
  'certificates.list': {
    id: 'certificates.list',
    method: 'GET',
    path: '/api/certificates',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract',
    destructive: false,
    summary: 'List certificates.',
  },
  'residual.findings': {
    id: 'residual.findings',
    method: 'GET',
    path: '/api/operations/{operation_id}/residuals',
    inContract: false,
    implemented: false,
    backendPhase: 'Not in contract',
    destructive: false,
    summary: 'Residual findings for an operation.',
  },
}

export function getCapability(id: CapabilityId): Capability {
  return CAPABILITIES[id]
}

export function isAvailable(id: CapabilityId): boolean {
  const c = CAPABILITIES[id]
  return c.inContract && c.implemented
}

/** Operator-facing reason a capability is unavailable, or null when it is available. */
export function unavailableReason(id: CapabilityId): string | null {
  const c = CAPABILITIES[id]
  if (!c.inContract) return 'Not defined in the API contract (OPENAPI.yaml v0.1.0).'
  if (!c.implemented) return `Awaiting backend: ${c.backendPhase}.`
  return null
}

/** Substitutes `{param}` placeholders with URL-encoded values. */
export function buildPath(id: CapabilityId, params: Record<string, string> = {}): string {
  return CAPABILITIES[id].path.replace(/\{(\w+)\}/g, (_match, key: string) => {
    const value = params[key]
    if (value === undefined) throw new Error(`Missing path parameter "${key}" for ${id}`)
    return encodeURIComponent(value)
  })
}
