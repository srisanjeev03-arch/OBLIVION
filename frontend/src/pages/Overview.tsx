import { useState } from 'react'
import { Link } from 'react-router'
import {
  Activity,
  ArrowRight,
  Crosshair,
  FileCheck,
  HardDrive,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { formatTimestamp } from '@/lib/format'
import { useConnection } from '@/lib/api/connection'
import { PageHeader } from '@/components/shell/PageHeader'
import { InspectorDrawer } from '@/components/shell/InspectorDrawer'
import { Panel, PanelHeader, Meta, MetaList } from '@/components/ui/Panel'
import { Button } from '@/components/ui/Button'
import { StatusBadge } from '@/components/status/StatusBadge'
import { EmptyState } from '@/components/states'
import { EvidenceId } from '@/components/evidence/EvidenceId'
import { Sparkles } from 'lucide-react'
import { AIPanel } from '@/components/ai/AIPanel'
import { useAIPreferences } from '@/stores/ai.store'

export function Overview() {
  const connection = useConnection()
  const aiEnabled = useAIPreferences((s) => s.enabled)
  const [selectedOp, setSelectedOp] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title="Forensic Operations Overview"
        purpose="Authoritative operator state, pending verifications, and active lifecycle tasks."
        actions={
          <div className="flex items-center gap-2">
            <Link to="/targets">
              <Button
                variant="primary"
                size="sm"
                leadingIcon={<Crosshair className="h-3.5 w-3.5" />}
              >
                Analyze target
              </Button>
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Active Operation Column (Takes 2 cols on lg) */}
        <div className="flex flex-col gap-6 lg:col-span-2">
          {/* Active Operation Panel */}
          <Panel>
            <PanelHeader
              title="Active Operation"
              description="Primary forensic lifecycle currently executing on backend engine."
              aside={<StatusBadge kind="screen" value="EMPTY" size="sm" />}
            />
            <div className="p-4">
              <EmptyState
                compact
                title="No active operations"
                description="The backend engine is currently idle. Initiate a target analysis to begin a controlled workflow."
                action={
                  <Link to="/targets">
                    <Button
                      size="sm"
                      variant="outline"
                      leadingIcon={<Zap className="h-3.5 w-3.5 text-accent" />}
                    >
                      Discover & Analyze Target
                    </Button>
                  </Link>
                }
              />
            </div>
          </Panel>

          {/* Attention Required Panel */}
          <Panel>
            <PanelHeader
              title="Attention Required"
              description="Anomalies, failed verifications, partial erasures, or authorization requests."
              aside={
                <span className="inline-flex items-center gap-1 text-xs text-mute font-mono">
                  0 PENDING
                </span>
              }
            />
            <div className="p-4">
              <div className="flex items-center gap-3 rounded border border-line bg-inset/50 p-3 text-xs text-dim">
                <ShieldCheck className="h-4 w-4 shrink-0 text-success" />
                <span>
                  All recorded states are nominal. No unhandled security warnings or inconclusive
                  results.
                </span>
              </div>
            </div>
          </Panel>

          {/* Quick Workflow Stepper */}
          <Panel>
            <PanelHeader
              title="Forensic Operating Model"
              description="Authoritative sequence for all data operations."
            />
            <div className="grid grid-cols-1 gap-2 p-4 sm:grid-cols-3 text-xs">
              <div className="flex flex-col gap-1 rounded border border-line bg-inset p-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-fg">1. ERASE</span>
                  <HardDrive className="h-3.5 w-3.5 text-accent" />
                </div>
                <p className="text-[0.6875rem] text-mute">
                  Target profiling, baseline capture, and selective permanent or recoverable
                  sanitization.
                </p>
              </div>

              <div className="flex flex-col gap-1 rounded border border-line bg-inset p-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-fg">2. VERIFY</span>
                  <Activity className="h-3.5 w-3.5 text-info" />
                </div>
                <p className="text-[0.6875rem] text-mute">
                  Sector-level verification, recovery test simulation, and remnant scan analysis.
                </p>
              </div>

              <div className="flex flex-col gap-1 rounded border border-line bg-inset p-3">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-fg">3. PROVE</span>
                  <FileCheck className="h-3.5 w-3.5 text-success" />
                </div>
                <p className="text-[0.6875rem] text-mute">
                  Cryptographic evidence-chain hashing, assurance assessment, and signed
                  certificates.
                </p>
              </div>
            </div>
          </Panel>
        </div>

        {/* System & Telemetry Snapshot Column (1 col) */}
        <div className="flex flex-col gap-6">
          {/* Backend Connection Health */}
          <Panel>
            <PanelHeader
              title="Engine Connection"
              description="Autoritative backend service interface status."
              aside={<StatusBadge kind="connection" value={connection.state} size="sm" />}
            />
            <div className="p-4">
              <MetaList>
                <Meta label="Status">
                  <span className="font-medium text-fg">{connection.state}</span>
                </Meta>
                <Meta label="Last Response" mono>
                  {formatTimestamp(connection.lastCheckedAt)}
                </Meta>
                <Meta label="Source">
                  {connection.source ? connection.source.toUpperCase() : 'NONE'}
                </Meta>
                {connection.lastError && (
                  <Meta label="Error Detail">
                    <span className="text-danger font-mono text-[0.6875rem]">
                      {connection.lastError.code}
                    </span>
                  </Meta>
                )}
              </MetaList>
            </div>
          </Panel>

          {/* Assurance Summary */}
          <Panel>
            <PanelHeader
              title="Assurance Snapshot"
              description="Evidence completeness across all operations."
            />
            <div className="flex flex-col gap-2 p-4">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <StatusBadge kind="assurance" value="VALIDATED" size="sm" />
                  <span className="text-mute">Verified & Proven</span>
                </div>
                <span className="font-mono tabular text-fg">0</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <StatusBadge kind="assurance" value="INCONCLUSIVE" size="sm" />
                  <span className="text-mute">Insufficient Evidence</span>
                </div>
                <span className="font-mono tabular text-fg">0</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <StatusBadge kind="assurance" value="PARTIAL" size="sm" />
                  <span className="text-mute">Incomplete Scope</span>
                </div>
                <span className="font-mono tabular text-fg">0</span>
              </div>
            </div>
          </Panel>

          {/* AI Security Intelligence Widget */}
          {aiEnabled && (
            <div className="rounded-md border border-accent/40 bg-surface p-4 space-y-2">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent" />
                <span className="text-xs font-bold text-fg uppercase tracking-wider">
                  AI Security Intelligence
                </span>
              </div>
              <AIPanel
                title="Threat-Sensitive Target Insights"
                state="UNAVAILABLE"
                summary="The AI advisory layer is not yet integrated. Authoritative backend facts remain the source of truth for all threat scoring."
                drawerSubtitle="AI ADVISORY — Threat-Sensitive Target Insights"
              />
            </div>
          )}

          {/* Quick Links */}
          <Panel>
            <PanelHeader title="Quick Actions" />
            <div className="flex flex-col divide-y divide-line text-xs">
              <Link
                to="/targets"
                className="flex items-center justify-between px-4 py-3 text-dim hover:bg-elevated hover:text-fg transition-colors"
              >
                <span>Target Analysis & Profiling</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                to="/operations"
                className="flex items-center justify-between px-4 py-3 text-dim hover:bg-elevated hover:text-fg transition-colors"
              >
                <span>Operations Monitor</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                to="/settings"
                className="flex items-center justify-between px-4 py-3 text-dim hover:bg-elevated hover:text-fg transition-colors"
              >
                <span>Console & Connection Settings</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </Panel>
        </div>
      </div>

      {/* Inspector Drawer for Detailed Inspections */}
      <InspectorDrawer
        open={Boolean(selectedOp)}
        onClose={() => setSelectedOp(null)}
        title="Operation Inspector"
        subtitle={selectedOp ?? undefined}
      >
        {selectedOp && (
          <div className="flex flex-col gap-4">
            <MetaList>
              <Meta label="Operation ID" mono>
                <EvidenceId value={selectedOp} label="Operation ID" />
              </Meta>
              <Meta label="State">
                <StatusBadge kind="operation" value="CREATED" />
              </Meta>
            </MetaList>
          </div>
        )}
      </InspectorDrawer>
    </div>
  )
}
