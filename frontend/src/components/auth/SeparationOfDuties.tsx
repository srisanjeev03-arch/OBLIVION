import { ShieldCheck, AlertCircle } from 'lucide-react'
import { useAuth } from '@/lib/auth/context'
import { ROLE_METADATA, type Role } from '@/lib/auth/types'
import { cn } from '@/lib/cn'

export type SoDPhase = 'REQUEST' | 'APPROVE' | 'EXECUTE' | 'VERIFY'

export interface SeparationOfDutiesProps {
  currentPhase: SoDPhase
  requestedByRole?: Role
  approvedByRole?: Role
  executedByRole?: Role
  verifiedByRole?: Role
  isApproved?: boolean
  isExecuted?: boolean
  isVerified?: boolean
  className?: string
}

const PHASES: readonly {
  id: SoDPhase
  title: string
  responsibleRole: Role
  verb: string
  requiredPermission: string
}[] = [
  {
    id: 'REQUEST',
    title: '1. Request',
    responsibleRole: 'INVESTIGATOR',
    verb: 'Initiates case scope & deletion request',
    requiredPermission: 'operation.request',
  },
  {
    id: 'APPROVE',
    title: '2. Approve',
    responsibleRole: 'ADMIN',
    verb: 'Validates policy, scope safety & signs authorization',
    requiredPermission: 'operation.approve',
  },
  {
    id: 'EXECUTE',
    title: '3. Execute',
    responsibleRole: 'OPERATOR',
    verb: 'Executes approved physical zeroing & key eradication',
    requiredPermission: 'operation.execute',
  },
  {
    id: 'VERIFY',
    title: '4. Verify',
    responsibleRole: 'AUDITOR',
    verb: 'Independently inspects hash-chain & evidence attestation',
    requiredPermission: 'operation.verify',
  },
] as const

export function SeparationOfDuties({ currentPhase, className }: SeparationOfDutiesProps) {
  const { user } = useAuth()
  const userRole = user?.role ?? 'VIEWER'

  const currentIdx = PHASES.findIndex((p) => p.id === currentPhase)
  const currentPhaseMeta = (currentIdx > -1 ? PHASES[currentIdx] : PHASES[0]) ?? {
    id: 'REQUEST',
    title: '1. Request',
    responsibleRole: 'INVESTIGATOR',
    verb: 'Initiates case scope & deletion request',
    requiredPermission: 'operation.request',
  }

  return (
    <div
      className={cn(
        'rounded-md border border-line bg-surface p-4 space-y-3.5 select-none',
        className,
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-accent" />
          <span className="text-xs font-bold uppercase tracking-wider text-fg">
            Separation of Duties (SoD) Governance Pipeline
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-mute font-mono text-[0.6875rem]">Active Operator:</span>
          <span
            className="px-1.5 py-0.5 rounded-xs font-mono text-[0.625rem] font-bold uppercase border"
            style={{
              color: ROLE_METADATA[userRole].color,
              borderColor: `${ROLE_METADATA[userRole].color}40`,
              backgroundColor: `${ROLE_METADATA[userRole].color}15`,
            }}
          >
            {userRole}
          </span>
        </div>
      </div>

      {/* 4-Phase Stepper Rail */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
        {PHASES.map((p, idx) => {
          const isPassed = idx < currentIdx
          const isCurrent = idx === currentIdx
          const roleMeta = ROLE_METADATA[p.responsibleRole]

          return (
            <div
              key={p.id}
              className={cn(
                'rounded-md border p-2.5 space-y-1.5 transition-all text-xs',
                isCurrent
                  ? 'border-accent bg-accent-soft text-fg ring-1 ring-accent/30'
                  : isPassed
                    ? 'border-success/40 bg-success-soft text-fg'
                    : 'border-line bg-elevated/40 text-dim opacity-70',
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[0.75rem]">{p.title}</span>
                <span
                  className="px-1.5 py-0.2 rounded-xs text-[0.5625rem] font-mono font-bold uppercase border"
                  style={{
                    color: roleMeta.color,
                    borderColor: `${roleMeta.color}40`,
                    backgroundColor: `${roleMeta.color}15`,
                  }}
                >
                  {p.responsibleRole}
                </span>
              </div>
              <p className="text-[0.625rem] text-dim leading-tight">{p.verb}</p>
            </div>
          )
        })}
      </div>

      {/* Guidance Note based on user role vs current phase */}
      <div className="rounded-sm border border-line bg-inset p-2.5 flex items-start gap-2 text-[0.6875rem] text-dim">
        <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-accent" />
        <div>
          <span className="font-semibold text-fg mr-1">
            Current Stage Authority ({currentPhaseMeta.responsibleRole}):
          </span>
          {userRole === currentPhaseMeta.responsibleRole ? (
            <span className="text-success font-medium">
              You are authenticated with the required authority ({userRole}) to proceed with this
              phase.
            </span>
          ) : (
            <span>
              This phase requires{' '}
              <strong className="text-fg">{currentPhaseMeta.responsibleRole}</strong> authority. As
              an authenticated <strong className="text-fg">{userRole}</strong>, your view is
              restricted according to strict separation of duties governance.
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
