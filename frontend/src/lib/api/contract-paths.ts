// GENERATED FILE - DO NOT EDIT.
// Written by scripts/gen_openapi.py from docs/OPENAPI.yaml, which is itself generated
// from the FastAPI application. Regenerate with: python scripts/gen_openapi.py
//
// Every operation the backend actually serves. The frontend capability registry consults
// this instead of hand-maintaining an `inContract` boolean, so a capability can never
// claim to be contracted when the application does not route it - or be marked absent
// while the application already serves it.

/** Format: `"<VERB> <path>"`, with path parameters left as `{name}`. */
export const CONTRACT_OPERATIONS: readonly string[] = [
  'GET /api/auth/me',
  'GET /api/certificates/{certificate_id}',
  'GET /api/operations/{operation_id}',
  'GET /api/operations/{operation_id}/events',
  'GET /api/recovery-objects',
  'GET /api/targets/{target_id}',
  'GET /health',
  'POST /api/auth/login',
  'POST /api/auth/logout',
  'POST /api/certificates/{certificate_id}/verify',
  'POST /api/evidence/verify',
  'POST /api/operations',
  'POST /api/operations/{operation_id}/approve',
  'POST /api/operations/{operation_id}/cancel',
  'POST /api/operations/{operation_id}/execute',
  'POST /api/operations/{operation_id}/pipeline',
  'POST /api/recovery-objects/{recovery_id}/restore',
  'POST /api/targets/analyze',
] as const

const LOOKUP: ReadonlySet<string> = new Set(CONTRACT_OPERATIONS)

/** True when the contract publishes this exact verb+path operation. */
export function isContractOperation(method: string, path: string): boolean {
  return LOOKUP.has(`${method.toUpperCase()} ${path}`)
}
