import { useState, type ElementType } from 'react'
import { useNavigate } from 'react-router'
import {
  AlertTriangle,
  ChevronRight,
  ClipboardList,
  Compass,
  Cpu,
  FileCheck,
  Info,
  Lock,
  Search,
  Trash2,
} from 'lucide-react'
import { PageHeader } from '@/components/shell/PageHeader'
import { NAV_ITEMS, type NavId } from '@/components/shell/nav'
import { Panel, PanelHeader } from '@/components/ui/Panel'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/lib/auth/context'
import { hasPermission } from '@/lib/auth/permissions'
import type { OperationMode } from '@/lib/api/types'
import { cn } from '@/lib/cn'

/**
 * Objective selection.
 *
 * A guided entry point only: choosing an objective opens an existing screen and performs nothing.
 * The permission shown for each objective is read from `nav.ts`, the same source the route guards
 * use, so this page cannot advertise access the destination would refuse.
 */

type Objective = 'ERASE' | 'RECOVERABLE' | 'TEST' | 'VERIFY' | 'REVIEW'
type Mode = 'OPERATOR' | 'EXPERT'

interface ObjectiveConfig {
  id: Objective
  title: string
  desc: string
  icon: ElementType
  color: string
  bg: string
  method: string
  limit: string
  destination: NavId
  /** Preselected on the erasure screen; the operator still confirms the mode there. */
  mode?: OperationMode
}

const OBJECTIVES: readonly ObjectiveConfig[] = [
  {
    id: 'ERASE',
    title: 'Remove data',
    desc: 'Request an approved logical deletion of files or folders on a supported NTFS volume. Recoverability is then tested with the techniques this build supports.',
    icon: Trash2,
    color: 'text-danger',
    bg: 'bg-danger-soft',
    method: 'Erasure workflow',
    limit:
      'Irreversible at the filesystem level and requires a second actor to approve. No physical media sanitization is performed.',
    destination: 'erasure',
  },
  {
    id: 'RECOVERABLE',
    title: 'Remove with controlled recovery',
    desc: 'Remove the original while keeping an encrypted recovery object that can be restored only with authorization.',
    icon: Lock,
    color: 'text-accent',
    bg: 'bg-accent-soft',
    method: 'Controlled recoverable',
    limit: 'Restoration requires authorization and is verified against the original hash.',
    destination: 'erasure',
    mode: 'CONTROLLED_RECOVERABLE',
  },
  {
    id: 'TEST',
    title: 'Check for remaining traces',
    desc: 'Review residual analysis for artifacts left behind, within the scanners this build supports.',
    icon: Search,
    color: 'text-warning',
    bg: 'bg-warning-soft',
    method: 'Residual analysis',
    limit: 'A scan that finds nothing is not proof that nothing remains.',
    destination: 'residuals',
  },
  {
    id: 'VERIFY',
    title: 'Review an operation’s assurance',
    desc: 'Examine the evidence-bound assurance result recorded for an existing operation.',
    icon: FileCheck,
    color: 'text-success',
    bg: 'bg-success-soft',
    method: 'Assurance review',
    limit: 'Conclusions are limited to the evidence that was collected.',
    destination: 'assurance',
  },
  {
    id: 'REVIEW',
    title: 'Review evidence and the audit trail',
    desc: 'Examine the audit log, evidence chain and certificates.',
    icon: ClipboardList,
    color: 'text-dim',
    bg: 'bg-inset',
    method: 'Audit review',
    limit: 'The audit log records what was done; it does not by itself prove erasure.',
    destination: 'audit',
  },
]

const WORKFLOW_STEPS = [
  { id: 'TARGET', label: 'TARGET', desc: 'Select target' },
  { id: 'SCOPE', label: 'SCOPE', desc: 'Define scope' },
  { id: 'RECOMMENDATION', label: 'RECOMMEND', desc: 'Policy recommendation' },
  { id: 'REVIEW', label: 'REVIEW', desc: 'Review risk and limits' },
]

function destinationOf(objective: ObjectiveConfig) {
  const item = NAV_ITEMS.find((n) => n.id === objective.destination)
  if (!item) throw new Error(`Objective ${objective.id} points at unknown nav id`)
  return item
}

