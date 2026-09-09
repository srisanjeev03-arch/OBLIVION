import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/cn'
import { Badge } from '@/components/ui/Badge'

export type AIResultState =
  | 'AVAILABLE'
  | 'ANALYZING'
  | 'COMPLETED'
  | 'LOW_CONFIDENCE'
  | 'INCONCLUSIVE'
  | 'UNAVAILABLE'
  | 'ERROR'

export interface AIAnalysisData {
  classification?: string
  confidence?: number
  recommendation?: string
  reasoningFactors?: string[]
  evidenceUsed?: string[]
  limitations?: string
  modelInformation?: string
  generatedAt?: string
  advisoryStatus?: 'ADVISORY' | 'AUTHORITATIVE'
}

export interface AIAnalysisDrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  subtitle?: string
  aiData: AIAnalysisData | null
  showAdvisoryLabel: boolean
  className?: string
}

export function AIAnalysisDrawer({
  isOpen,
  onClose,
  title,
  subtitle,
  aiData,
  showAdvisoryLabel = true,
  className,
}: AIAnalysisDrawerProps) {
  useEffect(() => {
    if (!isOpen) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs"
    >
      <button
        type="button"
        aria-label="Close AI analysis drawer"
        onClick={onClose}
        className="absolute inset-0 cursor-default"
      />
      <div
        className={cn(
          'rounded-2xl p-6 max-w-md w-full text-sm bg-elevated border-t border-accent/60 relative',
          'motion-enter',
          className,
        )}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-lg text-fg">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="Close AI analysis drawer"
          >
            <X className="h-4 w-4 text-dim" />
          </button>
        </div>

        {subtitle && <p className="text-sm text-dim mb-4">{subtitle}</p>}

        {aiData && aiData.classification && (
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              {showAdvisoryLabel && (
                <span className="text-xs font-medium uppercase tracking-wider text-accent">
                  AI ADVISORY
                </span>
              )}
              <Badge variant={aiData.advisoryStatus === 'AUTHORITATIVE' ? 'success' : 'warning'}>
                {aiData.advisoryStatus ?? 'ADVISORY'}
              </Badge>
            </div>
            <p className="text-xs text-dim">{aiData.classification}</p>
          </div>
        )}

        {/* Confidence Display */}
        {aiData && aiData.confidence !== undefined && (
          <div className="mb-4">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium text-fg">Confidence:</span>
              <span
                className={cn(
                  'px-2 rounded text-xs font-medium border',
                  aiData.confidence >= 80
                    ? 'border-success/40 bg-success-soft text-success'
                    : aiData.confidence >= 50
                      ? 'border-warning/40 bg-warning-soft text-warning'
                      : 'border-line-strong bg-inset text-mute',
                )}
              >
                {aiData.confidence}%
              </span>
              <span className="text-xs text-dim">
                {getConfidenceInterpretation(aiData.confidence)}
              </span>
            </div>
          </div>
        )}

        {/* Recommendation */}
        {aiData && aiData.recommendation && (
          <div className="mb-4">
            <p className="text-xs font-medium text-fg uppercase tracking-wider mb-1">
              Recommendation
            </p>
            <p className="text-xs text-dim leading-relaxed">{aiData.recommendation}</p>
          </div>
        )}

        {/* Reasoning Factors */}
        {aiData && aiData.reasoningFactors && aiData.reasoningFactors.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-medium text-fg uppercase tracking-wider mb-1">
              Reasoning Factors
            </p>
            <ul className="list-disc list-inside text-xs text-dim space-y-0.5">
              {aiData.reasoningFactors.map((factor, idx) => (
                <li key={idx}>{factor}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Evidence Used */}
        {aiData && aiData.evidenceUsed && aiData.evidenceUsed.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-medium text-fg uppercase tracking-wider mb-1">
              Evidence Used
            </p>
            <ul className="list-disc list-inside text-xs text-dim space-y-0.5">
              {aiData.evidenceUsed.map((ev, idx) => (
                <li key={idx}>{ev}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Limitations */}
        {aiData && aiData.limitations && (
          <div className="mb-4">
            <p className="text-xs font-medium text-fg uppercase tracking-wider mb-1">Limitations</p>
            <p className="text-xs text-dim leading-relaxed">{aiData.limitations}</p>
          </div>
        )}

        {/* Model Information */}
        {aiData && aiData.modelInformation && (
          <div className="mb-4">
            <p className="text-xs font-medium text-fg uppercase tracking-wider mb-1">
              Model Information
            </p>
            <p className="text-xs text-dim">{aiData.modelInformation}</p>
          </div>
        )}

        {/* Generated At */}
        {aiData && aiData.generatedAt && (
          <div className="text-xs text-dim">
            <div className="font-medium text-fg">Generated At:</div>
            <span className="ml-1">{aiData.generatedAt}</span>
          </div>
        )}

        {/* Close button */}
        <div className="mt-6 pt-4 border-t border-line/50">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-md border border-line-strong py-2 text-sm font-medium text-accent hover:bg-accent/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function getConfidenceInterpretation(confidence: number): string {
  if (confidence >= 80) return 'HIGH'
  if (confidence >= 50) return 'MEDIUM'
  if (confidence > 0) return 'LOW'
  return 'INCONCLUSIVE'
}
