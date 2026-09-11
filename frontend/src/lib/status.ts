/**
 * Status vocabulary — the single source of truth for every state the console renders.
 *
 * Backend enum values are never renamed in the data layer. This module only decides how a
 * given value is *presented* (label, tone, explanation). Every important status is rendered
 * with text + icon + tone, never colour alone (see components/status/StatusBadge).
 */

export type Tone = 'neutral' | 'info' | 'accent' | 'success' | 'warning' | 'danger'

export interface StatusMeta {
  readonly label: string
  readonly tone: Tone
  /** Short operator-facing explanation shown in tooltips / inspectors. */
  readonly description: string
}

/* ------------------------------------------------------------------------------------------ */
/* Screen state — every backend-driven surface resolves to exactly one of these.                */
/* ------------------------------------------------------------------------------------------ */

export const SCREEN_STATES = [
  'LOADING',
  'EMPTY',
  'AVAILABLE',
  'RUNNING',
  'COMPLETED',
  'FAILED',
  'PARTIAL',
  'BLOCKED',
  'INCONCLUSIVE',
  'UNAVAILABLE',
  'NOT_EVALUATED',
] as const
export type ScreenState = (typeof SCREEN_STATES)[number]

export const screenStateMeta: Readonly<Record<ScreenState, StatusMeta>> = {
  LOADING: {
    label: 'Loading',
    tone: 'neutral',
    description: 'Waiting for the backend to respond.',
  },
  EMPTY: { label: 'Empty', tone: 'neutral', description: 'The backend returned no records.' },
  AVAILABLE: { label: 'Available', tone: 'info', description: 'Backend data is available.' },
  RUNNING: { label: 'Running', tone: 'accent', description: 'An operation is in progress.' },
  COMPLETED: {
    label: 'Completed',
    tone: 'success',
    description: 'The backend reports completion.',
  },
  FAILED: { label: 'Failed', tone: 'danger', description: 'The backend reports failure.' },
  PARTIAL: {
    label: 'Partial',
    tone: 'warning',
    description: 'Only part of the requested work completed. Review the details.',
  },
  BLOCKED: {
    label: 'Blocked',
    tone: 'warning',
    description: 'A precondition or authorization requirement is not met.',
  },
  INCONCLUSIVE: {
    label: 'Inconclusive',
    tone: 'warning',
    description: 'Evidence is insufficient to reach a conclusion. Not a success.',
  },
  UNAVAILABLE: {
    label: 'Unavailable',
    tone: 'neutral',
    description: 'This capability is not provided by the backend yet.',
  },
  NOT_EVALUATED: {
    label: 'Not evaluated',
    tone: 'neutral',
    description: 'No assessment has been performed.',
  },
}

/* ------------------------------------------------------------------------------------------ */
/* Operation lifecycle — mirrors Operation.state in contract/OPENAPI.yaml exactly.              */
/* ------------------------------------------------------------------------------------------ */

export const OPERATION_LIFECYCLE = [
  'CREATED',
  'ANALYZING',
  'READY',
  'ERASING',
  'VERIFYING',
  'RECOVERY_TEST',
  'RESIDUAL_SCAN',
  'ASSESSING',
  'CERTIFYING',
  'COMPLETED',
] as const

export const OPERATION_TERMINAL_ALTERNATIVES = [
  'PARTIAL',
  'FAILED',
  'INCONCLUSIVE',
  'CANCELLED',
] as const

/**
 * States the backend machine can report that are not stages of the happy path.
 *
 * These are deliberately kept out of `OPERATION_LIFECYCLE` - the stepper rail renders the
 * documented ten-stage progression and should not grow a branch - but they must be *nameable*,
 * because the backend really returns them:
 *
 * - `PENDING_APPROVAL` is where every newly created operation sits, waiting for a second actor.
 *   The console previously had no case for it at all, so the most common state in the system was
 *   unrenderable.
 * - `RESIDUAL_ANALYSIS` is an alias the machine also emits alongside `RESIDUAL_SCAN`.
 * - `RECONCILIATION_REQUIRED` means the process stopped mid-operation and nobody has yet
 *   established what happened on disk. It is the most safety-critical state in the machine, and
 *   rendering it as "unknown" would bury exactly the case that needs a human.
 */
