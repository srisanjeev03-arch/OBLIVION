/**
 * Capability registry — the single place that decides which backend operations the console may call.
 *
 * WHY `inContract` IS NOT A FIELD ANY MORE
 * The previous revision hand-maintained two booleans per capability, `inContract` and `implemented`,
 * and both rotted. `certificates.verify` was marked unimplemented although the backend had shipped
 * and tested certificate verification for a long time; `health` was marked absent although the
 * application routes `/health`; and the auth trio was missing entirely. A stale `implemented: false`
 * is the more dangerous direction, because it makes the console refuse a capability the backend
 * actually serves and then presents that refusal to the operator as a product limitation.
 *
 * So the gate is now derived, not asserted: `isContractOperation()` reads the operation list that
 * `scripts/gen_openapi.py` extracts from the FastAPI application itself. A capability therefore
 * cannot claim to be contracted while unrouted, nor be suppressed while routed.
 *
 * What the backend answers at runtime remains the authority on whether a call *worked*. A 404 or a
 * 500 is rendered as the real failure it is; it is never pre-empted by a frontend guess.
 */
import { isContractOperation } from './contract-paths'

export type CapabilityStatus =
  'AVAILABLE' | 'LIMITED' | 'UNAVAILABLE' | 'NOT_IMPLEMENTED' | 'INCONCLUSIVE'

export type CapabilityId =
  | 'auth.login'
  | 'auth.me'
  | 'auth.logout'
  | 'targets.analyze'
  | 'targets.get'
  | 'operations.create'
  | 'operations.get'
  | 'operations.approve'
  | 'operations.execute'
  | 'operations.cancel'
  | 'operations.events'
  | 'operations.pipeline'
  | 'recovery.list'
  | 'recovery.restore'
  | 'certificates.get'
  | 'certificates.verify'
  | 'evidence.verify'
  | 'audit.events'
  | 'audit.verify'
  | 'health'
  // Absent from the contract. Each is kept here so the screen that would use it can name the gap
  // precisely instead of rendering an empty success state.
  | 'operations.list'
  | 'targets.list'
  | 'assurance.get'
  | 'certificates.list'
  | 'residual.findings'

export interface Capability {
  readonly id: CapabilityId
  readonly method: 'GET' | 'POST'
  /** Path template, with `{param}` placeholders resolved by `buildPath`. */
  readonly path: string
  /** True when the call destroys or overwrites data and must carry an explicit confirmation. */
  readonly destructive: boolean
  readonly summary: string
  /**
   * Only meaningful for capabilities deliberately left out of the contract. Explains what the
   * screen does instead, so the absence is a stated fact rather than a silent blank.
   */
  readonly gapNote?: string
}

