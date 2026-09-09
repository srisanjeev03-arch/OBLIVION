import { RouterProvider } from 'react-router'
import { router } from './router'

/**
 * Routing only.
 *
 * Providers (query cache, auth, theme) are mounted once, in `main.tsx`, via `Providers`. Keeping
 * them out of this component is what prevents a second, provider-less tree from shipping: the
 * previously released build rendered `<App />` without `AuthProvider`, so every `useAuth()` call
 * threw at startup.
 */
export function App() {
  return <RouterProvider router={router} />
}
