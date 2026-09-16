import { createBrowserRouter } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Overview } from '@/features/dashboard/pages/Overview'
import { ObjectiveSelection } from '@/features/objective/pages/ObjectiveSelection'
import { Targets } from '@/features/discovery/pages/Targets'
import { Operations } from '@/features/operations/pages/Operations'
import { OperationDetail } from '@/features/operations/pages/OperationDetail'
import { ErasureWorkflow } from '@/features/operations/pages/ErasureWorkflow'
import { RecoveryVault } from '@/features/recovery/pages/RecoveryVault'
import { ResidualAnalysis } from '@/features/residual/pages/ResidualAnalysis'
import { Assurance } from '@/features/assurance/pages/Assurance'
import { Certificates } from '@/features/certificates/pages/Certificates'
import { Audit } from '@/features/audit/pages/Audit'
import { Settings } from '@/features/settings/pages/Settings'
import { Administration } from '@/features/administration/pages/Administration'
import { NotFound } from '@/app/NotFound'
import { Login } from '@/features/authentication/pages/Login'
import { Unauthorized } from '@/features/authentication/pages/Unauthorized'
import {
  RequireAuth,
  RequireNavPermission,
  RequirePermission,
} from '@/components/auth/RouteGuards'
import { RouteError } from './RouteError'

/**
 * Every route below resolves to a real page. Gating comes from `nav.ts` via `RequireNavPermission`
 * wherever the route is also a navigation destination, so a sidebar entry and its guard can never
 * disagree. `RequirePermission` is used only for the two detail routes that are not nav items, and
 * `nav-parity.test.ts` pins them to their parent's permission.
 */
export const router = createBrowserRouter([
  { path: '/login', element: <Login /> },
  { path: '/unauthorized', element: <Unauthorized /> },
  {
    path: '/',
    errorElement: <RouteError />,
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Overview /> },
      {
        // Guided entry point: it only navigates, and every destination carries its own guard.
        path: 'objective',
        element: (
          <RequireNavPermission navId="objective">
            <ObjectiveSelection />
          </RequireNavPermission>
        ),
      },
      {
        path: 'targets',
        element: (
          <RequireNavPermission navId="targets">
            <Targets />
          </RequireNavPermission>
        ),
      },
      {
        path: 'operations',
        element: (
          <RequireNavPermission navId="operations">
            <Operations />
          </RequireNavPermission>
        ),
      },
      {
        // Not a navigation destination, so it cannot inherit one. Must stay equal to `operations`.
        path: 'operations/:id',
        element: (
          <RequirePermission permission="operation.view">
            <OperationDetail />
          </RequirePermission>
        ),
      },
      {
        path: 'erasure',
        element: (
          <RequireNavPermission navId="erasure">
            <ErasureWorkflow />
          </RequireNavPermission>
        ),
      },
      {
        path: 'recovery',
        element: (
          <RequireNavPermission navId="recovery">
            <RecoveryVault />
          </RequireNavPermission>
        ),
      },
      {
        path: 'residuals',
        element: (
          <RequireNavPermission navId="residuals">
            <ResidualAnalysis />
          </RequireNavPermission>
        ),
      },
      {
        path: 'assurance',
        element: (
          <RequireNavPermission navId="assurance">
            <Assurance />
          </RequireNavPermission>
        ),
      },
      {
        path: 'certificates',
        element: (
          <RequireNavPermission navId="certificates">
            <Certificates />
          </RequireNavPermission>
        ),
      },
      {
        // Deep link to one certificate. Same guard as the certificates destination above; the page
        // reads the id from the route instead of ignoring it.
        path: 'certificates/:certificateId',
        element: (
          <RequirePermission permission="operation.view">
            <Certificates />
          </RequirePermission>
        ),
      },
      {
        path: 'audit',
        element: (
          <RequireNavPermission navId="audit">
            <Audit />
          </RequireNavPermission>
        ),
      },
      {
        path: 'administration',
        element: (
          <RequireNavPermission navId="administration">
            <Administration />
          </RequireNavPermission>
        ),
      },
      {
        // Console preferences: appearance and connection target. Holds no backend data, so it is
        // reachable by any authenticated operator by design.
        path: 'settings',
        element: <Settings />,
      },
      { path: '*', element: <NotFound /> },
    ],
  },
])
