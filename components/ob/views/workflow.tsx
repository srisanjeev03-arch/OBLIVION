'use client'

import { useEffect, useRef, useState } from 'react'
import {
  Check,
  Loader2,
  ArrowRight,
  ArrowLeft,
  AlertTriangle,
  ShieldCheck,
  FileCheck,
  Sparkles,
  Lock,
} from 'lucide-react'
import { Page, PageHeader } from '../page'
import { Button, Meta, Hash, StatusPill, Tag, Progress, Switch } from '../primitives'
import { useShell } from '../shell-context'
import { cn } from '@/lib/utils'
import { demoTargets } from '@/lib/mock-data'
import { formatBytes, modeLabel } from '@/lib/labels'
import type { EraseMode } from '@/lib/types'

const RAIL = [
  'Target',
  'Analyze',
  'Configure',
  'Confirm',
  'Execute',
  'Verify',
  'Recover',
  'Residual',
  'Assurance',
  'Certificate',
]

// execution stages 4..8 each contribute to progress; 9 is the certificate result
const EXEC_STAGES = [
  { i: 4, label: 'Overwriting target (pass 1–3)' },
  { i: 5, label: 'Verifying erasure' },
  { i: 6, label: 'Running recovery test' },
  { i: 7, label: 'Scanning for residuals' },
  { i: 8, label: 'Assessing assurance' },
]

