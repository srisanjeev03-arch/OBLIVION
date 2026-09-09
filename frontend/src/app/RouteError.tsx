import { useRouteError } from 'react-router'
import { AlertOctagon } from 'lucide-react'
import { isRouteErrorResponse } from 'react-router'

/**
 * Router-level error boundary. Without an `errorElement`, React Router unmounts the whole tree and
 * the operator sees a blank page with the real reason only in the devtools console.
 */
export function RouteError() {
  const error = useRouteError()

  const detail = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : error instanceof Error
      ? error.message
      : 'Unknown routing failure.'

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-bg p-6 text-fg">
      <div className="flex w-full max-w-lg flex-col gap-3 rounded-lg border border-danger/40 bg-surface p-6">
        <div className="flex items-center gap-2 text-danger">
          <AlertOctagon className="h-5 w-5 shrink-0" aria-hidden="true" />
          <h1 className="text-sm font-semibold tracking-tight">Route failed to render</h1>
        </div>
        <p className="text-xs leading-relaxed text-dim">
          This screen could not be displayed. No data was loaded and no operation was started.
        </p>
        <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded border border-line-strong bg-inset p-2 font-mono text-[0.6875rem] text-mute">
          {detail}
        </pre>
        <button
          type="button"
          onClick={() => {
            window.location.assign('/')
          }}
          className="mt-1 self-start rounded-sm border border-line-strong bg-elevated px-3 py-1.5 text-xs font-medium text-fg hover:border-accent"
        >
          Return to overview
        </button>
      </div>
    </div>
  )
}