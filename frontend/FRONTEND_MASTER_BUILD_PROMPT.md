# OBLIVION FRONTEND — MASTER BUILD PROMPT
## Production Forensic Operator Console

PROJECT:
OBLIVION — Intelligent Data Erasure, Recovery & Verification Platform

ROLE:
Build/refine the FRONTEND ONLY. The backend/deletion/recovery engine is separate and authoritative.

CORE UX:
ERASE → VERIFY → PROVE

Do not make Oblivion look like a generic SaaS dashboard, SOC dashboard, AI chatbot, CRUD admin panel, or cyberpunk demo. It should feel like a professional desktop-first digital-forensics/security operator console.

==================================================
1. SOURCE OF TRUTH
==================================================

Before changing code:
- recursively inspect the existing frontend
- read existing frontend documentation
- inspect the existing OpenAPI/API contract
- inspect current routes, components, state management, styling and build configuration
- identify existing Bolt-generated UI and preserve good work where practical
- do not invent backend endpoints
- do not invent backend responses
- do not fabricate data

Backend is authoritative for:
- filesystem facts
- target validation
- deletion
- recovery
- residual analysis
- authorization
- cryptography
- evidence
- certificates
- security decisions

Frontend only:
- renders state
- requests operations
- manages UI state
- presents evidence/results
- provides workflow UX

NEVER:
- delete files from frontend code
- recover files from frontend code
- execute PowerShell/shell/subprocesses
- perform cryptographic key operations
- expose privileged IPC to browser code
- store secrets/recovery keys/private keys in browser storage
- make frontend-only security decisions

==================================================
2. VISUAL IDENTITY
==================================================

Use the existing Bolt visual foundation if present, but make it substantially less generic.

Desired character:
- dark graphite/near-black workspace
- restrained monochrome palette
- thin technical borders
- subtle surface hierarchy
- compact, information-dense layouts
- precise typography
- monospace for technical identifiers/hashes/IDs
- restrained accent
- minimal gradients
- minimal decorative effects
- subtle depth
- restrained motion

Avoid:
- neon cyberpunk
- hacker imagery
- particle backgrounds
- excessive glassmorphism
- excessive rounded cards
- giant hero sections
- identical card grids
- meaningless charts
- fake terminal animations
- generic blue cybersecurity aesthetics
- excessive shadows/gradients

Make it resemble a specialized forensic instrument.

Core visual hierarchy:
1. ACTIVE OPERATION
2. SAFETY STATE
3. EVIDENCE
4. VERIFICATION
5. RESIDUAL RISK
6. CERTIFICATE
7. GENERAL METRICS

==================================================
3. APPLICATION SHELL
==================================================

Build/refine:
- AppShell
- Sidebar
- TopBar
- PageHeader
- PageToolbar
- MainWorkspace
- InspectorDrawer
- CommandPalette
- NotificationCenter
- BackendConnectionStatus
- GlobalErrorBoundary
- KeyboardShortcutOverlay

Navigation:
- Overview
- Targets
- Operations
- Erasure
- Recovery Vault
- Residual Analysis
- Assurance
- Certificates
- Audit
- Settings

Requirements:
- real routing
- clear active route
- keyboard accessible
- collapsed sidebar support
- no dead navigation
- do not expose unfinished backend capabilities as working features

==================================================
4. GLOBAL STATE MODEL
==================================================

Every backend-driven screen must support:
LOADING
EMPTY
AVAILABLE
RUNNING
COMPLETED
FAILED
PARTIAL
BLOCKED
INCONCLUSIVE
UNAVAILABLE
NOT_EVALUATED

Never fabricate:
- users
- dates
- operation IDs
- certificate IDs
- hashes
- file counts
- sizes
- storage metrics
- health metrics
- latency
- timestamps

If backend returns nothing, show a meaningful empty state.

If endpoint is not implemented, show UNAVAILABLE rather than fake functionality.

==================================================
5. API / OPENAPI BOUNDARY
==================================================

Create a clean typed API layer, appropriate to the existing framework.

Suggested:
lib/api/client
lib/api/types
lib/api/errors
lib/api/query
lib/api/mutations

Requirements:
- typed requests/responses
- centralized error handling
- cancellation where appropriate
- safe retry behavior
- mutation pending/success/failure states
- backend connection status
- no direct filesystem APIs
- no invented endpoints

If a feature is not yet supported by backend, keep the UI integration-ready but explicitly unavailable.

==================================================
6. OVERVIEW
==================================================

Overview answers:
“What requires my attention right now?”

Do not create a generic metric-card wall.

Primary sections:

ACTIVE OPERATION
- operation ID
- target
- mode
- current state
- lifecycle
- progress only if backend provides it
- elapsed time if backend provides it
- safety status
- verification status
- next action