export const OPERATION_NON_LINEAR_STATES = [
  'PENDING_APPROVAL',
  'RESIDUAL_ANALYSIS',
  'RECONCILIATION_REQUIRED',
] as const

export const OPERATION_STATES = [
  ...OPERATION_LIFECYCLE,
  ...OPERATION_NON_LINEAR_STATES,
  ...OPERATION_TERMINAL_ALTERNATIVES,
] as const
export type OperationState = (typeof OPERATION_STATES)[number]

export const operationStateMeta: Readonly<Record<OperationState, StatusMeta>> = {
  CREATED: {
    label: 'Created',
    tone: 'neutral',
    description: 'Operation record exists; nothing has run.',
  },
  ANALYZING: {
    label: 'Analyzing',
    tone: 'info',
    description: 'Target facts and storage profile are being collected.',
  },
  READY: { label: 'Ready', tone: 'info', description: 'Validated and awaiting execution.' },
  ERASING: { label: 'Erasing', tone: 'accent', description: 'Destructive phase in progress.' },
  VERIFYING: {
    label: 'Verifying',
    tone: 'info',
    description: 'Post-erasure verification in progress.',
  },
  RECOVERY_TEST: {
    label: 'Recovery test',
    tone: 'info',
    description: 'Supported recovery techniques are being attempted.',
  },
  RESIDUAL_SCAN: {
    label: 'Residual scan',
    tone: 'info',
    description: 'Scanning for remnants within the defined scope.',
  },
  ASSESSING: {
    label: 'Assessing',
    tone: 'info',
    description: 'Assurance is being computed from evidence.',
  },
  CERTIFYING: {
    label: 'Certifying',
    tone: 'info',
    description: 'Evidence is being canonicalised and signed.',
  },
  COMPLETED: { label: 'Completed', tone: 'success', description: 'All stages completed.' },
  PARTIAL: {
    label: 'Partial',
    tone: 'warning',
    description: 'Some items were not processed. Review failures.',
  },
  FAILED: {
    label: 'Failed',
    tone: 'danger',
    description: 'The operation failed. Nothing is claimed as erased.',
  },
  INCONCLUSIVE: {
    label: 'Inconclusive',
    tone: 'warning',
    description: 'Evidence is insufficient. Do not treat as success.',
  },
  CANCELLED: { label: 'Cancelled', tone: 'neutral', description: 'Cancelled by an operator.' },
  PENDING_APPROVAL: {
    label: 'Pending Approval',
    tone: 'warning',
    description:
      'Awaiting approval by a principal other than the requester. Nothing has been destroyed.',
  },
  RESIDUAL_ANALYSIS: {
    label: 'Residual Analysis',
    tone: 'info',
    description: 'Scanning for what the operation left behind.',
  },
  RECONCILIATION_REQUIRED: {
    label: 'Reconciliation Required',
    tone: 'danger',
    description:
      'The process stopped mid-operation. Whether data was destroyed has not been established — ' +
      'this is neither a success nor a failure until someone looks.',
  },
}

export const ACTIVE_OPERATION_STATES: ReadonlySet<OperationState> = new Set<OperationState>([
  'CREATED',
  'ANALYZING',
  'PENDING_APPROVAL',
  'READY',
  'RESIDUAL_ANALYSIS',
  // Deliberately active, not terminal: an unreconciled operation still needs
  // attention, and treating it as finished would close the case on a question
  // nobody has answered.
  'RECONCILIATION_REQUIRED',
  'ERASING',
  'VERIFYING',
  'RECOVERY_TEST',
  'RESIDUAL_SCAN',
  'ASSESSING',
  'CERTIFYING',
])

export function isOperationState(value: unknown): value is OperationState {
  return typeof value === 'string' && (OPERATION_STATES as readonly string[]).includes(value)
}

/* ------------------------------------------------------------------------------------------ */
/* Assurance, certificate verification, sensitivity                                            */
/* ------------------------------------------------------------------------------------------ */

