import { useState } from 'react'
import { ScrollText, ShieldCheck } from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { Input } from '@/components/ui/Input'
import { Select } from '@/components/ui/Select'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { DataTable, type ColumnDef } from '@/components/ui/DataTable'
import { EvidenceId } from '@/features/evidence/components/EvidenceId'
import { InspectorDrawer } from '@/components/shell/InspectorDrawer'
import { EmptyState, ErrorState, LoadingState, UnavailableState } from '@/components/states'
import { isAvailable, unavailableReason } from '@/lib/api/capabilities'
import {
  toScreenState,
  useAuditEventsQuery,
  type AuditEventOut,
  type AuditLinkOut,
} from '@/lib/api/queries'
import { useVerifyAuditChainMutation } from '@/lib/api/mutations'
import { formatIso } from '@/lib/format'

/**
 * The recorded audit trail, read from `GET /api/audit/events`.
 *
 * Two distinctions are load-bearing on this screen and are never collapsed:
 *
 * **Who acted.** `actor_source` separates an identity proven by a server-side session lookup from
 * one the application asserted about itself, from one that was merely *claimed* by an
 * unauthenticated caller. A failed sign-in records the username that was typed; rendering that the
 * same way as a verified principal would turn an attacker's input into an accusation against a
 * real person.
 *
 * **What verification proves.** An intact audit chain means the log has not been altered. It is not
 * a statement about erasure, evidence integrity or certificate trust, and the server returns those
 * limits in `does_not_prove` - which this screen renders rather than summarising away.
 */

/** Per-record chain link state -> how alarmed the operator should be. */
const LINK_VARIANT: Record<string, 'success' | 'warning' | 'danger' | 'neutral'> = {
  VALID_GENESIS: 'success',
  VALID_PREDECESSOR: 'success',
  MISSING_PREDECESSOR: 'warning',
  BROKEN_PREDECESSOR: 'danger',
  MUTATED_EVENT: 'danger',
}

const CHAIN_VARIANT: Record<string, 'success' | 'warning' | 'danger'> = {
  INTACT: 'success',
  UNVERIFIABLE: 'warning',
  BROKEN: 'danger',
}

const OUTCOME_VARIANT: Record<string, 'success' | 'warning' | 'danger'> = {
  SUCCEEDED: 'success',
  REFUSED: 'warning',
  FAILED: 'danger',
}

/**
 * How an actor is labelled. The wording is deliberate: only AUTHENTICATED_SESSION names a person.
 */
const ACTOR_SOURCE: Record<string, { label: string; variant: 'success' | 'neutral' | 'warning' }> = {
  AUTHENTICATED_SESSION: { label: 'Authenticated', variant: 'success' },
  SYSTEM: { label: 'System', variant: 'neutral' },
  UNAUTHENTICATED: { label: 'Claimed — not authenticated', variant: 'warning' },
}

