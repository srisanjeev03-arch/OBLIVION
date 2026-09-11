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
import {
  queryKeys,
  type AuditChainVerificationOut,
  type CertificateVerificationOut,
  type PipelineResultOut,
} from './queries'
import type {
  CreateOperationRequest,
  Operation,
  RestoreRequest,
  TargetAnalyzeRequest,
  TargetProfile,
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

/**
 * POST /api/operations/{id}/approve — the second half of the duty split.
 *
 * The request carries no body. The approving identity comes from the authenticated session, so
 * there is no field in which a caller could name someone else as the approver. The backend refuses
 * a requester approving their own operation with 403, and that refusal is recorded in the audit log
 * even though the request itself rolls back.
 */
export function useApproveOperationMutation(operationId: string) {
  const qc = useQueryClient()
  return useMutation<Operation, ApiError, void>({
    mutationFn: () =>
      gatedMutation<undefined, Operation>('operations.approve', {
        operation_id: operationId,
      })(undefined),
    retry: false,
    onSuccess: () => void qc.invalidateQueries({ queryKey: queryKeys.operation(operationId) }),
  })
}

/**
 * POST /api/operations/{id}/pipeline — the closed loop, and the destructive one.
 *
 * No request body, deliberately: target, mode, policy and approval are read from the persisted
 * operation, so an approved erasure cannot be redirected at another path.
 *
 * A 200 does not mean the target was erased. It means the pipeline ran and reported what happened,
 * which may be a refusal — callers must read `final_state` and the per-stage statuses rather than
 * inferring success from the status code. A null `certificate_id` is a normal outcome.
 */
export function useRunPipelineMutation(operationId: string) {
  const qc = useQueryClient()
  return useMutation<PipelineResultOut, ApiError, void>({
    mutationFn: () =>
      gatedMutation<undefined, PipelineResultOut>('operations.pipeline', {
        operation_id: operationId,
      })(undefined),
    retry: false,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.operation(operationId) })
      void qc.invalidateQueries({ queryKey: queryKeys.operationEvents(operationId) })
      void qc.invalidateQueries({ queryKey: ['oblivion', 'audit', 'events'] })
    },
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

/**
 * POST /api/certificates/{id}/verify — the backend's Ed25519 verification, returning one result per
 * verification dimension plus an overall status.
 *
 * The console does not verify anything itself and never did: there is no frontend crypto here.
 */
export function useVerifyCertificateMutation(certificateId: string) {
  const qc = useQueryClient()
  return useMutation<CertificateVerificationOut, ApiError, void>({
    mutationFn: () =>
      gatedMutation<undefined, CertificateVerificationOut>('certificates.verify', {
        certificate_id: certificateId,
      })(undefined),
    retry: false,
    onSuccess: (result) => {
      qc.setQueryData(queryKeys.certificateVerification(certificateId), result)
    },
  })
}

/**
 * POST /api/audit/verify - the server re-hashes every persisted audit record and answers.
 *
 * The console performs no verification of its own and sends no body: there is no field in this
 * request in which a client could assert that the chain is intact, which is exactly what keeps the
 * verdict the server's. The result carries `does_not_prove` and `scope_note`, and the UI renders
 * them, because an intact audit log is not a claim about erasure, evidence or certificate trust.
 */
export function useVerifyAuditChainMutation() {
  const qc = useQueryClient()
  return useMutation<AuditChainVerificationOut, ApiError, void>({
    mutationFn: () =>
      gatedMutation<undefined, AuditChainVerificationOut>('audit.verify')(undefined),
    retry: false,
    onSuccess: (result) => {
      qc.setQueryData(queryKeys.auditVerification(), result)
      // Verifying is itself an audited act, so the log the operator is looking at
      // is now one record out of date.
      void qc.invalidateQueries({ queryKey: ['oblivion', 'audit', 'events'] })
    },
  })
}
