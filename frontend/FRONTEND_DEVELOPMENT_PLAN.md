# OBLIVION FRONTEND — AUDIT FINDINGS & DEVELOPMENT PLAN

Date: 2026-09-09 · Scope: `h:\frontend` (canonical tree) · Mode: read-only audit → remediation plan
Governance: `FRONTEND_MASTER_BUILD_PROMPT.md`, `FRONTEND_REVIEW_CHECKLIST.md`, `contract/OPENAPI.yaml`, `docs/FRONTEND_AUTH_RBAC.md`

---

## 0. VERDICT

**The console does not run.** Every route — including `/login` — renders React Router's raw internal
error screen. This was proven empirically, not inferred.

Captured DOM when mounting the shipped `<App />`:

```html
<h2>Unexpected Application Error!</h2>
<h3 style="font-style: italic;">useAuth must be used within an AuthProvider</h3>
<pre>Error: useAuth must be used within an AuthProvider
    at useAuth (H:/frontend/src/lib/auth/context.ts:9:11)
    at RequireAuth (H:/frontend/src/components/auth/RouteGuards.tsx:12:31)</pre>
```

The critical insight: **the quality gate reports green while the product is 100% broken.**

| Gate | Command | Result | Meaning |
|---|---|---|---|
| Typecheck | `tsc -p tsconfig.json --noEmit` | **EXIT 0** | TS cannot see a missing provider |
| Unit tests | `vitest run` | **84 passed / 11 files** | No test renders `<App/>` or a route |
| Build | `vite build` | **EXIT 0**, 536 kB chunk | Bundler is indifferent to wiring |
| Lint | `eslint . --max-warnings 0` | **EXIT 2 — CRASH** | Broken for an unrelated reason (F-04) |
| Runtime | mount `<App />` | **BROKEN** | Covered by no gate at all |

`npm run check` fails today only because of the lint crash. **If that crash were merely ignored,
`check` would pass on a completely non-functional application.** Closing that gap with a routed
smoke test is the single most important process change in this plan.

### Scorecard against `FRONTEND_REVIEW_CHECKLIST.md`

| Area | Status | Blocking findings |
|---|---|---|
| Architecture | ❌ FAIL | Provider tree unmounted; two duplicate provider stacks; error boundary dead |
| Visual | ✅ PASS | Genuine forensic-console identity; restrained palette; mono IDs |
| Data | ❌ FAIL | Fabricated cert IDs, hashes, policy IDs, timestamps, compliance badges |
| Erasure | ❌ | Invented policy catalogue sent to backend |
| Recovery | ❌ | Asserts "RESTORE COMPLETED & VERIFIED" from a `void` mutation |
| Residual | ❌ | Dead search + dead filter over a permanently empty table |
| Assurance/Cert | ❌❌ | Worst offender: UI self-attests a cryptographic verification it never ran |
| Audit | ❌ | Dead controls, no ingestion, filters wired to nothing |
| Accessibility | ⚠️ PARTIAL | Good bones; no live-region/toast; reduced-motion unverified |
| Production | ❌ FAIL | Lint crash, dead routes, dead controls, 191 MB stray trees, **no git repo** |

### What is already good — preserve, do not rewrite

Several foundations are genuinely production-grade, and the plan builds on them:

- **`lib/api/client.ts`** — single transport, timeout+signal merge, all failures normalised to
  `ApiError`, feeds the passive connection tracker, refuses to invent a health endpoint.
- **`lib/api/capabilities.ts`** — the "in-contract vs. implemented" two-axis gate that short-circuits
  to `UNAVAILABLE` *before* touching the network is an excellent, honest pattern.
- **`lib/status.ts` + `components/states/index.tsx`** — a real screen-state vocabulary with correct
  `role="status"`/`role="alert"` and colour-independent badges. The primitives are right; pages
  simply don't use them.
- **`lib/themes.ts` + `lib/prefs.ts`** — persisted, typed, security-scoped, 8 passing tests.
- **`lib/auth/permissions.ts` + `store.ts`** — clean RBAC model, 19 passing tests, correct
  "backend remains authoritative" disclaimer.
- **`components/shell/nav.ts`** — one navigation source for sidebar + palette + guards with
  `pendingBackend` markers. Right shape; wrong targets.
- **Visual identity** — already meets the "forensic instrument, not SaaS dashboard" brief.

---

## 1. BASELINE: WHAT ACTUALLY EXISTS

