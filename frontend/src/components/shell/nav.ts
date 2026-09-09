import type { ComponentType } from 'react'
import {
  Activity,
  Archive,
  Crosshair,
  Eraser,
  FileCheck,
  LayoutGrid,
  ScanSearch,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
} from 'lucide-react'
import type { User, PermissionKey, Role } from '@/lib/auth/types'
import { hasPermission } from '@/lib/auth/permissions'

export type NavId =
  | 'overview'
  | 'targets'
  | 'operations'
  | 'erasure'
  | 'recovery'
  | 'residuals'
  | 'assurance'
  | 'certificates'
  | 'audit'
  | 'administration'
  | 'settings'

export interface NavItem {
  id: NavId
  label: string
  path: string
  icon: ComponentType<{ className?: string }>
  /** One-line answer to "what does this screen tell me?" shown in PageHeader. */
  purpose: string
  /** Set when the backend has not shipped the capability the page depends on. */
  pendingBackend?: string
  /** Required permission to see this item. If missing, the item is hidden for the active role. */
  permission?: PermissionKey
  /** Explicit roles allowed to see this item (in addition to permission checking). */
  roles?: readonly Role[]
}

export interface NavSection {
  label: string
  items: NavItem[]
}

/**
 * Single navigation source consumed by the router, the sidebar and the command palette.
 * Order follows the operator workflow: act → verify → prove.
 */
export const ALL_NAV_SECTIONS: readonly NavSection[] = [
  {
    label: 'Workspace',
    items: [
      {
        id: 'overview',
        label: 'Overview',
        path: '/',
        icon: LayoutGrid,
        purpose: 'What requires attention right now.',
      },
      {
        id: 'targets',
        label: 'Targets',
        path: '/targets',
        icon: Crosshair,
        purpose: 'Facts about a filesystem target, separated from advisory analysis.',
        permission: 'case.view',
      },
      {
        id: 'operations',
        label: 'Operations',
        path: '/operations',
        icon: Activity,
        purpose: 'Every operation, its lifecycle state and verification outcome.',
        permission: 'operation.view',
      },
      {
        id: 'erasure',
        label: 'Sanitization',
        path: '/erasure',
        icon: Eraser,
        purpose:
          'Discover → analyze → recommend → configure → review → authorize → erase → verify → prove.',
        permission: 'file_erasure.request',
      },
    ],
  },
  {
    label: 'Verification & Forensics',
    items: [
      {
        id: 'recovery',
        label: 'Recovery Vault',
        path: '/recovery',
        icon: Archive,
        purpose: 'Controlled-recoverable objects, authorization and restore state.',
        permission: 'recovery.view',
      },
      {
        id: 'residuals',
        label: 'Residual Analysis',
        path: '/residuals',
        icon: ScanSearch,
        purpose: 'What remains after erasure, and why.',
        permission: 'evidence.view',
      },
      {
        id: 'assurance',
        label: 'Assurance',
        path: '/assurance',
        icon: ShieldCheck,
        purpose: 'Evidence completeness and the limits of what was verified.',
        permission: 'operation.view',
      },
    ],
  },
  {
    label: 'Evidence & Attestation',
    items: [
      {
        id: 'certificates',
        label: 'Certificates',
        path: '/certificates',
        icon: FileCheck,
        purpose: 'Signed evidence documents and their verification state.',
        permission: 'operation.view',
      },
      {
        id: 'audit',
        label: 'Audit Trail',
        path: '/audit',
        icon: ScrollText,
        purpose: 'Chronological timeline of every recorded forensic event.',
        permission: 'audit.view',
      },
    ],
  },
  {
    label: 'System & Governance',
    items: [
      {
        id: 'administration',
        label: 'Administration',
        // Distinct route: it previously shared '/settings' with the Settings item, so two nav
        // entries highlighted the same destination and the permission-gated one was unreachable.
        path: '/administration',
        icon: Users,
        purpose: 'User and role management.',
        permission: 'user.manage',
      },
      {
        id: 'settings',
        label: 'Settings',
        path: '/settings',
        icon: Settings,
        purpose: 'Appearance, backend connection, curated themes, and operator preferences.',
      },
    ],
  },
]

export const NAV_ITEMS: readonly NavItem[] = ALL_NAV_SECTIONS.flatMap((s) => s.items)

export function findNavByPath(pathname: string): NavItem | undefined {
  if (pathname === '/') return NAV_ITEMS.find((n) => n.path === '/')
  const match = NAV_ITEMS.filter((n) => n.path !== '/').find((n) => pathname.startsWith(n.path))
  return match
}

/**
 * Filter navigation sections and items dynamically according to the authenticated user's permissions and role.
 */
export function getNavSectionsForUser(user: User | null | undefined): NavSection[] {
  if (!user) {
    const overviewItem = ALL_NAV_SECTIONS[0]?.items[0]
    return [
      {
        label: 'Workspace',
        items: overviewItem ? [overviewItem] : [],
      },
    ]
  }

  return ALL_NAV_SECTIONS.map((section) => ({
    label: section.label,
    items: section.items.filter((item) => {
      if (item.roles && !item.roles.includes(user.role)) return false
      if (item.permission && !hasPermission(user, item.permission)) return false
      return true
    }),
  })).filter((section) => section.items.length > 0)
}
