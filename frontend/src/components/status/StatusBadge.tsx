import type { ComponentType } from 'react'
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  Circle,
  CircleDashed,
  CircleDot,
  CircleHelp,
  CircleSlash,
  Loader2,
  MinusCircle,
  ShieldAlert,
  ShieldCheck,
  ShieldOff,
  ShieldQuestion,
  XCircle,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import {
  assuranceStateMeta,
  connectionStateMeta,
  operationStateMeta,
  screenStateMeta,
  sensitivityMeta,
  verificationStateMeta,
  type AssuranceState,
  type ConnectionState,
  type OperationState,
  type ScreenState,
  type SensitivityLevel,
  type StatusMeta,
  type Tone,
  type VerificationState,
} from '@/lib/status'

type Icon = ComponentType<{ className?: string }>

/* Icon per value — every status carries a distinct glyph so colour is never the only signal. */

const screenIcons: Record<ScreenState, Icon> = {
  LOADING: Loader2,
  EMPTY: Circle,
  AVAILABLE: CircleDot,
  RUNNING: Loader2,
  COMPLETED: CheckCircle2,
  FAILED: XCircle,
  PARTIAL: MinusCircle,
  BLOCKED: Ban,
  INCONCLUSIVE: CircleHelp,
  UNAVAILABLE: CircleSlash,
  NOT_EVALUATED: CircleDashed,
}

const operationIcons: Record<OperationState, Icon> = {
  CREATED: Circle,
  ANALYZING: Loader2,
  // Waiting on a second actor: a hold, not progress and not a fault.
  PENDING_APPROVAL: CircleDashed,
  READY: CircleDot,
  RESIDUAL_ANALYSIS: Loader2,
  // The process stopped and nobody has established what happened on disk.
  // Deliberately a question glyph, never a failure or a success: both of those
  // would assert something that has not been determined.
  RECONCILIATION_REQUIRED: CircleHelp,
  ERASING: Loader2,
  VERIFYING: Loader2,
  RECOVERY_TEST: Loader2,
  RESIDUAL_SCAN: Loader2,
  ASSESSING: Loader2,
  CERTIFYING: Loader2,
  COMPLETED: CheckCircle2,
  PARTIAL: MinusCircle,
  FAILED: XCircle,
  INCONCLUSIVE: CircleHelp,
  CANCELLED: Ban,
}

const assuranceIcons: Record<AssuranceState, Icon> = {
  PASSED: ShieldCheck,
  PARTIAL: ShieldAlert,
  INCONCLUSIVE: ShieldQuestion,
  FAILED: ShieldOff,
  NOT_EVALUATED: CircleDashed,
}

const verificationIcons: Record<VerificationState, Icon> = {
  VALID: ShieldCheck,
  INVALID: ShieldOff,
  UNVERIFIED: ShieldQuestion,
  UNAVAILABLE: CircleSlash,
}

const sensitivityIcons: Record<SensitivityLevel, Icon> = {
  PUBLIC: Circle,
  INTERNAL: CircleDot,
  CONFIDENTIAL: AlertTriangle,
  CRITICAL: ShieldAlert,
}

const connectionIcons: Record<ConnectionState, Icon> = {
  UNKNOWN: CircleDashed,
  CONNECTED: Wifi,
  UNREACHABLE: WifiOff,
  ERROR: AlertTriangle,
}

const SPINNING = new Set<string>([
  'LOADING',
  'RUNNING',
  'ANALYZING',
  'ERASING',
  'VERIFYING',
  'RECOVERY_TEST',
  'RESIDUAL_SCAN',
  'ASSESSING',
  'CERTIFYING',
])

const toneClasses: Record<Tone, string> = {
  neutral: 'border-line-strong bg-transparent text-dim',
  info: 'border-info/40 bg-info-soft text-info',
  accent: 'border-accent/40 bg-accent-soft text-accent',
  success: 'border-success/40 bg-success-soft text-success',
  warning: 'border-warning/40 bg-warning-soft text-warning',
  danger: 'border-danger/40 bg-danger-soft text-danger',
}

export type StatusBadgeProps =
  | { kind: 'screen'; value: ScreenState }
  | { kind: 'operation'; value: OperationState }
  | { kind: 'assurance'; value: AssuranceState }
  | { kind: 'verification'; value: VerificationState }
  | { kind: 'sensitivity'; value: SensitivityLevel }
  | { kind: 'connection'; value: ConnectionState }

function resolve(props: StatusBadgeProps): { meta: StatusMeta; Icon: Icon } {
  switch (props.kind) {
    case 'screen':
      return { meta: screenStateMeta[props.value], Icon: screenIcons[props.value] }
    case 'operation':
      return { meta: operationStateMeta[props.value], Icon: operationIcons[props.value] }
    case 'assurance':
      return { meta: assuranceStateMeta[props.value], Icon: assuranceIcons[props.value] }
    case 'verification':
      return { meta: verificationStateMeta[props.value], Icon: verificationIcons[props.value] }
    case 'sensitivity':
      return { meta: sensitivityMeta[props.value], Icon: sensitivityIcons[props.value] }
    case 'connection':
      return { meta: connectionStateMeta[props.value], Icon: connectionIcons[props.value] }
  }
}

/**
 * The one way status is rendered in the console: enum value → label + icon + tone.
 * Always shows the raw backend value in a title so operators can cross-reference evidence.
 */
export function StatusBadge(
  props: StatusBadgeProps & {
    size?: 'sm' | 'md'
    emphasis?: 'quiet' | 'strong'
    className?: string
  },
) {
  const { size = 'sm', emphasis = 'quiet', className } = props
  const { meta, Icon } = resolve(props)
  const spinning = SPINNING.has(props.value)
  return (
    <span
      title={`${props.value} — ${meta.description}`}
      data-status={props.value}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-sm border font-medium whitespace-nowrap',
        size === 'sm' ? 'h-5 px-1.5 text-[0.6875rem]' : 'h-6 px-2 text-xs',
        toneClasses[meta.tone],
        emphasis === 'strong' && 'font-semibold uppercase tracking-[0.06em]',
        className,
      )}
    >
      <Icon className={cn('h-3 w-3 shrink-0', spinning && 'motion-spin')} aria-hidden="true" />
      <span>{meta.label}</span>
    </span>
  )
}
