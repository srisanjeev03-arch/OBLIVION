'use client'

import { useState } from 'react'
import { Archive, Lock, Check, X, ShieldAlert, KeyRound } from 'lucide-react'
import { Page, PageHeader } from '../page'
import { Button, StatusPill, Meta, Hash, EmptyState } from '../primitives'
import { useShell } from '../shell-context'
import { cn } from '@/lib/utils'
import { recoveryObjects } from '@/lib/mock-data'
import { formatTime, relativeTime } from '@/lib/labels'
import type { RecoveryObject } from '@/lib/types'

const STATUS_TONE = {
  SEALED: 'neutral',
  AUTHORIZED: 'info',
  DENIED: 'danger',
  RESTORED: 'success',
  EXPIRED: 'warning',
} as const

export function RecoveryView() {
  const { toast } = useShell()
  const [objects, setObjects] = useState<RecoveryObject[]>(recoveryObjects)
  const [selectedId, setSelectedId] = useState(recoveryObjects[0]?.id)
  const selected = objects.find((o) => o.id === selectedId) ?? objects[0]

  // The frontend only presents backend authorization results — it does not
  // decide them. Requesting a restore reflects the object's server-side state.
  const requestRestore = (obj: RecoveryObject) => {
    if (obj.status === 'DENIED' || obj.status === 'SEALED') {
      toast({
        title: 'Restore denied',
        description: 'Backend authorization did not approve this recovery object.',
        tone: 'danger',
      })
      return
    }
    if (obj.status === 'AUTHORIZED') {
      setObjects((prev) =>
        prev.map((o) =>
          o.id === obj.id ? { ...o, status: 'RESTORED', restoreResult: 'HASH_MATCH' } : o,
        ),
      )
      toast({
        title: 'Restore complete',
        description: 'Restored object hash matches the original.',
        tone: 'success',
      })
    }
  }

  return (
    <Page className="max-w-none">
      <PageHeader
        title="Recovery Vault"
        description="Sealed recovery objects and their authorization state. Restoration is only ever permitted by the backend — OBLIVION presents the result, it never grants access itself."
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="grid grid-cols-[1fr_auto] gap-2 border-b border-line px-3.5 py-2 text-[0.6875rem] font-medium text-mute">
            <span>Object</span>
            <span>Status</span>
          </div>
          <ul>
            {objects.map((o) => (
              <li key={o.id}>
                <button
                  onClick={() => setSelectedId(o.id)}
                  className={cn(
                    'grid w-full grid-cols-[1fr_auto] items-center gap-2 border-b border-line px-3.5 py-2.5 text-left transition-colors last:border-0',
                    selected?.id === o.id ? 'bg-inset' : 'hover:bg-inset/50',
                  )}
                >
                  <span className="min-w-0">
                    <span className="block truncate font-mono text-[0.75rem] text-fg">{o.label}</span>
                    <span className="block font-mono text-[0.625rem] text-mute">{o.id}</span>
                  </span>
                  <StatusPill tone={STATUS_TONE[o.status]}>{o.status}</StatusPill>
                </button>
              </li>
            ))}
          </ul>
        </div>

        {selected && (
          <div className="rounded-lg border border-line bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-md border border-line bg-inset">
                  <Archive className="h-4 w-4 text-dim" />
                </div>
                <div>
                  <h2 className="font-mono text-[0.8125rem] text-fg">{selected.label}</h2>
                  <p className="font-mono text-[0.6875rem] text-mute">{selected.id}</p>
                </div>
              </div>
              <StatusPill tone={STATUS_TONE[selected.status]}>{selected.status}</StatusPill>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-x-6">
              <Meta label="Operation" mono>{selected.operationId}</Meta>
              <Meta label="Created">{formatTime(selected.createdAt)}</Meta>
              <Meta label="Expires">{relativeTime(selected.expiresAt).replace('ago', 'from now')}</Meta>
              <Meta label="Restore result" mono>{selected.restoreResult ?? '—'}</Meta>
            </div>

            <div className="mt-3 flex items-center gap-2 border-t border-line pt-3">
              <span className="text-xs text-mute">Original hash</span>
              <Hash value={selected.originalHash} />
            </div>

            {/* Authorization state */}
            <div className="mt-4">
              {selected.status === 'DENIED' && (
                <ResultBanner tone="danger" icon={X} title="Recovery denied" body="The backend did not authorize restoration of this object. No data was returned to the client." />
              )}
              {selected.status === 'SEALED' && (
                <ResultBanner tone="neutral" icon={Lock} title="Sealed — awaiting authorization" body="This object is sealed. Restoration requires backend authorization that has not been granted." />
              )}
              {selected.status === 'AUTHORIZED' && (
                <ResultBanner tone="info" icon={KeyRound} title="Recovery approved" body="Backend authorization is granted. You may perform a restore; the restored object will be hash-verified." />
              )}
              {selected.status === 'RESTORED' && (
                <ResultBanner tone="success" icon={Check} title="Restored · hash match" body="The restored object was verified against its original hash and matches exactly." />
              )}
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant={selected.status === 'AUTHORIZED' ? 'primary' : 'outline'}
                size="sm"
                disabled={selected.status === 'RESTORED'}
                onClick={() => requestRestore(selected)}
              >
                {selected.status === 'AUTHORIZED' ? 'Restore object' : 'Request restore'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Page>
  )
}

function ResultBanner({
  tone,
  icon: Icon,
  title,
  body,
}: {
  tone: 'success' | 'danger' | 'info' | 'neutral'
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  title: string
  body: string
}) {
  const color =
    tone === 'success' ? 'var(--success)' : tone === 'danger' ? 'var(--danger)' : tone === 'info' ? 'var(--info)' : 'var(--mute)'
  return (
    <div
      className="flex items-start gap-3 rounded-lg border p-3.5"
      style={{
        borderColor: tone === 'neutral' ? 'var(--line-strong)' : `color-mix(in oklab, ${color} 35%, transparent)`,
        backgroundColor: tone === 'neutral' ? 'var(--inset)' : `color-mix(in oklab, ${color} 10%, transparent)`,
      }}
    >
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full" style={{ backgroundColor: `color-mix(in oklab, ${color} 18%, transparent)` }}>
        <Icon className="h-4 w-4" style={{ color }} />
      </div>
      <div>
        <p className="text-[0.8125rem] font-medium text-fg">{title}</p>
        <p className="mt-0.5 text-[0.75rem] text-dim">{body}</p>
      </div>
    </div>
  )
}
