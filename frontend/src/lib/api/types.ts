/**
 * Domain types mirroring contract/OPENAPI.yaml (v0.1.0) and the standard error shape from the
 * backend's docs/API.md.
 *
 * Run `npm run gen:api` to regenerate `schema.d.ts` from the contract; the aliases below are
 * kept deliberately narrow so they can be re-pointed at the generated `components['schemas']`
 * without touching call sites.
 */

import type { OperationState, SensitivityLevel } from '@/lib/status'

export type OperationMode = 'COMPLETE_ERASURE' | 'SELECTIVE_PERMANENT' | 'CONTROLLED_RECOVERABLE'

export interface TargetAnalyzeRequest {
  path: string
  include_content_analysis?: boolean
}

export interface StorageProfile {
  volume?: string
  filesystem?: string
  media_type?: string
  encryption_status?: string
  capabilities?: string[]
  limitations?: string[]
}

export interface Sensitivity {
  level?: SensitivityLevel
  categories?: string[]
  explanation?: string
}

export interface TargetProfile {
  id?: string
  path?: string
  type?: string
  size_bytes?: number
  file_count?: number
  sha256?: string
  storage_profile?: StorageProfile
  sensitivity?: Sensitivity
}

export interface CreateOperationRequest {
  target_id: string
  mode: OperationMode
  policy_id: string
  confirmation: { acknowledged_risk: boolean }
  recovery?: { retention_seconds?: number }
}

export interface Operation {
  id?: string
  target_id?: string
  mode?: string
  policy_id?: string
  state?: OperationState
  progress_percent?: number
  warnings?: string[]
  error?: Record<string, unknown> | null
}

export interface RecoveryObject {
  id?: string
  operation_id?: string
  status?: string
  created_at?: string
  expires_at?: string
  original_sha256?: string
}

export interface EvidenceEvent {
  sequence?: number
  event_type?: string
  timestamp?: string
  payload_hash?: string
  previous_event_hash?: string
}

export interface VerificationResult {
  valid?: boolean
  evidence_integrity?: boolean
  signature_valid?: boolean
  reason?: string
}

export interface RestoreRequest {
  destination: string
}

/** Standard error envelope from docs/API.md. Not yet in OPENAPI.yaml — tracked as a contract gap. */
export interface ApiErrorEnvelope {
  error: {
    code: string
    message: string
    retryable?: boolean
    request_id?: string
  }
}

export function isApiErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== 'object' || value === null) return false
  const err = (value as { error?: unknown }).error
  return (
    typeof err === 'object' &&
    err !== null &&
    typeof (err as { code?: unknown }).code === 'string' &&
    typeof (err as { message?: unknown }).message === 'string'
  )
}