`h:\frontend` is the live project: it owns `package.json`, `src/`, `contract/`, `docs/` and is what
`vite build` compiles. `frontend oblivion\frontend\` is the salvaged legacy tree (F-24) and is
**not** the target. All work happens in `h:\frontend\src`.

### 1.1 Route table (`src/app/router.tsx`)

| Path | Guard | Element | Problem |
|---|---|---|---|
| `/login` | — | `Login` | **crashes** on `useAuth` |
| `/unauthorized` | — | `Unauthorized` | **crashes** on `useAuth` |
| `/` | `RequireAuth` | `AppShell` | **crashes** on `useAuth` |
| `/targets` | `case.view` | `Targets` | behind crash |
| `/operations` | `operation.view` | `Operations` | behind crash |
| `/operations/:id` | `operation.view` | `OperationDetail` | behind crash |
| `/erasure` | `file_erasure.request` | `ErasureWorkflow` | behind crash |
| `/recovery` | `recovery.view` | `RecoveryVault` | behind crash |
| `/residuals` | `evidence.view` | `ResidualAnalysis` | dead filters |
| `/assurance` | `operation.view` | `Assurance` | fabricated compliance claim |
| `/certificates` | `operation.view` | `Certificates` | fully fabricated screen |
| `/certificates/:id` | `operation.view` | `Certificates` | **DEAD ROUTE** — `:id` ignored |
| `/audit` | `audit.view` | `Audit` | dead filters |
| `/settings` | **none** | `Settings` | unguarded, inconsistent |
| `*` | — | `NotFound` | ok |

`nav.ts` advertises an **Administration / "User and role management"** item gated on `user.manage`
that resolves to `/settings`. There is no administration route and no `Users.tsx`. That is dead
navigation (master prompt §3) and misrepresents a capability the console does not have.

### 1.2 Defined but referenced by nobody

| File | Status |
|---|---|
| `src/app/providers.tsx` | **the only mount of `AuthProvider`** — imported by nobody (root cause F-01) |
| `src/app/ErrorBoundary.tsx` | `GlobalErrorBoundary` defined, never mounted |
| `src/lib/auth/mock.ts` | orphaned; would violate the repo's own `no-restricted-imports` ban on `**/mock*` |
| `src/lib/auth/mockAdapter.ts` | orphaned near-duplicate of `devAuth.ts` |
| `src/lib/auth/index.ts` | barrel nobody imports |
| `toScreenState()` (`queries.ts:91`) | the canonical state mapper — **zero call sites** |
| `queryKeys.certificate` | unused |
| `Users` / `SystemStatus` / `DaemonMonitor` / `Capabilities` pages | **do not exist**, referenced by nav/docs |

### 1.3 Required shell / design-system items that are missing

Master prompt §3, §17, §26 require these; none exist:

`NotificationCenter` · `KeyboardShortcutOverlay` · toast system · `Radio` · `Dropdown` ·
`Pagination` · `FilterBar` · `ProgressIndicator` · `Stepper` · `Timeline` · `HashField` ·
`EvidenceInspector` · `EvidenceChain` · `EvidenceTimeline` · `OperationLifecycle` ·
`OperationInspector` · `AuditEventInspector` · `CertificateInspector` · `TargetAnalysis` ·
`PolicyRecommendation` · `AssuranceChecklist` · `SystemHealth` · shared skeletons.

(`InspectorDrawer` exists and is good. Several items above are correctly deferred until the backend
ships — but `Stepper`, `EvidenceChain`, `OperationLifecycle` and the toast layer are core to the
ERASE→VERIFY→PROVE story and are needed now.)

---

## 2. FINDINGS REGISTER

Severity: **P0** blocks the app or falsifies evidence · **P1** violates governance / misleads
operators · **P2** quality debt.



### P0 — Application is non-functional

**F-01 · AuthProvider is never mounted → every route crashes.**
`main.tsx` renders `<App/>`; `App.tsx` renders `QueryClientProvider` → `RouterProvider`. Nothing
mounts `AuthProvider` — that only happens in `providers.tsx`, which is imported by nobody. `useAuth()`
(`context.ts:9`) throws. Sites that therefore crash: `RouteGuards.tsx:12,44`, `Login.tsx:26`,
`Unauthorized.tsx:9`, `Sidebar.tsx:23`, `PermissionGuard.tsx:27`, `SeparationOfDuties.tsx:58`,
`UserIdentityBadge.tsx:13`. React Router silently converts the throw into its default error screen,
which is why no gate caught it. → *Phase 1.*

**F-02 · Two divergent provider stacks with different semantics.**
`providers.tsx` builds a `QueryClient` with a considered retry policy and mounts `AuthProvider`, but
never applies accent CSS variables. `App.tsx` builds a **second, different** `QueryClient` (different
retry / gcTime) and applies accent variables but mounts no `AuthProvider`. Whichever survives, the
duplicate must go — split-brain here silently changes retry behaviour for destructive mutations. → *Phase 1.*

**F-03 · `GlobalErrorBoundary` is dead code.**
Defined at `ErrorBoundary.tsx:16`, mounted nowhere. Any throw outside the router is a white screen;
inside the router it is the default screen. Governance §3 lists it as a required shell component. → *Phase 1.*

**F-04 · `npm run lint` crashes (exit 2) — the gate cannot run.**
`eslint.config.js:9` ignores only `['dist','node_modules','coverage','src/lib/api/schema.d.ts']`, so
ESLint walks `frontend oblivion/frontend/postcss.config.js` — plain JS with no `parserOptions` — and
`@typescript-eslint/await-thenable` (from `recommendedTypeChecked`) aborts the entire run. Until fixed,
"lint passes" is unverifiable and `npm run check` is permanently red. → *Phase 0.*

**F-05 · Auth cannot work even after F-01: no credential is ever transmitted.**
Grep for `Authorization|Bearer|session\.token` across `src/` returns **zero** request-header usage.
`devAuth` stores `session.token`; `client.ts` never reads it. A token-based backend can never be
authenticated against. → *Phase 3, decision D-1.*

**F-06 · Cross-origin session auth is structurally impossible as configured.**
`env.ts` defaults `apiBaseUrl` to `http://127.0.0.1:8000`; dev server is `localhost:3000`;
`client.ts:56` sends `credentials: 'same-origin'` — which means **no cookies on a cross-origin
request**; and `vite.config.ts` defines **no proxy**. Meanwhile `api/auth.ts` assumes cookie sessions
(`/api/auth/login` then `/api/auth/me`). Three independent failure modes. → *Phase 3.*

