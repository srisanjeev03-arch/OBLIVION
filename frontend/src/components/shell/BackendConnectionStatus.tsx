import { useState } from 'react'
import { probeHealth } from '@/lib/api/client'
import { useConnection } from '@/lib/api/connection'
import { formatTimestamp } from '@/lib/format'
import { StatusBadge } from '@/components/status/StatusBadge'
import { Tooltip } from '@/components/ui/Tooltip'

export function BackendConnectionStatus() {
  const { state, lastCheckedAt, lastError } = useConnection()
  const [probing, setProbing] = useState(false)

  const handleProbe = async () => {
    if (probing) return
    setProbing(true)
    try {
      await probeHealth()
    } finally {
      setProbing(false)
    }
  }

  const tooltipContent = (
    <div className="flex flex-col gap-1 text-[0.6875rem]">
      <div className="font-semibold text-fg">Backend Connection: {state}</div>
      <div>Last activity: {formatTimestamp(lastCheckedAt)}</div>
      {lastError && (
        <div className="text-danger">
          Error ({lastError.kind}): {lastError.code}
          {lastError.status ? ` [HTTP ${lastError.status}]` : ''}
        </div>
      )}
      <div className="text-mute pt-1">Click to probe health endpoint</div>
    </div>
  )

  return (
    <Tooltip content={tooltipContent} side="bottom">
      <button
        type="button"
        onClick={handleProbe}
        aria-label={`Backend connection status: ${state}`}
        className="inline-flex items-center rounded focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
      >
        <StatusBadge kind="connection" value={state} size="sm" />
      </button>
    </Tooltip>
  )
}
