'use client'

import { useMemo, useState } from 'react'
import {
  Plus,
  ChevronRight,
  Check,
  X,
  Minus,
  Loader2,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react'
import { Page, PageHeader } from '../page'
import { Button, StatusPill, Progress, Meta, Hash, Tag, Segmented, EmptyState } from '../primitives'
import { useShell } from '../shell-context'
import { cn } from '@/lib/utils'
import { operations } from '@/lib/mock-data'
import type { Operation, StageRecord } from '@/lib/types'
import {
  operationLabel,
  assuranceLabel,
  modeLabel,
  formatBytes,
  formatDuration,
  formatTime,
  relativeTime,
} from '@/lib/labels'

type Filter = 'all' | 'active' | 'attention' | 'done'

export function OperationsView() {
  const { params, navigate } = useShell()
  const [filter, setFilter] = useState<Filter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(
    params.operationId ?? operations[0]?.id ?? null,
  )

  const filtered = useMemo(() => {
    if (filter === 'active')
      return operations.filter((o) =>
        ['ERASING', 'VERIFYING', 'ANALYZING', 'RECOVERY_TEST', 'RESIDUAL_SCAN', 'ASSESSING', 'CERTIFYING'].includes(o.state),
      )
    if (filter === 'attention')
      return operations.filter((o) => ['FAILED', 'INCONCLUSIVE', 'PARTIAL'].includes(o.state))
    if (filter === 'done') return operations.filter((o) => o.state === 'COMPLETED')
    return operations
  }, [filter])

  const selected = operations.find((o) => o.id === selectedId) ?? filtered[0] ?? null

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Operations"
        description="Every erasure operation and its lifecycle, from analysis through signed evidence."
        actions={
          <Button variant="primary" size="sm" onClick={() => navigate('workflow')}>
            <Plus className="h-3.5 w-3.5" /> New operation
          </Button>
        }
      />

      <div className="mb-4">
        <Segmented
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'all', label: `All ${operations.length}` },
            { value: 'active', label: 'Active' },
            { value: 'attention', label: 'Attention' },
            { value: 'done', label: 'Completed' },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,380px)_1fr]">
        {/* List */}
        <div className="space-y-2">
          {filtered.length === 0 ? (
            <div className="rounded-lg border border-line">
              <EmptyState
                icon={AlertTriangle}
                title="Nothing here"
                description="No operations match this filter."
              />
            </div>
          ) : (
            filtered.map((o) => {
              const l = operationLabel[o.state]
              const isSel = selected?.id === o.id
              return (
                <button
                  key={o.id}
                  onClick={() => setSelectedId(o.id)}
                  className={cn(
                    'w-full rounded-lg border p-3 text-left transition-colors',
                    isSel ? 'border-line-strong bg-surface' : 'border-line bg-surface/50 hover:bg-surface',
                  )}
                  style={isSel ? { boxShadow: 'inset 2px 0 0 var(--accent)' } : undefined}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-[0.8125rem] font-medium text-fg">{o.target}</span>
                    <StatusPill tone={l.tone}>{l.text}</StatusPill>
                  </div>
                  <div className="mt-1 flex items-center gap-2 font-mono text-[0.6875rem] text-mute">
                    <span>{o.id}</span>
                    <span>·</span>
                    <span>{formatBytes(o.sizeBytes)}</span>
                  </div>
                  {['ERASING', 'VERIFYING', 'ANALYZING'].includes(o.state) && (
                    <div className="mt-2">
                      <Progress value={o.progress} />
                    </div>
                  )}
                </button>
              )
            })
          )}
        </div>

        {/* Detail */}
        {selected ? (
          <OperationDetail op={selected} onView={(v) => navigate(v as never)} />
        ) : null}
      </div>
    </Page>
  )
}

const STAGE_ICON: Record<StageRecord['state'], React.ReactNode> = {
  done: <Check className="h-3 w-3" style={{ color: 'var(--success)' }} />,
  active: <Loader2 className="h-3 w-3 animate-spin" style={{ color: 'var(--accent)' }} />,
  failed: <X className="h-3 w-3" style={{ color: 'var(--danger)' }} />,
  inconclusive: <AlertTriangle className="h-3 w-3" style={{ color: 'var(--warning)' }} />,
  skipped: <Minus className="h-3 w-3 text-mute" />,
  pending: <span className="h-1.5 w-1.5 rounded-full bg-[var(--mute)]" />,
}

