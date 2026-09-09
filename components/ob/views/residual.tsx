'use client'

import { useState } from 'react'
import { ScanSearch, AlertTriangle } from 'lucide-react'
import { Page, PageHeader } from '../page'
import { StatusPill, Meta, Segmented } from '../primitives'
import { cn } from '@/lib/utils'
import { residualFindings } from '@/lib/mock-data'
import { riskTone, sensitivityTone, toneColor } from '@/lib/labels'
import type { ResidualFinding } from '@/lib/types'

export function ResidualView() {
  const [selected, setSelected] = useState<ResidualFinding>(residualFindings[0])
  const sorted = [...residualFindings].sort((a, b) => rankRisk(b.risk) - rankRisk(a.risk))

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Residual Analysis"
        description="Forensic examination of what remains after erasure. Uncertainty is reported honestly — inconclusive findings are never converted into a false percentage."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,440px)_1fr]">
        <div className="space-y-2">
          {sorted.map((f) => {
            const isSel = selected.id === f.id
            const inconclusive = f.similarity === null
            return (
              <button
                key={f.id}
                onClick={() => setSelected(f)}
                className={cn(
                  'w-full rounded-lg border p-3 text-left transition-colors',
                  isSel ? 'border-line-strong bg-surface' : 'border-line bg-surface/50 hover:bg-surface',
                )}
                style={isSel ? { boxShadow: `inset 2px 0 0 ${toneColor(riskTone[f.risk])}` } : undefined}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-[0.8125rem] font-medium text-fg">{f.artifact}</span>
                  <StatusPill tone={riskTone[f.risk]}>{f.risk}</StatusPill>
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-[0.6875rem] text-mute">
                  <span>{f.artifactType}</span>
                  <span>·</span>
                  {inconclusive ? (
                    <span style={{ color: 'var(--warning)' }}>similarity inconclusive</span>
                  ) : (
                    <span className="font-mono">{f.similarity}% similarity</span>
                  )}
                </div>
              </button>
            )
          })}
        </div>

        <div className="rounded-lg border border-line bg-surface p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-inset">
                <ScanSearch className="h-4 w-4 text-dim" />
              </div>
              <div>
                <h2 className="text-[0.9375rem] font-semibold text-fg">{selected.artifact}</h2>
                <p className="text-[0.6875rem] text-mute">{selected.operationId} · {selected.artifactType}</p>
              </div>
            </div>
            <StatusPill tone={riskTone[selected.risk]}>{selected.risk} risk</StatusPill>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-x-6 sm:grid-cols-3">
            <Meta label="Sensitivity">{selected.sensitivity}</Meta>
            <div className="flex items-baseline justify-between gap-4 py-1.5">
              <span className="text-xs text-mute">Similarity to original</span>
              <span className="text-right text-[0.8125rem]">
                {selected.similarity === null ? (
                  <span style={{ color: 'var(--warning)' }}>Inconclusive</span>
                ) : (
                  <span className="font-mono tabular text-fg">{selected.similarity}%</span>
                )}
              </span>
            </div>
            <Meta label="Location" mono>{selected.location}</Meta>
          </div>

          {selected.similarity === null ? (
            <div
              className="mt-3 flex items-start gap-2.5 rounded-md border p-3 text-[0.8125rem]"
              style={{ borderColor: 'color-mix(in oklab, var(--warning) 35%, transparent)', backgroundColor: 'var(--warning-soft)' }}
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: 'var(--warning)' }} />
              <div>
                <p className="font-medium text-fg">Inconclusive by design</p>
                <p className="mt-0.5 text-dim leading-relaxed">{selected.evidence}</p>
              </div>
            </div>
          ) : (
            <div className="mt-3 rounded-md border border-line bg-inset p-3">
              <p className="text-[0.6875rem] text-mute">EVIDENCE</p>
              <p className="mt-1 text-[0.8125rem] text-dim leading-relaxed">{selected.evidence}</p>
            </div>
          )}
        </div>
      </div>
    </Page>
  )
}

function rankRisk(r: ResidualFinding['risk']): number {
  return ['MINIMAL', 'LOW', 'MODERATE', 'ELEVATED', 'SEVERE'].indexOf(r)
}