ATTENTION REQUIRED
- failures
- partial operations
- inconclusive verification
- residual findings
- authorization required
- backend unavailable

EVIDENCE SNAPSHOT
- evidence count
- latest evidence
- evidence-chain state if provided

ASSURANCE SNAPSHOT
- VALIDATED
- PARTIAL
- INCONCLUSIVE
- FAILED
- NOT_EVALUATED

RECENT OPERATIONS
Use compact table/list, not repetitive cards.

SYSTEM HEALTH
Only real backend data.

==================================================
7. TARGETS / TARGET ANALYSIS
==================================================

Clearly separate:

FACTS
AI ANALYSIS
RECOMMENDATION

Facts are authoritative.
AI is advisory.
Recommendation must be visibly labeled.

Show when available:
- target path
- target ID
- filesystem
- volume
- volume identity
- size
- file count
- directory count
- file types
- timestamps
- attributes
- SHA-256
- storage characteristics
- reparse status
- sensitivity
- safety status
- baseline

Components:
- TargetAnalysis
- TargetStorageProfile
- ScopeBoundaryCard
- HashComparison
- PolicyRecommendation
- EvidenceInspector

Technical IDs/hashes should use monospace.

==================================================
8. ERASURE WORKFLOW
==================================================

Workflow:
DISCOVER → ANALYZE → RECOMMEND → CONFIGURE → REVIEW → AUTHORIZE → ERASE → VERIFY → PROVE

The frontend does NOT perform erasure.

DISCOVER:
- choose target through supported backend workflow
- show facts
- validate scope

ANALYZE:
- facts
- storage
- sensitivity
- baseline
- warnings

RECOMMEND:
- recommended method
- reason
- policy
- capability
- limitations
- AI advisory label

CONFIGURE:
- only backend-supported methods

REVIEW:
- exact target
- exact scope
- operation mode
- method
- warnings
- limitations
- authorization requirements
- deliberate confirmation

AUTHORIZE:
- operator
- required role
- authorization state
- history if supplied

ERASE:
- live backend state
- never fabricate percentage progress

VERIFY:
- exactly what was checked
- result
- scope
- limitations
- recovery/residual status

PROVE:
- evidence
- assurance
- certificate

==================================================
9. OPERATIONS
==================================================

Operations table:
- Operation ID
- Target
- Mode
- State
- Started
- Duration
- Verification
- Assurance
- Result

Filters:
- state
- operation type
- date
- assurance
- verification
- target

Selecting an operation opens InspectorDrawer.

Inspector:
- summary
- lifecycle
- target
- authorization
- evidence
- failures
- verification
- residual status
- assurance
- certificate

Lifecycle:
CREATED
→ ANALYZING
→ READY
→ ERASING
→ VERIFYING
→ RECOVERY_TEST
→ RESIDUAL_SCAN
→ ASSESSING
→ CERTIFYING
→ COMPLETED

Also support:
FAILED / PARTIAL / INCONCLUSIVE / BLOCKED / CANCELLED

Only display states actually supplied by backend.

==================================================
10. RECOVERY VAULT
==================================================

Show:
- recovery object ID
- source operation
- target
- creation time
- encryption status
- authorization state
- retention/expiration
- restore state
- restore history

States:
LOCKED
AUTHORIZATION_REQUIRED
AVAILABLE
EXPIRED
RESTORING
RESTORED
FAILED

Restore UX:
REQUEST → AUTHORIZE → DECRYPT → RESTORE → VERIFY HASH → COMPLETE

Never expose keys or plaintext recovery material.

Frontend must never decrypt.

==================================================
11. RECOVERY
==================================================

When backend supports recovery, show:
- recovery target
- scan scope
- filesystem
- scan mode
- file types
- scan state
- recovered items
- confidence
- evidence

Results:
RECOVERED
NOT_DETECTED
PARTIAL
FAILED
INCONCLUSIVE

Inspector:
- recovered filename
- type
- size
- source relationship
- confidence
- hash
- evidence
- destination

Clearly distinguish:
“not detected in the tested scope”
from:
“provably unrecoverable.”

==================================================
12. RESIDUAL / REMNANT ANALYSIS
==================================================

Core question:
“What remains, and why?”

Show:
- scan scope
- techniques
- baseline comparison
- finding count
- sensitivity
- risk
- relationship
- evidence

Classifications:
DIRECT_MATCH
LIKELY_RELATED
POSSIBLY_RELATED
UNRELATED
INCONCLUSIVE

ResidualFinding inspector:
- finding ID
- type
- location/scope
- similarity
- sensitivity
- risk
- relationship
- evidence
- explanation

Include a prominent:
“Why is this still here?”

Only show backend-provided explanations.

==================================================
13. ASSURANCE
==================================================

Do not reduce assurance to a green check.

