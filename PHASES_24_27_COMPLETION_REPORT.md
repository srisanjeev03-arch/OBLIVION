# Phases 24–27 — Backend Implementation Milestone

**Branch:** `pre-phase23-repair` (not merged, no remote)
**Final HEAD:** `df44bee`
**Started from:** `8744305` — the merge-gated Phase 23 tree

---

## Status vocabulary

The brief requires these be distinguished, so they are used strictly:

| Term | Meaning here |
|---|---|
| **IMPLEMENTED** | Real code, not a placeholder |
| **TESTED** | Exercised by tests that would fail if it broke |
| **INTEGRATED** | Reachable from a real application path |
| **AVAILABLE** | Works in this environment |
| **UNAVAILABLE** | Cannot work here; reported as such, never degraded silently |
| **DEFERRED** | Deliberately not built; named in the docs |

---

## Section 0 — Reconciliation (done before implementing)

| Check | Result |
|---|---|
| Phase 23 HEAD confirmed | `8744305` (+ docs `1ea926a`) |
| Phase 23 present in tree | Yes — 286 tests passing at start |
| Backend tests | 286 passed, 0 failed |
| mypy | Clean, 88 source files |
| Unresolved Phase 23 security defect | **None found** — built on it rather than reworking it |

Inspected before writing code: `DEVELOPMENT_PLAN.md`, `PRIVILEGE_BOUNDARY.md`,
`AI.md`, `SafePathValidator`, `PolicyEngine`, `ErasureEngine`, `RecoveryVault`,
discovery, baseline, dry-run, residual, assurance, evidence, certificate,
persistence models and repositories, API routes and dependencies, test fixtures.

---

## PHASE 24 — Privileged Execution Boundary

**Implementation status: IMPLEMENTED, TESTED, INTEGRATED.**

`src/oblivion/privileged/` — protocol, validation, service, transport, client.

- Closed operation set: six operations, exactly the ones
  `PRIVILEGE_BOUNDARY.md` names. No `execute_command`, no shell, no arbitrary
  executable. Dispatch is an explicit enum→method mapping, never a name lookup.
- Wire protocol `OBLIVION-PRIV-1`: 4-byte length prefix + UTF-8 JSON, 1 MiB cap,
  byte-mode pipe.
- HMAC-SHA256 over the **Phase 23 canonical bytes**, so verification and use
  cover identical bytes.
- Replay protection: single-use nonces retained exactly as long as a request
  bearing one could still pass freshness.
- Named pipe with ACL `D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;<creator SID>)`,
  remote clients rejected, protected DACL.
- Crash reconciliation: `RECONCILIATION_REQUIRED` state + `OperationReconciler`.

**Tests: 87 passed, 1 skipped** (symlink creation — unprivileged Windows).
Includes a **real named-pipe round trip** across a thread boundary.

**Security status: no findings.**

| Property | Verified by |
|---|---|
| No execution primitive in the package | AST/source scan of all 5 modules |
| Operation set cannot be widened accidentally | Enum asserted by equality |
| Unknown/case-variant operations refused | 12 parametrized cases |
| Unknown fields refused, not ignored | Test |
| Secret-named parameters refused | 10 parametrized cases |
| Wrong MAC / altered request refused | Tests |
| Replayed request refused | Test |
| Stale and future-dated requests refused | Tests |
| No fallback key — unconfigured service refuses all | Tests |
| Containment/policy/identity decided service-side | Tests incl. TOCTOU substitution |
| Restore never overwrites | Test |
| `media_sanitization`, `raw_volume_access` = UNAVAILABLE | Tests |

Reconciliation never reports `COMPLETED` — an interrupted operation did not run
the stages completion implies. Target gone → `PARTIAL`; target present →
`FAILED`; filesystem unreadable → `INCONCLUSIVE`, never folded into "present".

---

## PHASE 25 — Closed-Loop Pipeline

**Implementation status: IMPLEMENTED, TESTED, INTEGRATED.**

`ClosedLoopPipeline` runs all twelve stages. Every previously orphaned module
now has a real caller:

| Module | Caller |
|---|---|
| `BaselineManager` | `_capture_baseline` |
| `DryRunPlanner` | `_recommend` |
| Residual scanners | `_analyse_residuals` |
| `AssuranceEngine` | `_assess` |
| `EvidenceGenerator` | `_generate_evidence` |
| `CertificateIssuer` | `_issue_certificate` |
| `verify_certificate` | `_verify_certificate` |
| `RecoveryTester` (new) | `_test_recovery` |

`ForensicRecoveryEngine` remains **unwired** — its two defects are still
`xfail(strict)` and fixing them means implementing real forensic recovery.
`RecoveryTester` is the honest, working replacement for the recovery-test stage.

