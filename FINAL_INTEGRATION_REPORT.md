# OBLIVION — Final Integration Milestone Report

**Audit log + existing frontend integration**

| | |
|---|---|
| Branch | `pre-phase23-repair` |
| HEAD at start | `1ddad5c4050ad807e7f6b6f4db2568892ec8a009` |
| HEAD at finish | `7e601a35b264f58ef3366a7c65ab31472b2748e1` |
| Commits | 4 (`a8c5f45`, `982bfd0`, `ba03cd8`, `7e601a3`) |
| Diff | 36 files, +5292 / −179 |
| Date | 2026-09-11 |

---

## 1. Baseline, recorded before any change

Measured, not carried over from the previous report.

| | Before | After |
|---|---|---|
| Backend tests | 505 passed, 2 skipped, 1 xfailed | **562 passed**, 2 skipped, 1 xfailed |
| mypy (strict) | clean, 109 files | **clean, 115 files** |
| ruff (repo-wide) | 192 errors | **191 errors** |
| OpenAPI paths | 18 | **20** |
| Frontend tests | 184 passed, **2 failed** (18 files) | **205 passed, 0 failed** (20 files) |
| Frontend typecheck | clean | clean |
| Frontend lint | clean | clean |
| Frontend build | OK | OK |
| End-to-end run | not established | **23/23 steps** |

The ruff count went *down* by one: two findings were introduced by my own first drafts and
cleared, and one pre-existing import sort was fixed in passing. **This milestone introduced
no new lint findings.**

The frontend baseline could not be taken at first: `frontend/node_modules` did not exist in
the worktree. It was installed before anything was measured.

### The two pre-existing frontend failures

Both were real, and neither was fixed by weakening a test.

1. **`authBoundary.test.tsx` — a time bomb, not a product defect.** The fixture hard-coded
   `expires_at: '2026-09-10T12:00:00Z'`. The transport deliberately refuses to attach a
   credential it already knows is expired, so once that timestamp passed, the logout test
   began failing *against correct code*. The date was wrong, not the transport. The fixture
   is now clock-relative, and the complementary property — an expired token is **not**
   attached — is now covered by a test that did not exist before.

2. **`capabilities.test.ts` — hardcoded lists that must track the generated contract.**
   `POST /api/operations/{operation_id}/pipeline` had entered the contract during Phase 25
   with no capability registered. Registered, and flagged destructive.

---

## 2. What was delivered

**Phase A** — a new `src/oblivion/core/audit/` package (records, chain, log), a migration,
two endpoints, and emission wired into authentication, the operation lifecycle, certificate
verification and the closed-loop pipeline. 56 new backend tests.

**Phase B** — the audit screen wired to real data; the operation workflow completed
(approval and the closed loop were unreachable from the console); three backend states the
console could not name added; two pre-existing frontend failures fixed. 19 new frontend
tests.

No frontend route, layout, component library, styling or information architecture was
reorganised. The one page rewritten — `Audit.tsx` — keeps its `PageHeader`, `DataTable`,
`InspectorDrawer`, filter bar and column structure; what changed is that its rows come from
the backend instead of `rows={[]}`.

---

## 3. The audit record model

`core/audit/records.py`. Nineteen event types in a closed enum, spanning authentication,
discovery, the operation lifecycle including its refusals, the closed loop, controlled
recovery, evidence and certificates, the privileged boundary, and the log's own readers.

Three properties are enforced in code rather than documented:

- **The actor is server-derived.** `AuditActor` has no constructor that takes an identity
  from a request. Its three named constructors — `authenticated()`, `system()`,
  `unauthenticated()` — each record where the identity came from, and `ActorSource` is part
  of the hashed bytes. A test asserts that re-labelling a claimed identity as authenticated
  changes the digest.
- **Secrets cannot enter.** Metadata field names are checked against the *same*
  `FORBIDDEN_FIELD_PATTERNS` the evidence record uses — one list, so a pattern added for one
  retained artefact protects the other.
- **Records are immutable.** Frozen dataclass; the digest is a function of the content.

`AuditOutcome` keeps `REFUSED` and `FAILED` distinct, for the same reason the privileged
boundary does: refused means nothing happened, failed means it was attempted and did not
complete.

---

## 4. Append-only, and how that is enforced

Append-only is a property of the surface area, not a promise about behaviour:

- `AuditLog` exposes `append`, `query`, `count`, `verify`. There is no `update`, no
  `delete`. A test asserts that set is free of mutation verbs.
