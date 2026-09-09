'use client'

import type { WidgetSize, Workspace } from './types'
import {
  operations,
  recoveryObjects,
  residualFindings,
  certificates,
  auditEvents,
  systemComponents,
  erasureActivity,
  assuranceDistribution,
  methodDistribution,
  demoTargets,
} from './mock-data'
import {
  StatusPill,
  Progress,
  Meta,
  Hash,
  EmptyState,
} from '@/components/ob/primitives'
import {
  StackedActivityChart,
  DonutChart,
  BarList,
  Sparkline,
  RadialGauge,
} from '@/components/ob/charts'
import {
  operationLabel,
  assuranceLabel,
  formatBytes,
  formatTime,
  relativeTime,
  sensitivityTone,
  toneColor,
} from './labels'
import { CheckCircle2, AlertTriangle, Activity, FileCheck } from 'lucide-react'

export interface WidgetDef {
  type: string
  title: string
  description: string
  category: 'CORE' | 'DATA' | 'RECOVERY' | 'EVIDENCE' | 'SYSTEM' | 'ANALYTICS' | 'AI'
  defaultSize: WidgetSize
  render: () => React.ReactNode
}

const active = operations.filter((o) =>
  ['ERASING', 'VERIFYING', 'ANALYZING', 'RECOVERY_TEST', 'RESIDUAL_SCAN'].includes(o.state),
)
const attention = operations.filter((o) =>
  ['FAILED', 'INCONCLUSIVE', 'PARTIAL'].includes(o.state),
)

function StatRow({
  label,
  value,
  sub,
  tone,
}: {
  label: string
  value: string
  sub?: string
  tone?: string
}) {
  return (
    <div>
      <p className="text-xs text-mute">{label}</p>
      <p
        className="mt-1 text-2xl font-semibold tabular tracking-tight"
        style={tone ? { color: tone } : undefined}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-dim">{sub}</p>}
    </div>
  )
}

