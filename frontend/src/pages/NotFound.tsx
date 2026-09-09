import { useNavigate } from 'react-router'
import { FileQuestion, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/Button'

export function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center space-y-4">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-inset border border-line text-mute">
        <FileQuestion className="h-7 w-7" />
      </div>

      <div className="space-y-1">
        <h1 className="text-base font-bold text-fg">404 — Screen Not Found</h1>
        <p className="text-xs text-dim max-w-sm">
          The requested forensic console route does not exist in the routing table.
        </p>
      </div>

      <Button
        variant="default"
        size="sm"
        leadingIcon={<ArrowLeft className="h-3.5 w-3.5" />}
        onClick={() => navigate('/')}
      >
        Return to Overview
      </Button>
    </div>
  )
}