- The HTTP surface publishes `GET /api/audit/events` and `POST /api/audit/verify` and
  nothing else. A test asserts no `PUT`, `PATCH` or `DELETE` is routed.

Enforcement below the application is *detection*, not prevention — that is what the chain is
for, and §6 shows it working against direct database edits.

---

## 5. The cryptographic model is reused, not reinvented

The brief required preserving the existing evidence-chain model. The audit chain uses:

- the same versioned canonicalizer, `OBLIVION-CANON-1`, imported from
  `core/evidence/canonicalize.py`;
- SHA-256 over canonical bytes;
- the same predecessor-link shape (`previous_*_id` + `previous_*_digest`, set together or
  not at all);
- the same three-word verdict vocabulary: `INTACT` / `BROKEN` / `UNVERIFIABLE`.

A test reads `core/audit/records.py` and asserts it imports the evidence canonicalizer and
defines no `canonicalize(` of its own, because a second canonicalizer would be a second
definition of integrity.

**One storage decision was load-bearing.** `occurred_at` and `safe_metadata` are part of the
hashed bytes, so they are stored as canonical *text*: the ISO-8601 string that was hashed,
and canonical JSON. A `DateTime` column under SQLite drops `tzinfo`; a record written as
`...+00:00` would reload naive, hash differently, and the verifier would report **every
honest row** as `MUTATED_EVENT`. A tamper detector that fires on every row is worse than
none, because it trains its reader to ignore it. The previous revision stored metadata as
`str(dict)` — a Python repr that cannot be parsed back at all, so it could never be rehashed.

---

## 6. Tamper evidence: the six distinctions

`core/audit/chain.py` reports a status per record and one verdict overall.

| Link status | Meaning |
|---|---|
| `VALID_GENESIS` | Sequence 1, no predecessor, own digest matches |
| `VALID_PREDECESSOR` | Own digest matches; names the preceding record with its real digest |
| `MISSING_PREDECESSOR` | Names a predecessor not supplied, or the numbering jumps |
| `BROKEN_PREDECESSOR` | Names the right predecessor with the wrong digest |
| `MUTATED_EVENT` | Stored digest disagrees with a recomputation over the row's content |

Mutation is checked **before** linkage. A record whose content was edited will usually also
fail its successor's link check, and reporting "broken predecessor" against the successor
would point the reader at the wrong record.

Detection is two-layer, and both layers are exercised against **direct SQLite edits**, not
through the application:

| Injected tampering | Result |
|---|---|
| Edit a row's `actor_id` | `BROKEN`; that row `MUTATED_EVENT`, its successor `BROKEN_PREDECESSOR` |
| Edit a row *and* rewrite its own digest to match | `BROKEN`; successor `BROKEN_PREDECESSOR` — the second, independent binding |
| Delete a row from the middle | `BROKEN`; `MISSING_PREDECESSOR` plus a visible gap in the contiguous sequence |
| Empty log | `UNVERIFIABLE`, never `INTACT` — deleting the whole log must not look clean |
| A window not starting at genesis | `UNVERIFIABLE`, with the reason stating the history before it was not established |

In every `BROKEN` or `UNVERIFIABLE` case, `proves` is empty.

---

## 7. Verification reads persisted records

`AuditLog.verify()` loads rows from the database and rehashes them. `StoredAuditRecord`
deliberately keeps the record and the digest *storage held* apart: a design that recomputed
the digest on load and compared it against itself would always agree and detect nothing.

Tests verify from a **fresh session**, so records are genuinely reloaded rather than checked
against the objects that created them.

---

## 8. Non-self-authenticating

`AuditVerifyRequest` has exactly one field, `operation_id`, and a test asserts that. There is
no field in which a caller can supply a digest, a record, or an expected status — so the
verdict is the server's. An API test posts an injected verdict (`status: "INTACT"`,
`checked: 9999`, `reason: "trust me"`) and asserts it is either rejected or discarded, never
echoed back.

Narrowing by `operation_id` cannot make a window look complete: the chain spans every event
in the system, so a per-operation slice is reported `UNVERIFIABLE` unless it happens to begin
at the genesis record.

---

## 9. Audit-chain integrity is not evidence integrity

These are different claims and the code refuses to conflate them.

`AuditChainVerification` carries `proves` and `does_not_prove`. `does_not_prove` is non-empty
**at every status**, and names: that any erasure succeeded or any target is unrecoverable;
that the referenced evidence records are intact (a separate check against the evidence
chain); that any certificate is trustworthy; that acts outside this application were recorded
at all. The API adds `scope_note` restating the boundary, and the UI renders both (§14).