**F-07 · Three competing auth implementations.**
`provider.tsx`+`devAuth.ts` (live), `mock.ts` (orphan), `mockAdapter.ts` (orphan). Dead seams get
revived by the next contributor. → *Phase 3.*

**F-08 · No test renders the application.**
84 tests pass over `format`, `themes`, `status`, `errors`, `capabilities`, `ai.store`, auth `store`,
`permissions`, `Button`, `Badge`, `StatusBadge`, `PageStatePanel`, `EvidenceHash`. **None** imports
`App`, `router`, `AppShell`, `RouteGuards` or any page. This is precisely why a total failure shipped
green. → *Phase 1 + Phase 9.*

**F-09 · No git repository.** `h:\frontend` has no `.git`: no history, no bisect, no review surface,
and no safety net for a 10-phase refactor. → *Phase 0, task 0.1.*

### P1 — Fabricated evidence (governance-critical)

These are not cosmetic. In a forensic assurance product, a UI that asserts verification it did not
perform is the most serious class of defect: it can cause an operator to certify data destruction
that never happened.

**F-10 · `Certificates.tsx` is an entirely synthetic evidence document.**
- `useState('cert-8841-a9f-2026')` — hardcoded certificate ID (line 13).
- Hardcoded SHA-256 digest, Merkle root and Ed25519 signature strings rendered as real evidence.
- Hardcoded `Timestamp: 2026-09-07T18:44:00Z` and `Attestation Authority: Oblivion Enterprise Root CA`.
- Verification state initialised to `valid: true` **before any verification occurs**.
- A **"Simulate Payload Tamper"** button that fabricates a failure state on demand.
- When `certificates.verify` is `UNAVAILABLE`, it **fakes success locally**
  (`setVerificationResult({ valid: true, … })`) — the console displays a cryptographic verification
  it demonstrably never performed.

Violates: "No fabricated IDs/hashes", "No fake certificates", Verification ∈
{VALID, INVALID, UNVERIFIED, UNAVAILABLE}, "Tamper state". → *Phase 6.*

**F-11 · `ErasureWorkflow.tsx` invents a policy catalogue and sends it to the backend.**
`pol-nist-800-88-purge`, `pol-dod-5220-22-m`, `pol-bld-zero-verify` (lines 44/51/58) are hardcoded;
`selectedPolicyId` defaults to the first (line 78). The OpenAPI contract exposes **no**
`GET /api/policies`, so these IDs are invented and then transmitted as authorization material for a
destructive operation. Also asserts "This confirmation is cryptographically timestamped in the audit
log" (line 288) — a frontend claim about backend cryptography. → *Phase 6.*

