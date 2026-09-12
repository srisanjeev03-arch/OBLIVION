# OBLIVION — Canonical Project Documentation

**Intelligent Data Erasure, Recovery & Verification Platform**

This is the single authoritative record for the Oblivion project. It replaces the phase
reports, audit reports, milestone reports and scattered specification documents that
previously lived across the repository. Where history and current implementation disagree,
the history is described as history and **the implementation is authoritative**.

| | |
|---|---|
| Problem statement | **SIH26149 — NTRO** |
| Repository state | branch `pre-phase23-repair`, pre-cleanup HEAD `21103f3` |
| Document date | 2026-09-11 |
| Platform | Windows-first, NTFS-focused |

---

## Table of contents

| § | Section | § | Section |
|---|---|---|---|
| 1 | [Project Identity](#1-project-identity) | 21 | [Certificate Model](#21-certificate-model) |
| 2 | [Executive Summary](#2-executive-summary) | 22 | [Audit Log Architecture](#22-audit-log-architecture) |
| 3 | [Scope](#3-scope) | 23 | [Audit Chain Integrity](#23-audit-chain-integrity) |
| 4 | [MVP Scope and Non-Scope](#4-explicit-mvp-scope-and-non-scope) | 24 | [Privileged IPC Boundary](#24-privileged-ipc-boundary) |
| 5 | [Product Workflow](#5-product-workflow) | 25 | [Replay Protection](#25-replay-protection) |
| 6 | [System Architecture](#6-system-architecture) | 26 | [AI Architecture and Safety Boundary](#26-ai-architecture-and-ai-safety-boundary) |
| 7 | [Component Architecture](#7-component-architecture) | 27 | [Data Model / Persistence](#27-data-model--persistence) |
| 8 | [Backend Architecture](#8-backend-architecture) | 28 | [Security Properties](#28-security-properties) |
| 9 | [Frontend Architecture](#9-frontend-architecture) | 29 | [Standards and Methodology](#29-standards-and-methodology) |
| 10 | [API Architecture](#10-api-architecture) | 30 | [Implementation History](#30-implementation-history) |
| 11 | [Authentication](#11-authentication) | 31 | [Security Audit History](#31-security-audit-history) |
| 12 | [RBAC and Separation of Duties](#12-rbac-and-separation-of-duties) | 32 | [Test and Verification History](#32-test-and-verification-history) |
| 13 | [Safety Architecture](#13-safety-architecture) | 33 | [Current Architecture Diagram](#33-current-architecture-diagram) |
| 14 | [Target Validation](#14-target-validation) | 34 | [End-to-End Demonstration Procedure](#34-end-to-end-demonstration-procedure) |
| 15 | [Erasure Architecture](#15-erasure-architecture) | 35 | [Security Demonstration Scenarios](#35-security-demonstration-scenarios) |
| 16 | [Recovery Architecture](#16-recovery-architecture) | 36 | [Known Limitations](#36-known-limitations) |
| 17 | [Residual Analysis](#17-residual-analysis) | 37 | [Future Scope](#37-future-scope) |
| 18 | [Baseline and Validation](#18-baseline-and-validation) | 38 | [Final Current-State Summary](#38-final-current-state-summary) |
| 19 | [Assurance Model](#19-assurance-model) | 39 | [Repository Usage](#39-repository-usage--development-instructions) |
| 20 | [Evidence Model](#20-evidence-model) | 40 | [Demo Checklist](#40-demo-checklist) |
| | | 41 | [Repository Cleanup Record](#41-repository-cleanup-record) |

---

## 1. Project Identity

**Oblivion — Intelligent Data Erasure, Recovery & Verification Platform.**

Submitted against **SIH26149**, an **NTRO** problem statement concerning trustworthy data
erasure and verifiable assurance.

### The problem

Ordinary file deletion does not establish what remains recoverable. A delete call returning
success says only that the call returned. Recovery tools, filesystem metadata, journal
entries, shadow copies, temporary duplicates and storage-controller behaviour all survive it,
and none of them are visible to the person who pressed the button.

### The objective

Build a controlled platform that answers a harder question than "did the delete succeed":

> **What evidence exists that the target data is no longer recoverable within the supported
> recovery and verification scope?**

Concretely, the platform must discover targets, profile storage, classify sensitivity,
recommend an allowlisted erasure policy, perform the selected erasure, test supported recovery
paths, scan residual artefacts, produce an explainable assurance result, and emit
tamper-evident signed evidence — with controlled encrypted recovery when that is what was
asked for.

### The vocabulary this project uses, deliberately

**Used:** assurance · supported recovery techniques · residual risk · recovery test ·
evidence · inconclusive · supported media/filesystem · logical deletion.

**Never used:** 100% irrecoverable · universal forensic resistance · military-grade deletion ·
physical destruction · guaranteed removal from every backup or snapshot · guaranteed SSD/NAND
sanitization.

---

## 2. Executive Summary

Oblivion is a working Windows/NTFS platform, not a prototype. It performs real deletion behind
a privileged boundary, re-observes the filesystem afterwards rather than trusting the engine's
own report, tests which recovery methods can still retrieve the data, scans for what the
operation left behind, derives an assurance verdict strictly from the coverage actually
achieved, and issues an Ed25519-signed certificate that an independent party can verify across
ten dimensions.

Every act is recorded in a tamper-evident, append-only audit log whose chain detects edited
records, records whose digests were rewritten to match, and records removed from the middle.

The system's defining property is that **it refuses to overstate what it knows.** A scan that
did not run is `NOT_PERFORMED`, not "clean". A method that found nothing is evidence about
that method, not proof of irrecoverability. An unconfigured trust anchor yields
`INCONCLUSIVE`, not `VALID`. These are enforced in types and tested, not promised in prose.

### Current state at a glance

| | |
|---|---|
| Backend tests | 591 passed, 3 skipped, 1 xfailed |
| Frontend tests | 221 passed, 0 failed |
| mypy (strict) | clean, 115 source files |
| Frontend typecheck / lint / build | clean / clean / OK |
| OpenAPI contract | 21 operations across 20 paths, gate passing |
| Live backend end-to-end | 29/29 steps |
| Browser/live-frontend E2E | **not performed** (see §32, §36) |

---

## 3. Scope

### In scope

- Windows, NTFS, files and directories.
- Controlled test volumes, virtual machines, dedicated test drives.
- Logical erasure with verification, recovery testing, residual analysis and assurance.
- Cryptographically verifiable evidence and certificates.
- A tamper-evident audit log.
- A minimal privileged execution boundary.
- Advisory-only AI classification.

### Out of scope

- Physical or NAND-level sanitization; block-level or device-level overwrite.
- Raw volume access, MFT/USN/shadow-copy forensics, unallocated-space carving.
- Non-Windows platforms and non-NTFS filesystems.
- Guarantees about backups, snapshots or replicas outside the analysed scope.
- Any claim of certification against a standard.

---

## 4. Explicit MVP Scope and Non-Scope

### Target environment

Windows · NTFS · controlled test volume / VM / dedicated test drive · files and folders.

### The three modes

| Mode | What it promises |
|---|---|
| `COMPLETE_ERASURE` | Remove the target tree; verify by re-observation |
| `SELECTIVE_PERMANENT` | Remove specific targets permanently, no recovery object |
| `CONTROLLED_RECOVERABLE` | Remove the original, retain an encrypted recovery object restorable under RBAC |

### The required pipeline

```
Discover → Analyze → Recommend → Erase → Test Recovery
        → Analyze Residuals → Assess → Certify
```

### Explicit non-scope, stated as capability states

The privileged service reports what it can actually do. Two capabilities are permanently
`UNAVAILABLE` in this build and say so in every report:

| Capability | State | Meaning |
|---|---|---|
| `media_sanitization` | **UNAVAILABLE** | No overwrite, block-level or device sanitization is performed. This build cannot and does not claim physical irrecoverability. |
| `raw_volume_access` | **UNAVAILABLE** | No raw physical-drive handles are opened. Recovery testing is filesystem-level, not media-level. |

`UNAVAILABLE` means the environment cannot provide it — **not** that it silently degrades to
something weaker.

---

## 5. Product Workflow

```
 1. DISCOVER          Target inspected through the privileged boundary
 2. BASELINE          Pre-operation state captured, including SHA-256
 3. RECOMMEND         Dry-run plan produced. Grants no authorization.
 4. AUTHORIZE         A durable approval by a second actor, read from storage
 5. ERASE             The destructive step, performed privileged
 6. VALIDATE          Post-state RE-OBSERVED, not trusted from the engine
 7. TEST RECOVERY     Which supported methods can still retrieve the data
 8. ANALYZE RESIDUALS What the operation left behind
 9. ASSESS ASSURANCE  Verdict derived from the coverage actually achieved
10. GENERATE EVIDENCE Canonicalised, hashed, persisted
11. ISSUE CERTIFICATE Ed25519-signed, only with all prerequisites present
12. VERIFY CERTIFICATE Independent verification across ten dimensions
```

Three rules shape this sequence:

1. **Every stage records what it did, including nothing.** A stage that was skipped, refused
   or unavailable produces an outcome saying so. There is no path where a stage silently does
   not happen and the pipeline continues as if it had.
2. **Later stages cannot invent earlier ones.** Assurance consumes the coverage the recovery
   and residual stages actually reported. If a scan did not run, coverage is `NOT_PERFORMED`
   and assurance is inconclusive *by construction*.
3. **A certificate needs more than a successful delete.** Issuance is refused without all four
   of: a signing identity, an evidence record, a real execution result, and a real assurance
   assessment.

`VALIDATE` deliberately re-observes the filesystem rather than trusting the execution result.
"The engine reported success" and "the target is actually gone" are two different facts, and
only the second is evidence.

---

## 6. System Architecture

```
┌──────────────────────────────────────────────────────────┐
│  React console (Vite 6 · React 19 · TanStack Query 5)    │
│  Renders backend truth. Invents no security status.      │
└───────────────────────────┬──────────────────────────────┘
                            │  REST / JSON, bearer session
┌───────────────────────────▼──────────────────────────────┐
│  FastAPI application  —  UNPRIVILEGED                    │
│   Authentication → RBAC → Policy → Safety validation     │
│   → Operation authorization (separation of duties)       │
└───────────────────────────┬──────────────────────────────┘
                            │  Authenticated IPC  ← THE BOUNDARY
                            │  OBLIVION-PRIV-1, HMAC-SHA256
┌───────────────────────────▼──────────────────────────────┐
│  Oblivion privileged service  —  MINIMAL AUTHORITY       │
│   Re-validates containment, policy, target identity      │
│   Six allowlisted operations. No shell. No arbitrary exe.│
└───────────────────────────┬──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│  Windows filesystem primitives (NTFS)                    │
└──────────────────────────────────────────────────────────┘

        Evidence ──► canonicalize ──► hash ──► sign  ──► certificate
        Audit    ──► canonicalize ──► hash ──► chain ──► verify
```

The API process runs unprivileged. Operations needing more authority are *described* to a
separate service which decides for itself whether to perform them. The API can therefore be
compromised without the attacker inheriting unrestricted filesystem authority: they inherit
only the ability to ask, and every ask is re-checked against the privileged process's own
configuration.

---

## 7. Component Architecture

| Package | Responsibility |
|---|---|
| `core/discovery` | Target analysis, storage profiling, hashing |
| `core/safety` | `SafePathValidator` — canonicalization, containment, reparse points, system-volume protection |
| `core/policy` | Allowlisted policy registry and compatibility rules |
| `core/erasure` | `ErasureEngine`, recovery vault, engine event emission |
| `core/state` | Operation state machine, reconciliation |
| `core/recovery` | Recovery testing, per-method outcomes |
| `core/residual` | Four residual scanners and the scan suite |
| `core/assurance` | `AssuranceEngine`, coverage-driven verdict rules |
| `core/evidence` | Evidence records, observation states, canonicalization, evidence chain |
| `core/audit` | Audit records, chain verification, append-only log |
| `core/pipeline` | `ClosedLoopPipeline` — the twelve stages |
| `core/auth` | Passwords, sessions, RBAC, separation of duties |
| `certificate` | Signing identity, issuance, ten-dimension verification, trust store |
| `privileged` | Protocol, validation, service, transports, client |
| `ai` | Advisory schema, providers, validation, `SecurityAdvisor` |
| `evaluation` | Dataset, metrics, baseline, harness |
| `persistence` | SQLAlchemy models and repositories |
| `api` | FastAPI routes, schemas, dependencies |

---

## 8. Backend Architecture

**Stack:** Python 3.14 · FastAPI · Pydantic v2 · SQLAlchemy 2.x (`Mapped` / `mapped_column`) ·
Alembic · SQLite · pytest · mypy (strict) · ruff.

**Principles in force:**

- Typed interfaces and dependency injection throughout; services are constructed from
  configuration rather than reaching for globals.
- Errors are never silently swallowed. Explicit error types; fail-closed defaults.
- Every destructive path has a testable precondition and postcondition.
- Deterministic services: the same inputs produce the same canonical bytes, in this process
  and any other.

---

## 9. Frontend Architecture

**Stack:** Vite 6 · React 19 · react-router 7 · TanStack Query 5 · Zustand 5 · Tailwind 4 ·
Vitest · TypeScript 5.7 (strict, `noUncheckedIndexedAccess`) · ESLint 9.

Organised by capability: `features/{administration, assurance, audit, authentication,
certificates, dashboard, discovery, evidence, operations, recovery, residual, settings}`, over
a shared `components/` library and a `lib/api` data layer.

### The two properties that matter

**Availability is derived, not asserted.** `lib/api/capabilities.ts` consults
`contract-paths.ts`, which `scripts/gen_openapi.py` generates from the running FastAPI
application. A capability therefore cannot claim to be contracted while unrouted, nor be
suppressed while routed. A drift test fails the build if the registry and the application
disagree.

**The console renders backend truth and invents no security status.** A guard test
(`test/no-fabricated-security.test.ts`) walks the shipped source and fails on fabricated
standards claims, invented tamper verdicts, absolute irrecoverability claims, hardcoded
digests or identifiers, `Math.random` used for security or progress data, and imports from any
mock-data module.

Screen states are a closed vocabulary — `LOADING`, `EMPTY`, `AVAILABLE`, `BLOCKED`,
`UNAVAILABLE`, `FAILED`, `NOT_EVALUATED` — so "the backend refused you" is never rendered as
"there is nothing here".

---

## 10. API Architecture

Twenty-one operations across twenty paths - `GET` and `POST /api/operations` share a path. The
contract in `docs/OPENAPI.yaml` is generated from the application and gated.

| Method | Path | Permission |
|---|---|---|
| POST | `/api/auth/login` | — |
| POST | `/api/auth/logout` | session |
| GET | `/api/auth/me` | session |
| POST | `/api/targets/analyze` | `evidence.hash` |
| GET | `/api/targets/{target_id}` | `evidence.view` |
| POST | `/api/operations` | `operation.request` |
| GET | `/api/operations` | `operation.view` |
| GET | `/api/operations/{operation_id}` | `operation.view` |
| POST | `/api/operations/{operation_id}/approve` | `operation.approve` |
| POST | `/api/operations/{operation_id}/execute` | `operation.execute` |
| POST | `/api/operations/{operation_id}/pipeline` | `operation.execute` |
| POST | `/api/operations/{operation_id}/cancel` | `operation.view` |
| GET | `/api/operations/{operation_id}/events` | `evidence.view` |
| GET | `/api/recovery-objects` | `recovery.view` |
| POST | `/api/recovery-objects/{recovery_id}/restore` | `recovery.execute` |
| GET | `/api/certificates/{certificate_id}` | `evidence.view` |
| POST | `/api/certificates/{certificate_id}/verify` | `evidence.verify` |
| POST | `/api/evidence/verify` | `evidence.verify` |
| GET | `/api/audit/events` | `audit.view` |
| POST | `/api/audit/verify` | `audit.verify` |
| GET | `/health` | — |

### Body-less by design

`approve`, `execute`, `pipeline` and `audit/verify` take **no request body**. That shape is the
security property:

- No field names a target, so an approved erasure cannot be redirected at another path.
- No field names an actor, so identity cannot be spoofed.
- No field carries a verdict, so verification results are the server's.

The frontend asserts this too: tests confirm the console sends no body on these calls.

### Error discipline

`401` and `403` remain distinguishable — "identify yourself" and "you are known and refused"
are different answers. Unrecognised filter values return `422` rather than being silently
ignored: a dropped filter returns more than was asked for while looking like it returned
exactly what was asked for. No traceback ever reaches a client.

---

## 11. Authentication

Opaque bearer sessions. The server stores only a SHA-256 digest of the token; nothing in the
system can reverse a stored session back into a usable credential. Passwords are hashed with
Argon2id.

The console holds the token **in memory only** — never `localStorage`, `sessionStorage` or a
cookie. A page reload therefore signs the operator out, which is a deliberate privacy and
XSS-surface choice rather than an oversight: there is no refresh endpoint that could honestly
re-establish a session. The transport refuses to attach a credential it already knows has
expired, so a dead token produces a clear "no session" rather than a confusing 401.

A development-persona substitute exists for local work. It is gated on `import.meta.env.DEV`,
has deliberately **no** environment-variable escape hatch (a build-time flag can be set by
whoever controls the build environment, which would turn a development door into a production
backdoor), and compiles to `return false` in production builds — verified by inspecting the
built bundle, not assumed. See §36.6 for what *does* remain in the bundle.

---

## 12. RBAC and Separation of Duties

Five roles, fine-grained permissions, enforced server-side. Frontend role checks are
**usability only** and are never trusted.

| Role | Holds |
|---|---|
| ADMIN | All permissions |
| INVESTIGATOR | Case management, evidence import/view/hash, erasure *request*, recovery view/execute, operation view/request, report export |
| OPERATOR | Case/evidence view, erasure *execute*, recovery view, operation view/execute, report export |
| AUDITOR | Case/evidence view, evidence verify, recovery view, operation view/verify, **audit view/verify**, report export |
| VIEWER | Case/evidence/operation view, report export |

### The asymmetry that makes the log evidence

`audit.view` and `audit.verify` are granted to **ADMIN and AUDITOR only**. An OPERATOR holds
the authority to *erase* and cannot read the record of having done so. This is verified over
real HTTP.

### Separation of duties

An operation is requested by one principal and must be approved by a **different** one. The
rule is enforced against the persisted operation record, never against a caller-supplied
identity:

- the operation must exist;
- its state must be `READY`;
- `approved_by` must be set;
- `approved_by` must differ from `requested_by`.

Holding `operation.execute` is **necessary and not sufficient** to run an operation.

A refused self-approval returns `403` *and* is recorded in the audit log — in a transaction of
its own, because the request that produced it is about to roll back (§22).

---

## 13. Safety Architecture

Twelve rules, all enforced in code:

1. Never execute arbitrary shell commands from API or UI input.
2. Never allow the AI model to choose or execute destructive commands.
3. Use an allowlisted operation policy.
4. Protect system and boot volumes by default.
5. Require explicit confirmation for destructive operations.
6. Normalize and validate every path.
7. Handle symlinks, junctions and reparse points safely.
8. Revalidate target identity immediately before destructive action.
9. Prevent path traversal and target substitution.
10. Never log sensitive plaintext.
11. Never expose vault keys through API responses.
12. Fail closed when target identity or safety checks are ambiguous.

The system-volume protection is real and was observed refusing work during this project's own
end-to-end testing: the first E2E run failed with `PROTECTED_PATH` because Python's temporary
directory sits on the boot volume. That was the control working, and the harness was moved to
a non-system volume rather than the control being relaxed.

---

## 14. Target Validation

`SafePathValidator` establishes, in order: canonicalization; containment within configured
allowed roots; reparse-point / junction rejection; system-volume protection by volume serial;
and target identity (volume serial + file ID).

Identity is checked **twice**: once early and cheaply at the boundary, and again by the engine
immediately before acting. The second check is what closes the TOCTOU window — the first
refuses early, the second refuses late.

The privileged service's allowed roots are **its own**. Nothing in a request can contribute to,
extend or override them. This single control is what keeps a compromised API from turning the
service into a general-purpose file deleter.

---

## 15. Erasure Architecture

### COMPLETE_ERASURE

Removes a validated directory tree logically. Post-state is re-observed; the engine's report is
not accepted as evidence.

### SELECTIVE_PERMANENT

Removes specific validated targets with no recovery object retained. Deletion is logical: the
directory entry and data runs are released to the filesystem. **This is not media
sanitization** — see §29.

### CONTROLLED_RECOVERABLE

Strict sequence, each step gating the next:

```
analyze → hash target → package data + metadata
        → encrypt (AES-256-GCM, authenticated)
        → store recovery object → VERIFY the vault round trip
        → final TOCTOU identity re-check → delete original
```

The vault object is verified *before* the original is removed. If verification fails, nothing
is destroyed. Restoration is authorized through RBAC, and the restored content's hash is
compared against the hash recorded in evidence.

All cryptography uses vetted libraries (`cryptography`). No primitive is implemented by hand.

---

## 16. Recovery Architecture

Results are scoped **per method**. The rule this enforces:

> A recovery method that found nothing is evidence about **that method**. It is not proof that
> the data is unrecoverable.

| Method | Status in this build |
|---|---|
| `filesystem_enumeration` | **Attempted.** Target present, or a byte-identical copy in scope, means the data is trivially recoverable |
| `vault_round_trip` | **Attempted** for `CONTROLLED_RECOVERABLE`. Success is the *correct* outcome — the mode promises recoverability |
| `mft_record` | **Not attempted** — requires raw volume access |
| `usn_journal` | **Not attempted** — requires raw volume access |
| `shadow_copy` | **Not attempted** |
| `unallocated_carving` | **Not attempted** — requires raw volume access |
| `physical_medium` | **Not attempted** |

`RecoveryTestReport.universal_irrecoverability` is a permanently-`None` property with a
docstring explaining why it can never be otherwise. `MethodOutcome` raises if a method that did
not run tries to report a result, so an unavailable capability cannot quietly strengthen a
verdict.

---

## 17. Residual Analysis

Four scanners, not path-existence alone:

| Scanner | Looks for | Confidence |
|---|---|---|
| `path_existence` | Is the target still at its path (`lexists`, so a dangling symlink counts as surviving) | HIGH |
| `content_copy_by_hash` | A byte-identical copy elsewhere in scope | HIGH |
| `name_remnants` | `file.txt~`, `.bak`, `~$file` beside the original | MEDIUM |
| `alternate_data_streams` | NTFS named streams a directory listing hides | MEDIUM |

`content_copy_by_hash` is the consequential one: erasing a named file does not erase its
content if a copy sits beside it, and no amount of path checking sees that.

**Findings and coverage are separate axes.** A scanner that could not run degrades coverage
rather than contributing to "nothing was found".

### Residual limitations, reported on every operation

MFT record inspection · USN journal inspection · volume shadow copy inspection ·
unallocated-space carving · physical medium examination. Each requires capability this build
does not have, and each is named rather than omitted.

---

## 18. Baseline and Validation

`BaselineManager` captures pre-operation state including SHA-256 before anything destructive
happens. Without a baseline, recovery testing and residual analysis report `UNAVAILABLE` and
assurance is `INCONCLUSIVE` — a cascade that fails *honestly* rather than proceeding on
assumptions.

`VALIDATE` re-observes the filesystem after execution. The distinction it preserves:

| Statement | Status |
|---|---|
| "The engine reported success" | A claim by the engine |
| "The target is not at its path when re-observed" | Evidence |

---

## 19. Assurance Model

### The coverage vocabulary

One word, one meaning, used identically by the residual sweep and by recovery testing.

| State | Meaning |
|---|---|
| `NOT_PERFORMED` | Never attempted |
| `UNAVAILABLE` | Attempted, but nothing this build supports could run here |
| `INCONCLUSIVE` | Ran but reached no determination |
| `PARTIAL` | Ran, but did not cover every supported method or scanner |
| `PERFORMED` | **Every unit of work this build supports** ran |

`PERFORMED` is complete coverage *of what this build supports*. It is never a claim that
unsupported techniques were applied.

### How assurance reads coverage

| Coverage | Assurance |
|---|---|
| Any required analysis `NOT_PERFORMED`, `UNAVAILABLE` or `INCONCLUSIVE` | `INCONCLUSIVE` |
| Any required analysis `PARTIAL` | **`PARTIAL`** — real evidence, incomplete search |
| All `PERFORMED`, non-critical residual findings present | `PARTIAL` |
| All `PERFORMED`, nothing found | `PASSED` |

A conclusive negative overrides everything: a recovery method that *recovered* the data, or a
critical residual finding, yields `FAILED` regardless of how complete the search was.

`PARTIAL` exists because discarding a genuine but incomplete search as inconclusive would be as
wrong as calling it `PASSED`.

### Coverage is recorded, not inferred

Neither report reduces to a boolean. Each carries named lists:

- `recovery_report.method_coverage` → `supported`, `attempted`, `successful`, `failed`,
  `unavailable`
- `residual_report.scanner_coverage` → `supported`, `ran`, `inconclusive`, `unavailable`

"Recovery testing was performed" is not a fact anyone can check. "`filesystem_enumeration` ran
and found nothing; five other methods were never attempted" is.

---

## 20. Evidence Model

### Observation states

The central distinction. A field that is absent, a scan that could not run, and a scan that ran
and found nothing are three different things, and collapsing them is how a system ends up
certifying an operation it never examined.

| State | Carries a value? | Meaning |
|---|---|---|
| `OBSERVED` | yes | Measured directly |
| `INFERRED` | yes | Derived by a documented deterministic rule |
| `NOT_CHECKED` | **no** | Never attempted in this operation |
| `UNAVAILABLE` | **no** | Attempted, not obtainable here |

`Observation.__post_init__` **raises** if a `NOT_CHECKED` or `UNAVAILABLE` observation is given
a value. The absence of a measurement cannot be recorded as a measurement.

### Canonicalization

Exactly one authoritative, versioned implementation: `OBLIVION-CANON-1`, aligned to RFC 8785
(JCS) — keys ordered by UTF-16 code unit, deterministic number and datetime formatting, nulls
preserved. It **rejects** types it cannot represent faithfully rather than coercing them with
`str()`, because silent coercion is how two different objects end up sharing a digest.

### Secrets never enter evidence

`FORBIDDEN_FIELD_PATTERNS` refuses observation names containing `password`, `secret`, `token`,
`private_key`, `vault_key`, `recovery_key`, `credential`, `api_key`, `dsn` and others. Evidence
is signed, persisted and handed to verifiers; a secret that reaches it cannot be withdrawn. The
audit log shares this exact list — one list, so a pattern added for one retained artefact
protects the other.

### Evidence chain

`verify_evidence_chain()` establishes, in order: every record's digest matches its content;
every record after the first names its predecessor; the digest each record recorded for its
predecessor equals that predecessor's actual digest.

An empty sequence is `UNVERIFIABLE`, never `INTACT`. A lone record that *names* a predecessor is
`UNVERIFIABLE` — its own correct digest says nothing about what came before.

---

## 21. Certificate Model

Ed25519 signatures over the complete canonical certificate payload. The signing identity is
**loaded, never generated** — implicit generation would make a misconfiguration look like a
working signer.

### The ten verification dimensions

| # | Dimension | Establishes |
|---|---|---|
| 1 | `STRUCTURE` | The certificate is well-formed |
| 2 | `VERSION_COMPATIBILITY` | This verifier understands this schema version |
| 3 | `EVIDENCE_AVAILABILITY` | The referenced evidence was found in storage |
| 4 | `EVIDENCE_DIGEST` | Recomputed evidence digest matches the certificate's |
| 5 | `SIGNATURE_VALIDITY` | The signature verifies against the presented key |
| 6 | `PUBLIC_KEY_CONSISTENCY` | The presented key matches the trusted key |
| 7 | `SIGNER_TRUST` | The signer is trusted by the **server's** TrustStore |
| 8 | `EVIDENCE_CHAIN_INTEGRITY` | The loaded evidence chain is internally consistent |
| 9 | `OPERATION_CONSISTENCY` | The certificate attests to the operation the caller expected |
| 10 | `TARGET_CONSISTENCY` | The certificate attests to the target the caller expected |

### Aggregation, order-independent

```
any required FAIL              → INVALID
else any required INCONCLUSIVE → INCONCLUSIVE
else any required NOT_CHECKED  → INCONCLUSIVE
else all required PASS         → VALID
```

`NOT_CHECKED` can never silently become `PASS`.

### The trust model

**A valid signature is not a trusted certificate.** Dimension 5 proves the mathematics;
dimension 7 proves the *authority*, and it consults the server's `TrustStore` — never the key
embedded in the certificate. A certificate cannot establish its own trustworthiness, and it
cannot establish the identity against which it is verified: `expected_operation_id` and
`expected_target_identity` come from the caller, and a mismatch fails.

With no trust anchor configured, `SIGNER_TRUST` is `NOT_CHECKED` and the overall verdict is
`INCONCLUSIVE`. That is correct fail-closed behaviour, not a defect.

### Limitations travel with the certificate

`limitations` is part of the signed canonical payload and is published by
`GET /api/certificates/{id}`, so a reader sees what was explicitly *not* established - that no
device or media sanitization was performed, and which recovery methods were never attempted.
They were persisted and signed but withheld from the API until this milestone; a certificate
without them reads as a stronger claim than the one that was actually signed. The console
renders them beside the certificate rather than behind the verify action.

### The expectations come from elsewhere

`expected_operation_id` and `expected_target_identity` are supplied by the caller, and the
console derives them from the **operation and target records**, fetched separately. Reading
them off the certificate would let the artifact prove its own identity, and both consistency
dimensions would pass for any internally consistent forgery. Sending neither is honest but
weak: both dimensions report `NOT_CHECKED` and the aggregate is `INCONCLUSIVE`.

---

## 22. Audit Log Architecture

The authoritative record of **what acts were performed against this system, by whom**. This is
distinct from evidence, which records *what was observed about a target*.

### Nineteen event types

Authentication (`AUTH_LOGIN_SUCCEEDED`, `AUTH_LOGIN_FAILED`, `AUTH_LOGOUT`,
`AUTH_ACCESS_DENIED`) · discovery (`TARGET_ANALYZED`) · operation lifecycle
(`OPERATION_CREATED`, `OPERATION_APPROVED`, `OPERATION_APPROVAL_REFUSED`, `OPERATION_EXECUTED`,
`OPERATION_CANCELLED`, `OPERATION_STATE_CHANGED`) · closed loop (`PIPELINE_STARTED`,
`PIPELINE_CONCLUDED`) · recovery (`RECOVERY_RESTORE_REQUESTED`, `RECOVERY_RESTORE_PERFORMED`) ·
artefacts (`EVIDENCE_RECORDED`, `CERTIFICATE_ISSUED`, `CERTIFICATE_VERIFIED`) · the log about
the log (`AUDIT_LOG_QUERIED`, `AUDIT_LOG_VERIFIED`) · the boundary
(`PRIVILEGED_REQUEST_REFUSED`).

### The actor is server-derived

`AuditActor` has **no constructor that takes an identity from a request**. Three named
constructors each record the provenance of the identity, and `ActorSource` is part of the hashed
bytes:

| Source | Meaning |
|---|---|
| `AUTHENTICATED_SESSION` | Resolved from a server-side session record. The only source that names a human and means it. |
| `SYSTEM` | The application acting on its own behalf |
| `UNAUTHENTICATED` | No valid session. Any identifier is a *claim* — e.g. a username typed into a failed login |

The console renders these distinctly. A failed sign-in records the username someone typed;
rendering that the same way as a verified principal would turn an attacker's input into an
accusation against a real person.

### Append-only

A property of the surface area, not a promise: `AuditLog` exposes `append`, `query`, `count`,
`verify` — there is no `update`, no `delete`, and a test asserts that. The HTTP surface routes
no `PUT`, `PATCH` or `DELETE`, and a test asserts that too.

### Two append paths, for a correctness reason

`append` joins the caller's transaction; `append_independently` commits its own.

A **success** entry must share the transaction — writing `OPERATION_CREATED / SUCCEEDED` and
then letting the operation insert fail would leave the log asserting an act that never happened,
which is worse than a missing record.

A **refusal** must not. "This principal was denied" really occurred, and the request that
produced it is about to raise and roll back. Written inside that transaction it would be undone,
silencing precisely the events most worth keeping: denied access, rejected approvals, failed
logins.

### Auditable audit access

Reading the log is itself a privileged act and is recorded *before* the response is built. A log
that cannot answer "who read this" is missing exactly the events an insider would want hidden.

### The outcome describes the stage that actually ran

`OPERATION_EXECUTED` is written only when the destructive step was genuinely attempted, and its
outcome is mapped from the ERASE stage's real status: `COMPLETED` to `SUCCEEDED`; `FAILED` and
`UNAVAILABLE` to `FAILED`, because the operation had already passed authorization and was
permitted; `REFUSED` and `SKIPPED` to `REFUSED`, because nothing was destroyed. When the erase
did not happen, no `OPERATION_EXECUTED` record is written at all - an append-only log must not
carry a record of an execution that never occurred - and the refusal is carried by
`PIPELINE_CONCLUDED` instead.

This was audit finding F-A. `Stage` mixes in `str`, but `Enum.__str__` still wins, so
`str(Stage.ERASE)` is `"Stage.ERASE"` and comparing it against `"ERASE"` was always false. Every
run - successful ones included - recorded `outcome=FAILED, erase_status=NOT_RUN`, and a refused
operation recorded exactly the same thing. The stage is now located by enum identity and mapped
through a table that is total over `StageStatus`, so a new stage status forces a decision rather
than defaulting.

### Failures are never swallowed

The previous revision ended its audit write with `except Exception: pass`, hard-coded
`actor_id="system"` and `outcome="OK"`, and stored metadata as a Python repr that could never be
parsed back. All of that is gone; `AuditAppendError` is raised instead. A log that silently
declines to record is indistinguishable from a log with nothing to record.

---

## 23. Audit Chain Integrity

### The same cryptographic model, reused

The audit chain uses the *same* `OBLIVION-CANON-1` canonicalizer, the same SHA-256 over
canonical bytes, the same predecessor-link shape and the same `INTACT` / `BROKEN` /
`UNVERIFIABLE` vocabulary as the evidence chain. A second canonicalizer would be a second
definition of integrity. A test asserts the audit record imports the evidence canonicalizer and
defines none of its own.

### Five per-record link states

| Status | Meaning |
|---|---|
| `VALID_GENESIS` | Sequence 1, no predecessor, own digest matches |
| `VALID_PREDECESSOR` | Own digest matches; names the preceding record with its real digest |
| `MISSING_PREDECESSOR` | Names a predecessor not supplied, or the numbering jumps |
| `BROKEN_PREDECESSOR` | Names the right predecessor with the wrong digest |
| `MUTATED_EVENT` | Stored digest disagrees with a recomputation over the row's content |

Mutation is checked **before** linkage: an edited record would usually also fail its successor's
link check, and reporting "broken predecessor" against the successor would point the reader at
the wrong record.

### Detection is two-layer

| Injected tampering | Result |
|---|---|
| Edit a row's content | `BROKEN` — that row `MUTATED_EVENT`, successor `BROKEN_PREDECESSOR` |
| Edit a row **and** rewrite its own digest to match | `BROKEN` — successor `BROKEN_PREDECESSOR`, the second independent binding |
| Delete a row from the middle | `BROKEN` — `MISSING_PREDECESSOR` plus a visible gap in the contiguous sequence |
| Empty log | `UNVERIFIABLE`, never `INTACT` |
| Window not starting at genesis | `UNVERIFIABLE` |

All of these are tested against **direct SQLite edits**, not through the application — that is
the threat the chain exists for.

### Audit-chain integrity is not evidence integrity

`AuditChainVerification` carries `proves` **and** `does_not_prove`. The second list is non-empty
at every status and names: that any erasure succeeded or any target is unrecoverable; that the
referenced evidence records are intact; that any certificate is trustworthy; that acts outside
this application were recorded at all. The API adds a `scope_note`, and the console renders both.

An intact audit chain around a failed operation is the correct outcome — the log faithfully
records a failure.

### Verification reads persisted records

`AuditLog.verify()` loads rows from the database and rehashes them. `StoredAuditRecord`
deliberately keeps the record and the digest *storage held* apart: a design that recomputed the
digest on load and compared it against itself would always agree and detect nothing.

### Non-self-authenticating

`AuditVerifyRequest` has exactly one field, `operation_id`. There is no field in which a caller
can supply a digest, a record, or an expected status.

---

## 24. Privileged IPC Boundary

### Six operations, and nothing else

| Operation | Kind | Effect |
|---|---|---|
| `inspect_target` | read | Analyses one validated target |
| `scan_scope` | read | Storage profile for a validated scope |
| `delete_file` | destructive | Unlinks one validated file |
| `delete_tree` | destructive | Removes one validated directory tree |
| `prepare_recovery_object` | destructive | Vaults an encrypted copy, then unlinks |
| `restore_recovery_object` | write | Restores a vault object to a new path |

There is no `execute_command`, no `powershell`, no `cmd`, no arbitrary executable and no
arbitrary script. A request naming anything outside this set fails at parse. Tests pin the enum
by equality and scan every module in the package for `subprocess`, `os.system`, `os.popen`,
`os.exec`, `os.spawn`, `shell=True`, `eval(`, `exec(`, `__import__(` — none are present.

### Wire protocol — `OBLIVION-PRIV-1`

4-byte big-endian length prefix, UTF-8 JSON, 1 MiB cap. Byte-mode pipe (message mode fails a
prefix-sized read with `ERROR_MORE_DATA`). Envelope:
`{"request": {...}, "mac": "<hmac-sha256>"}` computed over the **canonical request bytes**, so
integrity is defined over exactly the bytes the service acts on — a field cannot change between
verification and use.

Parsing is total and fail-closed. Unknown fields are **refused, not ignored**: a field the
privileged side silently drops is a field the unprivileged side may believe is being enforced.
Parameter names matching secret-material patterns are refused by name before the value is read.

### What authentication proves — and what it does not

The MAC proves the request came from a process holding the service key and was not altered in
transit. **It does not prove which human is behind it.** A privileged service cannot
authenticate an end user. `actor_id` is carried for attribution and grants nothing; the API
derives it from the authenticated session and must never take it from a request body.

**There is no fallback key.** A service with no `OBLIVION_IPC_KEY` reports `UNAVAILABLE_NO_KEY`
and refuses everything — a default secret would be indistinguishable from no authentication at
all.

### Transport ACL

`D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;<creator SID>)` — SYSTEM, Administrators and the creating
account only, with a protected DACL so no inherited ACE can widen it. Remote clients are
rejected. The server handles one client at a time.

Every Win32 call declares `argtypes`/`restype`: undeclared calls marshal handles as 32-bit ints,
silently truncating them on x64 and producing failures that look like access-denied. A security
boundary reporting a misleading cause is worse than one that fails loudly.

---

## 25. Replay Protection

A nonce is remembered for exactly as long as a request bearing it could still pass the freshness
check (default 5 minutes), so memory is bounded without opening a gap. A correctly formed,
correctly signed request is refused on its second arrival.

**Atomicity.** Eviction, membership check and insert happen under one lock as a single
operation. Between a bare check and a bare insert, a second thread bearing the same nonce would
also see "not seen". A test releases 32 threads simultaneously on one nonce and asserts exactly
one is admitted.

**Bounds.** Retention is bounded twice: by expiry, and by a hard ceiling of 100 000 entries. At
the ceiling the cache **refuses rather than evicting a live nonce** — forgetting an unexpired
nonce to make room would silently re-open its replay window. A refused legitimate request is
recoverable; an accepted replay is not.

**Lifetime.** The cache lives on `app.state` for the life of the FastAPI application. The
service object is rebuilt per request (it is cheap, and its validator must track configuration)
but the cache is injected so it is not. This was audit finding **M-1** (§31).

**Restart.** There is no restart persistence and none is claimed. A restart empties the cache, so
a captured request stays replayable for the remainder of its freshness window. Bounding that
window is the mitigation. See §36.5.

---

## 26. AI Architecture and AI Safety Boundary

The AI layer is **advisory only** and is deliberately *not* wired into the destructive pipeline.

### AI may

Classify sensitivity · explain findings · classify residual artefacts · estimate qualitative
recovery risk · recommend an allowlisted policy · explain why a policy was selected.

### AI may not

Issue arbitrary commands · bypass safety controls · decide authorization · directly delete
files · select filesystem targets · approve operations · bypass RBAC or `SafePathValidator` ·
modify evidence or audit records · manufacture evidence · declare physical irrecoverability ·
generate authoritative certificate results · override deterministic policy.

### How that is enforced

- `Advisory` exposes a read-only `advisory` property; `apply_is_not_supported()` is a stub that
  raises.
- Thirteen `UNSAFE_CLAIM_PATTERNS` reject advisory text asserting irrecoverability or certainty.
- Nine `FORBIDDEN_OUTPUT_FIELDS` and twelve `FORBIDDEN_AUTHORITY_FIELDS` reject any attempt to
  emit an authoritative decision.
- Providers are pluggable (`NullProvider`, `StaticProvider`, `LocalQwenProvider`); the
  deterministic policy engine remains authoritative in all configurations.
- The console must never imply that AI authorized deletion, executed deletion, certified
  irrecoverability, modified policy, bypassed safety or generated assurance. The
  no-fabricated-security guard test enforces the rendering side.

An evaluation harness scores the advisory classifier against a 55-case dataset including 11
adversarial cases, using **signed** over-confidence rather than raw calibration error —
understating confidence is the safe direction.

---

## 27. Data Model / Persistence

SQLAlchemy 2.x over SQLite, migrated with Alembic.

| Model | Holds |
|---|---|
| `UserModel`, `RoleModel`, `PermissionModel`, `RolePermissionModel`, `SessionModel` | Identity, roles, permissions, server-side sessions (token digest only) |
| `TargetModel` | Analysed targets, canonical path, size, hash |
| `OperationModel` | Mode, policy, state, `requested_by` / `approved_by` / `executed_by` / `verified_by` |
| `OperationEventModel` | Append-only per-operation events with sequence and state transition |
| `BaselineModel` | Pre-operation captured state |
| `RecoveryTestModel`, `ResidualFindingModel`, `AssuranceResultModel` | Analysis outputs |
| `EvidenceRecordModel` | Canonical evidence, digest, chain linkage |
| `CertificateModel` | Issued certificates and signer metadata |
| `AuditEventModel` | The chained audit log |

### Migrations

| Revision | Adds |
|---|---|
| `0001_initial` | Core schema |
| `0002_auth_rbac` | Identity, roles, sessions |
| `0003_phase23_evidence_certificate` | Evidence chain linkage, certificate verification bindings |
| `0004_audit_chain` | Audit chaining and actor provenance |

### One storage decision worth stating

`occurred_at` and `safe_metadata` on audit rows are part of the hashed bytes, so they are stored
as canonical **text**: the ISO-8601 string that was hashed, and canonical JSON. A `DateTime`
column under SQLite drops `tzinfo` — a record written as `...+00:00` would reload naive, hash
differently, and the verifier would report **every honest row** as `MUTATED_EVENT`. A tamper
detector that fires on every row is worse than none, because it trains its reader to ignore it.

`0004` is additive and nullable. Rows written before the chain existed keep `digest = NULL`; the
log refuses to append on top of a digest-less tail rather than fabricating a link, and
verification excludes such rows and reports them in `records_predating_chain`. Back-filling
digests over content never hashed at the time was considered and rejected — it would manufacture
exactly the evidence of integrity that does not exist.

---

## 28. Security Properties

| Property | How it is held |
|---|---|
| Unprivileged API | Destructive authority lives behind an IPC boundary that re-validates independently |
| No shell path | Six allowlisted operations; execution constructs statically absent and tested |
| Containment | Service-owned allowed roots; nothing in a request can extend them |
| TOCTOU closure | Target identity re-checked immediately before mutation |
| Separation of duties | Requester ≠ approver, enforced against persisted state |
| Server-derived identity | No endpoint accepts a caller-supplied actor, approver or verifier |
| Replay resistance | Single-use nonces, atomic check-and-insert, bounded, refuses at ceiling |
| Evidence integrity | Canonical bytes, SHA-256, Ed25519, chain linkage |
| Trust separation | Signature validity ≠ signer trust; TrustStore is the authority |
| Audit integrity | Append-only surface, two-layer tamper detection |
| Secret containment | Shared forbidden-pattern list across evidence and audit; no key crosses the IPC boundary; vault keys never in API responses |
| Fail-closed defaults | No signing key → cannot sign. No IPC key → refuse all. No trust anchor → `INCONCLUSIVE` |
| Honest absence | `NOT_CHECKED` / `UNAVAILABLE` cannot carry values and cannot become `PASS` |

---

## 29. Standards and Methodology

Oblivion's terminology and method are aligned to:

| Standard | Relevance |
|---|---|
| **NIST SP 800-88 Rev. 2** | Media sanitization categories — Clear / Purge / Destroy — and the principle that assurance depends on verification |
| **ISO/IEC 27040:2024** | Storage security, including sanitization and evidence expectations |
| **IEEE 2883-2022** | Standard for sanitizing storage |
| **IEEE 2883.1-2025** | Recommended practice for the use of IEEE 2883 |

### What Oblivion does *not* claim

- **Oblivion is not "NIST certified" or "ISO certified".** No certification is held, claimed or
  implied. Alignment of terminology and method is not certification.
- **DoD 5220.22-M is not presented as a modern policy.** It is historical; the modern references
  are those above.
- **No claim of universal irrecoverability** is made anywhere in the product or this document.

### Logical deletion vs physical/NAND sanitization

This distinction is load-bearing and is stated wherever a result is presented:

| | Logical deletion (what Oblivion performs) | Physical / NAND sanitization (what it does not) |
|---|---|---|
| What happens | Directory entry removed; data runs released to the filesystem | Media-level overwrite, block erase, cryptographic erase, or destruction |
| Verified by | Filesystem-level re-observation, copy-by-hash search, supported recovery methods | Device-level attestation, raw media examination |
| Residual risk | Unallocated content may persist until reused; controller-managed remapping is invisible at this layer | Addressed at the media layer |
| Oblivion's state | Performed and evidenced within the supported scope | `media_sanitization: UNAVAILABLE` |

On flash media in particular, wear levelling and over-provisioning mean logically freed content
may remain in physical cells that no filesystem-level operation can reach. Oblivion reports this
as a limitation rather than working around it.

---

## 30. Implementation History

| Milestone | What it established |
|---|---|
| **Initial foundation** | Repository, configuration, logging, database, shared schemas. Stack selected (Python/FastAPI/SQLAlchemy) — the first audit had found the stack undecided |
| **Discovery & safety** | Target analysis, hashing, dry-run, `SafePathValidator` |
| **Erasure & state machine** | `ErasureEngine`, operation state machine, progress, structured errors |
| **Selective deletion hardening** | Path traversal, reparse points, identity revalidation, protected roots |
| **Recoverable deletion (Phase 11)** | `CONTROLLED_RECOVERABLE` with AES-256-GCM vault; strict analyse → vault → verify → TOCTOU → delete sequence |
| **Recovery engine (Phase 12)** | Authorized restore, hash comparison against evidence |
| **Residual analysis (Phase 13)** | Residual scanning |
| **Assurance engine (Phase 14)** | Coverage-driven verdicts |
| **Evidence & certificate (Phases 15–16)** | Evidence records, signing, certificate verification |
| **Persistence (Phase 17)** | Database schema, repositories, migrations |
| **Phase 23** | Evidence foundation, certificate issuance, **independent** verification. Eliminated the self-verification trust flaw: `verify_certificate(cert, evidence, signer_public_key)` was removed so a caller can no longer supply the key that decides trust. One authoritative canonicalizer established |
| **Phase 24** | Privileged execution boundary: `OBLIVION-PRIV-1`, six-operation allowlist, named-pipe transport with SDDL ACL, HMAC over canonical bytes, replay protection |
| **Phase 25** | Closed-loop pipeline connecting twelve stages that previously did not call each other; four residual scanners; per-method recovery results |
| **Phase 26** | Advisory AI layer with a hard safety boundary, deliberately not wired into the pipeline |
| **Phase 27** | Deterministic evaluation harness, 55-case dataset, signed-overconfidence decision rule |
| **Security remediation** | M-1 and M-2 closed at root cause (§31) |
| **Audit log** | Authoritative tamper-evident audit layer replacing a write that recorded a constant actor, a constant outcome, unparseable metadata, and swallowed its own failures |
| **Frontend integration** | Audit screen wired to real data; approval and the closed loop made reachable from the console; three backend states the console could not name added |

---

## 31. Security Audit History

**Findings are recorded as they were. Nothing here is rewritten to look cleaner.**

### The initial audit (2026-09-03) — a specification-only repository

The first audit examined a repository containing comprehensive specifications and **zero
implementation code**. Its own executive summary: *"Overall Readiness Score: 1/10 —
Specification completeness is strong (7/10), but implementation readiness is zero."*

Its CRITICAL and HIGH findings were therefore **implementation gaps, not vulnerabilities in
running code**. They are listed here because they were real and because the record should not
suggest they never existed:

| ID | Severity | Finding | Closed by |
|---|---|---|---|
| SEC-CRIT-001 | CRITICAL | No path-traversal protection implemented | `core/safety` (§14) |
| SEC-CRIT-002 | CRITICAL | No system-drive protection implemented | `SafePathValidator` volume-serial protection |
| SEC-CRIT-003 | CRITICAL | No privileged service; boundary unengineered | Phase 24 (§24) |
| SEC-CRIT-004 | CRITICAL | No cryptographic implementation | Vetted `cryptography` throughout |
| SEC-CRIT-005 | CRITICAL | No AI security boundary | Phase 26 (§26) |
| PRIV-001 | CRITICAL | No privileged service exists | Phase 24 |
| CRYPTO-001/2/3 | CRITICAL | No hashing / encryption / signing | SHA-256, AES-256-GCM, Ed25519 |
| VAULT-001 | CRITICAL | No vault implementation | Phase 11 (§15) |
| FS-001…004 | HIGH | No canonicalization, reparse handling, revalidation, protected roots | `core/safety` (§13, §14) |
| PRIV-002/003/004 | HIGH | No command-execution prohibition, auth, RBAC | Phase 24, `core/auth` (§11, §12) |
| CRYPTO-004/005 | HIGH | No key management, no RNG selection | `certificate/keys.py`, `secrets` |
| VAULT-002 | HIGH | No key isolation | Vault keys never returned through the API |
| ARCH-001/002/003 | MEDIUM | Stack undecided, IPC undefined, no migration strategy | Python/FastAPI, `OBLIVION-PRIV-1`, Alembic |

### The independent security audit of Phases 23–27

Verdict: **PASS_WITH_FINDINGS**. Conducted read-only against the implementation, weighting
source inspection and independent execution over the implementation's own test suite.

| ID | Severity | Finding | Status |
|---|---|---|---|
| **M-1** | MEDIUM | Replay protection ineffective in the default in-process deployment. The service was rebuilt per request, so each request built its own empty nonce cache and no nonce was ever seen twice. The existing test validated a *different* configuration (a long-lived hand-built service) | **CLOSED** |
| **M-2** | MEDIUM | `PERFORMED` meant two different things — "every scanner ran" for residual, "at least one method was attempted" for recovery. Assurance `PASSED` was reachable on one weak method | **CLOSED** |
| **L-1** | LOW | The AI structural AST control is a denylist; `importlib.import_module` and new module paths would evade it | **OPEN** |
| **F-1** | INFORMATIONAL | `SIGNATURE_VALIDITY` can PASS on certificate-controlled material — by design, which is why `SIGNER_TRUST` is a separate dimension (§21) | Accepted |
| **F-2** | LOW | Trust validity window is evaluated against certificate-claimed time | **OPEN** |
| **F-3 / N-1** | LOW | Nonce cache does not survive restart, and is per-application-object so it does not span multiple workers | **OPEN — documented limitation** (§25, §36.5) |

### Remediation and post-remediation re-audit

**M-1** was closed at the root cause: the cache now lives on `app.state` for the application's
lifetime and is injected into the per-request service. A defect was found *while fixing the
defect* — `config.replay_cache or ReplayCache(...)` discarded an injected-but-empty cache because
`ReplayCache` defines `__len__` and an empty cache is falsy, reintroducing M-1 in exactly the
case that matters, the first request after startup. Corrected to an `is not None` check, with a
regression test.

**M-2** was closed by measuring recovery coverage against the methods this build can actually
perform, and by adding `PARTIAL` so that a genuine but incomplete search is neither discarded as
inconclusive nor promoted to `PASSED`. The alternative — requiring all methods — was rejected
because it would have made assurance permanently inconclusive, which is a different way of being
useless.

The independent post-remediation re-audit confirmed both **CLOSED at the root cause**, verified
by executing the attacks rather than by reading the new tests. Remaining: one LOW (N-1,
multi-worker scope), plus the informational observations above.

### Defects found later, by running the system rather than reading it

| Defect | Impact | Status |
|---|---|---|
| Every analyzed target reported as **0 bytes** — the route read a key the analyzer publishes only inside `metadata` | An operator saw "0 bytes" for the file they were about to erase; operations persisted `total_size=0` | **Fixed**, with a regression test |
| The closed-loop pipeline emitted almost nothing to the audit log | The primary destructive path recorded one generic state change. A log that records logins but not the erasure is worse than none, because it looks complete | **Fixed** — five event types now recorded |
| Alembic ignored `OBLIVION_DATABASE_URL` | Migrations were applied to whatever database sat in the working directory and could not be exercised against a throwaway one — which is how they stayed untested | **Fixed** |
| `devAuth.ts` claimed to be dead-code-eliminated from production builds | Measured: the gate *does* compile to `return false` and every persona path is unreachable, but the persona constants **do** ship. Not a privilege path; an inaccurate claim | **Documentation corrected** (§36.6) |

---

## 32. Test and Verification History

### Current authoritative state

| Gate | Result |
|---|---|
| Backend pytest | **591 passed, 3 skipped, 1 xfailed** |
| mypy (strict) | **clean, 115 source files** |
| Frontend Vitest | **221 passed, 0 failed** (21 files) |
| Frontend typecheck | **clean** |
| Frontend lint | **clean** (`--max-warnings 0`) |
| Frontend build | **OK** |
| OpenAPI contract gate | **OK — 21 operations, 20 paths** |
| Live backend E2E | **29/29 steps** |

### Three distinct levels of verification — do not conflate them

| Level | What it exercises | Status |
|---|---|---|
| **Automated tests** | Units, integration, API via `TestClient`; frontend components with the real query layer, capability gate and HTTP client over a stubbed network | **Performed** |
| **Live backend E2E** | A real `uvicorn` server, real HTTP, real bearer tokens, a real file erased on a disposable non-system volume, real certificate verification, real audit chain and real injected tampering | **Performed — 29/29** |
| **Browser / live-frontend E2E** | The actual UI driven against the live backend | **NOT PERFORMED** |

The link between the frontend and the live backend is **mechanical rather than observed**: the
contract is generated from the running application, `check:contract` fails on drift, the
capability drift test fails if the registry and contract disagree, and the E2E confirms those
same paths and request shapes work live. No Playwright-style browser run was made, and none is
claimed.

### A correction worth recording

The first version of the E2E's separation-of-duties step **passed for the wrong reason**. An
INVESTIGATOR does not hold `operation.approve` at all, so the 403 came from the permission guard
and the duty-split rule was never reached. The step was rewritten to use an ADMIN — who holds
every permission — attempting to approve their own request, so a 403 can only come from the rule
being tested. A test that passes without exercising the control it names is worse than no test.

---

## 33. Current Architecture Diagram

```
                        ┌────────────────────────────┐
   Operator / Auditor   │  React console             │
   ────────────────────►│  · renders backend truth   │
                        │  · role gating = usability │
                        └──────────────┬─────────────┘
                                       │ bearer session (in-memory only)
                        ┌──────────────▼─────────────┐
                        │  FastAPI  (unprivileged)   │
                        │                            │
                        │  auth → RBAC → SoD → policy│
                        │  → safety validation       │
                        └──────┬──────────────┬──────┘
                               │              │
                  ┌────────────▼───┐   ┌──────▼──────────────┐
                  │ ClosedLoop     │   │ AuditLog            │
                  │ Pipeline       │   │ append-only, chained│
                  │ 12 stages      │   └──────┬──────────────┘
                  └────────┬───────┘          │
                           │ OBLIVION-PRIV-1  │
                           │ HMAC over canon  │
                  ┌────────▼───────┐          │
                  │ Privileged svc │          │
                  │ 6 operations   │          │
                  │ own allowed    │          │
                  │ roots          │          │
                  └────────┬───────┘          │
                           │                  │
                  ┌────────▼───────┐          │
                  │  NTFS          │          │
                  └────────────────┘          │
                                              │
       ┌──────────────────────────────────────▼───────────────┐
       │  SQLite  ·  evidence · certificates · audit_events    │
       └──────────────────────────────────────────────────────┘

       Advisory AI — recommends only, NOT in the destructive path
```

---

## 34. End-to-End Demonstration Procedure

> **Safety:** use a disposable directory on a **non-system volume**. `SafePathValidator` refuses
> every target on the boot volume, which is where Windows temp directories usually live.

### 1. Configure

```
OBLIVION_DATABASE_URL=sqlite:///demo.db
OBLIVION_ALLOWED_ROOTS=E:\oblivion-demo\scratch
OBLIVION_VAULT_DIR=E:\oblivion-demo\vault
OBLIVION_VAULT_ROOT=E:\oblivion-demo\vault
OBLIVION_VAULT_KEY=<64 hex characters>
OBLIVION_IPC_KEY=<64 hex characters>
OBLIVION_SIGNING_KEY=<64 hex characters>
OBLIVION_TRUSTED_SIGNERS=oblivion-issuer:<64 hex public key>
OBLIVION_BOOTSTRAP_ADMIN_USER=admin
OBLIVION_BOOTSTRAP_ADMIN_PASSWORD=<choose one>
```

Generate the signing key with `oblivion.certificate.keys.generate_signing_key()` and derive the
public half; the trust anchor must be the public key matching `OBLIVION_SIGNING_KEY`, or
`SIGNER_TRUST` will correctly report `NOT_CHECKED`.

### 2. Run

```bash
alembic upgrade head
python -m uvicorn oblivion.api:app --host 127.0.0.1 --port 8000
cd frontend && npm install && npm run dev
```

### 3. The sequence

| Step | Action | Expected |
|---|---|---|
| 1 | `GET /api/audit/events` with no credential | **401** `UNAUTHENTICATED` |
| 2 | Log in as admin | 200, bearer token |
| 3 | Log in with a wrong password | **401**, and an `AUTH_LOGIN_FAILED` record appears |
| 4 | Provision a second ADMIN, an OPERATOR and an AUDITOR | — |
| 5 | `POST /api/targets/analyze` on the sample file | 200, real size and SHA-256 |
| 6 | `POST /api/operations` (mode `SELECTIVE_PERMANENT`, policy `ERASURE.LOGICAL.SELECTIVE.V1`, `confirmation.acknowledged_risk = true`) | 202, `PENDING_APPROVAL` |
| 7 | Approve as the **requester** | **403 Separation of Duties**, and `OPERATION_APPROVAL_REFUSED` is recorded |
| 8 | Approve as the **second** admin | 200, `READY` |
| 9 | `POST /api/operations/{id}/pipeline` as the operator | 200, twelve stages, `certificate_id` |
| 10 | Check the file on disk | **gone** — re-observed, not inferred |
| 11 | `POST /api/certificates/{id}/verify` with expected operation and target | **`VALID`**, ten dimensions PASS |
| 12 | `GET /api/audit/events` as the auditor | The full act history |
| 13 | `GET /api/audit/events` as the operator | **403** — erasing ≠ auditing |
| 14 | `POST /api/audit/verify` | **`INTACT`**, with `does_not_prove` listed |
| 15 | Edit an `audit_events` row directly in SQLite, re-verify | **`BROKEN`** — `MUTATED_EVENT` + `BROKEN_PREDECESSOR`, `proves` empty |

---

## 35. Security Demonstration Scenarios

| # | Scenario | Demonstrates | Observed result |
|---|---|---|---|
| 1 | **Unauthorized access** — call any protected route with no credential | Authentication is required and distinguishable from authorization | `401 UNAUTHENTICATED` |
| 2 | **Insufficient authority** — OPERATOR reads the audit log | RBAC; erasing does not confer auditing | `403 FORBIDDEN` |
| 3 | **Self-approval rejection** — requester approves their own operation | Separation of duties enforced against persisted state | `403` + `OPERATION_APPROVAL_REFUSED` recorded despite the rollback |
| 4 | **Approved execution** — second actor approves, operator runs | Duty split completes; execution is authorized, not assumed | `READY` → pipeline runs |
| 5 | **Real erasure** — the pipeline's ERASE stage | Destruction happens behind the privileged boundary | Stage `COMPLETED` |
| 6 | **Re-observation** — VALIDATE stage and direct filesystem check | "Engine reported success" ≠ "target is gone" | `exists() == False` |
| 7 | **Evidence** — evidence record persisted and chained | Canonical, hashed, linked | `EVIDENCE_RECORDED` |
| 8 | **Certificate** — issuance | Refused without signing identity, evidence, execution result and assurance | `CERTIFICATE_ISSUED` |
| 9 | **Certificate verification** — with a configured trust anchor | Signature validity and signer trust are separate dimensions | `VALID`, 10/10 PASS |
| 9b | **Certificate verification** — with **no** trust anchor | Fail-closed: unknown signer cannot yield VALID | `INCONCLUSIVE`, `SIGNER_TRUST = NOT_CHECKED` |
| 10 | **Audit log** — auditor reads the trail | Every act attributed to a server-derived identity | 16 records, 12 event types |
| 11 | **Audit tampering detection** — edit a row directly in the database | Two-layer detection; a broken chain proves nothing | `BROKEN`, `MUTATED_EVENT` + `BROKEN_PREDECESSOR`, `proves == []` |

---

## 36. Known Limitations

Stated plainly. Nothing here is hidden, and none of it is worked around by weakening a check.

1. **The browser UI was not driven against a live backend.** Automated frontend tests run the
   real component, query layer, capability gate and HTTP client with the network stubbed; the
   live E2E exercises the backend directly. No browser-level run links the two. (§32)
2. **No user-management endpoint exists.** Principals must be provisioned directly against the
   database; the Administration screen cannot create users.
3. **Capabilities absent from the contract**, each labelled in the registry with what the screen
   does instead: `targets.list`, `assurance.get`, `certificates.list`, `residual.findings`.
   (`operations.list` was one of these until `GET /api/operations` shipped.)
4. **Screens not individually live-verified**: Dashboard, Assurance, Residual, Recovery. They
   consume the generated contract and are covered by the contract gate and tests, but no live
   walkthrough was performed.
5. **Replay protection is process/application scoped** (finding N-1). It does not survive a
   restart and does not span multiple workers. A captured request stays replayable for the
   remainder of its freshness window; bounding that window is the mitigation. A persistent or
   shared nonce store is not implemented.
6. **Dev-persona constants remain in the production bundle but are unreachable.** The gate
   compiles to `return false` and every persona path throws, verified against the built bundle —
   but the persona array and banner string still ship, because the auth barrel re-exports the
   module and defeats tree-shaking. Wasted payload and a misleading thing to find in a forensic
   product's bundle; not a privilege path.
7. **Physical / NAND sanitization is unavailable.** `media_sanitization` and `raw_volume_access`
   are `UNAVAILABLE`. This build performs logical deletion only (§29).
8. **The audit chain is not externally anchored.** It detects edits to stored rows; it does not
   defend against an adversary who controls the application at write time and forges a consistent
   history from the genesis record forward. There is no external timestamping or third-party
   notarisation.
9. **Pre-existing repository-wide ruff findings remain** in older modules. None were introduced
   by recent work; clearing them is cleanup that has not been undertaken.
10. **`frontend/src/lib/api/contract-paths.ts` is a generated artifact** written by
    `scripts/gen_openapi.py` from the running application. It is a backend contract artefact
    rather than hand-written frontend code, and the contract gate fails if it is stale.
11. **Asynchronous execution is not implemented.** The pipeline endpoint runs synchronously; a
    long operation holds the request open, and progress streaming does not exist.
12. **Automatic startup reconciliation is not wired.** `OperationReconciler` exists and is tested,
    but nothing calls it during application start, so a `RECONCILIATION_REQUIRED` operation waits
    for a human.
13. **Certificate issuance has no standalone endpoint.** Issuance happens inside the pipeline.
14. **The AI structural control is a denylist** (finding L-1) with a known evasion path via
    `importlib.import_module`.

---

## 37. Future Scope

Clearly separated from current capability. **None of the following is implemented.**

| Area | Intended work |
|---|---|
| Media sanitization | Device-level Clear/Purge per NIST SP 800-88 Rev. 2 and IEEE 2883-2022, with device attestation |
| Raw volume forensics | MFT, USN journal, shadow copy and unallocated-space analysis to widen recovery-test coverage |
| External anchoring | Timestamping or third-party notarisation so audit history is provable against an outside reference |
| Distributed replay store | Shared, restart-persistent nonce storage to close N-1 across workers |
| User management API | Provisioning, role assignment and deactivation through the API |
| Collection endpoints | `targets.list`, `certificates.list`, assurance and residual reads |
| Asynchronous execution | Background pipeline execution with progress streaming |
| Startup reconciliation | Automatic invocation of `OperationReconciler` |
| Browser E2E | Playwright suite driving the console against a live backend |
| AI control inversion | Replace the AST denylist with an allowlist (L-1) |
| Cross-platform | Non-Windows filesystems |

---

## 38. Final Current-State Summary

Oblivion currently performs, end to end and verified against a live server:

authenticated access with distinguishable 401/403 · role-based authorization with audit access
restricted to ADMIN and AUDITOR · enforced separation of duties with refusals recorded · real
target analysis with true size and SHA-256 · policy-gated operation creation · a twelve-stage
closed loop executing real deletion behind a privileged boundary · post-state re-observation
rather than trusted reporting · per-method recovery testing · four-scanner residual analysis ·
coverage-driven assurance that will not round `INCONCLUSIVE` or `PARTIAL` up to success ·
canonicalized, hashed, chained evidence · Ed25519 certificate issuance and independent
ten-dimension verification reaching `VALID` with a configured trust anchor and `INCONCLUSIVE`
without one · and an append-only audit log whose chain reports `INTACT` and correctly reports
`BROKEN` when the database is edited underneath it.

It does **not** perform physical or NAND-level sanitization, does not claim universal
irrecoverability, holds no certification, and has not been exercised through a browser against a
live backend.

---

## 39. Repository Usage / Development Instructions

### Layout

```
src/oblivion/       backend implementation
tests/              backend test suite
frontend/           React console (src, tests, config)
alembic/            migrations
scripts/            gen_openapi.py, run_evaluation.py
evaluation/         dataset and baseline report
reference/          error codes, policy ids, operation states, example payloads
docs/               OBLIVION_DOCUMENTATION.md (this file) + OPENAPI.yaml (generated)
```

### Backend

```bash
pip install -r requirements.txt
alembic upgrade head
python -m pytest -q                      # 591 passed, 3 skipped, 1 xfailed
python -m mypy src/oblivion              # clean, 115 files
python -m ruff check src/oblivion
python -m uvicorn oblivion.api:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run check      # contract gate + typecheck + lint + test + build
```

### The contract gate

`docs/OPENAPI.yaml`, `frontend/src/lib/api/contract-paths.ts` and
`frontend/src/lib/api/contract-policies.ts` are **generated** from the running application:

```bash
python scripts/gen_openapi.py            # regenerate
python scripts/gen_openapi.py --check    # fail if stale
```

Never hand-edit them. If a route changes, regenerate and commit the result.

### Configuration

All configuration is by environment variable; see `.env.example`. Fail-closed behaviour is
deliberate:

| Variable | Absent → |
|---|---|
| `OBLIVION_IPC_KEY` | Privileged service `UNAVAILABLE_NO_KEY`, refuses all work |
| `OBLIVION_SIGNING_KEY` / `_FILE` | Cannot sign; issuance refused. Keys are never generated implicitly |
| `OBLIVION_VAULT_KEY` / `OBLIVION_VAULT_ROOT` | `recovery_vault` capability `UNAVAILABLE` |
| `OBLIVION_TRUSTED_SIGNERS` | `NullTrustStore`; `SIGNER_TRUST` is `NOT_CHECKED` and verdicts are `INCONCLUSIVE` |
| `OBLIVION_ALLOWED_ROOTS` | No target is contained; work is refused |

**Never commit a real key.** A wrong-length vault key is treated as *absent*, never padded or
hashed into shape — silently deriving a key from malformed input would make a misconfiguration
look like a working vault.

---

## 40. Demo Checklist

**Before**

- [ ] Disposable directory prepared on a **non-system volume**
- [ ] Sample files with known content created inside it
- [ ] `OBLIVION_ALLOWED_ROOTS` points at that directory and nothing else
- [ ] Signing key generated; matching public key set in `OBLIVION_TRUSTED_SIGNERS`
- [ ] IPC and vault keys set; `alembic upgrade head` run
- [ ] Second ADMIN, OPERATOR and AUDITOR accounts provisioned
- [ ] Backend and frontend both running

**Demonstrate**

- [ ] Unauthenticated call → **401** (not 403)
- [ ] Wrong password → **401**, and the attempt appears in the audit log with the username
      marked *claimed, not authenticated*
- [ ] Analyze a target → real size and SHA-256
- [ ] Create the operation → `PENDING_APPROVAL`
- [ ] **Requester approves own operation → 403 Separation of Duties**
- [ ] Second actor approves → `READY`
- [ ] Run the closed loop → twelve stages, each with its own status
- [ ] Show the file is gone **on disk**, not just in the response
- [ ] Show coverage: the method that ran, and the five never attempted, **by name**
- [ ] Verify the certificate → `VALID`, ten dimensions
- [ ] Unset the trust anchor → `INCONCLUSIVE`, `SIGNER_TRUST = NOT_CHECKED`
- [ ] Auditor reads the audit log → the full history
- [ ] **Operator** reads the audit log → **403**
- [ ] Verify the audit chain → `INTACT`, with `does_not_prove` on screen
- [ ] Edit a row in SQLite, re-verify → **`BROKEN`**, the mutated record named

**Say plainly**

- [ ] This is **logical deletion**, verified within a stated scope — not physical or NAND
      sanitization
- [ ] Terminology aligns to NIST SP 800-88 Rev. 2, ISO/IEC 27040:2024, IEEE 2883-2022 and
      IEEE 2883.1-2025; **no certification is held or claimed**
- [ ] A method that found nothing is evidence about that method, **not** proof of
      irrecoverability
- [ ] An intact audit chain proves the log was not altered — **not** that the erasure was sound


---

## 41. Repository Cleanup Record

The cleanup that produced this document, recorded so the removals are auditable.

### What was removed

| Category | Count | Detail |
|---|---|---|
| **Duplicate project trees** | 266 files | `OBLIVION/` (134) and `OBLIVION_BACKUP/` (132) - near-identical stale copies of the whole project committed inside the repository. They differed only by the **abandoned Phase 23 certificate WIP**: a `certificate/trust.py`, a divergent `certificate/verification.py`, and a competing `core/evidence/canonical.py`. That second canonicalizer is exactly what Phase 23 eliminated, and it is not revived. |
| **Root-level reports** | 18 | Phase, audit, freeze, remediation, handoff and milestone reports, plus two `.docx` references |
| **`docs/` specifications and reports** | 52 | 48 `docs/*.md` plus `docs/frontend/` (4) |
| **Frontend build documents** | 5 | Development plan, execution handoff, master build prompt, review checklist, auth/RBAC spec |
| **Build prompts** | 1 | `Oblivion_Engine_Features_and_Build_Prompts/` |
| **Machine-local settings** | 1 | `.claude/settings.local.json` untracked (kept on disk); it pinned a permission for a stale `D:\OBLIVION` path |

### Runtime artifacts removed from disk

`.mypy_cache` (16 MB) - `.pytest_cache` - `.ruff_cache` - `.pytest-scratch` - `.e2e-scratch` -
`oblivion.db` - `test_file.txt` - `frontend/dist` - 30 `__pycache__` directories.

None were tracked by git, and each is regenerated by its own tool. `frontend/node_modules`,
`package-lock.json` and `requirements.txt` were **not** touched.

### What was retained, and why

| Retained | Why |
|---|---|
| `src/`, `tests/`, `frontend/src/`, `alembic/`, `scripts/` | The implementation and its tests |
| `docs/OPENAPI.yaml` | **Required by the contract gate**; generated from the application |
| `reference/` | Compact operational reference data (error codes, policy IDs, operation states, example payloads). `core/policy/engine.py` cites `reference/POLICY_IDS.md` |
| `evaluation/` | Dataset and baseline report needed to reproduce the evaluation harness |
| `CLAUDE.md` | Active project/agent working instructions |
| `README.md` | Repository entry point, rewritten to point at this document |
| All build and lock files | `pyproject.toml`, `requirements.txt`, `alembic.ini`, `package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `.env.example` |

### Archived outside the repository

All 79 removed documents were copied to
`H:\final integration\oblivion-archive-2026-09-11\` before deletion -
`root-reports/`, `docs/`, `frontend-docs/`, `build-prompts/`, and `security-audits/`. The last
holds the independent Phase 23-27 security audit and the post-remediation re-audit, which had
never been committed to the repository at all. Everything also remains in git history; no
history was rewritten.

### Source cross-references

Fifteen files carried docstring or comment references to documents this cleanup removed. Each
was repointed to the corresponding section of this document. **Only comments changed** - the
staged diff over `src/`, `tests/` and `frontend/src/` contains no executable line.

An interim version of those references spelled out each section title, which pushed nine lines
past the 100-character limit and raised the repository's ruff count from 191 to 200. They were
compressed to `docs/OBLIVION_DOCUMENTATION.md §NN`, returning the count to exactly 191.
Cleanup that leaves the tree measurably worse than it found it is not cleanup.

### Secret scan

**Clean.** Every pattern match is either an environment-variable *name*
(`ENV_SIGNING_KEY = "OBLIVION_SIGNING_KEY"`) or a synthetic test fixture. No PEM block exists
anywhere in the tree. The one 64-character hex value, in `.env.example`, is a single repeated
character and is commented out, directly beneath the line "Never commit a real key". The
duplicate trees were scanned before removal; their only high-entropy strings were SHA-256 test
vectors. No file was modified to conceal a finding.

### Measurements

| | Before | After | Change |
|---|---|---|---|
| Tracked files | 646 | **304** | -342 (-53%) |
| Tracked content | 3.16 MB | **1.99 MB** | -1.17 MB (-37%) |
| Working tree (excl. `node_modules`, `.git`) | ~23 MB | **~4 MB** | -19 MB, mostly the 16 MB mypy cache |
| Documentation files | 79 across 5 locations | **1 canonical + 1 generated contract** | - |

### Validation - no functional regression

Every gate produced **exactly** its pre-cleanup result:

| Gate | Before | After |
|---|---|---|
| Backend pytest | 562 passed, 2 skipped, 1 xfailed | **591 passed, 3 skipped, 1 xfailed** |
| mypy (strict) | clean, 115 files | **clean, 115 files** |
| ruff (`src/oblivion`) | 191 pre-existing | **191** |
| Frontend Vitest | 205 passed | **221 passed** |
| Frontend typecheck | clean | **clean** |
| Frontend lint | clean | **clean** |
| Frontend build | OK | **OK** |
| OpenAPI contract gate | OK, 20 paths | **OK, 20 paths** |
| Alembic history | 4 revisions to `0004_audit_chain` | **4 revisions, intact** |

No test was weakened, skipped or deleted. No security control was altered. `H:\OBLIVION`, the
protected reference tree, remains at `b91cc45` with only the pre-existing working-tree changes
it had before this project began.
