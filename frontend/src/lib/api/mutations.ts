import { useMutation, useQueryClient } from '@tanstack/react-query'
import { request } from './client'
import { ApiError } from './errors'
import {
  buildPath,
  getCapability,
  isAvailable,
  unavailableReason,
  type CapabilityId,
} from './capabilities'
import { queryKeys } from './queries'
import type {
  CreateOperationRequest,
  Operation,
  RestoreRequest,
  TargetAnalyzeRequest,
  TargetProfile,
  VerificationResult,
} from './types'

/**
 * Mutations are never retried. Destructive capabilities additionally require the caller to pass
 * the exact confirmation the operator saw; the frontend never synthesises it.
 */
export function gatedMutation<TBody, TResult>(
  id: CapabilityId,
  params: Record<string, string> = {},
) {
  return async (body: TBody): Promise<TResult> => {
    if (!isAvailable(id)) {
      throw new ApiError({
        kind: 'not_implemented',
        message: unavailableReason(id) ?? 'Capability unavailable',
      })
    }
    return request<TResult>(buildPath(id, params), { method: getCapability(id).method, body })
  }
}

/** POST /api/targets/analyze — the only capability the backend has shipped (Phase 1). */
export function useAnalyzeTargetMutation() {
  const qc = useQueryClient()
  return useMutation<TargetProfile, ApiError, TargetAnalyzeRequest>({
    mutationFn: gatedMutation<TargetAnalyzeRequest, TargetProfile>('targets.analyze'),
    retry: false,
    onSuccess: (profile) => {
      if (profile.id) qc.setQueryData(queryKeys.target(profile.id), profile)
    },
  })
}

/** POST /api/operations — destructive. Gated off until Phase 2 ships. */
export function useCreateOperationMutation() {
  return useMutation<Operation, ApiError, CreateOperationRequest>({
    mutationFn: gatedMutation<CreateOperationRequest, Operation>('operations.create'),
    retry: false,
  })
}

export function useCancelOperationMutation(operationId: string) {
  const qc = useQueryClient()
  return useMutation<void, ApiError, void>({
    mutationFn: () =>
      gatedMutation<undefined, void>('operations.cancel', { operation_id: operationId })(undefined),
    retry: false,
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.operation(operationId) }),
  })
}

export function useRestoreRecoveryObjectMutation(recoveryId: string) {
  const qc = useQueryClient()
  return useMutation<void, ApiError, RestoreRequest>({
    mutationFn: gatedMutation<RestoreRequest, void>('recovery.restore', {
      recovery_id: recoveryId,
    }),
    retry: false,
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.recoveryObjects() }),
  })
}

export function useVerifyCertificateMutation(certificateId: string) {
  return useMutation<VerificationResult, ApiError, void>({
    mutationFn: () =>
      gatedMutation<undefined, VerificationResult>('certificates.verify', {
        certificate_id: certificateId,
      })(undefined),
    retry: false,
  })
}