Show:
- overall assurance
- validation status
- evidence completeness
- verification
- recovery
- residual result
- limitations

Statuses:
VALIDATED
PARTIAL
INCONCLUSIVE
FAILED
NOT_EVALUATED

Evidence checklist:
- Target identified
- Scope validated
- Baseline captured
- Hash verified
- Policy selected
- Erasure executed
- Verification completed
- Recovery evaluated
- Residuals evaluated
- Evidence captured
- Certificate generated

Each row:
- status
- evidence reference
- timestamp if supplied
- explanation

==================================================
14. CERTIFICATES
==================================================

Certificate view should look like a cryptographic evidence document.

Show:
- certificate ID
- operation ID
- target ID
- scope
- operation type
- method
- hashes
- verification
- recovery result
- residual result
- assurance
- evidence references
- signature status
- public verification information

Verification:
VALID
INVALID
UNVERIFIED
UNAVAILABLE

If invalid/tampered, make the state unmistakable.

==================================================
15. AUDIT
==================================================

Audit should feel like a forensic timeline.

Columns:
- timestamp
- event ID
- operation ID
- actor
- event type
- result
- evidence ID
- hash-chain status if supplied

Possible event types:
TARGET_DISCOVERED
TARGET_ANALYZED
BASELINE_CAPTURED
HASH_CALCULATED
POLICY_RECOMMENDED
AUTHORIZED
ERASURE_STARTED
ERASURE_COMPLETED
ERASURE_FAILED
VERIFICATION_COMPLETED
RECOVERY_STARTED
RECOVERY_COMPLETED
RESIDUAL_SCAN
ASSURANCE
CERTIFICATE

Click event → InspectorDrawer.

Show relationships when backend supplies them.

Never show secrets.

==================================================
16. EVIDENCE COMPONENTS
==================================================

Create reusable:
- EvidenceId
- EvidenceInspector
- EvidenceChain
- EvidenceRelationshipGraph
- EvidenceTimeline
- EvidenceReference
- EvidenceStatus
- EvidenceHash
- OperationLifecycle
- OperationInspector
- AuditEventInspector
- CertificateInspector

Technical identifiers:
- monospace
- copy-to-clipboard
- copy feedback

==================================================
17. DESIGN SYSTEM
==================================================

Reusable primitives:
- Button
- IconButton
- Input
- Select
- Checkbox
- Radio
- Switch
- Tabs
- Badge
- StatusBadge
- Tooltip
- Dialog
- Drawer
- Dropdown
- DataTable
- Pagination
- FilterBar
- Breadcrumbs
- ProgressIndicator
- Stepper
- Timeline
- Code/HashField
- LoadingState
- EmptyState
- ErrorState
- UnavailableState

All interactive components need:
- hover
- active
- focus
- disabled
- loading when relevant
- error when relevant

==================================================
18. STATUS UX
==================================================

Never communicate state using color alone.

Every important status has:
- text
- icon
- semantic styling

Keep status semantics consistent across every page.

==================================================
19. COMMAND PALETTE
==================================================

Ctrl/Cmd + K

Commands:
- Overview
- Targets
- Operations
- Erasure
- Recovery Vault
- Residual Analysis
- Assurance
- Certificates
- Audit
- Settings
- Refresh
- Open active operation
- Search operations
- Search targets

Keyboard:
- arrows
- Enter
- Escape

No dead commands.

==================================================
20. DESTRUCTIVE ACTION UX
==================================================

Destructive operations need stronger confirmation than normal actions.

Confirmation must show exact backend data:
- target
- scope
- count
- size
- mode
- method
- warnings
- limitations
- authorization

Never use only:
“Are you sure?”

Use a specific confirmation such as:
“Delete 1 file / 2.4 MB from the selected controlled scope?”

Only use real backend values.

Buttons need:
- pending
- disabled while executing
- success/failure result
- retry where safe

==================================================
21. ACCESSIBILITY
==================================================

Implement:
- keyboard navigation
- visible focus
- semantic HTML
- accessible dialogs
- accessible drawers
- labels
- error association
- reduced motion
- sufficient contrast
- status announcements where useful

Never make critical workflows mouse-only.

==================================================
22. RESPONSIVE
==================================================

Primary target:
desktop 1280px+

Also support:
1024px+
tablet where practical

Narrow layouts:
- collapsible sidebar
- inspector becomes overlay
- tables adapt intentionally
- critical actions remain visible
- no accidental clipping

Desktop forensic workflow is the priority.

==================================================
23. MOTION
==================================================

Motion communicates state only.

Use subtle:
- drawer transitions
- state transitions
- loading indicators
- confirmation transitions

Avoid:
- animated backgrounds
- particles
- constant pulsing
- excessive chart animation

