import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertOctagon, RefreshCw, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { PREFS_STORAGE_KEY } from '@/lib/prefs'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

export class GlobalErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  }

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo })
    console.error('Oblivion Global Error Boundary caught an unhandled error:', error, errorInfo)
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleResetState = () => {
    try {
      localStorage.removeItem(PREFS_STORAGE_KEY)
    } catch {
      // ignore
    }
    window.location.reload()
  }

  public override render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen w-screen flex-col items-center justify-center bg-bg p-6 text-fg">
          <div className="flex max-w-xl flex-col items-center gap-4 rounded-lg border border-danger/40 bg-surface p-8 text-center shadow-lg">
            <div className="flex h-12 w-12 items-center justify-center rounded-full border border-danger/40 bg-danger-soft text-danger">
              <AlertOctagon className="h-6 w-6" aria-hidden="true" />
            </div>

            <div className="flex flex-col gap-1.5">
              <h1 className="text-base font-semibold tracking-tight text-fg">
                Console Execution Error
              </h1>
              <p className="text-xs leading-relaxed text-dim">
                An unexpected exception halted rendering in the operator interface. Forensic log
                details are provided below.
              </p>
            </div>

            {this.state.error && (
              <div className="w-full rounded border border-line-strong bg-inset p-3 text-left font-mono text-[0.75rem] text-danger">
                <div className="font-semibold">
                  {this.state.error.name}: {this.state.error.message}
                </div>
                {this.state.error.stack && (
                  <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-[0.6875rem] text-mute">
                    {this.state.error.stack}
                  </pre>
                )}
              </div>
            )}

            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              <Button
                variant="primary"
                size="sm"
                leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
                onClick={this.handleReload}
              >
                Reload console
              </Button>
              <Button
                variant="outline"
                size="sm"
                leadingIcon={<Trash2 className="h-3.5 w-3.5" />}
                onClick={this.handleResetState}
              >
                Reset UI preferences
              </Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
