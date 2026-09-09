import { createBrowserRouter } from 'react-router'
import { AppShell } from '@/components/shell/AppShell'
import { Overview } from '@/pages/Overview'
import { Targets } from '@/pages/Targets'
import { Operations } from '@/pages/Operations'
import { OperationDetail } from '@/pages/OperationDetail'
import { ErasureWorkflow } from '@/pages/ErasureWorkflow'
import { RecoveryVault } from '@/pages/RecoveryVault'
import { ResidualAnalysis } from '@/pages/ResidualAnalysis'
import { Assurance } from '@/pages/Assurance'
import { Certificates } from '@/pages/Certificates'
import { Audit } from '@/pages/Audit'
import { Settings } from '@/pages/Settings'
import { Administration } from '@/pages/Administration'
import { NotFound } from '@/pages/NotFound'
import { Login } from '@/pages/Login'
import { Unauthorized } from '@/pages/Unauthorized'
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
