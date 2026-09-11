/**
 * Domain types mirroring contract/OPENAPI.yaml (v0.1.0) and the standard error shape from the
 * backend's docs/OBLIVION_DOCUMENTATION.md §10.
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

/**
 * Error envelope as *documented* in docs/OBLIVION_DOCUMENTATION.md §10: nested under `error`.
 *
 * IMPORTANT: the backend does not currently emit this shape. It answers with the flat form below
 * (see `FastAPI`'s handlers in `src/oblivion/api/app.py`, which pass `detail` through as
 * `{"error_code": ..., "message": ...}`). Verified live:
 *
 *   401 -> {"error_code": "UNAUTHENTICATED",   "message": "Authentication required"}
 *   401 -> {"error_code": "INVALID_CREDENTIALS","message": "Invalid username or password"}
 *
 * Both shapes are accepted so the console works against the backend as it is today while remaining
 * correct if the documented envelope is ever adopted. Neither shape is invented here.
 */
export interface ApiErrorEnvelope {
  error: {
    code: string
    message: string
    retryable?: boolean
    request_id?: string
  }
}

/** The shape the backend actually returns. */
export interface FlatApiErrorEnvelope {
  error_code: string
  message: string
  retryable?: boolean
  request_id?: string
  details?: unknown
}

/** Normalised view of either envelope. */
export interface NormalisedApiError {
  code: string
  message: string
  retryable?: boolean
  requestId?: string
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

export function isFlatApiErrorEnvelope(value: unknown): value is FlatApiErrorEnvelope {
  if (typeof value !== 'object' || value === null) return false
  const v = value as { error_code?: unknown; message?: unknown }
  return typeof v.error_code === 'string' && typeof v.message === 'string'
}

/**
 * Read either error envelope into one shape, or return null when the body matches neither.
 *
 * Returning null (rather than a default) is deliberate: the caller then falls back to the HTTP
 * status text and we never invent a backend error code that was not sent.
 */
export function normaliseApiErrorBody(value: unknown): NormalisedApiError | null {
  if (isApiErrorEnvelope(value)) {
    return {
      code: value.error.code,
      message: value.error.message,
      retryable: value.error.retryable,
      requestId: value.error.request_id,
    }
  }
  if (isFlatApiErrorEnvelope(value)) {
    return {
      code: value.error_code,
      message: value.message,
      retryable: value.retryable,
      requestId: value.request_id,
    }
  }
  return null
}
