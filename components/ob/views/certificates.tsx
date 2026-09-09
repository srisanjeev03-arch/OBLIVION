'use client'

import { useState } from 'react'
import { FileCheck, ShieldCheck, ShieldX, Stamp, RefreshCw } from 'lucide-react'
import { Page, PageHeader } from '../page'
import { Button, StatusPill, Meta, Hash, Switch } from '../primitives'
import { OblivionMark } from '../mark'
import { useShell } from '../shell-context'
import { cn } from '@/lib/utils'
import { certificates } from '@/lib/mock-data'
import { assuranceLabel, modeLabel, formatTime } from '@/lib/labels'

export function CertificatesView() {
  const { params, toast } = useShell()
  const [selectedId, setSelectedId] = useState(
    params.certificateId ?? certificates[0]?.id,
  )
  // Local demo control: tampering with the evidence flips verification to INVALID.
  const [tampered, setTampered] = useState<Record<string, boolean>>({})
  const [verified, setVerified] = useState<Record<string, 'VALID' | 'INVALID' | 'UNVERIFIED'>>({})

  const selected = certificates.find((c) => c.id === selectedId) ?? certificates[0]
  const isTampered = !!tampered[selected.id]
  const state = verified[selected.id] ?? (isTampered ? 'UNVERIFIED' : selected.verification)

  const verify = () => {
    const result = isTampered ? 'INVALID' : 'VALID'
    setVerified((v) => ({ ...v, [selected.id]: result }))
    toast({
      title: result === 'VALID' ? 'Certificate verified' : 'Verification failed',
      description: result === 'VALID' ? 'Evidence hash and signature match.' : 'Evidence hash mismatch.',
      tone: result === 'VALID' ? 'success' : 'danger',
    })
  }

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Certificates"
        description="Signed evidence documents. Validity is derived from the evidence hash and signature — never inferred from whether an operation completed."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,300px)_1fr]">
        <ul className="space-y-2">
          {certificates.map((c) => {
            const isSel = selected.id === c.id
            const cs = verified[c.id] ?? (tampered[c.id] ? 'UNVERIFIED' : c.verification)
            return (
              <li key={c.id}>
                <button
                  onClick={() => setSelectedId(c.id)}
                  className={cn(
                    'w-full rounded-lg border p-3 text-left transition-colors',
                    isSel ? 'border-line-strong bg-surface' : 'border-line bg-surface/50 hover:bg-surface',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[0.75rem] text-fg">{c.id}</span>
                    <StatusPill tone={cs === 'VALID' ? 'success' : cs === 'INVALID' ? 'danger' : 'neutral'} dot={false}>
                      {cs}
                    </StatusPill>
                  </div>
                  <p className="mt-1 truncate text-[0.75rem] text-mute">{c.target}</p>
                </button>
              </li>
            )
          })}
        </ul>

        {/* Certificate document */}
        <div>
          <div
            className={cn('overflow-hidden rounded-xl border bg-surface')}
            style={{
              borderColor:
                state === 'INVALID'
                  ? 'color-mix(in oklab, var(--danger) 45%, transparent)'
                  : state === 'VALID'
                    ? 'color-mix(in oklab, var(--success) 40%, transparent)'
                    : 'var(--line-strong)',
            }}
          >
            {/* header band */}
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div className="flex items-center gap-2.5">
                <OblivionMark className="h-6 w-6" />
                <div className="leading-tight">
                  <p className="text-[0.8125rem] font-semibold text-fg">Certificate of Erasure</p>
                  <p className="font-mono text-[0.625rem] text-mute">{selected.id}</p>
                </div>
              </div>
              {state === 'VALID' && <StatusPill tone="success"><ShieldCheck className="h-3 w-3" /> VALID</StatusPill>}
              {state === 'INVALID' && <StatusPill tone="danger"><ShieldX className="h-3 w-3" /> INVALID</StatusPill>}
              {state === 'UNVERIFIED' && <StatusPill tone="neutral">UNVERIFIED</StatusPill>}
            </div>

            <div className="grid grid-cols-1 gap-x-8 p-5 sm:grid-cols-2">
              <Meta label="Operation" mono>{selected.operationId}</Meta>
              <Meta label="Target">{selected.target}</Meta>
              <Meta label="Mode">{modeLabel[selected.mode]}</Meta>
              <Meta label="Assurance">{assuranceLabel[selected.assurance].text}</Meta>
              <Meta label="Signature">{selected.signatureState}</Meta>
              <Meta label="Issued">{formatTime(selected.issuedAt)}</Meta>
            </div>

            <div className="border-t border-line px-5 py-4">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-mute">Evidence hash (SHA-256)</span>
                <Hash value={isTampered ? 'de1e7ed0000tampered0000de1e7ed0000tampered0000de1e7ed0000tamper' : selected.evidenceHash} />
              </div>
            </div>

            {state === 'INVALID' && (
              <div className="mx-5 mb-5 rounded-md border px-3 py-2.5 text-[0.8125rem]" style={{ borderColor: 'color-mix(in oklab, var(--danger) 40%, transparent)', backgroundColor: 'var(--danger-soft)' }}>
                <p className="font-medium" style={{ color: 'var(--danger)' }}>Evidence hash mismatch.</p>
                <p className="mt-0.5 text-dim">The recomputed evidence hash does not match the value signed at issue time. This certificate cannot be trusted.</p>
              </div>
            )}

            <div className="flex items-center justify-between border-t border-line px-5 py-3">
              <span className="flex items-center gap-2 text-[0.6875rem] text-mute">
                <Stamp className="h-3.5 w-3.5" /> Signed by OBLIVION Evidence Service
              </span>
              <Button variant={state === 'UNVERIFIED' ? 'primary' : 'outline'} size="sm" onClick={verify}>
                <RefreshCw className="h-3.5 w-3.5" /> Verify certificate
              </Button>
            </div>
          </div>

          {/* Demo control */}
          <div className="mt-3 flex items-center justify-between rounded-lg border border-dashed border-line-strong px-3.5 py-2.5">
            <div>
              <p className="text-[0.8125rem] text-fg">Simulate evidence tampering</p>
              <p className="text-[0.6875rem] text-mute">Modify the sealed evidence, then re-verify to see the certificate invalidate.</p>
            </div>
            <Switch
              checked={isTampered}
              onChange={(v) => {
                setTampered((t) => ({ ...t, [selected.id]: v }))
                setVerified((vf) => ({ ...vf, [selected.id]: 'UNVERIFIED' }))
              }}
              label="Simulate tampering"
            />
          </div>
        </div>
      </div>
    </Page>
  )
}
