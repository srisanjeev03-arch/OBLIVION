import { ShieldAlert, ArrowLeft, LogIn } from 'lucide-react'
import { useNavigate } from 'react-router'
import { useAuth } from '@/lib/auth/context'
import { ROLE_METADATA } from '@/lib/auth/types'
import { Button } from '@/components/ui/Button'

export function Unauthorized() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const roleMeta = user ? ROLE_METADATA[user.role] : null

  return (
    <div className="flex flex-col items-center justify-center min-h-[65vh] p-6 text-center space-y-4 max-w-lg mx-auto">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-danger-soft border border-danger/40 text-danger">
        <ShieldAlert className="h-7 w-7" />
      </div>

      <div className="space-y-1.5">
        <h1 className="text-base font-bold text-fg tracking-tight">403 — Restricted Operation</h1>
        <p className="text-xs text-dim leading-relaxed">
          Your authenticated persona does not have the authorization credentials required to view or
          execute this console workspace.
        </p>
      </div>

      {user && roleMeta && (
        <div className="rounded-sm border border-line bg-surface p-3 text-xs text-left w-full space-y-1 font-mono">
          <div className="flex justify-between">
            <span className="text-dim">Authenticated Operator:</span>
            <span className="text-fg font-semibold">{user.displayName}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">Assigned Role:</span>
            <span className="font-bold" style={{ color: roleMeta.color }}>
              {roleMeta.label} (Level {roleMeta.level})
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">Available Permissions:</span>
            <span className="text-mute">{user.permissions.length} granted</span>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 pt-2">
        <Button
          variant="outline"
          size="sm"
          leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
          onClick={() => void navigate('/')}
        >
          Return to Overview
        </Button>
        <Button
          variant="primary"
          size="sm"
          leadingIcon={<LogIn className="h-3.5 w-3.5" />}
          onClick={() => void navigate('/login')}
        >
          Authenticate Different Role
        </Button>
      </div>
    </div>
  )
}
