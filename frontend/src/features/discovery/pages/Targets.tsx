import { useState } from 'react'
import { AlertTriangle, ArrowRight, Crosshair, HardDrive, Search } from 'lucide-react'
import { Link } from 'react-router'
import { useAnalyzeTargetMutation } from '@/lib/api/mutations'
import { formatBytes, formatInteger, textOrPlaceholder } from '@/lib/format'
import { PageHeader } from '@/components/shell/PageHeader'
import { Panel, PanelHeader, Meta, MetaList, Tag } from '@/components/ui/Panel'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { StatusBadge } from '@/components/status/StatusBadge'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { EvidenceId } from '@/features/evidence/components/EvidenceId'
import { Badge } from '@/components/ui/Badge'
import { AIPanel } from '@/components/ai/AIPanel'
import type { AIAnalysisData } from '@/components/ai/AIAnalysisDrawer'
import { useAIPreferences } from '@/stores/ai.store'
import { useUIStore } from '@/stores/ui.store'

export function Targets() {
  const [targetPath, setTargetPath] = useState('')
  const [includeContentAnalysis, setIncludeContentAnalysis] = useState(true)
  const analyzeMutation = useAnalyzeTargetMutation()
  const aiEnabled = useAIPreferences((s) => s.enabled)
  const setSelectedTargetId = useUIStore((s) => s.setSelectedTargetId)

  const handleAnalyze = (e: React.FormEvent) => {
    e.preventDefault()
    if (!targetPath.trim()) return
    analyzeMutation.mutate(
      {
        path: targetPath.trim(),
        include_content_analysis: includeContentAnalysis,
      },
      {
        // Selecting the profiled target is what connects this screen to the
        // erasure workflow. `setSelectedTargetId` existed on the store and was
        // never called, so `selectedTargetId` was permanently null: a target
        // could be profiled successfully and then never become the subject of
        // an operation.
        //
        // The identifier comes from the backend's response, never from the path
        // the operator typed. The backend remains authoritative - it revalidates
        // the target when the operation is created, and again immediately before
        // anything destructive happens.
        // `id` is optional in the contract, so it is checked rather than
        // coerced. A response without one selects nothing: the workflow then
        // reports that no target is selected, which is true, instead of
        // carrying an empty identifier the backend would reject later.
        onSuccess: (analysed) => {
          if (analysed.id) setSelectedTargetId(analysed.id)
        },
      },
    )
  }

  const profile = analyzeMutation.data

  // AI advisory: state is hardcoded to UNAVAILABLE because the AI advisory layer
  // has not yet been integrated for this domain. No fabricated data.
  const aiState:
    | 'AVAILABLE'
    | 'ANALYZING'
    | 'COMPLETED'
    | 'LOW_CONFIDENCE'
    | 'INCONCLUSIVE'
    | 'UNAVAILABLE'
    | 'ERROR' = 'UNAVAILABLE'
  const aiSensitivity: AIAnalysisData | undefined = undefined

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader
        title="Target Analysis & Profiling"
        purpose="Forensic reconnaissance, storage profile discovery, and AI sensitivity analysis."
      />

      {/* Target Discovery & Input Form */}
      <Panel>
        <PanelHeader
          title="Analyze Target Scope"
          description="Submit a filesystem path for read-only inspection, dry-run profiling, and hash calculation."
        />
        <form onSubmit={handleAnalyze} className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex-1">
              <Input
                label="Filesystem Path"
                placeholder="e.g. C:\Data\Exports or /var/data/vault"
                value={targetPath}
                onChange={(e) => setTargetPath(e.target.value)}
                leadingIcon={<Search className="h-3.5 w-3.5" />}
                required
              />
            </div>
            <div className="sm:self-end">
              <Button
                type="submit"
                variant="primary"
                loading={analyzeMutation.isPending}
                leadingIcon={<Crosshair className="h-3.5 w-3.5" />}
              >
                Inspect Target
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs text-mute">
            <Checkbox
              checked={includeContentAnalysis}
              onChange={(e) => setIncludeContentAnalysis(e.target.checked)}
              label="Perform content & sensitivity classification"
            />
          </div>
        </form>
      </Panel>

      {/* State Transitions */}
      {analyzeMutation.isPending && (
        <LoadingState
          title="Analyzing Target..."
          description="Querying backend engine for volume characteristics, calculating SHA-256 digest, and evaluating content safety."
        />
      )}

      {analyzeMutation.isError && (
        <ErrorState
          error={analyzeMutation.error}
          onRetry={() => {
            if (targetPath) {
              analyzeMutation.mutate({
                path: targetPath,
                include_content_analysis: includeContentAnalysis,
              })
            }
          }}
        />
      )}

      {!analyzeMutation.isPending && !analyzeMutation.isError && !profile && (
        <EmptyState
          title="No target inspected"
          description="Enter a filesystem path above to perform authoritative inspection and sensitivity profiling."
        />
      )}

      {/* Analysis Results Display */}
      {profile && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Column 1: Authoritative Facts */}
          <div className="flex flex-col gap-6">
            <Panel>
              <PanelHeader
                title="Authoritative Target Facts"
                description="Deterministic metadata collected by backend inspection."
                aside={<Badge variant="accent">AUTHORITATIVE</Badge>}
              />
              <div className="p-4">
                <MetaList>
                  <Meta label="Target ID" mono>
                    {profile.id ? <EvidenceId value={profile.id} label="Target ID" /> : 'â€”'}
                  </Meta>
                  <Meta label="Resolved Path" mono>
                    {profile.path ?? targetPath}
                  </Meta>
                  <Meta label="Target Type">
                    <span className="font-semibold text-fg uppercase">
                      {profile.type ?? 'FILE / DIRECTORY'}
                    </span>
                  </Meta>
                  <Meta label="Total Size">
                    <span className="font-mono tabular">{formatBytes(profile.size_bytes)}</span>
                  </Meta>
                  <Meta label="File Count">
                    <span className="font-mono tabular">{formatInteger(profile.file_count)}</span>
                  </Meta>
                  <Meta label="Baseline SHA-256" mono>
                    {profile.sha256 ? (
                      <span className="text-[0.75rem] text-accent break-all">{profile.sha256}</span>
                    ) : (
                      'â€”'
                    )}
                  </Meta>
                </MetaList>
              </div>
            </Panel>

            {/* Storage Profile */}
            <Panel>
              <PanelHeader
                title="Storage Profile"
                description="Physical and logical characteristics of the hosting volume."
                aside={<HardDrive className="h-4 w-4 text-mute" />}
              />
              <div className="p-4">
                <MetaList>
                  <Meta label="Volume">{textOrPlaceholder(profile.storage_profile?.volume)}</Meta>
                  <Meta label="Filesystem">
                    <Tag mono>{textOrPlaceholder(profile.storage_profile?.filesystem)}</Tag>
                  </Meta>
                  <Meta label="Media Type">
                    {textOrPlaceholder(profile.storage_profile?.media_type)}
                  </Meta>
                  <Meta label="Encryption Status">
                    {textOrPlaceholder(profile.storage_profile?.encryption_status)}
                  </Meta>
                </MetaList>

                {profile.storage_profile?.limitations &&
                  profile.storage_profile.limitations.length > 0 && (
                    <div className="mt-4 rounded border border-warning/30 bg-warning-soft p-3 text-xs text-warning">
                      <div className="font-semibold flex items-center gap-1.5">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        <span>Volume Limitations</span>
                      </div>
                      <ul className="mt-1 list-disc list-inside space-y-0.5 text-[0.6875rem]">
                        {profile.storage_profile.limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>
            </Panel>
          </div>

          {/* Column 2: AI Sensitivity Analysis & Actions */}
          <div className="flex flex-col gap-6">
            {aiEnabled && (
              <AIPanel
                title="Sensitive Data Classification"
                state={aiState}
                aiData={aiSensitivity}
                confidence={undefined}
                summary="The AI advisory layer is not yet integrated for target sensitivity classification. Authoritative content classification and policy recommendation are derived from backend deterministic evidence only."
                drawerSubtitle="AI ADVISORY â€” Sensitive Data Classification"
              />
            )}

            <Panel>
              <PanelHeader
                title="Backend Sensitivity Analysis"
                description="Authoritative sensitivity classification and policy recommendation from backend engine."
                aside={<Badge variant="info">AUTHORITATIVE</Badge>}
              />
              <div className="p-4">
                <MetaList>
                  <Meta label="Sensitivity Classification">
                    {profile.sensitivity?.level ? (
                      <StatusBadge kind="sensitivity" value={profile.sensitivity.level} size="md" />
                    ) : (
                      <StatusBadge kind="sensitivity" value="INTERNAL" size="md" />
                    )}
                  </Meta>
                  <Meta label="Detected Categories">
                    <div className="flex flex-wrap justify-end gap-1">
                      {profile.sensitivity?.categories &&
                      profile.sensitivity.categories.length > 0 ? (
                        profile.sensitivity.categories.map((cat, idx) => <Tag key={idx}>{cat}</Tag>)
                      ) : (
                        <span className="text-mute">None flagged</span>
                      )}
                    </div>
                  </Meta>
                  <Meta label="Assessment Rationale">
                    <span className="text-xs text-dim">
                      {profile.sensitivity?.explanation ??
                        'Standard content classification evaluated nominal.'}
                    </span>
                  </Meta>
                </MetaList>
              </div>
            </Panel>

            {/* Next Action Panel */}
            <Panel>
              <PanelHeader
                title="Next Action: Erasure Workflow"
                description="Configure controlled deletion policy based on target profile."
              />
              <div className="flex flex-col gap-3 p-4">
                <p className="text-xs text-mute">
                  Target profile has been registered. You may proceed to review scope boundaries and
                  configure permanent or recoverable erasure policies.
                </p>
                <div className="flex items-center justify-end pt-2">
                  <Link to="/erasure">
                    <Button
                      variant="primary"
                      size="sm"
                      trailingIcon={<ArrowRight className="h-3.5 w-3.5" />}
                    >
                      Configure Erasure Policy
                    </Button>
                  </Link>
                </div>
              </div>
            </Panel>
          </div>
        </div>
      )}
    </div>
  )
}
