'use client'

import { useState } from 'react'
import { Crosshair, FileText, ChevronRight, Sparkles, ArrowRight, ShieldAlert } from 'lucide-react'
import { Page, PageHeader } from '../page'
import { Button, Meta, Hash, StatusPill, Tag } from '../primitives'
import { useShell } from '../shell-context'
import { cn } from '@/lib/utils'
import { demoTargets } from '@/lib/mock-data'
import { formatBytes, modeLabel, sensitivityTone } from '@/lib/labels'
import type { TargetProfile } from '@/lib/types'

const BROWSE = [
  { path: '/mnt/test-vol/finance/quarterly-forecast.xlsx', size: 19_284_992, sensitivity: 'HIGH' as const },
  { path: '/mnt/test-vol/exports/client-pii-export.csv', size: 4_812_004, sensitivity: 'CRITICAL' as const },
  { path: '/mnt/test-vol/var/session-tokens.log', size: 8_388_608, sensitivity: 'HIGH' as const },
  { path: '/mnt/test-vol/tmp/temp-cache-fragment', size: 1_048_576, sensitivity: 'LOW' as const },
  { path: '/mnt/test-vol/backups/legacy-backup-04', size: 240_128_512, sensitivity: 'MODERATE' as const },
]

export function TargetsView() {
  const { navigate } = useShell()
  const [selected, setSelected] = useState(BROWSE[0].path)
  const demo = demoTargets[0]
  const isDemo = selected === demo.path

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Targets"
        description="Inspect a target before acting. OBLIVION separates measured facts from AI analysis and from its recommendation — these are never blurred together."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,360px)_1fr]">
        {/* Browser */}
        <div className="rounded-lg border border-line bg-surface">
          <div className="border-b border-line px-3.5 py-2.5">
            <p className="text-[0.75rem] font-medium text-dim">/mnt/test-vol</p>
          </div>
          <ul className="p-1.5">
            {BROWSE.map((t) => {
              const name = t.path.split('/').pop()!
              const isSel = selected === t.path
              return (
                <li key={t.path}>
                  <button
                    onClick={() => setSelected(t.path)}
                    className={cn(
                      'flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors',
                      isSel ? 'bg-inset' : 'hover:bg-inset/60',
                    )}
                  >
                    <FileText className="h-4 w-4 shrink-0 text-mute" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[0.8125rem] text-fg">{name}</span>
                      <span className="block font-mono text-[0.6875rem] text-mute">{formatBytes(t.size)}</span>
                    </span>
                    <StatusPill tone={sensitivityTone[t.sensitivity]} dot={false}>
                      {t.sensitivity}
                    </StatusPill>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>

        {/* Analysis */}
        {isDemo ? (
          <TargetAnalysis profile={demo.profile} ai={demo.ai} onErase={() => navigate('workflow')} />
        ) : (
          <div className="flex items-center justify-center rounded-lg border border-dashed border-line-strong p-10 text-center">
            <div>
              <Crosshair className="mx-auto h-6 w-6 text-mute" />
              <p className="mt-3 text-sm font-medium text-fg">Analyze this target</p>
              <p className="mx-auto mt-1 max-w-xs text-[0.8125rem] text-mute">
                Run analysis to profile storage characteristics and classify sensitive content before choosing an action.
              </p>
              <Button variant="primary" size="sm" className="mt-4" onClick={() => setSelected(demo.path)}>
                <Sparkles className="h-3.5 w-3.5" /> Analyze target
              </Button>
            </div>
          </div>
        )}
      </div>
    </Page>
  )
}

function Layer({
  kind,
  children,
}: {
  kind: 'FACTS' | 'AI ANALYSIS' | 'RECOMMENDATION'
  children: React.ReactNode
}) {
  const accent =
    kind === 'RECOMMENDATION'
      ? 'var(--accent)'
      : kind === 'AI ANALYSIS'
        ? 'var(--info)'
        : 'var(--mute)'
  return (
    <section className="rounded-lg border border-line bg-surface">
      <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
        <span
          className="rounded px-1.5 py-0.5 text-[0.625rem] font-semibold tracking-wide"
          style={{ color: accent, backgroundColor: `color-mix(in oklab, ${accent} 14%, transparent)` }}
        >
          {kind}
        </span>
        <span className="text-[0.6875rem] text-mute">
          {kind === 'FACTS' && 'Measured directly from the device'}
          {kind === 'AI ANALYSIS' && 'Model inference — not ground truth'}
          {kind === 'RECOMMENDATION' && 'Suggested policy · operator decides'}
        </span>
      </div>
      <div className="p-4">{children}</div>
    </section>
  )
}

function TargetAnalysis({
  profile,
  ai,
  onErase,
}: {
  profile: TargetProfile
  ai: (typeof demoTargets)[0]['ai']
  onErase: () => void
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4 rounded-lg border border-line bg-surface p-4">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-fg">{profile.name}</h2>
          <p className="mt-1 font-mono text-[0.75rem] text-mute break-all">{profile.path}</p>
        </div>
        <StatusPill tone={sensitivityTone[profile.sensitivity]}>{profile.sensitivity} sensitivity</StatusPill>
      </div>

      <Layer kind="FACTS">
        <div className="grid grid-cols-2 gap-x-6 sm:grid-cols-3">
          <Meta label="Filesystem">{profile.filesystem}</Meta>
          <Meta label="Volume" mono>{profile.volume}</Meta>
          <Meta label="Volume ID" mono>{profile.volumeId}</Meta>
          <Meta label="Size" mono>{formatBytes(profile.sizeBytes)}</Meta>
          <Meta label="Files" mono>{profile.fileCount}</Meta>
          <Meta label="Storage">{profile.storageClass}</Meta>
          <Meta label="Overwrite">{profile.overwriteSupported ? 'Supported' : 'Not supported'}</Meta>
          <Meta label="TRIM">{profile.trimEnabled ? 'Enabled' : 'Disabled'}</Meta>
          <Meta label="Snapshots">{profile.snapshotsPresent ? 'Present' : 'None detected'}</Meta>
        </div>
        <div className="mt-3 flex items-center gap-2 border-t border-line pt-3">
          <span className="text-xs text-mute">SHA-256</span>
          <Hash value={profile.sha256} />
        </div>
      </Layer>

      <Layer kind="AI ANALYSIS">
        <p className="text-[0.8125rem] text-dim leading-relaxed">{ai.summary}</p>
        <ul className="mt-3 space-y-2">
          {ai.classifications.map((c) => (
            <li key={c.label} className="flex items-center justify-between gap-3">
              <span className="text-[0.8125rem] text-fg">{c.label}</span>
              <span className="flex items-center gap-3">
                <Tag mono>{c.matches} matches</Tag>
                <span className="font-mono text-[0.6875rem] text-mute">
                  {(c.confidence * 100).toFixed(0)}% conf.
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Layer>

      <Layer kind="RECOMMENDATION">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[0.8125rem] text-dim">Recommended mode</span>
          <Tag>{modeLabel[ai.recommendedMode]}</Tag>
          <span className="text-[0.8125rem] text-dim">policy</span>
          <Tag>{ai.recommendedPolicy}</Tag>
        </div>
        <p className="mt-3 text-[0.8125rem] text-dim leading-relaxed">{ai.rationale}</p>
        {profile.warnings.map((w) => (
          <div
            key={w}
            className="mt-3 flex items-start gap-2 rounded-md border px-2.5 py-2 text-[0.75rem]"
            style={{ borderColor: 'color-mix(in oklab, var(--warning) 35%, transparent)', backgroundColor: 'var(--warning-soft)' }}
          >
            <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: 'var(--warning)' }} />
            <span className="text-dim">{w}</span>
          </div>
        ))}
        <div className="mt-4 flex justify-end">
          <Button variant="primary" size="sm" onClick={onErase}>
            Proceed to erasure <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </Layer>
    </div>
  )
}
