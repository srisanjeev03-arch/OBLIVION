'use client'

import {
  createContext,
  useCallback,
  useContext,
  useState,
} from 'react'

export type View =
  | 'overview'
  | 'operations'
  | 'targets'
  | 'recovery'
  | 'residual'
  | 'assurance'
  | 'certificates'
  | 'audit'
  | 'system'
  | 'settings'
  | 'workflow'

export interface NavParams {
  operationId?: string
  certificateId?: string
  settingsSection?: string
}

interface Toast {
  id: number
  title: string
  description?: string
  tone?: 'default' | 'success' | 'danger' | 'warning'
}

interface ShellCtx {
  view: View
  params: NavParams
  navigate: (view: View, params?: NavParams) => void
  commandOpen: boolean
  setCommandOpen: (v: boolean) => void
  toasts: Toast[]
  toast: (t: Omit<Toast, 'id'>) => void
  dismissToast: (id: number) => void
}

const Ctx = createContext<ShellCtx | null>(null)

export function ShellProvider({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<View>('overview')
  const [params, setParams] = useState<NavParams>({})
  const [commandOpen, setCommandOpen] = useState(false)
  const [toasts, setToasts] = useState<Toast[]>([])

  const navigate = useCallback((v: View, p: NavParams = {}) => {
    setView(v)
    setParams(p)
    setCommandOpen(false)
  }, [])

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const toast = useCallback(
    (t: Omit<Toast, 'id'>) => {
      const id = Date.now() + Math.random()
      setToasts((prev) => [...prev, { ...t, id }])
      setTimeout(() => dismissToast(id), 4200)
    },
    [dismissToast],
  )

  return (
    <Ctx.Provider
      value={{
        view,
        params,
        navigate,
        commandOpen,
        setCommandOpen,
        toasts,
        toast,
        dismissToast,
      }}
    >
      {children}
    </Ctx.Provider>
  )
}

export function useShell() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useShell must be used within ShellProvider')
  return ctx
}
