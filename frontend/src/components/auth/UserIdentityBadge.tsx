import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router'
import { useAuth } from '@/lib/auth/context'
import { ROLE_METADATA } from '@/lib/auth/types'
import { cn } from '@/lib/cn'

export interface UserIdentityBadgeProps {
  variant?: 'compact' | 'full'
  className?: string
}

export function UserIdentityBadge({ variant = 'compact', className }: UserIdentityBadgeProps) {
  const { user, logout, authState } = useAuth()
  const navigate = useNavigate()

  if (!user || authState !== 'AUTHENTICATED') {
    return null
  }

  const meta = ROLE_METADATA[user.role]
  const initials = user.displayName
    ? user.displayName
        .split(' ')
        .map((n) => n[0])
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : user.username.slice(0, 2).toUpperCase()

  const handleLogout = async () => {
    await logout()
    void navigate('/login', { replace: true })
  }

  if (variant === 'compact') {
    return (
      <div className={cn('flex items-center gap-2 text-xs', className)}>
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[0.625rem] font-bold text-black border border-white/20"
            style={{ backgroundColor: meta.color }}
            title={user.displayName}
          >
            {initials}
          </span>
          <span className="truncate font-medium text-fg hidden lg:inline max-w-[120px]">
            {user.displayName}
          </span>
          <span
            className="px-1.5 py-0.5 rounded-xs text-[0.625rem] font-mono font-bold tracking-wider uppercase border hidden sm:inline"
            style={{
              color: meta.color,
              borderColor: `${meta.color}40`,
              backgroundColor: `${meta.color}15`,
            }}
          >
            {meta.label}
          </span>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          title="Logout of session"
          aria-label="Logout"
          className="rounded-xs p-1 text-dim hover:bg-inset hover:text-danger transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>
    )
  }

  // Full variant for Sidebar footer
  return (
    <div
      className={cn(
        'rounded-md border border-line bg-elevated/40 p-2.5 space-y-2 text-xs',
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[0.6875rem] font-bold text-black"
            style={{ backgroundColor: meta.color }}
          >
            {initials}
          </span>
          <div className="min-w-0">
            <div className="truncate font-semibold text-fg text-xs">{user.displayName}</div>
            <div className="truncate text-[0.625rem] text-dim font-mono">@{user.username}</div>
          </div>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          title="Logout"
          aria-label="Logout"
          className="rounded-xs p-1 text-dim hover:bg-inset hover:text-danger transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex items-center justify-between pt-1 border-t border-line/40 text-[0.625rem]">
        <span
          className="px-1.5 py-0.5 rounded-xs font-mono font-bold tracking-wider uppercase border"
          style={{
            color: meta.color,
            borderColor: `${meta.color}40`,
            backgroundColor: `${meta.color}15`,
          }}
        >
          {meta.label} · LEVEL {meta.level}
        </span>
        <span className="text-mute font-mono">{user.permissions.length} perms</span>
      </div>
    </div>
  )
}
