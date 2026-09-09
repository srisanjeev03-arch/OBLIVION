import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App } from '@/app/App'
import { Providers } from '@/app/providers'
import { GlobalErrorBoundary } from '@/app/ErrorBoundary'
import '@/styles/globals.css'

const rootEl = document.getElementById('root')
if (!rootEl) {
  throw new Error('Root element #root not found')
}

/**
 * Composition root.
 *
 * GlobalErrorBoundary sits outermost so a render failure shows the branded recovery screen rather
 * than a blank page. Providers (query cache -> auth -> theme) wrap the router, which means every
 * route, including /login, can reach useAuth() and useQuery().
 */
createRoot(rootEl).render(
  <StrictMode>
    <GlobalErrorBoundary>
      <Providers>
        <App />
      </Providers>
    </GlobalErrorBoundary>
  </StrictMode>,
)
