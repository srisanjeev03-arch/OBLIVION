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

/** Query-key factory. Keep every key here so invalidation stays predictable. */
export const queryKeys = {
  all: ['oblivion'] as const,
  target: (id: string) => ['oblivion', 'target', id] as const,
  operation: (id: string) => ['oblivion', 'operation', id] as const,
  operationEvents: (id: string) => ['oblivion', 'operation', id, 'events'] as const,
  recoveryObjects: () => ['oblivion', 'recovery-objects'] as const,
  certificate: (id: string) => ['oblivion', 'certificate', id] as const,
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