### Complete pipeline trace (measured, not asserted)

`test_a_full_operation_runs_every_stage` — real file → real approval → real
privileged deletion → real recovery attempt → real residual scan → real
assurance → persisted evidence → signed certificate → independent verification
`VALID`, final state `COMPLETED`. Through HTTP as well, in
`test_an_approved_operation_runs_the_whole_loop`.

### Residual analysis upgraded beyond path existence

Four scanners: `path_existence`, `content_copy_by_hash`, `name_remnants`,
`alternate_data_streams`. The hash scanner catches the case path-checking cannot
see — the named file is gone but a byte-identical copy survives — and a test
proves it blocks positive assurance.

### The claim never made

`RecoveryTestReport.universal_irrecoverability` is permanently `None`.
`MethodOutcome` **raises** if a method that did not run reports a result. Five
methods are named as not attempted rather than omitted.

**Tests: 33 passed** (17 pipeline + 16 API).

**Evidence/certificate status:** evidence persisted for every run *including
refusals*; certificate issued only with signing identity + evidence + execution
+ assurance; `INCONCLUSIVE`/`PARTIAL` never promoted to `COMPLETED`.

**Security status: no findings.** Unapproved and self-approved operations are
refused before anything destructive and the target survives; a posted
`target_path` cannot redirect an approved erasure; a posted verdict is ignored;
concluded operations return 409.

---

## PHASE 26 — Advisory AI

**Implementation status: IMPLEMENTED, TESTED. Deliberately NOT INTEGRATED into
the erasure pipeline** — documented, not an oversight.

`src/oblivion/ai/` — schema, provider, validation, advisor.

**AI provider status: UNAVAILABLE in this environment.** No weights, no local
runtime. `provider_from_env()` returns `NullProvider` with a reason. This is the
correct output, and the pipeline is unaffected because it never consults the AI.

### Advisory-boundary verification

| Enforcement | Mechanism |
|---|---|
| Cannot reach execution | AST import-graph test over the whole package |
| Cannot express a decision | `advisory` is a read-only property; 7 authority fields refused |
| Cannot store hidden reasoning | 9 reasoning field names refused |
| Cannot make unsupported claims | 13 patterns over assessment, factors **and** limitations |
| Cannot bypass policy | Recommendation checked by `PolicyEngine` inside the advisor |
| Cannot receive file contents | No parameter exists for it |
| No way to apply an advisory | `apply_is_not_supported()` raises, so the absence is discoverable |

**Tests: 44 passed.** Includes 10 unsafe-claim variants, 9 malformed-output
variants, and a test that accurate scoped language still passes — so the
validator does not push authors toward vagueness.

**Security status: no findings.**

---

## PHASE 27 — Evaluation and Fine-Tuning Decision

**Implementation status: IMPLEMENTED, TESTED. Fine-tuning NOT performed.**

`src/oblivion/evaluation/` + `evaluation/datasets/sensitivity_v1.jsonl` (55
cases, 11 adversarial) + `scripts/run_evaluation.py`.

### Baseline metrics — measured

| Metric | Value |
|---|---|
| accuracy | 1.000 |
| macro F1 | 1.000 |
| ECE | 0.319 |
| **overconfidence** | **−0.319** (underconfident) |
| unsafe claim rate | 0.000 |
| schema rejection rate | 0.000 |
| unsafe recommendation rate | 0.000 |
| abstention rate | 0.073 |

### Fine-tuning decision: `FINE_TUNING_NOT_REQUIRED`

Every measured criterion is within threshold. **Read with the three caveats that
ship inside the report:** the dataset and baseline rules share an author, so
1.000 is a sanity check and an upper bound rather than evidence of field
performance; every case is a filename, so nothing here measures sensitive
content hidden under an innocuous name; and 55 cases is small.

The honest reading: the harness works, the baseline is sane, and the decision
says nothing yet about a language model because none has been run through it.

**Reproducibility status: VERIFIED.** File order, no sampling, injectable clock;
a test asserts two runs produce byte-identical reports.

**Tests: 27 passed**, including hand-computed metric arithmetic — which caught
an error in my own worked example while the implementation was correct.

---

## Final acceptance gate

| Gate | Result |
|---|---|
| **Total tests** | **480** |
| Passed | **477** |
| Failed | **0** |
| Skipped | 2 (symlink creation unsupported — environmental) |
| xfailed | 1 (`ForensicRecoveryEngine`, documented, Phase 25 scope) |
| **mypy** | **Clean — 109 source files** |
| **ruff** | **Clean on all new code**; pre-existing debt untouched |
| **OpenAPI/contract** | **OK — 18 paths** (was 17) |
| **Evaluation harness** | Runs; `FINE_TUNING_NOT_REQUIRED` |
| `H:\OBLIVION` | **Unchanged** — `b91cc45`, same 5 pre-existing entries |