export function WorkflowView() {
  const { navigate, toast } = useShell()
  const demo = demoTargets[0]
  const [stage, setStage] = useState(0)
  const [mode, setMode] = useState<EraseMode>(demo.ai.recommendedMode)
  const [verifyAfter, setVerifyAfter] = useState(true)
  const [recoveryTest, setRecoveryTest] = useState(true)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [log, setLog] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const timer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => () => { if (timer.current) clearInterval(timer.current) }, [])

  const beginExecution = () => {
    setConfirmOpen(false)
    setRunning(true)
    setStage(4)
    setProgress(0)
    setLog([`operation OP-${Math.random().toString(16).slice(2, 10).toUpperCase()} created`])
    let p = 0
    timer.current = setInterval(() => {
      p += 2
      setProgress(Math.min(p, 100))
      const idx = Math.min(EXEC_STAGES.length - 1, Math.floor(p / 20))
      const cur = EXEC_STAGES[idx]
      setStage(cur.i)
      setLog((l) => {
        const line = `${cur.label}…`
        return l[l.length - 1] === line ? l : [...l, line]
      })
      if (p >= 100) {
        if (timer.current) clearInterval(timer.current)
        setStage(9)
        setRunning(false)
        setDone(true)
        setLog((l) => [...l, 'evidence hash sealed', 'certificate signed · VALID'])
        toast({ title: 'Certificate generated', description: 'Assurance validated within tested scope.', tone: 'success' })
      }
    }, 90)
  }

  const scopeSentence = `You are about to permanently erase 1 file (${formatBytes(demo.profile.sizeBytes)}) from volume ${demo.profile.volume} using ${modeLabel[mode].toLowerCase()}.`

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Erasure Workflow"
        description="A focused, deliberate path from target to signed evidence."
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate('targets')}>
            <ArrowLeft className="h-3.5 w-3.5" /> Back to targets
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[220px_1fr]">
        {/* Progress rail */}
        <ol className="hidden lg:block">
          {RAIL.map((label, i) => {
            const state = i < stage || (done && i <= 9) ? 'done' : i === stage ? 'current' : 'todo'
            const isExec = running && i === stage
            const last = i === RAIL.length - 1
            return (
              <li key={label} className="relative pl-7 pb-4 last:pb-0">
                {!last && <span className="absolute left-[10px] top-5 h-[calc(100%-8px)] w-px bg-line" />}
                <span
                  className={cn(
                    'absolute left-0 top-0.5 flex h-5 w-5 items-center justify-center rounded-full border text-[0.625rem]',
                    state === 'todo' ? 'border-line text-mute' : 'border-line-strong',
                  )}
                  style={state === 'current' ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : state === 'done' ? { color: 'var(--success)' } : undefined}
                >
                  {state === 'done' ? <Check className="h-3 w-3" /> : isExec ? <Loader2 className="h-3 w-3 animate-spin" /> : i + 1}
                </span>
                <span className={cn('text-[0.8125rem]', state === 'todo' ? 'text-mute' : 'text-fg')}>
                  {label}
                </span>
              </li>
            )
          })}
        </ol>

        {/* Panel */}
        <div className="rounded-lg border border-line bg-surface p-5">
          {stage <= 1 && (
            <StepBody
              title={stage === 0 ? 'Selected target' : 'Analysis complete'}
              description={stage === 0 ? 'Confirm the target OBLIVION will act on.' : 'Facts, AI analysis and the recommended policy for this target.'}
            >
              <div className="rounded-md border border-line bg-inset p-3">
                <p className="text-[0.8125rem] font-medium text-fg">{demo.profile.name}</p>
                <p className="mt-0.5 font-mono text-[0.6875rem] text-mute break-all">{demo.profile.path}</p>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-x-6 sm:grid-cols-3">
                <Meta label="Size" mono>{formatBytes(demo.profile.sizeBytes)}</Meta>
                <Meta label="Storage">{demo.profile.storageClass}</Meta>
                <Meta label="Sensitivity">{demo.profile.sensitivity}</Meta>
              </div>
              {stage === 1 && (
                <div className="mt-3 rounded-md border border-line bg-inset p-3">
                  <span className="text-[0.625rem] font-semibold" style={{ color: 'var(--accent)' }}>RECOMMENDATION</span>
                  <p className="mt-1 text-[0.8125rem] text-dim leading-relaxed">{demo.ai.rationale}</p>
                </div>
              )}
            </StepBody>
          )}

          {stage === 2 && (
            <StepBody title="Configure erasure" description="Choose the method and post-erase checks. Defaults follow the recommendation.">
              <div className="space-y-2">
                {(['MULTI_PASS', 'CRYPTO_ERASE', 'PURGE', 'SINGLE_PASS'] as EraseMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={cn(
                      'flex w-full items-center justify-between rounded-md border px-3 py-2.5 text-left transition-colors',
                      mode === m ? 'border-line-strong bg-inset' : 'border-line hover:bg-inset/60',
                    )}
                    style={mode === m ? { boxShadow: 'inset 2px 0 0 var(--accent)' } : undefined}
                  >
                    <span>
                      <span className="block text-[0.8125rem] text-fg">{modeLabel[m]}</span>
                      {m === demo.ai.recommendedMode && (
                        <span className="text-[0.6875rem]" style={{ color: 'var(--accent)' }}>Recommended</span>
                      )}
                    </span>
                    <span className={cn('flex h-4 w-4 items-center justify-center rounded-full border', mode === m ? 'border-transparent' : 'border-line-strong')} style={mode === m ? { backgroundColor: 'var(--accent)' } : undefined}>
                      {mode === m && <Check className="h-3 w-3" style={{ color: 'var(--accent-fg)' }} />}
                    </span>
                  </button>
                ))}
              </div>
              <div className="mt-4 space-y-3 border-t border-line pt-4">
                <label className="flex items-center justify-between">
                  <span className="text-[0.8125rem] text-dim">Verify erasure after execution</span>
                  <Switch checked={verifyAfter} onChange={setVerifyAfter} />
                </label>
                <label className="flex items-center justify-between">
                  <span className="text-[0.8125rem] text-dim">Run recovery test</span>
                  <Switch checked={recoveryTest} onChange={setRecoveryTest} />
                </label>
              </div>
            </StepBody>
          )}

          {stage === 3 && (
            <StepBody title="Review before execution" description="This is the last reversible step. Review the exact scope and limitations.">
              <div className="grid grid-cols-2 gap-x-6">
                <Meta label="Target">{demo.profile.name}</Meta>
                <Meta label="Volume" mono>{demo.profile.volume}</Meta>
                <Meta label="Mode">{modeLabel[mode]}</Meta>
                <Meta label="Scope" mono>1 file · {formatBytes(demo.profile.sizeBytes)}</Meta>
              </div>
              <div className="mt-3 space-y-1.5">
                {demo.profile.warnings.map((w) => (
                  <WarnRow key={w}>{w}</WarnRow>
                ))}
                <WarnRow>Assurance is limited to the tested scope and supported recovery techniques. OBLIVION does not claim data is impossible to recover.</WarnRow>
              </div>
              <div className="mt-4 flex justify-end">
                <Button variant="danger" size="sm" onClick={() => setConfirmOpen(true)}>
                  Erase target
                </Button>
              </div>
            </StepBody>
          )}

          {stage >= 4 && stage <= 8 && (
            <StepBody title="Executing" description="OBLIVION is working through the secure lifecycle. You can watch progress below.">
              <div className="mb-3 flex items-center justify-between text-[0.8125rem]">
                <span className="text-dim">{EXEC_STAGES.find((e) => e.i === stage)?.label}</span>
                <span className="tabular text-fg">{progress}%</span>
              </div>
              <Progress value={progress} />
              <div className="mt-4 max-h-52 overflow-y-auto rounded-md border border-line bg-inset p-3 font-mono text-[0.6875rem] text-dim">
                {log.map((line, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-mute">→</span>
                    <span>{line}</span>
                  </div>
                ))}
              </div>
            </StepBody>
          )}

          {stage === 9 && done && (
            <StepBody title="Evidence generated" description="The operation completed and produced a signed certificate.">
              <div
                className="flex items-center gap-3 rounded-lg border p-4"
                style={{ borderColor: 'color-mix(in oklab, var(--success) 35%, transparent)', backgroundColor: 'var(--success-soft)' }}
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: 'color-mix(in oklab, var(--success) 20%, transparent)' }}>
                  <ShieldCheck className="h-5 w-5" style={{ color: 'var(--success)' }} />
                </div>
                <div>
                  <p className="text-[0.8125rem] font-medium text-fg">Assurance: Validated within tested scope</p>
                  <p className="text-[0.75rem] text-dim">Target verified · not recoverable via supported techniques · residuals low-risk</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {['Target verification', 'Recovery test', 'Residual scan', 'Evidence chain', 'Certificate'].map((c) => (
                  <div key={c} className="flex items-center gap-2 rounded-md border border-line bg-inset px-3 py-2">
                    <Check className="h-3.5 w-3.5" style={{ color: 'var(--success)' }} />
                    <span className="text-[0.8125rem] text-dim">{c}</span>
                  </div>
                ))}
              </div>
              <div className="mt-5 flex gap-2">
                <Button variant="primary" size="sm" onClick={() => navigate('certificates')}>
                  <FileCheck className="h-3.5 w-3.5" /> View certificate
                </Button>
                <Button variant="outline" size="sm" onClick={() => navigate('operations')}>
                  Back to operations
                </Button>
              </div>
            </StepBody>
          )}

          {/* Nav */}
          {stage <= 2 && (
            <div className="mt-6 flex justify-between border-t border-line pt-4">
              <Button variant="ghost" size="sm" disabled={stage === 0} onClick={() => setStage((s) => Math.max(0, s - 1))}>
                <ArrowLeft className="h-3.5 w-3.5" /> Back
              </Button>
              <Button variant="primary" size="sm" onClick={() => setStage((s) => s + 1)}>
                {stage === 0 ? 'Analyze' : 'Continue'} <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>
      </div>

      {confirmOpen && (
        <ConfirmDialog
          sentence={scopeSentence}
          onCancel={() => setConfirmOpen(false)}
          onConfirm={beginExecution}
        />
      )}
    </Page>
  )
}

