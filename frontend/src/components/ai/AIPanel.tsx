import { useState } from 'react'
import { Sparkles, ChevronDown, ChevronUp, AlertCircle, Loader2 } from 'lucide-react'
import { cn } from '@/lib/cn'
import { Badge } from '@/components/ui/Badge'
import { AIAnalysisDrawer, type AIAnalysisData, type AIResultState } from './AIAnalysisDrawer'

export interface AIPanelProps {
  title: string
  state: AIResultState
  summary?: string
  aiData?: AIAnalysisData | null
  confidence?: number
  drawerSubtitle?: string
  className?: string
}

const STATE_BADGE: Record<
  AIResultState,
  { label: string; variant: 'default' | 'success' | 'warning' | 'danger' | 'info' }
> = {
  AVAILABLE: { label: 'AVAILABLE', variant: 'success' },
  ANALYZING: { label: 'ANALYZING', variant: 'info' },
  COMPLETED: { label: 'COMPLETED', variant: 'success' },
  LOW_CONFIDENCE: { label: 'LOW CONFIDENCE', variant: 'warning' },
  INCONCLUSIVE: { label: 'INCONCLUSIVE', variant: 'warning' },
  UNAVAILABLE: { label: 'UNAVAILABLE', variant: 'default' },
  ERROR: { label: 'ERROR', variant: 'danger' },
}

export function AIPanel({
  title,
  state,
  summary,
  aiData,
  confidence,
  drawerSubtitle,
  className,
}: AIPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)

  const stateMeta = STATE_BADGE[state]
  const isUnavailable = state === 'UNAVAILABLE' || state === 'ERROR'

  return (
    <>
      <div
        className={cn(
          'rounded-md border bg-surface p-4 space-y-3',
          isUnavailable ? 'border-line' : 'border-accent/40',
          className,
        )}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles
              className={cn(
                'h-4 w-4 shrink-0',
                state === 'ANALYZING' ? 'text-accent motion-spin' : 'text-accent',
              )}
            />
            <h3 className="text-xs font-bold text-fg uppercase tracking-wider">
              AI Advisory: {title}
            </h3>
          </div>
          <Badge variant={stateMeta.variant}>{stateMeta.label}</Badge>
        </div>

        {/* AI Advisory Banner */}
        <div className="rounded-sm border border-info/30 bg-info-soft px-3 py-2 text-[0.6875rem] text-info flex items-center gap-2">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>
            AI output is advisory. Authoritative decisions are operator-controlled. Do not treat AI
            as a security boundary.
          </span>
        </div>

        {/* Confidence indicator (if applicable) */}
        {confidence !== undefined && state === 'COMPLETED' && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-dim uppercase text-[0.6875rem] font-medium tracking-wider">
              Confidence:
            </span>
            <span
              className={cn(
                'px-1.5 rounded-xs text-[0.6875rem] font-mono font-semibold border',
                confidence >= 80
                  ? 'border-success/40 bg-success-soft text-success'
                  : confidence >= 50
                    ? 'border-warning/40 bg-warning-soft text-warning'
                    : 'border-line-strong bg-inset text-mute',
              )}
            >
              {confidence}%
            </span>
            <span className="text-[0.6875rem] text-dim">
              {confidence >= 80 ? 'HIGH' : confidence >= 50 ? 'MEDIUM' : 'LOW'}
            </span>
          </div>
        )}

        {/* State-specific body */}
        {state === 'ANALYZING' && (
          <div className="flex items-center gap-2 text-xs text-dim">
            <Loader2 className="h-3.5 w-3.5 text-accent motion-spin" />
            <span>AI model is reasoning over available data...</span>
          </div>
        )}

        {(state === 'UNAVAILABLE' || state === 'ERROR') && (
          <div className="rounded-sm border border-line bg-inset p-3 text-[0.6875rem] text-dim leading-relaxed">
            <p className="font-medium text-fg mb-1">
              {state === 'ERROR' ? 'AI Analysis Error' : 'AI Advisory Unavailable'}
            </p>
            <p>
              {state === 'ERROR'
                ? 'The AI analysis layer encountered an unexpected error. Authoritative backend facts remain the source of truth for this view.'
                : 'The AI advisory layer has not yet been integrated for this domain. This page is fully functional using authoritative backend facts only.'}
            </p>
          </div>
        )}

        {state === 'INCONCLUSIVE' && (
          <div className="rounded-sm border border-warning/40 bg-warning-soft p-3 text-[0.6875rem] text-warning leading-relaxed">
            <p>
              AI advisory could not reach a reliable conclusion. Insufficient semantic context, low
              confidence thresholds, or ambiguous inputs may have caused this state.
            </p>
          </div>
        )}

        {(state === 'AVAILABLE' || state === 'COMPLETED' || state === 'LOW_CONFIDENCE') && (
          <>
            {summary && <p className="text-xs text-dim leading-relaxed">{summary}</p>}

            <button
              type="button"
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-[0.6875rem] font-medium text-accent uppercase tracking-wider hover:text-fg transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-xs px-1 py-0.5"
            >
              {expanded ? (
                <>
                  Hide technical explanation
                  <ChevronUp className="h-3 w-3" />
                </>
              ) : (
                <>
                  Show technical explanation
                  <ChevronDown className="h-3 w-3" />
                </>
              )}
            </button>

            {expanded && aiData && (
              <div className="space-y-3 pt-1 border-t border-line/50">
                {aiData.reasoningFactors && aiData.reasoningFactors.length > 0 && (
                  <div>
                    <p className="text-[0.6875rem] font-medium text-fg uppercase tracking-wider mb-1">
                      Reasoning Factors
                    </p>
                    <ul className="list-disc list-inside text-[0.6875rem] text-dim space-y-0.5">
                      {aiData.reasoningFactors.map((f, idx) => (
                        <li key={idx}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {aiData.evidenceUsed && aiData.evidenceUsed.length > 0 && (
                  <div>
                    <p className="text-[0.6875rem] font-medium text-fg uppercase tracking-wider mb-1">
                      Evidence Used
                    </p>
                    <ul className="list-disc list-inside text-[0.6875rem] text-dim space-y-0.5">
                      {aiData.evidenceUsed.map((e, idx) => (
                        <li key={idx}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {aiData.limitations && (
                  <div>
                    <p className="text-[0.6875rem] font-medium text-fg uppercase tracking-wider mb-1">
                      Limitations
                    </p>
                    <p className="text-[0.6875rem] text-dim leading-relaxed">
                      {aiData.limitations}
                    </p>
                  </div>
                )}
              </div>
            )}

            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              className="w-full text-[0.6875rem] font-medium text-accent uppercase tracking-wider border border-line-strong rounded-xs py-1.5 hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent transition-colors"
            >
              Open AI Analysis Drawer
            </button>
          </>
        )}
      </div>

      <AIAnalysisDrawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={`AI Analysis — ${title}`}
        subtitle={drawerSubtitle}
        aiData={aiData ?? null}
        showAdvisoryLabel
      />
    </>
  )
}