An intact audit chain around a failed operation is the correct outcome — the log faithfully
records a failure.

---

## 10. Secrets

No credential can enter the log:

- Field names matching the shared forbidden-pattern list are refused at construction *and* on
  the append path; seven patterns are tested.
- A failed login records only the **claimed** username, marked `UNAUTHENTICATED`. The
  submitted password is never recorded — a failed attempt is frequently a mistyped *valid*
  password for another account, so logging it would turn the audit trail into a credential
  dump.
- The end-to-end run searches every returned record for all four session tokens, both
  passwords and the Ed25519 signing key. None appear.

---

## 11. Reconstructing what happened

One record answers: **what** (`event_type`), **who** and on what authority (`actor_id`,
`actor_role`, `actor_source`), **when** (`occurred_at`, timezone-aware; naive stamps are
refused), **which** operation and target, **what was observed** (`evidence_id`), **what was
decided** (`certificate_id`, `outcome`, `safe_metadata`).

Separation of duties is reconstructable from the log alone, without trusting the mutable
operation row: `OPERATION_CREATED` carries `requested_by`, `OPERATION_APPROVED` carries both
`requested_by` and `approved_by`, and the pipeline records `executed_by`. The end-to-end run
recovers three distinct actors from the log.

---

## 12. The API

| Route | Permission | Notes |
|---|---|---|
| `GET /api/audit/events` | `audit.view` | Filters, paged, hard ceiling of 500 |
| `POST /api/audit/verify` | `audit.verify` | No verdict field |

Both permissions already existed in `core/auth/rbac.py`, granted to **ADMIN and AUDITOR
only** — no RBAC change was needed. The asymmetry is the point: an OPERATOR holds the
authority to *erase* and cannot read the record of having done so. Verified over HTTP.

Unrecognised filter values return **422**, never silently ignored. A dropped filter returns
more than was asked for while looking like it returned exactly what was asked for — in an
audit context, a way to miss the record you were told to find.

Both endpoints record their own use (`AUDIT_LOG_QUERIED`, `AUDIT_LOG_VERIFIED`) *before* the
response is built. A log that cannot answer "who read this" is missing exactly the events an
insider would want hidden.

---

## 13. Two append paths, for a correctness reason

`append` joins the caller's transaction; `append_independently` commits its own.

A **success** entry must share the transaction: writing `OPERATION_CREATED / SUCCEEDED` and
then letting the operation insert fail would leave the log asserting an act that never
happened — a false record, worse than a missing one.

A **refusal** must not. "This principal was denied" really occurred, and the request that
produced it is about to raise and roll back. Written inside that transaction it would be
undone, so the log would fall silent about precisely the events most worth keeping.

Verified end-to-end: after a rejected login and a refused self-approval, both
`AUTH_LOGIN_FAILED` and `OPERATION_APPROVAL_REFUSED` are present, despite their requests
having returned 401 and 403 and rolled back.

The previous revision ended its audit write with `except Exception: pass`. That is gone;
`AuditAppendError` is raised. A log that silently declines to record is indistinguishable
from a log with nothing to record.

---

## 14. Frontend: the audit screen

Real data from `GET /api/audit/events`, with the existing layout preserved. Two distinctions
are carried through rather than flattened:

**Who acted.** `actor_source` renders as *Authenticated* / *System* / *Claimed — not
authenticated*. A failed sign-in records the username someone typed; rendering that the same
way as a verified principal would turn an attacker's input into an accusation against a real
person. The inspector adds an explicit warning on unauthenticated records.

**What verification proves.** The verdict badge is accompanied by per-link status counts, the
named failing records, `does_not_prove` rendered verbatim, and `scope_note`. An INTACT chain
shown alone reads as "the erasure was sound".

Other behaviours: a 403 renders as a named refusal, never an empty table; an empty log says
it is empty rather than implying an all-clear; `records_predating_chain` is disclosed rather
than silently dropped; the client-side search narrows only what is on screen, so a
filtered-to-empty view cannot be mistaken for an empty log. Every record's digest,
predecessor and predecessor-digest are published so a reader can re-link the chain
independently — and a test does exactly that.

---

## 15. Frontend: the operation workflow

Running the real workflow exposed three gaps that reading the code had not.

- **Approval had no client at all.** `useApproveOperationMutation` did not exist, so
  separation of duties could not be completed from the console. Added.
- **Nothing invoked the closed-loop pipeline.** The path that produces evidence, assurance
  and a certificate was registered as a capability and unreachable from every screen. Added,
  flagged destructive.