function OperationDetail({ op, onView }: { op: Operation; onView: (v: string) => void }) {
  const [open, setOpen] = useState<string | null>(op.stages.find((s) => s.state === 'active')?.id ?? null)
  const l = operationLabel[op.state]

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-line bg-surface p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-base font-semibold text-fg">{op.target}</h2>
              <StatusPill tone={l.tone}>{l.text}</StatusPill>
            </div>
            <p className="mt-1 font-mono text-[0.75rem] text-mute break-all">{op.targetPath}</p>
          </div>
          {op.assurance && (
            <div className="text-right">
              <p className="text-[0.6875rem] text-mute">Assurance</p>
              <StatusPill tone={assuranceLabel[op.assurance].tone}>
                {assuranceLabel[op.assurance].text}
              </StatusPill>
            </div>
          )}
        </div>

        {['ERASING', 'VERIFYING', 'ANALYZING'].includes(op.state) && (
          <div className="mt-3">
            <div className="mb-1 flex items-center justify-between text-[0.6875rem] text-mute">
              <span>{op.currentStage}</span>
              <span className="tabular">{op.progress}%</span>
            </div>
            <Progress value={op.progress} />
          </div>
        )}

        <div className="mt-4 grid grid-cols-2 gap-x-6 sm:grid-cols-3">
          <Meta label="Operation ID" mono>{op.id}</Meta>
          <Meta label="Mode">{modeLabel[op.mode]}</Meta>
          <Meta label="Policy">{op.policy}</Meta>
          <Meta label="Started">{formatTime(op.startedAt)}</Meta>
          <Meta label="Duration" mono>{formatDuration(op.durationMs)}</Meta>
          <Meta label="Scope" mono>{op.fileCount} file{op.fileCount > 1 ? 's' : ''} · {formatBytes(op.sizeBytes)}</Meta>
        </div>

        {op.warnings.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {op.warnings.map((w) => (
              <div
                key={w}
                className="flex items-start gap-2 rounded-md border px-2.5 py-2 text-[0.75rem]"
                style={{ borderColor: 'color-mix(in oklab, var(--warning) 35%, transparent)', backgroundColor: 'var(--warning-soft)' }}
              >
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: 'var(--warning)' }} />
                <span className="text-dim">{w}</span>
              </div>
            ))}
          </div>
        )}

        {op.error && (
          <div
            className="mt-3 rounded-md border p-3"
            style={{ borderColor: 'color-mix(in oklab, var(--danger) 40%, transparent)', backgroundColor: 'var(--danger-soft)' }}
          >
            <div className="flex items-center justify-between">
              <span className="text-[0.8125rem] font-medium" style={{ color: 'var(--danger)' }}>
                {op.error.code}
              </span>
              {op.error.retryable && (
                <Button variant="outline" size="sm">
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              )}
            </div>
            <p className="mt-1 text-[0.8125rem] text-dim">{op.error.message}</p>
            <p className="mt-2 font-mono text-[0.6875rem] text-mute">
              request_id: {op.error.requestId} · retryable: {String(op.error.retryable)}
            </p>
          </div>
        )}
      </div>

      {/* Timeline */}
      <div className="rounded-lg border border-line bg-surface p-4">
        <h3 className="mb-3 text-[0.8125rem] font-semibold text-dim">Lifecycle</h3>
        <ol className="relative">
          {op.stages.map((s, i) => {
            const isOpen = open === s.id
            const last = i === op.stages.length - 1
            return (
              <li key={s.id} className="relative pl-7">
                {!last && (
                  <span className="absolute left-[9px] top-5 h-[calc(100%-4px)] w-px bg-line" />
                )}
                <span
                  className={cn(
                    'absolute left-0 top-1 flex h-[18px] w-[18px] items-center justify-center rounded-full border bg-surface',
                    s.state === 'pending' ? 'border-line' : 'border-line-strong',
                  )}
                >
                  {STAGE_ICON[s.state]}
                </span>
                <button
                  onClick={() => setOpen(isOpen ? null : s.id)}
                  className="flex w-full items-center justify-between gap-2 py-1.5 text-left"
                  disabled={!s.detail && !s.durationMs}
                >
                  <span className="flex items-center gap-2">
                    <span className={cn('text-[0.8125rem]', s.state === 'pending' ? 'text-mute' : 'text-fg')}>
                      {s.label}
                    </span>
                    {s.state === 'inconclusive' && (
                      <span className="text-[0.6875rem]" style={{ color: 'var(--warning)' }}>
                        inconclusive
                      </span>
                    )}
                  </span>
                  <span className="flex items-center gap-2">
                    {s.durationMs != null && (
                      <span className="font-mono text-[0.6875rem] text-mute">{formatDuration(s.durationMs)}</span>
                    )}
                    {(s.detail || s.durationMs) && (
                      <ChevronRight className={cn('h-3.5 w-3.5 text-mute transition-transform', isOpen && 'rotate-90')} />
                    )}
                  </span>
                </button>
                {isOpen && s.detail && (
                  <div className="animate-fade-up mb-2 rounded-md border border-line bg-inset px-3 py-2 text-[0.75rem] text-dim">
                    {s.detail}
                  </div>
                )}
              </li>
            )
          })}
        </ol>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
          <Button variant="outline" size="sm" onClick={() => onView('assurance')}>
            View assurance
          </Button>
          <Button variant="outline" size="sm" onClick={() => onView('residual')}>
            Residual analysis
          </Button>
          {op.state === 'COMPLETED' && (
            <Button variant="outline" size="sm" onClick={() => onView('certificates')}>
              View certificate
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => onView('audit')}>
            Audit trail
          </Button>
        </div>
      </div>
    </div>
  )
}