Test growth: 286 → 477 (+191).

---

## Security findings

**None.** All thirteen hard-stop conditions checked:

| # | Condition | Result |
|---|---|---|
| 1 | Unauthorized user executes destructive op | No — 401/403 tested, target survives |
| 2 | SafePathValidator bypassable | No — service re-validates with its own roots |
| 3 | FastAPI acquires raw drive handles | No — searched; zero matches anywhere in `src/` |
| 4 | AI reaches destructive execution | No — import-graph test |
| 5 | Missing evidence → PASS | No |
| 6 | NOT_CHECKED → PASS | No |
| 7 | FAILED → PASS | No |
| 8 | VALID without independent evidence | No |
| 9 | Certificate trusts its own key | No (Phase 23, re-verified) |
| 10 | Hard-coded production secret | No — searched for 64-hex literals; zero |
| 11 | Execution without durable authorization | No — AUTHORIZE reads the persisted record |
| 12 | Restore silently overwrites | No — refused, tested |
| 13 | Reports physical sanitization not performed | No — only the AI prompt *forbidding* the claim matches |

---

## Known limitations and unsupported capabilities

**UNAVAILABLE in this build** (reported, never silently degraded):

- `media_sanitization` — no overwrite of any kind is performed
- `raw_volume_access` — no raw physical-drive handles
- MFT records, USN journal, shadow copies, unallocated-space carving, physical
  medium examination
- AI provider — no local weights or runtime present

**DEFERRED** (named in the phase docs):

- Packaged Windows service host (`serve_forever()` exists; installation does not)
- Cooperative cancellation of in-flight destructive work
- Automatic reconciliation on application startup
- Asynchronous pipeline execution / progress streaming
- Standalone certificate-issuance endpoint
- AI wired into the pipeline; advisory persistence; hosted providers
- Fine-tuning pipeline; inter-annotator agreement; cross-run regression tracking
- Append-only audit ledger — `EVIDENCE_CHAIN_INTEGRITY` stays `NOT_CHECKED`
  without a chain and no records are manufactured to make it pass

**Product-level, unchanged:** `COMPLETE_ERASURE` is logical removal of a tree,
not sanitization; `ForensicRecoveryEngine` defects remain `xfail(strict)`.

---

## Files changed

44 files, +12,363 / −4 since `8744305`.

New packages: `oblivion/privileged/` (5), `oblivion/core/pipeline/` (2),
`oblivion/ai/` (4), `oblivion/evaluation/` (5).
New modules: `core/state/reconciliation.py`, `core/recovery/testing.py`,
`core/residual/scanners.py`, `api/routes/pipeline.py`, `api/schemas/pipeline.py`.
New tests: 6 files. New docs: 4. New data: 1 dataset, 1 report.
Modified: `api/app.py`, `api/routes/__init__.py`, `api/dependencies.py`,
`core/state/machine.py`, `pyproject.toml`, `docs/OPENAPI.yaml`,
`frontend/src/lib/api/contract-paths.ts` (one generated line — see below).

### One flagged decision

`frontend/src/lib/api/contract-paths.ts` gained **one line**. It is generated by
`scripts/gen_openapi.py` from the FastAPI definitions and validated by the
backend's own contract gate, which **fails if it is stale**. Your no-frontend
rule and your OpenAPI gate conflict here. I judged it a machine-generated
backend contract artifact rather than frontend work, regenerated it, and am
flagging it rather than choosing silently. To revert:
`git checkout -- frontend/src/lib/api/contract-paths.ts` (the contract gate will
then report STALE).

---

## Commits

| SHA | Summary |
|---|---|
| `53e99dd` | Phase 24 — authenticated privileged boundary over a named pipe |
| `3a27a02` | Phase 24 — reconcile interrupted operations against the filesystem |
| `bb5ef3a` | Phase 25 — close the loop from discovery to independent verification |
| `e8c962e` | Phase 25 — expose the loop as `POST /api/operations/{id}/pipeline` |
| `cf17f14` | Phase 26 — provider-agnostic advisory AI that structurally cannot decide |
| `821e83b` | Phase 27 — deterministic evaluation harness and measured decision |
| `df44bee` | Docs — Phases 25–27, each naming what is *not* implemented |

---

## Completion statement

Phases 24–27 are **implemented, tested and integrated** as described above, with
every unavailable capability reported as unavailable and every deferred item
named. Three defects were found by running the code rather than reading it — a
truncated-handle ctypes bug, a message-mode framing bug, and a baseline analyser
constructed with the wrong validator — and all three are fixed. One decision
rule was corrected after its first run produced an answer that was
technically-derived and wrong.

Nothing here claims a capability this build does not have.