/**
 * Assurance vocabulary aligned to the backend's `AssuranceStatus` enum
 * (`src/oblivion/core/assurance/models.py`): PASSED, FAILED, PARTIAL, INCONCLUSIVE.
 *
 * NOT_EVALUATED is the console's own state and is deliberately not a backend value: it means "no
 * assurance result has been retrieved", which is a fact about this session rather than about the
 * operation. The previous vocabulary used VALIDATED, a term the backend never emits — it came from
 * the mock scaffold and would have rendered a status no API response could ever produce.
 */
export const ASSURANCE_STATES = [
  'PASSED',
  'PARTIAL',
  'INCONCLUSIVE',
  'FAILED',
  'NOT_EVALUATED',
] as const
export type AssuranceState = (typeof ASSURANCE_STATES)[number]

export const assuranceStateMeta: Readonly<Record<AssuranceState, StatusMeta>> = {
  PASSED: {
    label: 'Passed',
    tone: 'success',
    description: 'Evidence supports the claimed result within the supported scope.',
  },
  PARTIAL: {
    label: 'Partial',
    tone: 'warning',
    description: 'Some evidence is missing or some checks did not complete.',
  },
  INCONCLUSIVE: {
    label: 'Inconclusive',
    tone: 'warning',
    description: 'Evidence does not permit a conclusion.',
  },
  FAILED: {
    label: 'Failed',
    tone: 'danger',
    description: 'Evidence contradicts the claimed result.',
  },
  NOT_EVALUATED: {
    label: 'Not evaluated',
    tone: 'neutral',
    description: 'Assurance has not been assessed.',
  },
}

export const VERIFICATION_STATES = ['VALID', 'INVALID', 'UNVERIFIED', 'UNAVAILABLE'] as const
export type VerificationState = (typeof VERIFICATION_STATES)[number]

export const verificationStateMeta: Readonly<Record<VerificationState, StatusMeta>> = {
  VALID: {
    label: 'Valid',
    tone: 'success',
    description: 'Signature and evidence integrity verified by the backend.',
  },
  INVALID: {
    label: 'Invalid',
    tone: 'danger',
    description: 'Verification failed. Evidence or signature does not match.',
  },
  UNVERIFIED: {
    label: 'Unverified',
    tone: 'neutral',
    description: 'Verification has not been requested.',
  },
  UNAVAILABLE: {
    label: 'Unavailable',
    tone: 'neutral',
    description: 'Verification is not available from the backend.',
  },
}

export const SENSITIVITY_LEVELS = ['PUBLIC', 'INTERNAL', 'CONFIDENTIAL', 'CRITICAL'] as const
export type SensitivityLevel = (typeof SENSITIVITY_LEVELS)[number]

export const sensitivityMeta: Readonly<Record<SensitivityLevel, StatusMeta>> = {
  PUBLIC: { label: 'Public', tone: 'neutral', description: 'No sensitive categories detected.' },
  INTERNAL: { label: 'Internal', tone: 'info', description: 'Internal-use data.' },
  CONFIDENTIAL: {
    label: 'Confidential',
    tone: 'warning',
    description: 'Confidential categories detected.',
  },
  CRITICAL: {
    label: 'Critical',
    tone: 'danger',
    description: 'Critical categories detected (e.g. credentials, regulated PII).',
  },
}

/* ------------------------------------------------------------------------------------------ */
/* Backend connection                                                                           */
/* ------------------------------------------------------------------------------------------ */

export const CONNECTION_STATES = ['UNKNOWN', 'CONNECTED', 'UNREACHABLE', 'ERROR'] as const
export type ConnectionState = (typeof CONNECTION_STATES)[number]

export const connectionStateMeta: Readonly<Record<ConnectionState, StatusMeta>> = {
  UNKNOWN: {
    label: 'Not probed',
    tone: 'neutral',
    description: 'No request has been made yet and the API contract defines no health endpoint.',
  },
  CONNECTED: {
    label: 'Connected',
    tone: 'success',
    description: 'The last backend request succeeded.',
  },
  UNREACHABLE: { label: 'Unreachable', tone: 'danger', description: 'The backend did not answer.' },
  ERROR: { label: 'Error', tone: 'warning', description: 'The backend answered with an error.' },
}
