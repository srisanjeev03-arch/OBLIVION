'use client'

import { useId } from 'react'
import { toneColor, type Tone } from '@/lib/labels'

/* Lightweight, purposeful SVG charts. Accent-aware where the series is
   product data; semantic colors are preserved for status series. */

export function StackedActivityChart({
  data,
  height = 120,
}: {
  data: { d: string; erased: number; verified: number; failed: number }[]
  height?: number
}) {
  const max = Math.max(...data.map((x) => x.erased), 1)
  const w = 100
  const gap = 1.4
  const bw = (w - gap * (data.length - 1)) / data.length
  return (
    <div>
      <svg
        viewBox={`0 0 ${w} ${height}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
        role="img"
        aria-label="Erasure activity, last 14 days"
      >
        {[0.25, 0.5, 0.75].map((g) => (
          <line
            key={g}
            x1={0}
            x2={w}
            y1={height * g}
            y2={height * g}
            stroke="var(--line)"
            strokeWidth={0.3}
          />
        ))}
        {data.map((x, i) => {
          const total = x.erased
          const h = (total / max) * (height - 6)
          const vh = (x.verified / max) * (height - 6)
          const fh = (x.failed / max) * (height - 6)
          const xPos = i * (bw + gap)
          return (
            <g key={x.d}>
              {/* unverified remainder (accent soft) */}
              <rect
                x={xPos}
                y={height - h}
                width={bw}
                height={h}
                rx={0.6}
                fill="var(--accent)"
                opacity={0.28}
              />
              {/* verified (accent) */}
              <rect
                x={xPos}
                y={height - vh}
                width={bw}
                height={vh}
                rx={0.6}
                fill="var(--accent)"
              />
              {/* failed (danger) sits on top */}
              {x.failed > 0 && (
                <rect
                  x={xPos}
                  y={height - h - fh - 1}
                  width={bw}
                  height={fh}
                  rx={0.6}
                  fill="var(--danger)"
                />
              )}
            </g>
          )
        })}
      </svg>
      <div className="mt-2 flex items-center justify-between text-[0.6875rem] text-mute">
        <span>{data[0].d}</span>
        <div className="flex items-center gap-3">
          <Legend color="var(--accent)" label="Verified" />
          <Legend color="color-mix(in oklab, var(--accent) 28%, transparent)" label="Erased" />
          <Legend color="var(--danger)" label="Failed" />
        </div>
        <span>{data[data.length - 1].d}</span>
      </div>
    </div>
  )
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className="h-2 w-2 rounded-[2px]"
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  )
}

export function DonutChart({
  segments,
  size = 132,
  thickness = 14,
  centerLabel,
  centerSub,
}: {
  segments: { label: string; value: number; color: string }[]
  size?: number
  thickness?: number
  centerLabel?: string
  centerSub?: string
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1
  const r = (size - thickness) / 2
  const c = 2 * Math.PI * r
  let offset = 0
  return (
    <div className="flex items-center gap-5">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--inset)"
            strokeWidth={thickness}
          />
          {segments.map((s) => {
            const len = (s.value / total) * c
            const el = (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={thickness}
                strokeDasharray={`${len} ${c - len}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
              />
            )
            offset += len
            return el
          })}
        </svg>
        {centerLabel && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-semibold tabular text-fg">
              {centerLabel}
            </span>
            {centerSub && (
              <span className="text-[0.6875rem] text-mute">{centerSub}</span>
            )}
          </div>
        )}
      </div>
      <ul className="flex-1 space-y-1.5">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center justify-between gap-3 text-[0.8125rem]">
            <span className="flex items-center gap-2 text-dim">
              <span
                className="h-2 w-2 rounded-[2px]"
                style={{ backgroundColor: s.color }}
              />
              {s.label}
            </span>
            <span className="tabular text-fg">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function BarList({
  items,
  tone = 'accent',
}: {
  items: { label: string; value: number }[]
  tone?: Tone
}) {
  const max = Math.max(...items.map((i) => i.value), 1)
  return (
    <ul className="space-y-2.5">
      {items.map((it) => (
        <li key={it.label} className="space-y-1">
          <div className="flex items-center justify-between text-[0.8125rem]">
            <span className="text-dim">{it.label}</span>
            <span className="tabular text-fg">{it.value}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-inset">
            <div
              className="h-full rounded-full"
              style={{
                width: `${(it.value / max) * 100}%`,
                backgroundColor: toneColor(tone),
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function Sparkline({
  points,
  height = 34,
  tone = 'accent',
}: {
  points: number[]
  height?: number
  tone?: Tone
}) {
  const gid = useId()
  const max = Math.max(...points)
  const min = Math.min(...points)
  const range = max - min || 1
  const w = 100
  const step = w / (points.length - 1)
  const path = points
    .map((p, i) => {
      const x = i * step
      const y = height - ((p - min) / range) * (height - 4) - 2
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
  const color = toneColor(tone)
  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height }}
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.22} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path
        d={`${path} L${w},${height} L0,${height} Z`}
        fill={`url(#${gid})`}
        stroke="none"
      />
      <path d={path} fill="none" stroke={color} strokeWidth={1.4} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function RadialGauge({
  value,
  size = 132,
  tone = 'success',
  label,
}: {
  value: number
  size?: number
  tone?: Tone
  label?: string
}) {
  const thickness = 12
  const r = (size - thickness) / 2
  const c = Math.PI * r // half circle
  const filled = (value / 100) * c
  const color = toneColor(tone)
  return (
    <div className="relative" style={{ width: size, height: size / 2 + 12 }}>
      <svg width={size} height={size / 2 + 12}>
        <path
          d={`M ${thickness / 2} ${size / 2} A ${r} ${r} 0 0 1 ${size - thickness / 2} ${size / 2}`}
          fill="none"
          stroke="var(--inset)"
          strokeWidth={thickness}
          strokeLinecap="round"
        />
        <path
          d={`M ${thickness / 2} ${size / 2} A ${r} ${r} 0 0 1 ${size - thickness / 2} ${size / 2}`}
          fill="none"
          stroke={color}
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${c}`}
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 flex flex-col items-center">
        <span className="text-2xl font-semibold tabular text-fg">
          {value.toFixed(1)}%
        </span>
        {label && <span className="text-[0.6875rem] text-mute">{label}</span>}
      </div>
    </div>
  )
}