**F-12 · Invented fallback values where the backend returned nothing.**
`OperationDetail.tsx:186` `{op.mode || 'COMPLETE_ERASURE'}` · `:194` `{op.policy_id || 'pol-nist-800-88-purge'}` ·
`Operations.tsx:217` / `:223` — identical. An absent value must render `NOT_EVALUATED`/`—`, never a
plausible-looking default. This is the easiest way to silently falsify an assurance record. → *Phase 6.*

**F-13 · `RecoveryVault.tsx` asserts a restore it cannot know about.**
The success panel reads "RESTORE COMPLETED & VERIFIED … post-restoration SHA-256 matches the original
escrow digest", derived solely from `mutation.isSuccess` while `useRestoreRecoveryObjectMutation` is
typed `void` — there is no response to base that sentence on. Also: hardcoded default destination
`C:\Oblivion\Restored\recovered_payload.dat`, and the mutation is constructed with
`selectedObject?.id || ''`, so a state race can target the wrong object. → *Phase 6.*

**F-14 · `Assurance.tsx` makes a compliance claim with zero data.**
Ten hardcoded assurance vectors all `NOT_EVALUATED`, plus rendered badges **"ISO 27040 COMPLIANT"**
and "NIST SP 800-88". The `assurance.get` capability exists in the registry but is never called.
A frontend must never assert standards compliance. → *Phase 6.*

**F-15 · `Overview.tsx` is decorative, not data-driven.**
Every counter is a literal `0`; the "Attention Required" row is static markup; assurance
`StatusBadge`s are decoration; the operation inspector hardcodes `value="CREATED"`. No query is used.
Violates "no fabricated metrics" and §6 (Overview must answer "what requires my attention now?"). → *Phase 5.*

**F-16 · Dead filters and dead controls.**
`Audit.tsx` and `ResidualAnalysis.tsx` render `<DataTable rows={[]} />` while wiring `searchQuery`
and `resultFilter` state to nothing — the inputs are functional React state with no effect, and
`onRowSelect` is unreachable. Violates "no dead controls". → *Phase 5/6.*

**F-17 · `Settings.tsx` has three dishonest controls.**
"Save Preferences" only flips a local boolean for 2s via `setTimeout` (line 55) — prefs already
auto-persist, so the button does nothing. The `apiUrl` field is editable but never reaches `env` or
the client. `requireExplicitPhrases` and `auditClientTelemetry` are `useState` that never persist.
Governance §24 requires these to be real or absent. → *Phase 4.*

**F-18 · Dev personas with fictional identities are one env flag from production.**
`isDevAuthEnabled()` is true under `DEV` and under `MODE === 'test'`; `Login.tsx:131-182` renders a
persona picker ("Dr. Sarah Connor", "Alex Morgan", …). Master prompt §25 requires fictional names
removed and any demo mode isolated from production state. Today it is one mis-set env var from shipping. → *Phase 3.*

**F-19 · Static capability registry with no runtime discovery.**
`isAvailable()` is driven by a hardcoded `implemented: false` for everything except `targets.analyze`.
When the backend ships Phase 2 the console stays `UNAVAILABLE` until a frontend redeploy. A second,
unrelated `FORENSIC_CAPABILITIES` list with near-identical type names (`CapabilityStatus` vs
`Capability`) is consumed only by `CapabilityBadge`/tests — confusing duplication. → *Phase 2.*


### P2 — Quality and hygiene