Respect prefers-reduced-motion.

==================================================
24. SETTINGS
==================================================

Appearance:
- light/dark/system
- accent
- density
- corner radius
- motion preference

Security UX:
- confirmation behavior
- session settings if backend exposes them

Evidence:
- evidence display/export preferences where supported

Backend:
- connection state
- API endpoint if appropriate
- health state

Never expose secrets.

==================================================
25. PROTOTYPE CLEANUP
==================================================

Remove:
- Made in Bolt
- fictional names
- fake dates
- fake IDs
- fake certificates
- fake hashes
- fake metrics
- fake health
- fake latency
- unexplained demo data
- fake real-time telemetry

If a demo mode is later required, isolate it explicitly and never mix it with production state.

==================================================
26. COMPONENT ARCHITECTURE
==================================================

Tier 1:
AppShell
Sidebar
TopBar
CommandPalette
PageHeader
PageToolbar
InspectorDrawer
StatusBadge
ProgressIndicator
LoadingState
EmptyState
ErrorState
UnavailableState
DataTable
FilterBar
EvidenceId
EvidenceInspector
EvidenceChain
OperationLifecycle
OperationInspector
TargetAnalysis
TargetStorageProfile
PolicyRecommendation
ErasureStepper
ErasureReview
ErasureProgress
AssuranceChecklist
ResidualFinding
CertificateInspector
AuditEventInspector

Tier 2:
OperationTimeline
EvidenceRelationshipGraph
ScopeBoundaryCard
AuthorizationHistory
CertificateVerification
HashComparison
ResidualScopeBanner
BackendConnectionStatus
SystemHealth
NotificationCenter
KeyboardShortcutOverlay

Defer:
3D visualizations
animated network maps
particle effects
AI chat assistant
fake telemetry
digital twin visualization

==================================================
27. DEMO JOURNEY
==================================================

The UI must support this future operator story:

1. Discover controlled dataset
2. Analyze target
3. Show sensitivity if available
4. Show recommendation
5. Review exact scope
6. Authorize
7. Execute deletion
8. Verify
9. Attempt recovery
10. Analyze remnants
11. Explain residuals
12. Show assurance
13. Generate certificate
14. Verify certificate
15. Demonstrate tamper detection

The UI should make this understandable without verbal explanation of every screen.

==================================================
28. PRODUCTION QUALITY
==================================================

Before declaring frontend complete:

- build passes
- typecheck passes
- lint passes
- no console errors
- no dead routes
- no dead buttons
- no fake data
- no unsupported API calls
- no direct filesystem access
- no shell execution
- no secrets in browser storage
- keyboard navigation works
- loading/error/empty states exist
- responsive behavior works
- prototype artifacts removed

==================================================
29. IMPLEMENTATION STRATEGY
==================================================

Do NOT rewrite the whole application in one uncontrolled generation.

Pass 1:
Reconnaissance and architecture report.

Pass 2:
App shell + design system.

Pass 3:
Remove demo data.

Pass 4:
API/OpenAPI boundary.

Pass 5:
Overview + Targets + Operations.

Pass 6:
Erasure workflow.

Pass 7:
Recovery Vault + Recovery UI.

Pass 8:
Residual Analysis.

Pass 9:
Assurance + Certificates + Audit.

Pass 10:
Accessibility + responsive + interaction audit.

Pass 11:
Visual refinement.

Pass 12:
Production audit.

After every major pass:
- build
- typecheck
- lint
- fix regressions
- inspect the result
- stop before next major pass

==================================================
30. FIRST EXECUTION — IMPORTANT
==================================================

For the FIRST execution only:

DO NOT implement all pages.

First:
1. inspect frontend
2. identify framework
3. read frontend docs
4. inspect OpenAPI/API contract
5. audit fake/demo data
6. audit routes
7. audit components
8. audit state management
9. audit accessibility
10. audit build/typecheck/lint
11. produce reconciliation report
12. propose staged implementation

Then implement ONLY:
- AppShell
- Sidebar
- TopBar
- CommandPalette
- PageHeader
- status system
- LoadingState
- EmptyState
- ErrorState
- UnavailableState
- API client boundary
- Overview shell
- Operations shell
- Targets shell

Do not implement destructive functionality.

Do not invent backend endpoints.

STOP after the first pass.

Report:
- files created
- files modified
- routes
- components
- API assumptions
- backend dependencies
- build result
- typecheck result
- lint result
- known issues
- next recommended pass

==================================================
31. CORE UX TEST
==================================================

For every important screen, the operator should be able to answer:

WHAT am I acting on?
WHY is this recommended?
WHAT will happen?
WHAT actually happened?
WHAT was verified?
WHAT remains uncertain?
WHAT evidence proves the result?

If the UI cannot answer those questions, improve the information hierarchy.
