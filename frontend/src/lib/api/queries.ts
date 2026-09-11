import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import type { ScreenState } from '@/lib/status'
import { request } from './client'
import { ApiError, isApiError } from './errors'
import {
  buildPath,
  getCapability,
  isAvailable,
  unavailableReason,
  type CapabilityId,
} from './capabilities'
import type { EvidenceEvent, Operation, RecoveryObject, TargetProfile } from './types'
import type { components } from './schema'

/**
 * Certificate types come straight from the generated contract rather than being restated here.
 * §14's dimension vocabulary is only trustworthy if it is the backend's own enum, and the generated
 * `DimensionResultOut` carries exactly that: the ten dimensions and PASS/FAIL/NOT_CHECKED/
 * INCONCLUSIVE, extracted from `oblivion.certificate.verification`.
 */
export type CertificateOut = components['schemas']['CertificateOut']
export type CertificateVerificationOut = components['schemas']['CertificateVerificationOut']
export type DimensionResultOut = components['schemas']['DimensionResultOut']
export type VerificationDimension = DimensionResultOut['dimension']
export type DimensionResult = DimensionResultOut['result']
export type OverallStatus = CertificateVerificationOut['overall_status']

/**
 * Audit types come from the generated contract too, for the same reason the certificate ones do:
 * the chain vocabulary is only worth rendering if it is the backend's own, not a restatement that
 * can drift from it.
 */
export type AuditEventOut = components['schemas']['AuditEventOut']
export type AuditEventPageOut = components['schemas']['AuditEventPageOut']
export type AuditChainVerificationOut = components['schemas']['AuditChainVerificationOut']
export type AuditLinkOut = components['schemas']['AuditLinkOut']

/** The closed-loop pipeline result, straight from the generated contract. */
export type PipelineResultOut = components['schemas']['PipelineResultOut']
export type PipelineStageOut = components['schemas']['PipelineStageOut']

/** Per-record link states, in escalating order of concern. */
export const AUDIT_LINK_STATUSES = [
  'VALID_GENESIS',
  'VALID_PREDECESSOR',
  'MISSING_PREDECESSOR',
  'BROKEN_PREDECESSOR',
  'MUTATED_EVENT',
] as const

export interface AuditEventFilters {
  operation_id?: string
  actor_id?: string
  event_type?: string
  outcome?: string
  limit?: number
  offset?: number
}

/** The ten verification dimensions, in the order the backend enumerates them. */
export const VERIFICATION_DIMENSIONS: readonly VerificationDimension[] = [
  'STRUCTURE',
  'VERSION_COMPATIBILITY',
  'EVIDENCE_AVAILABILITY',
  'EVIDENCE_DIGEST',
  'SIGNATURE_VALIDITY',
  'PUBLIC_KEY_CONSISTENCY',
  'SIGNER_TRUST',
  'EVIDENCE_CHAIN_INTEGRITY',
  'OPERATION_CONSISTENCY',
  'TARGET_CONSISTENCY',
] as const

/** Query-key factory. Keep every key here so invalidation stays predictable. */
export const queryKeys = {
  all: ['oblivion'] as const,
  target: (id: string) => ['oblivion', 'target', id] as const,
  operation: (id: string) => ['oblivion', 'operation', id] as const,
  operationEvents: (id: string) => ['oblivion', 'operation', id, 'events'] as const,
  recoveryObjects: () => ['oblivion', 'recovery-objects'] as const,
  certificate: (id: string) => ['oblivion', 'certificate', id] as const,
  certificateVerification: (id: string) =>
    ['oblivion', 'certificate', id, 'verification'] as const,
  auditEvents: (filters: AuditEventFilters) => ['oblivion', 'audit', 'events', filters] as const,
  auditVerification: () => ['oblivion', 'audit', 'verification'] as const,
}

/**
 * Wraps a capability so that unimplemented endpoints resolve to UNAVAILABLE without touching the
 * network. Retries are left to the QueryClient defaults (idempotent GETs only, see providers).
 */
export function gatedFetcher<T>(id: CapabilityId, path: string) {
  return async ({ signal }: { signal: AbortSignal }): Promise<T> => {
    if (!isAvailable(id)) {
      throw new ApiError({
        kind: 'not_implemented',
        message: unavailableReason(id) ?? 'Capability unavailable',
      })
    }
    return request<T>(path, { method: getCapability(id).method, signal })
  }
}