export function Audit() {
  const [searchQuery, setSearchQuery] = useState('')
  const [outcomeFilter, setOutcomeFilter] = useState('ALL')
  const [selectedEntry, setSelectedEntry] = useState<AuditEventOut | null>(null)

  const auditAvailable = isAvailable('audit.events')
  const eventsQuery = useAuditEventsQuery({
    limit: 200,
    ...(outcomeFilter === 'ALL' ? {} : { outcome: outcomeFilter }),
  })
  const screen = toScreenState('audit.events', eventsQuery, (page) => page.events.length === 0)

  const verify = useVerifyAuditChainMutation()
  const verification = verify.data

  const page = eventsQuery.data
  const allEvents = page?.events ?? []

  // Client-side text search only narrows what is already on screen. It never changes what the
  // server was asked for, so a filtered-to-empty view cannot be mistaken for an empty log.
  const needle = searchQuery.trim().toLowerCase()
  const rows = needle
    ? allEvents.filter((event) =>
        [
          event.actor_id,
          event.actor_role,
          event.event_type,
          event.summary,
          event.target_identity ?? '',
          event.operation_id ?? '',
        ]
          .join(' ')
          .toLowerCase()
          .includes(needle),
      )
    : allEvents

  const columns: ColumnDef<AuditEventOut>[] = [
    {
      key: 'sequence',
      header: '#',
      width: '60px',
      cell: (l) => <span className="font-mono text-[0.6875rem] text-dim">{l.sequence}</span>,
    },
    {
      key: 'occurred_at',
      header: 'Timestamp (UTC)',
      width: '160px',
      cell: (l) => (
        <span className="font-mono text-[0.6875rem] text-dim">{formatIso(l.occurred_at)}</span>
      ),
    },
    {
      key: 'actor_id',
      header: 'Actor / Role',
      width: '180px',
      cell: (l) => {
        const source = ACTOR_SOURCE[l.actor_source] ?? {
          label: l.actor_source,
          variant: 'warning' as const,
        }
        return (
          <div className="truncate">
            <div className="font-semibold text-xs text-fg truncate">{l.actor_id}</div>
            <div className="flex items-center gap-1">
              <span className="text-[0.625rem] text-dim font-mono">{l.actor_role}</span>
              <Badge variant={source.variant} size="xs">
                {source.label}
              </Badge>
            </div>
          </div>
        )
      },
    },
    {
      key: 'event_type',
      header: 'Recorded Event',
      width: '220px',
      cell: (l) => (
        <div className="truncate">
          <span className="font-mono text-xs font-semibold text-fg block truncate">
            {l.event_type}
          </span>
          <span className="text-[0.625rem] text-mute block truncate">
            {l.summary || l.target_identity || '—'}
          </span>
        </div>
      ),
    },
    {
      key: 'operation_id',
      header: 'Operation ID',
      width: '140px',
      cell: (l) => <EvidenceId value={l.operation_id ?? undefined} label="Operation ID" size="sm" />,
    },
    {
      key: 'outcome',
      header: 'Outcome',
      width: '110px',
      cell: (l) => <Badge variant={OUTCOME_VARIANT[l.outcome] ?? 'neutral'}>{l.outcome}</Badge>,
    },
    {
      key: 'digest',
      header: 'Record Digest',
      width: '140px',
      cell: (l) => <EvidenceId value={l.digest} label="Record digest" size="sm" />,
    },
  ]

  return (
    <div className="flex flex-col min-h-full">
      <PageHeader
        title="Recorded Forensic Audit Events"
        icon={<ScrollText className="h-4 w-4" />}
        description="Append-only record of authorizations, destructive dispatches and verification activity, chained so that an alteration is detectable."
      />

      <div className="flex-1 p-6 space-y-4 max-w-7xl">
        {/* Chain verification. Rendered above the table because the integrity of the
            log governs how much the rows below are worth. */}
        {isAvailable('audit.verify') && (
          <div className="rounded-md border border-line bg-surface p-4 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-dim" aria-hidden="true" />
                  <span className="text-xs font-semibold text-fg">Audit chain verification</span>
                  {verification && (
                    <Badge variant={CHAIN_VARIANT[verification.status] ?? 'neutral'}>
                      {verification.status}
                    </Badge>
                  )}
                </div>
                <p className="text-[0.6875rem] text-dim max-w-2xl">
                  {verification
                    ? verification.reason
                    : 'The server re-hashes every stored record and reports whether the log has been altered. This console performs no verification of its own.'}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={() => verify.mutate()}
                disabled={verify.isPending}
              >
                {verify.isPending ? 'Verifying…' : 'Verify chain'}
              </Button>
            </div>

            {verify.isError && (
              <ErrorState
                compact
                error={verify.error}
                title="Chain verification could not be completed"
              />
            )}

            {verification && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[0.6875rem]">
                  <div>
                    <span className="text-dim block">Records checked</span>
                    <span className="text-fg">{verification.checked}</span>
                  </div>
                  <div>
                    <span className="text-dim block">Predating the chain</span>
                    <span className="text-fg">{verification.records_predating_chain}</span>
                  </div>
                  <div>
                    <span className="text-dim block">First affected</span>
                    <span className="text-fg">{verification.first_invalid_audit_id ?? '—'}</span>
                  </div>
                  <div>
                    <span className="text-dim block">Log height</span>
                    <span className="text-fg">{page?.total_records ?? '—'}</span>
                  </div>
                </div>

                {verification.links.length > 0 && <LinkSummary links={verification.links} />}

                {/* The limits travel with the verdict. Rendering INTACT without them would
                    let an operator read "the log is fine" as "the erasure was sound". */}
                <div className="rounded-sm border border-line bg-inset p-3 space-y-2">
                  <span className="text-[0.625rem] uppercase font-medium text-dim block">
                    What this result does not establish
                  </span>
                  <ul className="space-y-1">
                    {verification.does_not_prove.map((claim) => (
                      <li key={claim} className="text-[0.6875rem] text-mute flex gap-2">
                        <span aria-hidden="true">·</span>
                        <span>{claim}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-[0.625rem] text-dim pt-1 border-t border-line">
                    {verification.scope_note}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Search & Filter Bar */}
        <div className="rounded-md border border-line bg-surface p-3 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 w-full sm:w-auto flex-1 max-w-md">
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by actor, event, target, or operation ID..."
              className="font-mono text-xs"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Select<string>
              label="Filter outcomes"
              hideLabel
              value={outcomeFilter}
              onChange={(val) => setOutcomeFilter(val)}
              options={[
                { value: 'ALL', label: 'All outcomes' },
                { value: 'SUCCEEDED', label: 'Succeeded' },
                { value: 'REFUSED', label: 'Refused' },
                { value: 'FAILED', label: 'Failed' },
              ]}
              size="sm"
            />
          </div>
        </div>

        {/* Table Content */}
        {!auditAvailable ? (
          <UnavailableState
            title="Audit stream not published by this backend"
            reason={unavailableReason('audit.events') ?? undefined}
          />
        ) : screen.state === 'LOADING' ? (
          <LoadingState title="Reading the audit log" />
        ) : screen.state === 'BLOCKED' ? (
          <UnavailableState
            title="Your role cannot read the audit log"
            reason={
              screen.reason ??
              'Reading the audit log requires audit.view, which is granted to ADMIN and AUDITOR only.'
            }
          />
        ) : screen.state === 'FAILED' ? (
          <ErrorState
            error={eventsQuery.error}
            title="The audit log could not be read"
            onRetry={() => void eventsQuery.refetch()}
            retrying={eventsQuery.isFetching}
          />
        ) : (
          <>
            <DataTable<AuditEventOut>
              columns={columns}
              rows={rows}
              rowKey={(l) => l.audit_id}
              caption="Audit Records"
              emptyContent={
                <EmptyState
                  title={needle ? 'No records match this search' : 'No audit records yet'}
                  description={
                    needle
                      ? `${allEvents.length} record(s) were returned; none match "${searchQuery}".`
                      : 'No acts have been recorded against this deployment.'
                  }
                />
              }
              onRowSelect={(entry) => setSelectedEntry(entry)}
            />
            {page && (
              <p className="text-[0.625rem] text-dim font-mono">
                Showing {rows.length} of {page.returned} returned · {page.total_records} record(s) in
                the chained log
                {page.records_predating_chain > 0 &&
                  ` · ${page.records_predating_chain} record(s) predate the chain and are not shown`}
              </p>
            )}
          </>
        )}
      </div>

      {/* Audit Event Detail Inspector */}
      <InspectorDrawer
        open={Boolean(selectedEntry)}
        onClose={() => setSelectedEntry(null)}
        title={`Audit Record: ${selectedEntry?.audit_id ?? ''}`}
        subtitle={selectedEntry ? `Sequence ${selectedEntry.sequence}` : undefined}
      >
        {selectedEntry && <AuditRecordDetail entry={selectedEntry} />}
      </InspectorDrawer>
    </div>
  )
}

/**
 * Render one metadata value.
 *
 * The backend canonicalizer only admits JSON primitives, so the object branch should be
 * unreachable - but it is handled explicitly rather than left to default stringification, which
 * would print `[object Object]` and quietly hide whatever the record actually said.
 */
function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

/** Counts per link state, so a single bad record in a long chain is not lost in the list. */
function LinkSummary({ links }: { links: AuditLinkOut[] }) {
  const counts = new Map<string, number>()
  for (const link of links) counts.set(link.status, (counts.get(link.status) ?? 0) + 1)

  const concerning = links.filter(
    (link) => link.status !== 'VALID_GENESIS' && link.status !== 'VALID_PREDECESSOR',
  )

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {[...counts.entries()].map(([status, count]) => (
          <Badge key={status} variant={LINK_VARIANT[status] ?? 'neutral'} size="xs">
            {status} · {count}
          </Badge>
        ))}
      </div>
      {concerning.length > 0 && (
        <ul className="space-y-1">
          {concerning.slice(0, 10).map((link) => (
            <li key={link.audit_id} className="text-[0.6875rem] text-danger">
              <span className="font-mono">#{link.sequence}</span> {link.detail}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AuditRecordDetail({ entry }: { entry: AuditEventOut }) {
  const source = ACTOR_SOURCE[entry.actor_source] ?? {
    label: entry.actor_source,
    variant: 'warning' as const,
  }
  const metadata = Object.entries(entry.safe_metadata ?? {})

  return (
    <div className="space-y-4 text-xs">
      <div className="rounded-md border border-line bg-elevated/40 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-dim uppercase text-[0.6875rem] font-medium">Outcome</span>
          <Badge variant={OUTCOME_VARIANT[entry.outcome] ?? 'neutral'}>{entry.outcome}</Badge>
        </div>

        <div className="grid grid-cols-2 gap-2 font-mono text-[0.6875rem]">
          <div>
            <span className="text-dim block">Actor / Role:</span>
            <span className="text-fg font-semibold">
              {entry.actor_id} ({entry.actor_role})
            </span>
          </div>
          <div>
            <span className="text-dim block">Identity provenance:</span>
            <Badge variant={source.variant} size="xs">
              {source.label}
            </Badge>
          </div>
          <div>
            <span className="text-dim block">Occurred at:</span>
            <span className="text-fg">{formatIso(entry.occurred_at)}</span>
          </div>
          <div>
            <span className="text-dim block">Sequence:</span>
            <span className="text-fg">{entry.sequence}</span>
          </div>
        </div>

        {entry.actor_source === 'UNAUTHENTICATED' && (
          <p className="text-[0.6875rem] text-warning border-t border-line pt-2">
            This identifier was supplied by an unauthenticated caller and was never verified. It
            records what was claimed, not who acted.
          </p>
        )}
      </div>

      <div className="space-y-1">
        <span className="text-dim text-[0.6875rem] block uppercase font-medium">Recorded act</span>
        <div className="rounded-sm border border-line bg-inset p-3 font-mono text-fg text-xs space-y-1">
          <div>{entry.event_type}</div>
          {entry.summary && <div className="text-dim text-[0.6875rem]">{entry.summary}</div>}
          {entry.target_identity && (
            <div className="text-mute text-[0.6875rem] break-all">{entry.target_identity}</div>
          )}
        </div>
      </div>

      {metadata.length > 0 && (
        <div className="space-y-1">
          <span className="text-dim text-[0.6875rem] block uppercase font-medium">
            Recorded details
          </span>
          <div className="rounded-sm border border-line bg-inset p-3 font-mono text-[0.6875rem] space-y-1">
            {metadata.map(([key, value]) => (
              <div key={key} className="flex gap-2">
                <span className="text-dim shrink-0">{key}:</span>
                <span className="text-fg break-all">{formatMetadataValue(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-1">
        <span className="text-dim text-[0.6875rem] block uppercase font-medium">
          Correlated artefacts
        </span>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <span className="text-dim text-[0.625rem] block">Operation ID:</span>
            <EvidenceId value={entry.operation_id ?? undefined} label="Operation ID" />
          </div>
          <div>
            <span className="text-dim text-[0.625rem] block">Evidence ID:</span>
            <EvidenceId value={entry.evidence_id ?? undefined} label="Evidence ID" />
          </div>
          <div>
            <span className="text-dim text-[0.625rem] block">Certificate ID:</span>
            <EvidenceId value={entry.certificate_id ?? undefined} label="Certificate ID" />
          </div>
        </div>
      </div>

      {/* The chain fields, so an operator can re-link the record independently rather
          than taking the server's verdict on trust. */}
      <div className="space-y-1">
        <span className="text-dim text-[0.6875rem] block uppercase font-medium">Chain linkage</span>
        <div className="grid grid-cols-1 gap-2">
          <div>
            <span className="text-dim text-[0.625rem] block">This record&apos;s digest:</span>
            <EvidenceId value={entry.digest} label="Record digest" />
          </div>
          <div>
            <span className="text-dim text-[0.625rem] block">Predecessor:</span>
            <EvidenceId value={entry.previous_audit_id ?? undefined} label="Predecessor ID" />
          </div>
          <div>
            <span className="text-dim text-[0.625rem] block">
              Predecessor digest recorded here:
            </span>
            <EvidenceId
              value={entry.previous_audit_digest ?? undefined}
              label="Predecessor digest"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
