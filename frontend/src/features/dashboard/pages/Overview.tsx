import { Link } from 'react-router'
import {
  ArrowRight,
  CircleSlash,
  Crosshair,
  FileCheck2,
  RotateCcw,
  ScanSearch,
  ShieldCheck,
} from 'lucide-react'
import { formatTimestamp } from '@/lib/format'
import { useConnection } from '@/lib/api/connection'
import { useAuth } from '@/lib/auth/context'
import { PageHeader } from '@/components/shell/PageHeader'
import { Panel, PanelHeader, Meta, MetaList } from '@/components/ui/Panel'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/status/StatusBadge'
import { ROLE_METADATA } from '@/lib/auth/types'
import { unavailableReason } from '@/lib/api/capabilities'

/**
 * The operator's landing view.
 *
 * This screen used to carry an "Assurance Snapshot" whose three counts all read 0, an "Attention
 * Required" panel asserting "All recorded states are nominal. No unhandled security warnings or
 * inconclusive results", and an "Active Operation" panel stating the engine was idle. None of it was
 * observed. The contract publishes no operation collection route, so the console cannot know how
 * many operations exist, whether any need attention, or that anything is idle — and a dashboard that
 * asserts "all nominal" without asking is the most dangerous kind of fake, because it reads as a
 * clean bill of health.
 *
 * Every value here is either derived from a real response (connection state changes only when a
 * request succeeds or fails; the principal comes from `/api/auth/me`) or is labelled as something
 * the backend has not published an endpoint for.
 */

/** The objective-driven entry points, each mapped to a route that actually exists. */
const OBJECTIVES = [
  {
    to: '/targets',
    label: 'Permanently remove data',
    detail:
      'Analyze a target, then request an erasure operation under a backend-allowlisted policy.',
    Icon: Crosshair,
  },
  {
    to: '/recovery',
    label: 'Remove data with controlled recovery',
    detail: 'CONTROLLED_RECOVERABLE keeps an encrypted vault object until an authorized restore.',
    Icon: RotateCcw,
  },
  {
    to: '/residuals',
    label: 'Test whether deleted data remains observable',
    detail: 'Residual analysis runs in the backend; findings have no read endpoint yet.',
    Icon: ScanSearch,
  },
  {
    to: '/operations',
    label: 'Verify a previous operation',
    detail: 'Open an operation by ID to read its state and evidence event chain.',
    Icon: ShieldCheck,
  },
  {
    to: '/certificates',
    label: 'Review evidence and assurance',
    detail: 'Retrieve a certificate and run backend verification across ten dimensions.',
    Icon: FileCheck2,
  },
] as const

/** Stage names taken from the backend state machine, not invented. */
const LIFECYCLE = [
  {
    title: '1. REQUEST',
    detail:
      'An operation is created in PENDING_APPROVAL. Creation never destroys anything by itself.',
  },
  {
    title: '2. APPROVE',
    detail:
      'A different principal must approve it. Separation of duties is enforced server-side, not by this console.',
  },
  {
    title: '3. ERASE',
    detail:
      'ERASING, then VERIFYING, RECOVERY_TEST, RESIDUAL_SCAN, ASSESSING and CERTIFYING. Each stage reports its own outcome.',
  },
  {
    title: '4. PROVE',
    detail:
      'Evidence events form a chained, digest-recorded trail; a certificate is issued and can be re-verified at any time.',
  },
] as const

export function Overview() {
  const connection = useConnection()
  const { user, isDevSession, sessionSourceId } = useAuth()

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title="Forensic Operations Overview"
        purpose="What this session can currently observe, and what the backend has not published an endpoint for."
        actions={
          <div className="flex items-center gap-2">
            <Link to="/targets">
              <Button variant="primary" size="sm" leadingIcon={<Crosshair className="h-3.5 w-3.5" />}>
                Analyze target
              </Button>
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Panel>
            <PanelHeader
              title="Start from an objective"
              description="Every route below exists in the router. Whether its data is available depends on the published contract."
            />
            <div className="grid grid-cols-1 divide-y divide-line">
              {OBJECTIVES.map((obj) => (
                <Link
                  key={obj.to + obj.label}
                  to={obj.to}
                  className="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-elevated"
                >
                  <obj.Icon className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-semibold text-fg">{obj.label}</span>
                    <span className="mt-0.5 block text-[0.6875rem] leading-relaxed text-dim">
                      {obj.detail}
                    </span>
                  </span>
                  <ArrowRight className="mt-1 h-3.5 w-3.5 shrink-0 text-mute transition-transform group-hover:translate-x-0.5" />
                </Link>
              ))}
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Operation lifecycle"
              description="Stage names as the backend state machine defines them."
            />
            <div className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-2">
              {LIFECYCLE.map((stage) => (
                <div key={stage.title} className="rounded border border-line bg-inset p-3">
                  <span className="block text-xs font-semibold text-fg">{stage.title}</span>
                  <p className="mt-1 text-[0.6875rem] leading-relaxed text-mute">{stage.detail}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>


        <div className="flex flex-col gap-6">
          <Panel>
            <PanelHeader
              title="Signed-in principal"
              description="Resolved by the backend, not asserted by this console."
              aside={<StatusBadge kind="screen" value={user ? 'AVAILABLE' : 'EMPTY'} size="sm" />}
            />
            <div className="p-4">
              {user ? (
                <MetaList>
                  <Meta label="Username" mono>
                    {user.username}
                  </Meta>
                  <Meta label="Roles" mono>
                    {user.roles.join(', ')}
                  </Meta>
                  <Meta label="Primary role">
                    {ROLE_METADATA[user.role].label} (level {ROLE_METADATA[user.role].level})
                  </Meta>
                  <Meta label="Granted permissions" mono>
                    {user.permissions.length}
                  </Meta>
                  <Meta label="Session source" mono>
                    {sessionSourceId}
                    {isDevSession ? ' — NOT BACKEND' : ''}
                  </Meta>
                </MetaList>
              ) : (
                <p className="text-[0.6875rem] leading-relaxed text-dim">
                  No principal is resolved. Sign in to obtain a backend session.
                </p>
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Engine connection"
              description="Changes only when a real request succeeds or fails."
              aside={<StatusBadge kind="connection" value={connection.state} size="sm" />}
            />
            <div className="p-4">
              <MetaList>
                <Meta label="Status">
                  <span className="font-medium text-fg">{connection.state}</span>
                </Meta>
                <Meta label="Last response" mono>
                  {formatTimestamp(connection.lastCheckedAt)}
                </Meta>
                <Meta label="Observed via" mono>
                  {connection.source ? connection.source.toUpperCase() : 'NO REQUEST YET'}
                </Meta>
                {connection.lastError && (
                  <Meta label="Error detail" mono>
                    <span className="text-[0.6875rem] text-danger">
                      {connection.lastError.code}
                    </span>
                  </Meta>
                )}
              </MetaList>
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              title="Not observable yet"
              description="Figures this console refuses to display because no endpoint publishes them."
            />
            <div className="space-y-2 p-4">
              {(
                ['operations.list', 'assurance.get', 'audit.events', 'certificates.list'] as const
              ).map((id) => (
                <div
                  key={id}
                  className="flex items-start gap-2 rounded-sm border border-line bg-inset p-2.5"
                >
                  <CircleSlash
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 text-mute"
                    aria-hidden="true"
                  />
                  <div className="min-w-0">
                    <span className="block font-mono text-[0.625rem] text-dim">{id}</span>
                    <p className="mt-0.5 text-[0.6875rem] leading-relaxed text-mute">
                      {unavailableReason(id)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}

