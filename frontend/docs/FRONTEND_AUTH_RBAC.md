# OBLIVION Frontend — Authentication & Role-Based Access Control (RBAC) Specification

## 1. Executive Summary & Security Disclaimer

```
================================================================================
CRITICAL SECURITY NOTICE
================================================================================
1. Frontend authentication, route guards, and permission checks are UX ENFORCEMENT ONLY.
2. The frontend is NEVER a security boundary.
3. The Oblivion backend engine remains SOLELY AUTHORITATIVE for all authentication,
   authorization, permission validation, operation approval, execution gating,
   SafePath containment, and TOCTOU validation.
4. A compromised or modified client cannot bypass server-side security policies.
================================================================================
```

---

## 2. Five-Role RBAC Model

Oblivion establishes five primary operational roles:

| Role | Conceptual Level | Badge Color | Primary Domain & Responsibilities |
|---|---|---|---|
| **`ADMIN`** | **Level 5** | `#ff3d57` (Red) | System administration, security governance, user & role management, sensitive operation approval. |
| **`INVESTIGATOR`** | **Level 4** | `#ff7043` (Orange) | Case discovery, target profiling, evidence analysis, recovery requests (cannot approve or execute destructive erasures). |
| **`OPERATOR`** | **Level 3** | `#ffb020` (Amber) | Approved sanitization and physical erasure execution (only after administrative approval). |
| **`AUDITOR`** | **Level 2** | `#35c88f` (Green) | Independent audit review, evidence hash-chain verification, certificate attestation inspection. |
| **`VIEWER`** | **Level 1** | `#5b9dff` (Blue) | Read-only viewing of cases, operations, assurance reports, and certificates. All operational actions hidden. |

> **Note on Access Levels:** Conceptual access levels (Levels 5 to 1) are informational UI metadata only. Authorization is enforced strictly through granular backend permissions, never by numeric level comparison (`user.level >= 3`).

---

## 3. Granular Permission Matrix

The frontend establishes 24 permission keys mirroring the backend security model:

```typescript
export type PermissionKey =
  // Case permissions
  | 'case.create' | 'case.view' | 'case.update' | 'case.close'
  // Evidence permissions
  | 'evidence.import' | 'evidence.view' | 'evidence.hash' | 'evidence.verify'
  // File erasure permissions
  | 'file_erasure.request' | 'file_erasure.execute'
  // Drive sanitization permissions
  | 'drive_sanitization.request' | 'drive_sanitization.execute'
  // Recovery permissions
  | 'recovery.view' | 'recovery.execute'
  // Operations permissions
  | 'operation.view' | 'operation.request' | 'operation.approve' | 'operation.execute' | 'operation.verify'
  // Audit permissions
  | 'audit.view' | 'audit.verify'
  // Reporting permissions
  | 'report.export'
  // Administration permissions
  | 'user.manage' | 'role.manage' | 'permission.manage' | 'system.configure'
```

### Centralized Permission Helpers (`src/lib/auth/permissions.ts`)
- `hasPermission(user, permission)`: Evaluates single permission presence.
- `hasAnyPermission(user, permissions[])`: Evaluates whether the user holds at least one permission.
- `hasAllPermissions(user, permissions[])`: Evaluates whether the user holds all required permissions.
- `hasRole(user, role | role[])`: Evaluates active role membership.

---

## 4. Critical Separation of Duties (SoD) Pipeline

The console structures high-consequence forensic workflows into four sequential phases:

```
   INVESTIGATOR
        │
        │ 1. REQUEST / INTAKE
        ▼
   OPERATION (PENDING_APPROVAL)
        │
        │ 2. ADMINISTRATIVE APPROVAL
        ▼
      ADMIN
        │
        │ 3. PHYSICAL EXECUTION
        ▼
    OPERATOR
        │
        │ 4. INDEPENDENT VERIFICATION
        ▼
     AUDITOR
```

