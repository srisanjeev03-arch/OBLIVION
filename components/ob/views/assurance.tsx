'use client'

import { useState } from 'react'
import { Check, X, Minus, AlertTriangle, ShieldCheck } from 'lucide-react'
import { Page, PageHeader } from '../page'
import { StatusPill, Meta, Segmented } from '../primitives'
import { cn } from '@/lib/utils'
import { operations } from '@/lib/mock-data'
import { assuranceLabel, modeLabel, toneColor } from '@/lib/labels'
import type { AssuranceResult, Operation } from '@/lib/types'

const CHECKS = ['Target verification', 'Recovery test', 'Residual scan', 'Evidence chain', 'Certificate'] as const

// Per-result check outcomes (mock backend results).
const RESULT_CHECKS: Record<AssuranceResult, Record<string, 'pass' | 'fail' | 'partial' | 'na'>> = {
  VALIDATED: { 'Target verification': 'pass', 'Recovery test': 'pass', 'Residual scan': 'pass', 'Evidence chain': 'pass', 'Certificate': 'pass' },
  PARTIALLY_VALIDATED: { 'Target verification': 'pass', 'Recovery test': 'pass', 'Residual scan': 'partial', 'Evidence chain': 'pass', 'Certificate': 'pass' },
  INCONCLUSIVE: { 'Target verification': 'partial', 'Recovery test': 'pass', 'Residual scan': 'partial', 'Evidence chain': 'pass', 'Certificate': 'na' },
  FAILED: { 'Target verification': 'fail', 'Recovery test': 'na', 'Residual scan': 'na', 'Evidence chain': 'na', 'Certificate': 'na' },
}

const STATEMENTS: Record<AssuranceResult, { established: string; unestablished: string; limitations: string }> = {
  VALIDATED: {
    established: 'Target content was verified as erased, a recovery test could not restore it via supported techniques, and residual artifacts were low-risk.',
    unestablished: 'Nothing outside the tested scope was assessed.',
    limitations: 'Validated within the tested scope and supported recovery techniques. OBLIVION does not claim the data is impossible to recover under all conditions.',
  },
  PARTIALLY_VALIDATED: {
    established: 'The files that were erased passed verification and recovery testing.',
    unestablished: '2 of 12 files were locked by another process and were not erased or verified.',
    limitations: 'Assurance applies only to the subset of files successfully processed.',
  },
  INCONCLUSIVE: {
    established: 'A recovery test and residual scan were performed.',
    unestablished: 'The underlying SSD did not confirm physical overwrite due to wear-levelling, so erasure could not be independently verified.',
    limitations: 'The result is inconclusive. No certificate was issued because assurance could not be established.',
  },
  FAILED: {
    established: 'The operation was created and analysis completed.',
    unestablished: 'Execution halted before any erasure could be verified; the device became read-only mid-operation.',
    limitations: 'No assurance can be claimed. The target was not confirmed erased.',
  },
}

const CHECK_ICON = {
  pass: <Check className="h-3.5 w-3.5" style={{ color: 'var(--success)' }} />,
  fail: <X className="h-3.5 w-3.5" style={{ color: 'var(--danger)' }} />,
  partial: <AlertTriangle className="h-3.5 w-3.5" style={{ color: 'var(--warning)' }} />,
  na: <Minus className="h-3.5 w-3.5 text-mute" />,
}

export function AssuranceView() {
  const assessed = operations.filter((o) => o.assurance)
  const [selectedId, setSelectedId] = useState(assessed[0]?.id)
  const selected = assessed.find((o) => o.id === selectedId) ?? assessed[0]
  const result = selected.assurance!

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Assurance"
        description="What OBLIVION can and cannot prove about each operation — stated plainly, with its limitations."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {assessed.map((o) => {
          const l = assuranceLabel[o.assurance!]
          const isSel = selected.id === o.id
          return (
            <button
              key={o.id}
              onClick={() => setSelectedId(o.id)}
              className={cn(
                'rounded-md border px-3 py-2 text-left transition-colors',
                isSel ? 'border-line-strong bg-surface' : 'border-line bg-surface/50 hover:bg-surface',
              )}
            >
              <div className="flex items-center gap-2">
                <span className="text-[0.8125rem] text-fg">{o.target}</span>
                <StatusPill tone={l.tone} dot={false}>{l.text}</StatusPill>
              </div>
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,340px)_1fr]">
        <ResultHeadline result={result} op={selected} />

        <div className="space-y-4">
          <div className="rounded-lg border border-line bg-surface p-4">
            <h3 className="mb-3 text-[0.8125rem] font-semibold text-dim">Verification checks</h3>
            <ul className="space-y-1.5">
              {CHECKS.map((c) => {
                const state = RESULT_CHECKS[result][c]
                return (
                  <li key={c} className="flex items-center justify-between rounded-md border border-line bg-inset px-3 py-2">
                    <span className={cn('text-[0.8125rem]', state === 'na' ? 'text-mute' : 'text-dim')}>{c}</span>
                    {CHECK_ICON[state]}
                  </li>
                )
              })}
            </ul>
          </div>

          <div className="rounded-lg border border-line bg-surface p-4">
            <Statement label="What was established" body={STATEMENTS[result].established} />
            <Statement label="What could not be established" body={STATEMENTS[result].unestablished} />
            <Statement label="Limitations" body={STATEMENTS[result].limitations} last />
          </div>
        </div>
      </div>
    </Page>
  )
}

function ResultHeadline({ result, op }: { result: AssuranceResult; op: Operation }) {
  const l = assuranceLabel[result]
  const color = toneColor(l.tone)
  return (
    <div
      className="rounded-lg border p-5"
      style={{ borderColor: `color-mix(in oklab, ${color} 30%, transparent)`, backgroundColor: `color-mix(in oklab, ${color} 8%, transparent)` }}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: `color-mix(in oklab, ${color} 18%, transparent)` }}>
        <ShieldCheck className="h-5 w-5" style={{ color }} />
      </div>
      <p className="mt-3 text-xl font-semibold tracking-tight" style={{ color }}>
        {l.text}
      </p>
      <p className="mt-1 text-[0.8125rem] text-dim">{op.target}</p>
      <div className="mt-4 border-t pt-4" style={{ borderColor: 'var(--line)' }}>
        <Meta label="Operation" mono>{op.id}</Meta>
        <Meta label="Mode">{modeLabel[op.mode]}</Meta>
        <Meta label="Policy">{op.policy}</Meta>
      </div>
    </div>
  )
}

function Statement({ label, body, last }: { label: string; body: string; last?: boolean }) {
  return (
    <div className={cn(!last && 'mb-4 border-b border-line pb-4')}>
      <p className="text-[0.6875rem] font-medium tracking-wide text-mute">{label}</p>
      <p className="mt-1 text-[0.8125rem] text-dim leading-relaxed">{body}</p>
    </div>
  )
}