function StepBody({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <div className="animate-fade-up">
      <h2 className="text-sm font-semibold text-fg">{title}</h2>
      <p className="mt-1 mb-4 text-[0.8125rem] text-dim">{description}</p>
      {children}
    </div>
  )
}

function WarnRow({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="flex items-start gap-2 rounded-md border px-2.5 py-2 text-[0.75rem]"
      style={{ borderColor: 'color-mix(in oklab, var(--warning) 35%, transparent)', backgroundColor: 'var(--warning-soft)' }}
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" style={{ color: 'var(--warning)' }} />
      <span className="text-dim">{children}</span>
    </div>
  )
}

function ConfirmDialog({ sentence, onCancel, onConfirm }: { sentence: string; onCancel: () => void; onConfirm: () => void }) {
  const [ack, setAck] = useState(false)
  const [typed, setTyped] = useState('')
  const ready = ack && typed.trim().toUpperCase() === 'ERASE'
  return (
    <div className="fixed inset-0 z-100 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" onClick={onCancel} />
      <div className="animate-scale-in relative w-full max-w-md rounded-xl border bg-surface p-5 shadow-2xl" style={{ borderColor: 'color-mix(in oklab, var(--danger) 40%, transparent)' }}>
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-full" style={{ backgroundColor: 'var(--danger-soft)' }}>
            <Lock className="h-4 w-4" style={{ color: 'var(--danger)' }} />
          </div>
          <h2 className="text-sm font-semibold text-fg">Confirm permanent erasure</h2>
        </div>
        <p className="mt-3 rounded-md border px-3 py-2.5 text-[0.8125rem] text-fg" style={{ borderColor: 'color-mix(in oklab, var(--danger) 30%, transparent)', backgroundColor: 'var(--danger-soft)' }}>
          {sentence}
        </p>
        <p className="mt-3 text-[0.75rem] text-mute">
          This action is bound to the exact scope above. If the target changes, this confirmation is invalidated.
        </p>
        <label className="mt-3 flex items-start gap-2.5">
          <input
            type="checkbox"
            checked={ack}
            onChange={(e) => setAck(e.target.checked)}
            className="mt-0.5 h-4 w-4 accent-[var(--danger)]"
          />
          <span className="text-[0.8125rem] text-dim">I understand this cannot be undone and is limited to the tested scope.</span>
        </label>
        <div className="mt-3">
          <label className="text-[0.75rem] text-mute">Type <span className="font-mono text-fg">ERASE</span> to confirm</label>
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            className="mt-1 h-9 w-full rounded-md border border-line bg-inset px-2.5 font-mono text-sm text-fg outline-none focus:border-line-strong"
            placeholder="ERASE"
          />
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
          <Button variant="danger" size="sm" disabled={!ready} onClick={onConfirm}>
            Permanently erase
          </Button>
        </div>
      </div>
    </div>
  )
}