- **The console could not name three states the backend returns**: `PENDING_APPROVAL` (where
  *every* newly created operation sits), `RESIDUAL_ANALYSIS`, and `RECONCILIATION_REQUIRED` —
  which means the process stopped and nobody has established whether data was destroyed.
  Added with metadata, kept out of the ten-stage stepper rail so the visual language is
  unchanged. `RECONCILIATION_REQUIRED` is treated as **active, not terminal**, and renders
  with a question glyph — never a success or failure mark, because both would assert a fact
  that has not been determined.

`PipelineResultPanel` refuses three temptations: every stage is listed including those that
did not run; `assurance_status` is its own field so `INCONCLUSIVE` and `PARTIAL` stay
themselves; and coverage is rendered as **named** method and scanner lists, because "recovery
testing was performed" is not checkable while "`filesystem_enumeration` ran, five other
methods were never attempted" is. It states in the UI that a method finding nothing is
evidence about that method, not a finding that the data is unrecoverable.

Both new mutations send **no request body**, and tests assert that: no approver field means
no approver can be named; no target field means an approved erasure cannot be redirected.

---

## 16. Backend defects found by running the system

Three, none of which code reading had surfaced.

1. **Every analyzed target was reported as 0 bytes.** `POST /api/targets/analyze` read
   `result["size_bytes"]`; the analyzer publishes the total under `result["size"]` and
   `size_bytes` only inside `metadata`. An operator was shown "0 bytes" for the file they
   were about to erase, and the operation persisted `total_size=0`. Fixed, with a regression
   test; the end-to-end run now reports the real 2432 bytes.

2. **The closed-loop pipeline emitted almost nothing to the audit log.** The primary
   destructive path recorded one generic state change. It now records `PIPELINE_STARTED`
   *before* anything destructive happens, then `OPERATION_EXECUTED`, `EVIDENCE_RECORDED`,
   `CERTIFICATE_ISSUED` and `PIPELINE_CONCLUDED`. An audit log that records logins but not
   the erasure is worse than none, because it looks complete.

3. **Alembic could not be pointed at a database.** `alembic/env.py` ignored
   `OBLIVION_DATABASE_URL` and used the hardcoded `sqlite:///oblivion.db` from `alembic.ini`.
   Migrations were applied to whatever file sat in the working directory, and could not be
   exercised against a throwaway database — which is how they stayed untested. Fixed to use
   the application's own resolver, which then let migration `0004` be verified against a real
   `0003`-schema database.

A fourth item is documentation, not behaviour: `devAuth.ts` claimed to be
dead-code-eliminated from production builds. Measured against the real bundle — the gate
*does* compile to `return false` and every persona path is unreachable, but the persona array
and banner string **do** ship, because `lib/auth/index.ts` re-exports the module and defeats
tree-shaking. Not a privilege path; an inaccurate claim, now corrected to say what is true.

---

## 17. Migration and upgrade behaviour

`0004_audit_chain` adds twelve nullable columns plus a unique index on `sequence`. Verified
against a database built at `0003` and carrying a legacy row written the way the old emitter
wrote them:

- the legacy row survives, with `sequence=0` and `digest=NULL`;
- the log **refuses** to append on top of a digest-less tail rather than fabricating a link;
- verification excludes such rows and reports them in `records_predating_chain`, with the
  limitation added to `does_not_prove`;
- a legacy row's unparseable Python-repr metadata is surfaced under
  `legacy_unparsed_metadata` rather than making the whole log unreadable — while a *chained*
  row with unparseable metadata is still an error, because there it is genuine corruption.

Back-filling digests over legacy rows was considered and rejected: computing a digest now,
over content never hashed at the time, would manufacture exactly the evidence of integrity
that does not exist.

---

## 18. End-to-end demonstration

A live `uvicorn` server, a throwaway SQLite database, four provisioned principals, real
bearer tokens, real HTTP. The only destructive target is a file the harness creates inside a
disposable directory that is also the sole configured allowed root — on a **non-system
volume**, because `SafePathValidator` correctly refuses every target on the boot volume (the
first run failed with `PROTECTED_PATH`, which was the safety control working).

**23 of 23 steps passed.**