### Separation Rules:
1. **Investigator**: Permitted to profile targets and request sanitization; destructive execution (`file_erasure.execute`) and approval (`operation.approve`) are hidden.
2. **Admin**: Permitted to approve sanitization policies and manage systems; cannot independently certify their own operations as an auditor.
3. **Operator**: Permitted to execute approved jobs; approval and independent verification actions are hidden.
4. **Auditor**: Permitted to independently verify evidence chains and certificates; execution and approval actions are hidden.
5. **Viewer**: Read-only observation across all screens; all operational and mutation controls are hidden.

---

## 5. Role-Aware Navigation & Workspaces

The shared Oblivion shell dynamically generates navigation based on the authenticated operator's role:

- **`ADMIN` Workspace**: Overview, Targets, Operations, Evidence, Audit, Certificates, Administration, Settings.
- **`INVESTIGATOR` Workspace**: Overview, Targets/Cases, Evidence, Recovery Vault, Residual Analysis, Assurance, Reports.
- **`OPERATOR` Workspace**: Overview, Targets, Sanitization, Operations, Verification, Evidence.
- **`AUDITOR` Workspace**: Overview, Operations, Evidence, Assurance, Certificates, Audit Trail, Reports.
- **`VIEWER` Workspace**: Overview, Operations, Assurance, Certificates (read-only).

---

## 6. Authentication State Machine

The frontend auth layer (`useAuthStore` & `AuthProvider`) manages five explicit states:

```
       ┌───────────────┐
       │    UNKNOWN    │ (Initial mount / probe)
       └───────┬───────┘
               │
               ▼
       ┌───────────────┐
       │AUTHENTICATING │ (Evaluating session / me API)
       └───────┬───────┘
               │
       ┌───────┴───────────────┐
       ▼                       ▼
┌──────────────┐        ┌──────────────┐
│AUTHENTICATED │        │UNAUTHENTICATED│
└──────┬───────┘        └──────┬───────┘
       │                       │
       │ (Logout / Revoked)    │ (Invalid creds / Network)
       ▼                       ▼
┌──────────────┐        ┌──────────────┐
│UNAUTHENTICATED│       │    ERROR     │
└──────────────┘        └──────────────┘
```

- **`UNKNOWN`**: Transient state on boot; renders a non-flashing loading screen.
- **`AUTHENTICATING`**: In-flight login or session verification.
- **`AUTHENTICATED`**: Active operator session verified.
- **`UNAUTHENTICATED`**: Unauthenticated; route guards redirect to `/login`.
- **`ERROR`**: Actionable error banner distinguishing invalid credentials from backend unreachable states.

---

## 7. Frontend Route Guards & Error States

- **`RequireAuth` (`src/components/auth/RouteGuards.tsx`)**: Guards all root routes under `AppShell`. Unauthenticated requests redirect to `/login` preserving the `from` return location.
- **`RequirePermission` (`src/components/auth/RouteGuards.tsx`)**: Guards permission-sensitive routes. Users lacking the required permission render the accessible `src/pages/Unauthorized.tsx` (403 Restricted Operation view).
- **`PermissionGuard` (`src/components/auth/PermissionGuard.tsx`)**: Declarative UI wrapper for conditional button and action rendering.

---

## 8. Development-Only Mock-Auth Adapter (`src/lib/auth/devAuth.ts`)

For local testing and verification without a live backend daemon:
- Strictly guarded by `isDevAuthEnabled()` (`import.meta.env.DEV` or `VITE_MOCK_AUTH === 'true'`).
- Provides 5 development personas:
  - `mock-admin` (`Dr. Sarah Connor`)
  - `mock-investigator` (`Alex Morgan`)
  - `mock-operator` (`David Kim`)
  - `mock-auditor` (`Elena Rostova`)
  - `mock-viewer` (`Public Stakeholder`)
- Stores zero plaintext passwords and is completely stripped in production builds.

---

## 9. Backend API Integration Boundary (`src/lib/api/auth.ts`)

Ready for direct integration with backend FastAPI routes:
- `POST /api/auth/login`: `{ username, password }` → `{ user, session }`
- `POST /api/auth/logout`: Invalidate session
- `GET /api/auth/me`: Retrieve current authenticated principal & permissions