export function ObjectiveSelection() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [selected, setSelected] = useState<ObjectiveConfig | null>(null)
  const [mode, setMode] = useState<Mode>('OPERATOR')

  const reachable = (objective: ObjectiveConfig) => {
    const permission = destinationOf(objective).permission
    return !permission || hasPermission(user, permission)
  }

  const handleContinue = () => {
    if (!selected) return
    const item = destinationOf(selected)
    void navigate(item.path, {
      state: { objective: selected.id, ...(selected.mode ? { mode: selected.mode } : {}) },
    })
  }

  return (
    <div className="flex min-h-full flex-col">
      <PageHeader
        title="Objective Selection"
        purpose="Define the goal before selecting targets and configuring policies."
        icon={<Compass className="h-4 w-4" aria-hidden="true" />}
        actions={
          <div role="group" aria-label="Detail level" className="flex gap-1">
            {(['OPERATOR', 'EXPERT'] as const).map((value) => (
              <Button
                key={value}
                size="sm"
                variant={mode === value ? 'primary' : 'outline'}
                aria-pressed={mode === value}
                onClick={() => setMode(value)}
              >
                {value}
              </Button>
            ))}
          </div>
        }
      />
      <div className="flex-1 p-6">
        {!selected && (
          <div className="mx-auto max-w-4xl py-10">
            <div className="mb-12 text-center">
              <h2 className="mb-4 text-2xl font-bold tracking-tight text-fg">
                What do you want to accomplish?
              </h2>
              <p className="text-sm text-dim">
                Choosing an objective opens the matching screen. Nothing is performed here.
              </p>
            </div>
            <div className="grid gap-3">
              {OBJECTIVES.map((obj) => {
                const allowed = reachable(obj)
                return (
                  <button
                    key={obj.id}
                    type="button"
                    disabled={!allowed}
                    onClick={() => setSelected(obj)}
                    className={cn(
                      'group flex items-center gap-4 rounded-sm border p-4 text-left transition-all',
                      'border-line bg-surface hover:border-accent/40 hover:bg-elevated',
                      'disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:border-line disabled:hover:bg-surface',
                    )}
                  >
                    <div
                      className={cn(
                        'flex h-12 w-12 shrink-0 items-center justify-center rounded-sm',
                        obj.bg,
                      )}
                    >
                      <obj.icon className={cn('h-6 w-6', obj.color)} aria-hidden="true" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="mb-0.5 text-sm font-bold text-fg transition-colors group-hover:text-accent">
                        {obj.title}
                      </h3>
                      <p className="text-xs text-dim">{obj.desc}</p>
                      {!allowed && (
                        <p className="mt-1 text-xs text-mute">
                          Your role does not have access to this screen.
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-mute" aria-hidden="true" />
                  </button>
                )
              })}
            </div>
          </div>
        )}
        {selected && (
          <WorkflowPanel
            objective={selected}
            mode={mode}
            onContinue={handleContinue}
            onCancel={() => setSelected(null)}
          />
        )}
      </div>
    </div>
  )
}

function WorkflowPanel({
  objective,
  mode,
  onContinue,
  onCancel,
}: {
  objective: ObjectiveConfig
  mode: Mode
  onContinue: () => void
  onCancel: () => void
}) {
  const destination = destinationOf(objective)
  return (
    <Panel className="mx-auto max-w-4xl">
      <PanelHeader
        title="Workflow Configuration"
        description={`${objective.method} — guided workflow`}
        aside={
          <Badge variant={objective.id === 'ERASE' ? 'danger' : 'default'}>{objective.id}</Badge>
        }
      />
      <div className="space-y-6 p-5">
        <div className="grid grid-cols-4 gap-3">
          {WORKFLOW_STEPS.map((s, idx) => (
            <div key={s.id} className="rounded-sm border border-line bg-inset p-3">
              <div className="mb-1 text-[10px] font-bold uppercase tracking-wider text-mute">
                {idx + 1}. {s.label}
              </div>
              <div className="text-xs font-semibold text-fg">{s.desc}</div>
            </div>
          ))}
        </div>
        {mode === 'OPERATOR' ? (
          <div className="flex items-start gap-3 rounded-sm border border-warning/40 bg-warning-soft p-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
            <div>
              <div className="mb-1 text-xs font-bold text-warning">Limits</div>
              <div className="text-xs text-dim">{objective.limit}</div>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3 rounded-sm border border-line bg-inset p-3">
            <Cpu className="mt-0.5 h-4 w-4 shrink-0 text-dim" aria-hidden="true" />
            <div className="space-y-0.5 text-xs text-dim">
              <div className="mb-1 font-bold text-fg">Technical Details</div>
              <div>
                Destination: <span className="font-mono text-accent">{destination.path}</span>
              </div>
              <div>
                Required permission:{' '}
                <span className="font-mono text-accent">{destination.permission ?? 'none'}</span>
              </div>
              {objective.mode && (
                <div>
                  Preselected mode: <span className="font-mono text-accent">{objective.mode}</span>
                </div>
              )}
            </div>
          </div>
        )}
        <div className="flex items-center gap-3 pt-2">
          <Button variant="primary" onClick={onContinue}>
            Continue to {destination.label}
          </Button>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        </div>
        <div className="rounded-sm border border-line bg-elevated/50 p-3 text-xs text-dim">
          <Info className="mr-1.5 inline h-3.5 w-3.5 text-mute" aria-hidden="true" />
          The selected objective only opens the next screen. No destructive action is taken until
          authorization and target confirmation are completed there.
        </div>
      </div>
    </Panel>
  )
}