export const CAPABILITIES: Readonly<Record<CapabilityId, Capability>> = {
  'auth.login': {
    id: 'auth.login',
    method: 'POST',
    path: '/api/auth/login',
    destructive: false,
    summary: 'Exchange credentials for an opaque bearer session token.',
  },
  'auth.me': {
    id: 'auth.me',
    method: 'GET',
    path: '/api/auth/me',
    destructive: false,
    summary: 'Resolve the principal and granted permissions behind a credential.',
  },
  'auth.logout': {
    id: 'auth.logout',
    method: 'POST',
    path: '/api/auth/logout',
    destructive: false,
    summary: 'Revoke the active session server-side.',
  },
  'targets.analyze': {
    id: 'targets.analyze',
    method: 'POST',
    path: '/api/targets/analyze',
    destructive: false,
    summary: 'Analyze a filesystem target.',
  },
  'targets.get': {
    id: 'targets.get',
    method: 'GET',
    path: '/api/targets/{target_id}',
    destructive: false,
    summary: 'Fetch an analyzed target.',
  },
  'operations.create': {
    id: 'operations.create',
    method: 'POST',
    path: '/api/operations',
    destructive: true,
    summary: 'Create a validated erasure operation.',
  },
  'operations.get': {
    id: 'operations.get',
    method: 'GET',
    path: '/api/operations/{operation_id}',
    destructive: false,
    summary: 'Get operation status.',
  },
  'operations.approve': {
    id: 'operations.approve',
    method: 'POST',
    path: '/api/operations/{operation_id}/approve',
    destructive: false,
    summary: 'Approve a pending operation, subject to separation of duties.',
  },
  'operations.execute': {
    id: 'operations.execute',
    method: 'POST',
    path: '/api/operations/{operation_id}/execute',
    destructive: true,
    summary: 'Execute an approved operation. Performs the real erasure.',
  },
  'operations.cancel': {
    id: 'operations.cancel',
    method: 'POST',
    path: '/api/operations/{operation_id}/cancel',
    destructive: false,
    summary: 'Request cancellation.',
  },
  'operations.events': {
    id: 'operations.events',
    method: 'GET',
    path: '/api/operations/{operation_id}/events',
    destructive: false,
    summary: 'Evidence events for an operation.',
  },
  'operations.pipeline': {
    id: 'operations.pipeline',
    method: 'POST',
    path: '/api/operations/{operation_id}/pipeline',
    destructive: true,
    summary:
      'Run the full closed loop for an approved operation: erase, re-observe, test recovery, ' +
      'scan residuals, assess assurance, issue and verify a certificate.',
  },
  'recovery.list': {
    id: 'recovery.list',
    method: 'GET',
    path: '/api/recovery-objects',
    destructive: false,
    summary: 'List authorized recovery objects.',
  },
  'recovery.restore': {
    id: 'recovery.restore',
    method: 'POST',
    path: '/api/recovery-objects/{recovery_id}/restore',
    destructive: true,
    summary: 'Restore a controlled-recoverable object to a destination.',
  },
  'certificates.get': {
    id: 'certificates.get',
    method: 'GET',
    path: '/api/certificates/{certificate_id}',
    destructive: false,
    summary: 'Fetch an issued certificate.',
  },
  'certificates.verify': {
    id: 'certificates.verify',
    method: 'POST',
    path: '/api/certificates/{certificate_id}/verify',
    destructive: false,
    summary: 'Verify a certificate and return dimension-level results.',
  },
  'evidence.verify': {
    id: 'evidence.verify',
    method: 'POST',
    path: '/api/evidence/verify',
    destructive: false,
    summary: 'Verify a raw evidence package signature against an Ed25519 public key.',
  },
  'audit.events': {
    id: 'audit.events',
    method: 'GET',
    path: '/api/audit/events',
    destructive: false,
    summary:
      'Read the append-only audit log, oldest first. Requires audit.view, held by ADMIN and ' +
      'AUDITOR only.',
  },
  'audit.verify': {
    id: 'audit.verify',
    method: 'POST',
    path: '/api/audit/verify',
    destructive: false,
    summary:
      'Verify the audit chain server-side. Reports audit-log integrity only - never evidence ' +
      'integrity, erasure success or certificate trust.',
  },
  health: {
    id: 'health',
    method: 'GET',
    path: '/health',
    destructive: false,
    summary: 'Unauthenticated liveness probe.',
  },
  // --- deliberately not in the contract -------------------------------------------------
  'operations.list': {
    id: 'operations.list',
    method: 'GET',
    path: '/api/operations',
    destructive: false,
    summary: 'List operations.',
    gapNote:
      'The contract publishes no operation collection route, so the console cannot enumerate ' +
      'operations. It opens a specific operation by ID instead of showing a fabricated table.',
  },
  'targets.list': {
    id: 'targets.list',
    method: 'GET',
    path: '/api/targets',
    destructive: false,
    summary: 'List analyzed targets.',
    gapNote:
      'No target collection route is published; targets are addressed by ID after analysis.',
  },
  'assurance.get': {
    id: 'assurance.get',
    method: 'GET',
    path: '/api/assurance/{operation_id}',
    destructive: false,
    summary: 'Assurance assessment for an operation.',
    gapNote:
      'The assurance engine exists in the backend and its result is embedded in signed evidence, ' +
      'but no assurance read endpoint is published. Assurance is therefore reported as not ' +
      'retrievable rather than evaluated here.',
  },
  'certificates.list': {
    id: 'certificates.list',
    method: 'GET',
    path: '/api/certificates',
    destructive: false,
    summary: 'List certificates.',
    gapNote:
      'No certificate collection route is published, so certificates are looked up by ID rather ' +
      'than listed.',
  },
  'residual.findings': {
    id: 'residual.findings',
    method: 'GET',
    path: '/api/operations/{operation_id}/residuals',
    destructive: false,
    summary: 'Residual findings for an operation.',
    gapNote:
      'Residual analysis runs in the backend and is recorded in evidence events, but no residual ' +
      'findings endpoint is published, so findings cannot be listed.',
  },
}

/** True when the generated contract publishes this exact operation. */
export function isInContract(id: CapabilityId): boolean {
  const c = CAPABILITIES[id]
  return isContractOperation(c.method, c.path)
}

export function getCapability(id: CapabilityId): Capability {
  return CAPABILITIES[id]
}

/**
 * Whether the console may call this operation. Derived from the contract alone: the frontend does
 * not maintain a private opinion about what the backend has shipped.
 */
export function isAvailable(id: CapabilityId): boolean {
  return isInContract(id)
}

/** Operator-facing reason a capability is unavailable, or null when it is available. */
export function unavailableReason(id: CapabilityId): string | null {
  const c = CAPABILITIES[id]
  if (isInContract(id)) return null
  return c.gapNote ?? `The contract publishes no ${c.method} ${c.path} operation.`
}

/** Substitutes `{param}` placeholders with URL-encoded values. */
export function buildPath(id: CapabilityId, params: Record<string, string> = {}): string {
  return CAPABILITIES[id].path.replace(/\{(\w+)\}/g, (_match, key: string) => {
    const value = params[key]
    if (value === undefined) throw new Error(`Missing path parameter "${key}" for ${id}`)
    return encodeURIComponent(value)
  })
}

/**
 * Capabilities whose intent disagrees with the generated contract.
 *
 * A `gapNote` marks a capability as expected-absent; everything else is expected-present. Either
 * disagreement means the registry and the application have drifted, which is the failure this
 * design removes. `capabilities.test.ts` asserts this list is empty.
 */
export function contractDrift(): { id: CapabilityId; expected: boolean; actual: boolean }[] {
  const drift: { id: CapabilityId; expected: boolean; actual: boolean }[] = []
  for (const key of Object.keys(CAPABILITIES) as CapabilityId[]) {
    const c = CAPABILITIES[key]
    const expected = c.gapNote === undefined
    const actual = isInContract(key)
    if (expected !== actual) drift.push({ id: key, expected, actual })
  }
  return drift
}