| | |
|---|---|
| Unauthenticated audit read | 401 `UNAUTHENTICATED` |
| Wrong password | 401, recorded as `AUTH_LOGIN_FAILED` / `REFUSED` |
| Analyze | 200, **2432 bytes** |
| Create operation | 202, `PENDING_APPROVAL` |
| **Self-approval** | **403 "Separation of Duties violation: Requester … cannot approve their own operation"** |
| Second-actor approval | 200, `READY` |
| Closed loop | 200, all twelve stages `COMPLETED` |
| Target actually gone | `exists() == False`, **re-observed on disk, not inferred** |
| Certificate | issued; `result=COMPLETED` |
| **Verification** | **`VALID`, all ten dimensions PASS, `signer_trusted=True`** |
| Audit log | 16 records, 12 distinct event types |
| Separation of duties | three distinct actors recovered from the log alone |
| Refusals | both survived their rolled-back requests |
| Secrets | none of 6 secrets appear in any record |
| Chain | `INTACT`, 17 checked, 0 predating |
| Operator reading the log | **403** — 401 and 403 stay distinguishable |
| Tampering | `BROKEN`; `#2 MUTATED_EVENT`, `#3 BROKEN_PREDECESSOR` |
| Broken chain | `proves == []` |

An important correction during this work: the first version of step 8 **passed for the wrong
reason**. An INVESTIGATOR does not hold `operation.approve` at all, so the 403 came from the
permission guard and the separation-of-duties rule was never reached. The step now has an
ADMIN — who holds every permission — attempt to approve their own request, so a 403 can only
come from the duty-split rule. A test that passes without exercising the control it names is
worse than no test.

Certificate verification initially returned `INCONCLUSIVE` with `SIGNER_TRUST=NOT_CHECKED`,
because no trust anchor was configured. That is correct fail-closed behaviour, not a defect —
but it left the trust model undemonstrated, so the harness now configures the real public key
and the run reaches `VALID`.

---

## 19. Limitations and known gaps

Stated plainly rather than left to be discovered.

1. **The browser UI was not driven against a live server.** The end-to-end run exercises the
   real backend over real HTTP. The frontend integration tests run the real component, query
   layer, capability gate and HTTP client, with the network stubbed. The link between them is
   mechanical rather than observed: the generated contract comes from the running
   application, `check:contract` fails on drift, `capabilities.test.ts` fails if the registry
   and the contract disagree, and the E2E confirms those same paths and request shapes work
   live. No Playwright-style browser run was performed.
2. **No user-management endpoint exists.** The E2E had to provision principals directly
   against the database. The Administration screen cannot create users.
3. **Capabilities still absent from the contract**, each labelled in the registry with what
   the screen does instead: `operations.list`, `targets.list`, `assurance.get`,
   `certificates.list`, `residual.findings`.
4. **Screens not re-verified individually against a live backend**: Dashboard, Assurance,
   Residual, Recovery. They consume the generated contract and are covered by the contract
   gate and existing tests, but no live walkthrough was performed.
5. **Replay protection does not survive a restart** (audit finding N-1). Documented, and
   explicitly out of scope for this milestone per the brief.
6. **Dev-persona data ships in the production bundle** as unreachable constants (§16).
7. **`media_sanitization` and `raw_volume_access` remain UNAVAILABLE.** This build performs
   logical deletion; it does not and cannot claim physical or NAND-level sanitization.
8. **The audit chain is per-deployment and not externally anchored.** It detects edits to
   stored rows; it does not defend against an adversary who controls the application at write
   time and forges a consistent history from the genesis record forward.
9. **Repository-wide ruff remains at 191 pre-existing findings.** None were introduced here;
   clearing them is cleanup this milestone deliberately did not do.
10. **`frontend/src/lib/api/contract-paths.ts` is regenerated** by `scripts/gen_openapi.py`.
    It is a machine-generated backend contract artefact, not hand-written frontend code, and
    the mandated contract gate fails if it is stale. Revert with
    `git checkout 1ddad5c -- frontend/src/lib/api/contract-paths.ts` if that judgement is not
    accepted.

---

## 20. Verdict

Every requirement the brief enumerated for Phase A is implemented and tested. Every
requirement it enumerated for Phase B is implemented, including three workflow gaps that only
surfaced by running the system rather than reading it. The real end-to-end workflow is
demonstrated against a live server: a real file erased, confirmed gone by re-observation, a
certificate issued and independently verified `VALID` across all ten dimensions, and a
tamper-evident audit chain that reports `INTACT` and then correctly reports `BROKEN` when the
database is edited underneath it.

All gates are green: 562 backend tests, 205 frontend tests, mypy clean on 115 files,
typecheck clean, lint clean, build OK, contract OK at 20 paths, 23/23 end-to-end steps.

The limitations in §19 are real and are not waved away — in particular, the browser UI itself
was not driven against a live backend (§19.1), and anyone relying on this report should read
that limitation before reading this verdict.

**INTEGRATION_READY**
