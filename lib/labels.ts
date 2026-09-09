import type {
  OperationState,
  AssuranceResult,
  EraseMode,
  Sensitivity,
  RiskLevel,
} from './types'

// Human-friendly display labels. Backend enum values are never renamed in the
// data layer — only presented differently here.

export type Tone = 'accent' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'

export const operationLabel: Record<OperationState, { text: string; tone: Tone }> = {
  CREATED: { text: 'Created', tone: 'neutral' },
  ANALYZING: { text: 'Analyzing', tone: 'info' },
  READY: { text: 'Ready', tone: 'info' },
  ERASING: { text: 'Erasing', tone: 'accent' },
  VERIFYING: { text: 'Verifying', tone: 'info' },
  RECOVERY_TEST: { text: 'Recovery test', tone: 'info' },
  RESIDUAL_SCAN: { text: 'Residual scan', tone: 'info' },
  ASSESSING: { text: 'Assessing', tone: 'info' },
  CERTIFYING: { text: 'Certifying', tone: 'info' },
  COMPLETED: { text: 'Completed', tone: 'success' },
  PARTIAL: { text: 'Partial', tone: 'warning' },
  FAILED: { text: 'Failed', tone: 'danger' },
  INCONCLUSIVE: { text: 'Evidence inconclusive', tone: 'warning' },
  CANCELLED: { text: 'Cancelled', tone: 'neutral' },
}

export const assuranceLabel: Record<AssuranceResult, { text: string; tone: Tone }> = {
  VALIDATED: { text: 'Validated', tone: 'success' },
  PARTIALLY_VALIDATED: { text: 'Partially validated', tone: 'warning' },
  INCONCLUSIVE: { text: 'Inconclusive', tone: 'warning' },
  FAILED: { text: 'Failed', tone: 'danger' },
}

export const modeLabel: Record<EraseMode, string> = {
  SINGLE_PASS: 'Single-pass overwrite',
  MULTI_PASS: 'Multi-pass overwrite',
  CRYPTO_ERASE: 'Crypto erase',
  PURGE: 'NIST 800-88 Purge',
}

export const sensitivityTone: Record<Sensitivity, Tone> = {
  NONE: 'neutral',
  LOW: 'info',
  MODERATE: 'warning',
  HIGH: 'warning',
  CRITICAL: 'danger',
}

export const riskTone: Record<RiskLevel, Tone> = {
  MINIMAL: 'neutral',
  LOW: 'info',
  MODERATE: 'warning',
  ELEVATED: 'warning',
  SEVERE: 'danger',
}

export function toneColor(tone: Tone): string {
  switch (tone) {
    case 'accent':
      return 'var(--accent)'
    case 'success':
      return 'var(--success)'
    case 'warning':
      return 'var(--warning)'
    case 'danger':
      return 'var(--danger)'
    case 'info':
      return 'var(--info)'
    default:
      return 'var(--dim)'
  }
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatDuration(ms?: number): string {
  if (ms == null) return '—'
  if (ms < 1000) return `${ms} ms`
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}m ${rem}s`
}

export function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.round(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}
