import { createBrowserRouter } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Overview } from '@/features/dashboard/pages/Overview'
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
import { RequireAuth, RequirePermission } from '@/components/auth/RouteGuards'
import { RouteError } from './RouteError'

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
        path: 'targets',
        element: (
          <RequirePermission permission="case.view">
            <Targets />
          </RequirePermission>
        ),
      },
      {
        path: 'operations',
        element: (
          <RequirePermission permission="operation.view">
            <Operations />
          </RequirePermission>
        ),
      },
      {
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
          <RequirePermission permission="file_erasure.request">
            <ErasureWorkflow />
          </RequirePermission>
        ),
      },
      {
        path: 'recovery',
        element: (
          <RequirePermission permission="recovery.view">
            <RecoveryVault />
          </RequirePermission>
        ),
      },
      {
        path: 'residuals',
        element: (
          <RequirePermission permission="evidence.view">
            <ResidualAnalysis />
          </RequirePermission>
        ),
      },
      {
        path: 'assurance',
        element: (
          <RequirePermission permission="operation.view">
            <Assurance />
          </RequirePermission>
        ),
      },
      {
        path: 'certificates',
        element: (
          <RequirePermission permission="operation.view">
            <Certificates />
          </RequirePermission>
        ),
      },
      {
        path: 'certificates/:id',
        element: (
          <RequirePermission permission="operation.view">
            <Certificates />
          </RequirePermission>
        ),
      },
      {
        path: 'audit',
        element: (
          <RequirePermission permission="audit.view">
            <Audit />
          </RequirePermission>
        ),
      },
      {
        path: 'administration',
        element: (
          <RequirePermission permission="user.manage">
            <Administration />
          </RequirePermission>
        ),
      },
      {
        path: 'settings',
        element: <Settings />,
      },
      { path: '*', element: <NotFound /> },
    ],
  },
])