export function useTargetQuery(targetId: string | undefined) {
  return useQuery<TargetProfile, ApiError>({
    queryKey: queryKeys.target(targetId ?? ''),
    queryFn: gatedFetcher<TargetProfile>(
      'targets.get',
      buildPath('targets.get', { target_id: targetId ?? '' }),
    ),
    enabled: !!targetId && isAvailable('targets.get'),
  })
}

export function useOperationQuery(operationId: string | undefined, options?: { pollMs?: number }) {
  return useQuery<Operation, ApiError>({
    queryKey: queryKeys.operation(operationId ?? ''),
    queryFn: gatedFetcher<Operation>(
      'operations.get',
      buildPath('operations.get', { operation_id: operationId ?? '' }),
    ),
    enabled: !!operationId && isAvailable('operations.get'),
    refetchInterval: options?.pollMs,
  })
}

export function useOperationEventsQuery(operationId: string | undefined) {
  return useQuery<EvidenceEvent[], ApiError>({
    queryKey: queryKeys.operationEvents(operationId ?? ''),
    queryFn: gatedFetcher<EvidenceEvent[]>(
      'operations.events',
      buildPath('operations.events', { operation_id: operationId ?? '' }),
    ),
    enabled: !!operationId && isAvailable('operations.events'),
  })
}

export function useRecoveryObjectsQuery() {
  return useQuery<RecoveryObject[], ApiError>({
    queryKey: queryKeys.recoveryObjects(),
    queryFn: gatedFetcher<RecoveryObject[]>('recovery.list', buildPath('recovery.list')),
    enabled: isAvailable('recovery.list'),
  })
}

/**
 * Fetch an issued certificate by ID.
 *
 * The contract publishes no certificate collection route, so there is no list to browse: an
 * operator arrives with an ID from an operation's evidence trail. That is a real limitation and is
 * stated as one on the screen rather than papered over with a table of invented certificates.
 */
export function useCertificateQuery(certificateId: string | undefined) {
  return useQuery<CertificateOut, ApiError>({
    queryKey: queryKeys.certificate(certificateId ?? ''),
    queryFn: gatedFetcher<CertificateOut>(
      'certificates.get',
      buildPath('certificates.get', { certificate_id: certificateId ?? '' }),
    ),
    enabled: !!certificateId && isAvailable('certificates.get'),
  })
}

/**
 * Read the append-only audit log.
 *
 * Requires `audit.view`, which only ADMIN and AUDITOR hold. A caller without it gets a 403, which
 * `toScreenState` renders as BLOCKED - a refusal the operator can see and act on, rather than an
 * empty table that would read as "no events happened".
 */
export function useAuditEventsQuery(filters: AuditEventFilters = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const suffix = query.toString()

  return useQuery<AuditEventPageOut, ApiError>({
    queryKey: queryKeys.auditEvents(filters),
    queryFn: gatedFetcher<AuditEventPageOut>(
      'audit.events',
      `${buildPath('audit.events')}${suffix ? `?${suffix}` : ''}`,
    ),
    enabled: isAvailable('audit.events'),
  })
}

export interface ScreenStateResult {
  state: ScreenState
  reason?: string
}

/**
 * Collapses a query result and its capability into the console's screen-state vocabulary.
 * Components render from this so LOADING / EMPTY / UNAVAILABLE / FAILED are never ad hoc.
 */
export function toScreenState<T>(
  capability: CapabilityId,
  result: Pick<UseQueryResult<T, ApiError>, 'status' | 'error' | 'data' | 'fetchStatus'>,
  isEmpty: (data: T) => boolean = (d) => Array.isArray(d) && d.length === 0,
): ScreenStateResult {
  if (!isAvailable(capability)) {
    return { state: 'UNAVAILABLE', reason: unavailableReason(capability) ?? undefined }
  }
  if (result.status === 'pending') {
    return result.fetchStatus === 'fetching' ? { state: 'LOADING' } : { state: 'NOT_EVALUATED' }
  }
  if (result.status === 'error') {
    if (isApiError(result.error) && result.error.isUnavailable) {
      return { state: 'UNAVAILABLE', reason: result.error.message }
    }
    if (isApiError(result.error) && result.error.isAuthorization) {
      return { state: 'BLOCKED', reason: result.error.message }
    }
    return { state: 'FAILED', reason: result.error?.message }
  }
  if (result.data === undefined || isEmpty(result.data)) return { state: 'EMPTY' }
  return { state: 'AVAILABLE' }
}
