/**
 * Presentation-only formatters. Every function accepts `undefined`/`null` and returns the
 * placeholder so that missing backend values are never fabricated.
 */

export const PLACEHOLDER = '—'

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return PLACEHOLDER
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** i
  return `${value.toFixed(i === 0 ? 0 : value >= 100 ? 0 : 1)} ${units[i]}`
}

export function formatInteger(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return PLACEHOLDER
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}

export function formatCount(count: number | null | undefined, unit = 'item'): string {
  if (count == null || !Number.isFinite(count)) return PLACEHOLDER
  const formatted = formatInteger(count)
  return `${formatted} ${count === 1 ? unit : `${unit}s`}`
}

export function formatIso(iso: string | null | undefined): string {
  if (!iso) return PLACEHOLDER
  return formatTimestamp(iso)
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return PLACEHOLDER
  return `${Math.round(value)}%`
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return PLACEHOLDER
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(d)
}

export function formatDurationMs(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return PLACEHOLDER
  if (ms < 1000) return `${Math.round(ms)} ms`
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  if (m < 60) return `${m} m ${rem} s`
  const h = Math.floor(m / 60)
  return `${h} h ${m % 60} m`
}

export function truncateMiddle(value: string, head = 10, tail = 6): string {
  if (value.length <= head + tail + 1) return value
  return `${value.slice(0, head)}…${value.slice(-tail)}`
}

export function textOrPlaceholder(value: string | null | undefined): string {
  return value && value.trim() !== '' ? value : PLACEHOLDER
}
