import { useEffect, useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { resolveTheme, usePrefs } from '@/lib/prefs'
import { resolveThemeVariables } from '@/lib/themes'
import { isApiError } from '@/lib/api/errors'
import { AuthProvider } from '@/lib/auth/provider'
import { SessionCacheBoundary } from './SessionCacheBoundary'

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5_000,
        gcTime: 10 * 60_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => {
          if (failureCount >= 2) return false
          // Never hammer the backend on a 401/403: re-issuing a rejected credential is
          // pointless and reads as an auth attack in the audit log.
          if (isApiError(error) && !error.retryable) return false
          return true
        },
      },
      mutations: {
        retry: false,
      },
    },
  })
}

/**
 * The single composition root for cross-cutting providers.
 *
 * Order matters: QueryClientProvider must exist before AuthProvider, because the auth layer and
 * the data layer share the transport, and anything under AuthProvider that reads auth state may
 * also issue queries. Routing lives in App.tsx and stays out of here.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(() => createQueryClient())
  const { theme, presetId, singleAccent, accentMode, density, corner, motion } = usePrefs()

  useEffect(() => {
    const root = document.documentElement
    const resolved = resolveTheme(theme)

    root.classList.remove('dark', 'light')
    root.classList.add(resolved)
    root.style.colorScheme = resolved

    root.setAttribute('data-density', density)
    root.setAttribute('data-corner', corner)
    root.setAttribute('data-motion', motion)
    root.setAttribute('data-preset', presetId)
    root.setAttribute('data-accent-mode', accentMode)

    const vars = resolveThemeVariables(accentMode, presetId, singleAccent)

    root.style.setProperty('--accent', vars.accent)
    root.style.setProperty('--accent-hover', vars.accentHover)
    root.style.setProperty('--accent-active', vars.accentActive)
    root.style.setProperty('--accent-soft', vars.accentSoft)
    root.style.setProperty('--accent-border', vars.accentBorder)
    root.style.setProperty('--accent-fg', vars.accentFg)

    root.style.setProperty('--accent-secondary', vars.accentSecondary)
    root.style.setProperty('--accent-secondary-soft', vars.accentSecondarySoft)
    root.style.setProperty('--accent-supporting', vars.accentSupporting)
    root.style.setProperty('--accent-supporting-soft', vars.accentSupportingSoft)

    root.style.setProperty('--viz-1', vars.viz1)
    root.style.setProperty('--viz-2', vars.viz2)
    root.style.setProperty('--viz-3', vars.viz3)
    root.style.setProperty('--viz-4', vars.viz4)
    root.style.setProperty('--viz-5', vars.viz5)
  }, [theme, presetId, singleAccent, accentMode, density, corner, motion])

  // Follow the OS while the preference is set to 'system'.
  useEffect(() => {
    if (theme !== 'system') return
    if (typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const root = document.documentElement
      root.classList.remove('dark', 'light')
      root.classList.add(mq.matches ? 'dark' : 'light')
      root.style.colorScheme = mq.matches ? 'dark' : 'light'
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [theme])

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <SessionCacheBoundary />
        {children}
      </AuthProvider>
    </QueryClientProvider>
  )
}