export const WIDGETS: Record<string, WidgetDef> = {
  'erasure-overview': {
    type: 'erasure-overview',
    title: 'Erasure Overview',
    description: 'Protected assets and lifetime erasures.',
    category: 'CORE',
    defaultSize: 'SM',
    render: () => (
      <div className="grid grid-cols-2 gap-4">
        <StatRow label="Protected assets" value="228" sub="+12 this week" />
        <StatRow label="Verified erasures" value="184" sub="last 30 days" tone={toneColor('success')} />
      </div>
    ),
  },
  'active-operations': {
    type: 'active-operations',
    title: 'Active Operations',
    description: 'Operations currently in progress.',
    category: 'CORE',
    defaultSize: 'MD',
    render: () =>
      active.length === 0 ? (
        <EmptyState icon={Activity} title="No active operations" description="Analyze a target to start a new erasure operation." />
      ) : (
        <ul className="space-y-3">
          {active.map((o) => {
            const l = operationLabel[o.state]
            return (
              <li key={o.id}>
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <span className="truncate text-[0.8125rem] font-medium text-fg">{o.target}</span>
                  <StatusPill tone={l.tone}>{l.text}</StatusPill>
                </div>
                <Progress value={o.progress} />
                <div className="mt-1 flex items-center justify-between text-[0.6875rem] text-mute">
                  <span>{o.currentStage}</span>
                  <span className="tabular">{o.progress}%</span>
                </div>
              </li>
            )
          })}
        </ul>
      ),
  },
  'recent-erasures': {
    type: 'recent-erasures',
    title: 'Recent Erasures',
    description: 'Most recent completed operations.',
    category: 'CORE',
    defaultSize: 'MD',
    render: () => (
      <ul className="divide-y divide-line">
        {operations.slice(0, 4).map((o) => {
          const l = operationLabel[o.state]
          return (
            <li key={o.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="truncate text-[0.8125rem] text-fg">{o.target}</p>
                <p className="font-mono text-[0.6875rem] text-mute">{o.id}</p>
              </div>
              <div className="text-right">
                <StatusPill tone={l.tone}>{l.text}</StatusPill>
                <p className="mt-1 text-[0.6875rem] text-mute">{relativeTime(o.startedAt)}</p>
              </div>
            </li>
          )
        })}
      </ul>
    ),
  },
  'verification-status': {
    type: 'verification-status',
    title: 'Verification Status',
    description: 'Share of erasures verified within scope.',
    category: 'CORE',
    defaultSize: 'SM',
    render: () => (
      <div className="flex flex-col items-center">
        <RadialGauge value={98.7} tone="success" label="verified in scope" />
        <p className="mt-1 text-center text-xs text-mute">
          184 of 187 operations verified
        </p>
      </div>
    ),
  },
  'asset-inventory': {
    type: 'asset-inventory',
    title: 'Asset Inventory',
    description: 'Targets discovered across the test environment.',
    category: 'DATA',
    defaultSize: 'SM',
    render: () => (
      <div className="space-y-3">
        <Meta label="Volumes">3</Meta>
        <Meta label="Discovered files" mono>48,210</Meta>
        <Meta label="Flagged sensitive" mono>1,204</Meta>
        <Meta label="Total size" mono>612 GB</Meta>
      </div>
    ),
  },
  'storage-overview': {
    type: 'storage-overview',
    title: 'Storage Overview',
    description: 'Distribution of target storage classes.',
    category: 'DATA',
    defaultSize: 'MD',
    render: () => (
      <BarList
        items={[
          { label: 'NVMe SSD (TRIM)', value: 62 },
          { label: 'SATA SSD', value: 41 },
          { label: 'Encrypted volume', value: 33 },
          { label: 'Spinning disk', value: 9 },
        ]}
      />
    ),
  },
  'sensitive-findings': {
    type: 'sensitive-findings',
    title: 'Sensitive Data Findings',
    description: 'AI-classified sensitive content by category.',
    category: 'DATA',
    defaultSize: 'MD',
    render: () => (
      <BarList
        tone="warning"
        items={[
          { label: 'Personal identifiers', value: 486 },
          { label: 'Financial records', value: 312 },
          { label: 'Credentials / tokens', value: 204 },
          { label: 'Health information', value: 98 },
        ]}
      />
    ),
  },
  'erasure-activity': {
    type: 'erasure-activity',
    title: 'Erasure Activity',
    description: 'Erased vs verified vs failed over 14 days.',
    category: 'DATA',
    defaultSize: 'LG',
    render: () => <StackedActivityChart data={erasureActivity} />,
  },
  'recovery-operations': {
    type: 'recovery-operations',
    title: 'Recovery Operations',
    description: 'Recent recovery authorization results.',
    category: 'RECOVERY',
    defaultSize: 'MD',
    render: () => (
      <ul className="divide-y divide-line">
        {recoveryObjects.slice(0, 4).map((r) => {
          const tone =
            r.status === 'RESTORED' || r.status === 'AUTHORIZED'
              ? 'success'
              : r.status === 'DENIED'
                ? 'danger'
                : 'neutral'
          return (
            <li key={r.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
              <span className="truncate font-mono text-[0.75rem] text-dim">{r.label}</span>
              <StatusPill tone={tone as never}>{r.status}</StatusPill>
            </li>
          )
        })}
      </ul>
    ),
  },
  'vault-objects': {
    type: 'vault-objects',
    title: 'Vault Objects',
    description: 'Sealed recovery objects awaiting authorization.',
    category: 'RECOVERY',
    defaultSize: 'SM',
    render: () => (
      <div className="grid grid-cols-2 gap-4">
        <StatRow label="Sealed" value="1" />
        <StatRow label="Authorized" value="1" tone={toneColor('success')} />
        <StatRow label="Denied" value="1" tone={toneColor('danger')} />
        <StatRow label="Restored" value="1" />
      </div>
    ),
  },
  'evidence-status': {
    type: 'evidence-status',
    title: 'Evidence Status',
    description: 'Certificate signature and verification state.',
    category: 'EVIDENCE',
    defaultSize: 'SM',
    render: () => (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-[0.8125rem] text-dim">Signed certificates</span>
          <span className="tabular text-fg">217</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[0.8125rem] text-dim">Chain integrity</span>
          <StatusPill tone="success">Intact</StatusPill>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[0.8125rem] text-dim">Last anchor</span>
          <span className="font-mono text-[0.6875rem] text-mute">2h ago</span>
        </div>
      </div>
    ),
  },
  'verification-rate': {
    type: 'verification-rate',
    title: 'Verification Rate',
    description: 'Rolling certificate verification success.',
    category: 'EVIDENCE',
    defaultSize: 'SM',
    render: () => (
      <div>
        <StatRow label="Verification rate" value="99.2%" tone={toneColor('success')} />
        <div className="mt-3">
          <Sparkline points={[96, 97, 98, 97, 99, 98, 99, 99]} tone="success" />
        </div>
      </div>
    ),
  },
  'recent-certificates': {
    type: 'recent-certificates',
    title: 'Recent Certificates',
    description: 'Latest issued evidence certificates.',
    category: 'EVIDENCE',
    defaultSize: 'MD',
    render: () => (
      <ul className="divide-y divide-line">
        {certificates.map((c) => (
          <li key={c.id} className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0">
            <div className="min-w-0">
              <p className="truncate font-mono text-[0.75rem] text-fg">{c.id}</p>
              <p className="truncate text-[0.6875rem] text-mute">{c.target}</p>
            </div>
            <StatusPill tone={c.verification === 'VALID' ? 'success' : 'danger'}>
              {c.verification}
            </StatusPill>
          </li>
        ))}
      </ul>
    ),
  },
  'backend-health': {
    type: 'backend-health',
    title: 'Backend Health',
    description: 'Status of core platform services.',
    category: 'SYSTEM',
    defaultSize: 'MD',
    render: () => (
      <ul className="space-y-2">
        {systemComponents.map((c) => {
          const tone =
            c.status === 'OPERATIONAL'
              ? 'success'
              : c.status === 'DEGRADED'
                ? 'warning'
                : 'danger'
          return (
            <li key={c.id} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-[0.8125rem] text-dim">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ backgroundColor: toneColor(tone as never) }}
                />
                {c.name}
              </span>
              <span className="font-mono text-[0.6875rem] text-mute">
                {c.latencyMs}ms
              </span>
            </li>
          )
        })}
      </ul>
    ),
  },
  'queue-status': {
    type: 'queue-status',
    title: 'Queue Status',
    description: 'Pending and in-flight worker jobs.',
    category: 'SYSTEM',
    defaultSize: 'SM',
    render: () => (
      <div className="grid grid-cols-2 gap-4">
        <StatRow label="Queued" value="3" />
        <StatRow label="Running" value="2" tone={toneColor('accent')} />
        <StatRow label="Workers" value="4" />
        <StatRow label="Failed (24h)" value="1" tone={toneColor('danger')} />
      </div>
    ),
  },
  'audit-activity': {
    type: 'audit-activity',
    title: 'Audit Activity',
    description: 'Most recent audit ledger events.',
    category: 'SYSTEM',
    defaultSize: 'MD',
    render: () => (
      <ul className="space-y-2">
        {auditEvents.slice(0, 4).map((e) => (
          <li key={e.id} className="flex items-center justify-between gap-3 text-[0.8125rem]">
            <span className="truncate text-dim">
              <span className="font-mono text-[0.6875rem] text-mute">{e.actor}</span>{' '}
              {e.action}
            </span>
            <StatusPill
              tone={
                e.result === 'OK'
                  ? 'success'
                  : e.result === 'DENIED' || e.result === 'FAILED'
                    ? 'danger'
                    : 'neutral'
              }
              dot={false}
            >
              {e.result}
            </StatusPill>
          </li>
        ))}
      </ul>
    ),
  },
  'erasure-trends': {
    type: 'erasure-trends',
    title: 'Erasure Trends',
    description: 'Verified erasure throughput trend.',
    category: 'ANALYTICS',
    defaultSize: 'MD',
    render: () => (
      <div>
        <StatRow label="Verified / day (avg)" value="18.2" />
        <div className="mt-3">
          <Sparkline points={erasureActivity.map((x) => x.verified)} />
        </div>
      </div>
    ),
  },
  'failure-analysis': {
    type: 'failure-analysis',
    title: 'Failure Analysis',
    description: 'Failed operations grouped by cause.',
    category: 'ANALYTICS',
    defaultSize: 'MD',
    render: () => (
      <BarList
        tone="danger"
        items={[
          { label: 'Device became read-only', value: 4 },
          { label: 'Files locked by process', value: 3 },
          { label: 'Storage did not confirm', value: 2 },
          { label: 'Cancelled by operator', value: 1 },
        ]}
      />
    ),
  },
  'method-distribution': {
    type: 'method-distribution',
    title: 'Method Distribution',
    description: 'Erasure methods used across operations.',
    category: 'ANALYTICS',
    defaultSize: 'MD',
    render: () => <BarList items={methodDistribution} />,
  },
  'assurance-distribution': {
    type: 'assurance-distribution',
    title: 'Assurance Distribution',
    description: 'Outcomes across all assessed operations.',
    category: 'ANALYTICS',
    defaultSize: 'MD',
    render: () => (
      <DonutChart
        centerLabel="228"
        centerSub="assessed"
        segments={assuranceDistribution.map((s) => ({
          label: s.label,
          value: s.value,
          color:
            s.key === 'VALIDATED'
              ? toneColor('success')
              : s.key === 'PARTIALLY_VALIDATED'
                ? toneColor('warning')
                : s.key === 'INCONCLUSIVE'
                  ? toneColor('warning')
                  : toneColor('danger'),
        }))}
      />
    ),
  },
  'sensitivity-overview': {
    type: 'sensitivity-overview',
    title: 'Sensitivity Overview',
    description: 'AI sensitivity classification of targets.',
    category: 'AI',
    defaultSize: 'MD',
    render: () => (
      <BarList
        tone="warning"
        items={[
          { label: 'Critical', value: 34 },
          { label: 'High', value: 88 },
          { label: 'Moderate', value: 141 },
          { label: 'Low', value: 210 },
        ]}
      />
    ),
  },
  'ai-recommendations': {
    type: 'ai-recommendations',
    title: 'AI Recommendations',
    description: 'Suggested policy for the selected target.',
    category: 'AI',
    defaultSize: 'MD',
    render: () => {
      const ai = demoTargets[0].ai
      return (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="rounded border border-line bg-inset px-1.5 py-0.5 text-[0.6875rem] text-mute">
              AI ANALYSIS
            </span>
            <span className="text-[0.8125rem] text-dim">{demoTargets[0].profile.name}</span>
          </div>
          <p className="text-[0.8125rem] text-dim leading-relaxed">{ai.summary}</p>
          <div className="rounded-md border border-line bg-inset p-2.5">
            <p className="text-[0.6875rem] text-mute">RECOMMENDATION</p>
            <p className="mt-0.5 text-[0.8125rem] font-medium text-fg">{ai.recommendedPolicy}</p>
          </div>
        </div>
      )
    },
  },
  'residual-classifications': {
    type: 'residual-classifications',
    title: 'Residual Classifications',
    description: 'Residual artifacts found after erasure.',
    category: 'AI',
    defaultSize: 'MD',
    render: () => (
      <ul className="space-y-2">
        {residualFindings.map((f) => (
          <li key={f.id} className="flex items-center justify-between gap-3 text-[0.8125rem]">
            <span className="truncate text-dim">{f.artifact}</span>
            {f.similarity === null ? (
              <StatusPill tone="warning" dot={false}>Inconclusive</StatusPill>
            ) : (
              <span className="font-mono text-[0.6875rem] text-mute">{f.similarity}% sim.</span>
            )}
          </li>
        ))}
      </ul>
    ),
  },
}

export const WIDGET_LIST = Object.values(WIDGETS)

export const DEFAULT_WORKSPACES: Workspace[] = [
  {
    id: 'overview',
    name: 'Overview',
    widgets: [
      { id: 'w1', type: 'erasure-overview', size: 'SM' },
      { id: 'w2', type: 'active-operations', size: 'MD' },
      { id: 'w3', type: 'verification-status', size: 'SM' },
      { id: 'w4', type: 'assurance-distribution', size: 'MD' },
      { id: 'w5', type: 'recent-erasures', size: 'MD' },
      { id: 'w6', type: 'erasure-activity', size: 'LG' },
      { id: 'w7', type: 'backend-health', size: 'MD' },
      { id: 'w8', type: 'recent-certificates', size: 'MD' },
    ],
  },
  {
    id: 'operations',
    name: 'Operations',
    widgets: [
      { id: 'o1', type: 'active-operations', size: 'MD' },
      { id: 'o2', type: 'queue-status', size: 'SM' },
      { id: 'o3', type: 'backend-health', size: 'MD' },
      { id: 'o4', type: 'failure-analysis', size: 'MD' },
      { id: 'o5', type: 'recent-erasures', size: 'MD' },
    ],
  },
  {
    id: 'forensics',
    name: 'Forensics',
    widgets: [
      { id: 'f1', type: 'residual-classifications', size: 'MD' },
      { id: 'f2', type: 'recovery-operations', size: 'MD' },
      { id: 'f3', type: 'recent-certificates', size: 'MD' },
      { id: 'f4', type: 'sensitivity-overview', size: 'MD' },
      { id: 'f5', type: 'audit-activity', size: 'MD' },
    ],
  },
]

export const SIZE_COLS: Record<WidgetSize, string> = {
  XS: 'md:col-span-3 lg:col-span-3',
  SM: 'md:col-span-6 lg:col-span-3',
  MD: 'md:col-span-6 lg:col-span-6',
  LG: 'md:col-span-12 lg:col-span-8',
  XL: 'md:col-span-12 lg:col-span-9',
  FULL: 'md:col-span-12 lg:col-span-12',
}

export const SIZE_ORDER: WidgetSize[] = ['XS', 'SM', 'MD', 'LG', 'XL', 'FULL']

export { CheckCircle2, AlertTriangle, FileCheck }