**F-20 · `toScreenState()` unused** → every page invents its own state logic; no skeletons exist
(only `Skeleton` inside `Panel.tsx`); tables flash empty. → *Phase 5.*
**F-21 · No toast/notification layer** → mutation outcomes are invisible unless a page happens to
render inline state; `NotificationCenter` (§3, §26) absent. → *Phase 5.*
**F-22 · No 401/403 handling in `client.ts`.** `ApiError.isAuthorization` exists but only
`toScreenState` reads it; there is no session-expiry path, and `session.expiresAt` is stored and never
checked. → *Phase 3.*
**F-23 · Stray trees: 191 MB inside the project.** `frontend oblivion\` = 11,759 files / **171.89 MB**
of salvaged legacy code; `H--frontend\` = 14 files / **18.89 MB** of internal AI session `.jsonl`
transcripts plus `auto-mode-classifier-error.txt` dumps. Neither is ignored (`.gitignore` lists only
`node_modules`, `dist`, `coverage`, `.env*`, `*.local`, `.vite`, `*.log`, `.DS_Store`, `Thumbs.db`).
Direct cause of F-04, and shipping internal session logs inside a security product's source tree is a
disclosure risk. → *Phase 0.*
**F-24 · Single 536 kB JS bundle**, no route-level code splitting (build emits the >500 kB warning). → *Phase 9.*
**F-25 · `index.html` pulls fonts from the Google CDN.** A forensic console must work air-gapped; this
also adds an external dependency to a security tool. No favicon, no CSP. → *Phase 9.*
**F-26 · No pagination UI** although the contract exposes cursor pagination. → *Phase 5.*
**F-27 · Dead exports** (`queryKeys.certificate`, `env.apiBaseUrlConfigured`, the unused auth barrel). → *Phase 9.*

---

## 3. DECISIONS REQUIRED BEFORE PHASE 3

These are genuine forks, not things the audit can settle. Each has a recommended default.

**D-1 · Credential transport.** `api/auth.ts` implies **cookie sessions** (`/api/auth/login` then
`/api/auth/me`, no token returned), but `devAuth` stores a **bearer token** that nothing sends.
→ **Recommend cookie sessions + a Vite dev proxy**, because `auth.ts` already assumes it and
`/api/auth/me` is the canonical rehydration endpoint. Requires `credentials: 'include'` (or
same-origin via proxy) and CSRF strategy.

**D-2 · Is there a live backend to develop against?** Only `targets.analyze` is marked implemented.
→ **Recommend building against a contract-faithful fixture server** (MSW or a static file server
driven by `contract/OPENAPI.yaml`) kept **outside** `src/` so the `no-restricted-imports` mock ban
still holds. Without this, Phases 5–8 cannot be verified end-to-end.

**D-3 · Do the four orphan pages get built or deleted?** `Users`, `SystemStatus`, `DaemonMonitor`,
`Capabilities` are referenced by nav/docs but do not exist.
→ **Recommend deleting the nav references** except Administration, and building `/administration`
only if the contract exposes role management. Never advertise an unbuilt capability.

**D-4 · Capability discovery.** Static registry (today) vs. a runtime endpoint.
→ **Recommend keeping the static registry as the default-deny floor**, and layering an optional
`GET /api/capabilities` (only if the contract gains one) on top. Default-deny is the correct security
posture and must survive.

**D-5 · Fate of the stray trees.** → **Recommend moving both out of the project root** (e.g.
`..\_archive\`) rather than deleting outright, since `frontend oblivion\` is described as salvaged
work; then add both to `.gitignore`.


---

## 4. DEVELOPMENT PLAN

Sequenced so that each phase ends green on all four gates **and** on the new runtime smoke test.
Do not start a later phase with an earlier one red.

### Phase 0 — Diagnostics baseline & repo hygiene (½ day) · fixes F-04, F-09, F-23

Nothing else is verifiable until this lands; today `npm run check` cannot complete.

1. `git init`; add `.gitignore` entries for `frontend oblivion/`, `H--frontend/`, `dist/`,
   `coverage/`, `.env`, `*.local`; commit the tree as the audit baseline.
2. Move `frontend oblivion\` and `H--frontend\` to `..\_archive\` (outside the project root) —
   pending D-5. Do **not** delete yet.
3. `eslint.config.js:9` → `ignores: ['dist','coverage','src/lib/api/schema.d.ts','**/node_modules']`
   plus `**/*.js` for config files already covered by `disableTypeChecked`.
4. Capture a golden baseline file `docs/BASELINE.md`: lint/typecheck/test/build exit codes + bundle size.

**Exit criteria:** `npm run check` runs to completion and its four results are recorded.
**Risk:** low. **Reversible:** yes (git).

### Phase 1 — Make the application run (1 day) · fixes F-01, F-02, F-03, F-08

The highest-value day in the plan.

1. **Single provider tree.** `providers.tsx` becomes canonical: `QueryClientProvider` →
   `ThemeProvider`(applies accent/density) → `AuthProvider` → children. Fold in the accent-variable
   application currently only in `App.tsx`; delete the duplicate `QueryClient` from `App.tsx`.
2. `main.tsx` → `createRoot(...).render(<GlobalErrorBoundary><Providers><App/></Providers></GlobalErrorBoundary>)`.
   `App.tsx` reduces to `<RouterProvider router={router} />`.
3. **Route error boundaries.** Add a branded `errorElement` (using `ErrorState` + `describeApiError`)
   to the `AppShell` layout route so a future throw can never show React Router's default screen.
4. **Wired smoke test** — the gate that would have caught all of this:
   - `src/app/app.smoke.test.tsx`: render `<Providers>` + `MemoryRouter` at `/`, assert redirect to
     `/login`; then seed a session and assert `Overview` mounts with the sidebar.
   - A test per guarded route asserting it does not throw, and one asserting an unauthenticated hit on
     `/operations` lands on `/login?from=`.
5. Confirm `usePrefs` theme/density actually reach the DOM (audit could not verify application);
   if not, implement `ThemeEffect` setting `data-theme`, `data-density` and the accent CSS custom
   properties on `document.documentElement`.

**Exit criteria:** app boots in a browser; smoke tests green; `check` green; **zero console errors on
load** (checklist item). **Risk:** medium — touches every page's assumptions. Mitigated by the new
smoke suite.

### Phase 2 — Typed data layer against the contract (1–2 days) · fixes F-19, F-27

1. Regenerate `schema.d.ts` from `contract/OPENAPI.yaml`; add `npm run codegen` and a CI drift check
   so `src/lib/api/types.ts` cannot silently diverge.
2. Add list queries the console currently lacks: `useOperationsListQuery`, `useAuditEventsQuery`,
   `useCertificatesQuery`, `useResidualFindingsQuery` — each through `gatedFetcher`, each with a
   `queryKeys` entry and cursor-pagination parameters.
3. **Adopt `toScreenState()` in every page** (F-20) — make it the only path from query → screen state.
4. Collapse the duplicate capability lists: one `CapabilityId` registry; `FORENSIC_CAPABILITIES`
   becomes a projection of it for the badge, not a second source of truth.
5. Delete dead exports (`queryKeys.certificate` once certificates are genuinely queried, then keep).

**Exit criteria:** no page declares its own `useState` for server data; every screen state flows
through `toScreenState`.

### Phase 3 — Auth/RBAC productionisation (2 days) · fixes F-05, F-06, F-07, F-18, F-22

Blocked on **D-1**, **D-2**.

1. Implement the chosen credential transport in `client.ts` and delete the unused-token path.
2. `vite.config.ts`: add `server.proxy['/api'] → http://127.0.0.1:8000`; default `apiBaseUrl` to
   `''` so dev and prod are same-origin.
3. Session lifecycle: check `expiresAt` on boot and on 401; clear store; redirect to `/login`
   preserving `from`; single-flight rehydration via `/api/auth/me` (no stampede on parallel queries).
4. **Gate dev auth hard**: `isDevAuthEnabled()` requires **all** of `import.meta.env.DEV` **and**
   `VITE_DEV_AUTH === 'true'`, and must be `false` under `MODE === 'test'` unless explicitly opted in.
   Add a build-time assertion that fails `vite build` if the flag can be true in a production bundle.
5. Replace fictional personas with role-labelled identities (`operator-1`, `auditor-1`, …) or delete
   the picker in prod.
6. Delete `mock.ts`, `mockAdapter.ts`; reconcile `provider.tsx` against `docs/FRONTEND_AUTH_RBAC.md`.
7. Verify the four RBAC layers agree on one permission source: route guards, `PermissionGuard`,
   sidebar visibility, and action-level gates.

**Exit criteria:** login/logout works against the fixture backend; 401 returns to `/login`; no dev
auth reachable from a production build.


### Phase 4 — Navigation, shell & settings integrity (1 day) · fixes F-17, resolves D-3

1. Reconcile `router.tsx` ↔ `nav.ts` mechanically, and **make it a test**, not a review note:
   `nav.smoke.test.ts` asserts every `nav` item resolves to a real route and every route is reachable.
2. Remove the Administration item, or build `/administration` — per **D-3**. Never ship a nav item
   that lands on an unrelated page.
3. Fix `/certificates/:id`: render a `CertificateDetail` that reads `useParams().id`, or delete the
   route. A parameter that is parsed and discarded is a dead route by definition.
4. Decide `/settings`'s guard — currently the only page behind `AppShell` with no `RequirePermission`.
5. Re-map permissions honestly: `certificates`/`assurance` gated on `operation.view` is wrong if the
   contract defines a distinct `certificate.view` / `assurance.view`.
6. `Settings.tsx`: delete the fake Save button (prefs persist on change — surface "Saved" as derived
   status, not a `setTimeout`); wire or remove `apiUrl`, `requireExplicitPhrases`,
   `auditClientTelemetry`. Add real theme/density/accent controls bound to `usePrefs`.

**Exit criteria:** zero dead routes; zero dead controls; nav test green.

### Phase 5 — Global UX infrastructure (2 days) · fixes F-20, F-21, F-26

Shared, so it must land **before** page work or every page reinvents it.

1. **Toast system** — `components/ui/Toast.tsx` + `lib/toast.ts` store, `role="status"`/`role="alert"`,
   no auto-dismiss for destructive-action results, `prefers-reduced-motion` respected.
2. **NotificationCenter** (§3, §26) — fed by failed operations, UNAVAILABLE capabilities, connection
   state, auth expiry.
3. **KeyboardShortcutOverlay** (§3) + one shortcut registry shared with `CommandPalette`.
4. **Skeletons** — `TableSkeleton`, `PanelSkeleton`, `DetailSkeleton`, driven by `toScreenState`'s
   `LOADING`; replace spinner-on-blank.
5. **Missing primitives** (§17): `Radio`, `Dropdown`, `Pagination`, `FilterBar`, `ProgressIndicator`,
   `Stepper`, `Timeline`, `HashField` (monospace + copy-to-clipboard + copy feedback, §16).
6. **`FilterBar` + real filtering** — the fix for dead filters: state must actually narrow rows.
7. **Pagination** wired to contract cursors for Operations / Audit / Residuals.
8. **Mutation feedback convention:** every mutation triggers toast + `invalidateQueries` + button
   pending/disabled (§20). Encode as a `useGatedMutation` wrapper so it cannot be forgotten.

**Exit criteria:** no page renders a bare spinner or bare "no data"; every mutation reports its outcome.

### Phase 6 — Evidence integrity: remove all fabrication (2–3 days) · fixes F-10…F-16

**The phase that makes this a trustworthy forensic product.** Governing rule: *if the backend did not
say it, the console does not show it.*

1. **`Certificates.tsx` — rewrite.** Delete the hardcoded certificate ID, digest, Merkle root,
   signature, timestamp and attestation authority. Delete **"Simulate Payload Tamper"** entirely.
   Delete the local fake-success path. Render `UnavailableState` until `certificates.get` /
   `certificates.verify` exist; then render only backend fields, with verification ∈
   {VALID, INVALID, UNVERIFIED, UNAVAILABLE} and an unmistakable tamper state (§14).
2. **`ErasureWorkflow.tsx` — remove invented policies.** The contract has no policy endpoint, so
   CONFIGURE renders `UnavailableState` with the registry reason. Keep the §8 workflow skeleton
   (DISCOVER→…→PROVE) integration-ready. Delete the "cryptographically timestamped" claim.
3. **Delete every `|| 'fallback'` on evidence fields** (F-12); render `NOT_EVALUATED` / `—` instead.
   Add an ESLint guard so it cannot regress — `no-restricted-syntax` on member-expression logical
   fallbacks for `mode` / `policy_id` / `hash` / `id`.
4. **`RecoveryVault.tsx`** — remove the unverified "RESTORE COMPLETED & VERIFIED" copy; state only
   what the response proves. Remove the hardcoded `C:\Oblivion\Restored\…` default. Bind the mutation
   to the selected id at call time, not render time.
5. **`Assurance.tsx`** — delete "ISO 27040 COMPLIANT" / "NIST SP 800-88" badges. Render the §13
   evidence checklist from `assurance.get` when available, else `NOT_EVALUATED` throughout. Assurance
   must never collapse to a green check (§13) — and equally never to a compliance claim.
6. **`Overview.tsx`** — replace literal `0`s and static rows with real queries (§6); every metric with
   no source is **omitted, not zero-filled**. Zero is a claim; absence is honesty.
7. **`Audit.tsx` / `ResidualAnalysis.tsx`** — connect to `useAuditEventsQuery` /
   `useResidualFindingsQuery` through `FilterBar` + `Pagination` + `toScreenState`; enable
   `onRowSelect` → `InspectorDrawer` (§15, §12).

**Exit criteria:** automated grep for fabricated literals in `src/pages/**` returns nothing; a test
asserts no component renders a verification state without a query result behind it.


### Phase 7 — Evidence & inspector components (2 days) · completes §16

Build the reusable forensic vocabulary the pages currently inline: `EvidenceId`, `EvidenceInspector`,
`EvidenceChain`, `EvidenceRelationshipGraph`, `EvidenceTimeline`, `EvidenceReference`,
`EvidenceStatus`, `EvidenceHash`, `OperationLifecycle`, `OperationInspector`, `AuditEventInspector`,
`CertificateInspector`, `TargetAnalysis`, `TargetStorageProfile`, `ScopeBoundaryCard`,
`HashComparison`, `PolicyRecommendation`, `AssuranceChecklist`, `ResidualFinding`,
`ErasureStepper` / `ErasureReview` / `ErasureProgress`. Each renders `UNAVAILABLE` rather than a stub.

### Phase 8 — Accessibility, responsive & motion (1–2 days)

Audit found good bones (skip link, `role="status"`, labelled inputs, colour-independent badges) but
**unverified** claims. Verify rather than assume:

1. Focus order/trap and `Escape` + `aria-modal` in `Dialog`, `Drawer`, `InspectorDrawer`,
   `CommandPalette`.
2. `aria-live` announcements for toasts, connection changes, operation state transitions.
3. Error/label association on every `Input`; keyboard-only walkthrough of the erasure authorization
   path — critical workflows must not be mouse-only (§21).
4. Enforce `prefers-reduced-motion` on `motion-spin` / `motion-enter` / drawer transitions (§23).
5. Contrast pass on `mute` / `dim` text against `bg` / `inset` — the small mono type is at risk.
6. 1024 px and narrow layouts: collapsible sidebar, inspector becomes overlay, tables adapt
   intentionally, no clipping (§22).

### Phase 9 — Build & delivery hardening (1 day) · fixes F-24, F-25, F-27

1. Route-level code splitting: `React.lazy` per page + `Suspense` with `LoadingState`; get the 536 kB
   chunk under ~200 kB gzipped initial, or add `manualChunks`.
2. **Self-host the fonts** — remove the Google CDN dependency so the console works air-gapped;
   `font-display: swap`, subset where possible.
3. Add `favicon`, `meta` description, `theme-color`; add a CSP (`default-src 'self'`, no
   `unsafe-eval`) and `X-Content-Type-Options` via hosting headers — appropriate for a security tool.
4. CI workflow running `check` + the smoke suite; add the OpenAPI drift check and the Phase 6
   fabricated-literal grep as hard gates.
5. Delete remaining dead exports; confirm `no-restricted-imports` still bans mock imports in app code.

### Phase 10 — Final review against the checklist (½ day)

Walk all 40 boxes of `FRONTEND_REVIEW_CHECKLIST.md`, each with evidence: a test name, a `file:line`,
or a screenshot. **Any box that cannot be evidenced is a defect, not a note.**

---

## 5. SEQUENCING & EFFORT

| Phase | Focus | Effort | Depends on | Unblocks |
|---|---|---|---|---|
| 0 | Baseline & hygiene | 0.5 d | — | every gate |
| 1 | **App boots** | 1 d | 0 | all runtime work |
| 2 | Typed data layer | 1–2 d | 0 | 5, 6, 7 |
| 3 | Auth/RBAC | 2 d | 1, D-1, D-2 | 4, 6 |
| 4 | Nav/shell/settings | 1 d | 1, 3 | 6 |
| 5 | Global UX infra | 2 d | 2 | 6, 7 |
| 6 | **Evidence integrity** | 2–3 d | 2, 3, 5 | 7, 10 |
| 7 | Evidence components | 2 d | 5, 6 | 10 |
| 8 | A11y/responsive | 1–2 d | 5, 7 | 10 |
| 9 | Build hardening | 1 d | all | 10 |
| 10 | Checklist sign-off | 0.5 d | all | ship |

**Total ≈ 15–17 working days.** Critical path: 0 → 1 → 2 → 5 → 6 → 9 → 10.
Phases 3 and 4 can run in parallel with 2 and 5 given two contributors.

---

## 6. NON-NEGOTIABLE GATES (add in Phase 0–1, keep forever)

The audit's real lesson is that a green suite proved nothing. These four gates make the suite mean
something:

1. **Routed smoke test** — renders `<Providers>` + the real router. Fails on F-01 in <1 s.
2. **Nav/route parity test** — no dead navigation, no unreachable route (F-16, D-3).
3. **Fabricated-literal grep** — fails the build on hardcoded IDs, hashes, policy IDs, timestamps,
   or `|| '<evidence field>'` fallbacks in `src/pages/**` (F-10…F-15).
4. **Console-error test** — asserts zero `console.error` during boot and navigation ("no console
   errors" is currently a checklist box nobody can tick).

---

## 7. ASSUMPTIONS & LIMITATIONS OF THIS AUDIT

- Static analysis plus one empirical probe (mounting `<App/>` under Vitest/jsdom). **No browser
  session was driven and no backend was contacted**, so visual polish, real responsive behaviour,
  contrast ratios and a11y claims are *unverified* — Phase 8 exists to verify them.
- Line numbers refer to the tree as read on 2026-09-09 and will drift once Phase 1 lands.
- F-19's "only `targets.analyze` is implemented" reflects the frontend's own registry, not a
  statement about the backend's true state; D-2 must confirm it.
- `frontend oblivion\` was not audited — it is treated as archive, not as target.
- Bundle/test figures are from the runs captured in §0 and are reproducible with the four listed
  commands.

