// OBLIVION domain model. Backend states are preserved verbatim; display
// labels are derived separately (see lib/labels.ts).

export type OperationState =
  | 'CREATED'
  | 'ANALYZING'
  | 'READY'
  | 'ERASING'
  | 'VERIFYING'
  | 'RECOVERY_TEST'
  | 'RESIDUAL_SCAN'
  | 'ASSESSING'
  | 'CERTIFYING'
  | 'COMPLETED'
  | 'PARTIAL'
  | 'FAILED'
  | 'INCONCLUSIVE'
  | 'CANCELLED'

export type AssuranceResult =
  | 'VALIDATED'
  | 'PARTIALLY_VALIDATED'
  | 'INCONCLUSIVE'
  | 'FAILED'

export type EraseMode = 'SINGLE_PASS' | 'MULTI_PASS' | 'CRYPTO_ERASE' | 'PURGE'

export type Sensitivity = 'NONE' | 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'

export type RiskLevel = 'MINIMAL' | 'LOW' | 'MODERATE' | 'ELEVATED' | 'SEVERE'

export interface TargetProfile {
  path: string
  name: string
  filesystem: string
  volume: string
  volumeId: string
  sizeBytes: number
  fileCount: number
  sha256: string
  storageClass: string
  overwriteSupported: boolean
  trimEnabled: boolean
  snapshotsPresent: boolean
  sensitivity: Sensitivity
  warnings: string[]
}

export interface AiAnalysis {
  classifications: { label: string; matches: number; confidence: number }[]
  summary: string
  recommendedMode: EraseMode
  recommendedPolicy: string
  rationale: string
}

export interface StageRecord {
  id: string
  label: string
  state: 'pending' | 'active' | 'done' | 'failed' | 'skipped' | 'inconclusive'
  startedAt?: string
  durationMs?: number
  detail?: string
}

export interface Operation {
  id: string
  target: string
  targetPath: string
  mode: EraseMode
  policy: string
  state: OperationState
  progress: number
  currentStage: string
  startedAt: string
  durationMs?: number
  sizeBytes: number
  fileCount: number
  assurance?: AssuranceResult
  warnings: string[]
  error?: { code: string; message: string; retryable: boolean; requestId: string }
  stages: StageRecord[]
}

export interface RecoveryObject {
  id: string
  operationId: string
  label: string
  status: 'SEALED' | 'AUTHORIZED' | 'DENIED' | 'RESTORED' | 'EXPIRED'
  createdAt: string
  expiresAt: string
  originalHash: string
  restoreResult?: 'HASH_MATCH' | 'HASH_MISMATCH' | 'PENDING'
}

export interface ResidualFinding {
  id: string
  operationId: string
  artifact: string
  artifactType: string
  similarity: number | null // null => inconclusive, do not fabricate precision
  sensitivity: Sensitivity
  risk: RiskLevel
  location: string
  evidence: string
}

export interface Certificate {
  id: string
  operationId: string
  target: string
  mode: EraseMode
  assurance: AssuranceResult
  evidenceHash: string
  signatureState: 'SIGNED' | 'UNSIGNED'
  verification: 'VALID' | 'INVALID' | 'UNVERIFIED'
  invalidReason?: string
  issuedAt: string
}

export interface AuditEvent {
  id: string
  timestamp: string
  actor: string
  action: string
  operationId?: string
  result: 'OK' | 'DENIED' | 'FAILED' | 'INFO'
  correlationId: string
  eventType: string
  hash: string
  prevHash: string
}

export interface SystemComponent {
  id: string
  name: string
  status: 'OPERATIONAL' | 'DEGRADED' | 'OFFLINE'
  detail: string
  latencyMs?: number
}

// ---- Appearance / workspace preferences ----

export type ThemeMode = 'dark' | 'light' | 'system'
export type Density = 'comfortable' | 'standard' | 'compact'
export type Corner = 'sharp' | 'balanced' | 'soft'
export type Motion = 'full' | 'reduced' | 'minimal'

export interface Appearance {
  theme: ThemeMode
  accent: string
  accentFg: string
  accentName: string
  density: Density
  corner: Corner
  motion: Motion
}

export type WidgetSize = 'XS' | 'SM' | 'MD' | 'LG' | 'XL' | 'FULL'

export interface WidgetInstance {
  id: string
  type: string
  size: WidgetSize
}

export interface Workspace {
  id: string
  name: string
  widgets: WidgetInstance[]
}
