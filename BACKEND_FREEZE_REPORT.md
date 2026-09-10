# Backend Freeze Report — Phases 23–27

Read-only reconciliation. No feature was implemented, no test was added,
removed or modified, and no source file was changed while producing this.

---

## A. HEAD

`5456509e071a7bf36c051c2f23dafe66443c8716` (`5456509`)

## B. Branch

`pre-phase23-repair` — **not merged, not pushed, no remote configured.**

## C. Commit history

Twelve commits from `b91cc45` (the last pre-Phase-23 frontend commit) through
HEAD. Total: **90 files changed, +18,251 / −1,101**.

| # | SHA | Purpose | Files | Δ |
|---|---|---|---|---|
| 1 | `1358218` | Repair pre-Phase-23 blockers; make the repo self-contained | 17 | +1859 −118 |
| 2 | `e4b5a37` | Evidence foundation, certificate issuance, independent verification | 28 | +3481 −966 |
| 3 | `8744305` | Reconcile stale pre-auth test contracts; close coverage gaps | 7 | +224 −19 |
| 4 | `1ea926a` | Record the Phase 23 reconciliation / merge-gate result | 1 | +338 |
| 5 | `53e99dd` | Authenticated privileged execution boundary over a named pipe | 8 | +3308 −1 |
| 6 | `3a27a02` | Reconcile interrupted operations against the filesystem | 3 | +646 |
| 7 | `bb5ef3a` | Close the loop from discovery to independent verification | 5 | +2531 |
| 8 | `e8c962e` | Expose the closed loop as `POST /api/operations/{id}/pipeline` | 8 | +914 −2 |
| 9 | `cf17f14` | Provider-agnostic advisory AI that structurally cannot decide | 6 | +1476 −1 |
| 10 | `821e83b` | Deterministic evaluation harness and measured fine-tuning decision | 10 | +2665 |
| 11 | `df44bee` | Document Phases 25–27, each naming what is *not* implemented | 3 | +485 |
| 12 | `5456509` | Record the Phases 24–27 milestone result | 1 | +330 |

## D. Phase-to-commit mapping

| Commit | Phase | Files (grouped) |
|---|---|---|
| `1358218` | **Pre-Phase-23** | `certificate/keys.py`, `core/assurance/*`, `core/dryrun/planner.py`, `core/erasure/engine.py`, `api/dependencies.py`, `.env.example`, `.gitignore`, 2 docs, 3 tests |
| `e4b5a37` | **Phase 23** | `core/evidence/*`, `certificate/*`, `persistence/{models,repositories}/certificate*`, `api/routes/certificates.py`, `api/schemas/certificate.py`, alembic `0003`, `docs/OPENAPI.yaml`, 9 tests |
| `8744305` | **Phase 23** (tests) | 7 test files only |
| `1ea926a` | **Phase 23** (docs) | 1 report |
| `53e99dd` | **Phase 24** | `privileged/{protocol,validation,service,transport,client,__init__}.py`, 1 doc, 1 test |
| `3a27a02` | **Phase 24** | `core/state/{machine,reconciliation}.py`, 1 test |
| `bb5ef3a` | **Phase 25** | `core/pipeline/*`, `core/recovery/testing.py`, `core/residual/scanners.py`, 1 test |
| `e8c962e` | **Phase 25** | `api/routes/pipeline.py`, `api/schemas/pipeline.py`, `api/{app,dependencies}.py`, `api/routes/__init__.py`, 1 test, **`docs/OPENAPI.yaml` + `frontend/.../contract-paths.ts` = generated contract artifacts** |
| `cf17f14` | **Phase 26** | `ai/{schema,provider,validation,advisor,__init__}.py`, 1 test |
| `821e83b` | **Phase 27** | `evaluation/*`, `scripts/run_evaluation.py`, dataset + report, 1 test, **`pyproject.toml` = supporting lint config** |
| `df44bee` | **Documentation** | 3 phase docs |
| `5456509` | **Documentation** | 1 report |

### Flagged as not-primary-phase work

Two entries are not phase source code. Neither is unrelated:

1. **`docs/OPENAPI.yaml` + `frontend/src/lib/api/contract-paths.ts`** in
   `e8c962e` — generated contract artifacts, required by the contract gate,
   which fails if they are stale. Detail in section L.
2. **`pyproject.toml`** in `821e83b` — adds `"scripts/*" = ["T201"]` to ruff's
   per-file-ignores, declaring the pre-existing convention that CLI scripts
   print. Four lines, comment included. It changes no runtime behaviour.

**No unrelated change was found in any commit.** No history was rewritten.

## E. Test results (re-run for this report)

```
477 passed, 2 skipped, 1 xfailed          (13.52s)
```

| Suite | Result |
|---|---|
| Full suite | **477 passed, 0 failed** |
| Phase 24 (privileged IPC + reconciliation) | 87 passed, 1 skipped |
| Phase 25 (closed loop + API) | 33 passed |
| Phase 26 (AI boundary) | 44 passed |
| Phase 27 (evaluation harness) | 27 passed |
| Phase 27 evaluation run | accuracy 1.000, macro F1 1.000, unsafe claims 0, `FINE_TUNING_NOT_REQUIRED` |

**Skips (2), both environmental and identical in cause:**

- `test_erasure.py:100` — "Symlink creation not supported"
- `test_operation_reconciliation.py:245` — "Symlink creation not supported"

Unprivileged Windows cannot create symlinks. Neither concerns certificate,
evidence, privilege or AI security.

**xfail (1):** `test_recovery_engine_execution_success` — two real
`ForensicRecoveryEngine` defects, `strict=True` so it fails loudly if ever
fixed without updating the marker. Not skipped, not hidden. That engine has no
caller.

No test was deleted or modified in this task.

## F. mypy

```
Success: no issues found in 109 source files
```

## G. OpenAPI / contract

```
OK: docs/OPENAPI.yaml matches the running application (18 paths)
```

17 paths before this milestone; `POST /api/operations/{operation_id}/pipeline`
is the addition.

## H. Phase 24 — privilege boundary verification

Chain confirmed: **FastAPI (unprivileged) → authenticated named pipe → minimal
privileged service → filesystem operation.**

| Control | Evidence in tree |
|---|---|
| **Authentication** | `RequestAuthenticator.from_env` returns `None` when unset; service reports `UNAVAILABLE_NO_KEY` and refuses all work. **No fallback key.** |
| **HMAC** | `service.py:192` — `hmac.new(key, request.to_bytes(), sha256)` over the Phase 23 **canonical** bytes, so verification and use cover identical bytes. `service.py:201` — `hmac.compare_digest`, constant time |
| **ACL** | `transport.py:90` — `D:P(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;{sid})`. Protected DACL (`D:P`), SYSTEM + Administrators + creating account only |
| **Remote clients** | `PIPE_REJECT_REMOTE_CLIENTS` set at pipe creation |
| **Nonce handling** | `ReplayCache.remember` — check-and-insert together; retained exactly as long as freshness would accept the request |
| **Replay resistance** | `service.py:368` — a correctly formed, correctly signed request is refused on second arrival |
| **Crash reconciliation** | `core/state/reconciliation.py` — `RECONCILIATION_REQUIRED` is non-terminal; resolves to `PARTIAL` / `FAILED` / `INCONCLUSIVE`, **never `COMPLETED`** |
| **x64 handle correctness** | `_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value` (pointer width, not `-1`); **18 `argtypes` declarations** so handles are not truncated |
| **Message framing** | Byte-mode pipe (`_PIPE_TYPE_BYTE`) + 4-byte length prefix + exact-read loop; 1 MiB cap refused **before** allocation |

### Raw physical-drive access

**None introduced.** Searched all of `src/` for `PhysicalDrive` and
`CreateFileW`:

- `privileged/transport.py` — 3 uses, all opening the **named pipe**
- `core/discovery/__init__.py:49` — opens `str(p.absolute())`, a **file path**
- `core/safety/paths.py:74` — opens `path` with zero access to read the file
  index (TOCTOU identity)

The latter two are **pre-existing** — neither file appears in any Phase 24–27
commit — and neither opens a `\\.\PhysicalDriveN` or volume handle. The
privileged service reports `raw_volume_access` as **UNAVAILABLE**.

## I. Phase 25 — closed-loop verification

Connectivity established from call sites in `core/pipeline/orchestrator.py`,
not from module existence.

| Stage | Implementation | Caller (line) | Output | Next consumer | Persistence |
|---|---|---|---|---|---|
| Discover | `PrivilegedClient.inspect_target` | `run` → `_discover` (254) | analysis dict | stage record | — |
| Baseline | `BaselineManager.capture_baseline` | `_capture_baseline` (255) | `baseline` incl. SHA-256 | recovery, residual, evidence | in evidence |
| Recommend | `DryRunPlanner.plan` | `_recommend` (256) | plan + limitations | `result.limitations` | — |
| Authorize | `OperationRepository.get_operation` (434) | `_authorize` (258) | bool | gates everything after | reads `operations` |
| Erase | `PrivilegedClient.request` (509) | `_erase` (266) | `execution` | validate, evidence, issuance gate | filesystem |
| Validate | `os.path.lexists`, re-observed | `_validate` (267) | `verification` | evidence | — |
| Recovery test | `RecoveryTester.run` (624) | `_test_recovery` (268) | `recovery_report` | coverage, assurance, evidence | in evidence |
| Residual | `ResidualScanSuite.run` (664) | `_analyse_residuals` (269) | `residual_report` | coverage, assurance, evidence | in evidence |
| Assurance | `AssuranceEngine.assess` (708) | `_assess` (284) | `assurance` | evidence, cert result | in evidence |
| Evidence | `EvidenceGenerator.generate` (780) | `_generate_evidence` (288) | `EvidenceRecord` | issuance, verification | **`save_evidence` (781)** |
| Certificate | `CertificateIssuer.issue` (853) | `_issue_certificate` (300) | `Certificate` | verification | **`save_certificate` (860)** |
| Verification | `verify_certificate` (917) | `_verify_certificate` (304) | status | `result.verification_status` | **`load_evidence_chain` (903)** |

**Coverage is derived, not defaulted** (lines 271–283): `EvidenceCoverage` takes
`residual_report.coverage` and `recovery_report.coverage`, falling back to
`NOT_PERFORMED` when a stage produced nothing — so assurance cannot reach a
positive verdict on analyses that did not run.

**Reachable from the application:** `api/routes/pipeline.py:119` constructs
`ClosedLoopPipeline` and `:127` calls `.run(PipelineRequest(...))`.

End-to-end proof, executed not asserted: `test_a_full_operation_runs_every_stage`
(direct) and `test_an_approved_operation_runs_the_whole_loop` (over HTTP) both
carry a real file through all twelve stages to `verification_status == "VALID"`.

## J. Phase 26 — AI boundary verification

**AI remains advisory only.** The whole `oblivion/ai` package imports exactly
**one** external Oblivion module:

```
src/oblivion/ai/advisor.py:34: from oblivion.core.policy.engine import PolicyEngine, PolicyError
```

Read-only policy validation — required to check a recommendation, and incapable
of acting.

| Cannot | Enforced by |
|---|---|
| Execute filesystem operations | No import of `core.erasure`, `privileged`, or any subprocess primitive |
| Authorize / approve | No import of `core.auth`; authority fields refused by the validator |
| Bypass policy | `recommend_policy` runs the suggestion through `PolicyEngine`; a refused policy makes the whole result `REJECTED` |
| Bypass safety validation | No import of anything that acts on a path |
| Modify evidence | No import of `persistence` |
| Generate authoritative certificate claims | No import of `certificate.issuer`; `certificate_result` is a refused field |
| Alter assurance results | `assurance_status` is a refused field |

**Structural test still present and passing:**
`test_the_ai_package_imports_nothing_that_can_execute` walks every module with
`ast` against a forbidden list (`oblivion.core.erasure`, `oblivion.privileged`,
`oblivion.core.pipeline`, `oblivion.core.auth`, `oblivion.certificate.issuer`,
`oblivion.persistence`, `subprocess`, `os.system`). 44 Phase 26 tests pass.

The AI is **not wired into the Phase 25 pipeline** — deliberate and documented.

## K. Phase 27 — evaluation claim boundary

Every required statement is present. Located precisely:

| Required statement | Where |
|---|---|
| Dataset was authored for the evaluation | Report `caveats[0]`: "This dataset and the deterministic baseline rules were authored together" |
| Rules were authored for the evaluation | Same caveat, same clause |
| 1.000 accuracy is a sanity check | `caveats[0]`: "Treat the baseline's accuracy as a sanity check and an upper bound" |
| Not evidence of production model performance | `caveats[0]`: "never as evidence of real-world performance" |
| `FINE_TUNING_NOT_REQUIRED` is an evaluation decision, not proof of model superiority | `decision_reasons[0]`: "Fine-tuning is not justified **by this evaluation**"; `docs/PHASE27_EVALUATION.md`: "the decision says nothing yet about a language model because none has been run through it" |

The caveats live in the dataset file as `# caveat:` lines and are copied into
**every** report, so a number cannot be read apart from its qualification.

Two further caveats are recorded: filename-only cases measure nothing about
sensitive content under an innocuous name; 55 cases is small.

**The evaluation was not altered, improved or re-tuned in this task.**

## L. Frontend-change verification

**Exactly one frontend file changed across all twelve commits, by one line.**

```
frontend/src/lib/api/contract-paths.ts | 1 +

@@ -24,6 +24,7 @@ export const CONTRACT_OPERATIONS: readonly string[] = [
   'POST /api/operations/{operation_id}/execute',
+  'POST /api/operations/{operation_id}/pipeline',
   'POST /api/recovery-objects/{recovery_id}/restore',
```

| Question | Answer |
|---|---|
| Why generated | The contract gate validates it; `gen_openapi.py --check` reports **STALE** and fails if it is not regenerated after a route is added |
| Source that generated it | `scripts/gen_openapi.py`, from `docs/OPENAPI.yaml`, itself generated from the FastAPI application |
| Self-declared | File header: `// GENERATED FILE - DO NOT EDIT.` |
| Contains application logic? | **No** |
| Contains business logic? | **No** |
| Contains UI logic? | **No** |
| What it is | One string appended to a `readonly string[]` of endpoint paths |

**Nothing beyond the generated contract artifact changed.** No component, route,
style, state-management or frontend test was touched.

This is the one place the "no frontend edits" rule and the mandated OpenAPI gate
conflict. It was resolved by treating a machine-generated backend contract
artifact as backend output, and flagged rather than decided silently. To revert:
`git checkout -- frontend/src/lib/api/contract-paths.ts` — the contract gate
will then report STALE.

## M. Workspace integrity

| Check | Result |
|---|---|
| Git tree clean | **Yes** — only `?? test_file.txt` (known; produced by `test_crypto.py` writing to CWD; untracked, never committed) |
| `H:\OBLIVION` HEAD | **`b91cc45`, unchanged.** Reflog shows no commit after it |
| `H:\OBLIVION` working tree | Same 4 modified + 1 untracked entries as at session start; all three frontend files re-verified **byte-identical** to the authority checkout, so this milestone did not diverge them |
| Tracked private key material | **None** — no `.pem`, `.key`, `.pfx`, `.p12`, `id_rsa` or `.env` tracked |
| Credentials / 64-hex literals in tracked source | **None** |
| Tracked runtime state | **None** — no `.db`, `.sqlite`, `.log` or `__pycache__` tracked |
| Destructive ops on production/system/user data | **None** — every destructive test runs inside a per-test directory under `<repo>/.pytest-scratch`, with containment enforced by `SafePathValidator` |

Test key material is generated at runtime via `secrets.token_hex` /
`generate_private_key_hex` and never written to the tree.

## N. Known limitations

**UNAVAILABLE in this build** — reported as such, never silently degraded:

- `media_sanitization` — no overwrite of any kind is performed
- `raw_volume_access` — no raw physical-drive handles
- MFT records, USN journal, shadow copies, unallocated-space carving, physical
  medium examination
- AI provider — no local weights or runtime on this machine

**DEFERRED** — named in the phase docs:

- Packaged Windows service host (`serve_forever()` exists; installation does not)
- Cooperative cancellation of in-flight destructive work
- Automatic reconciliation at application startup (`OperationReconciler` exists
  and is tested; nothing calls it on boot)
- Asynchronous pipeline execution / progress streaming
- Standalone certificate-issuance endpoint
- AI wired into the pipeline; advisory persistence; hosted providers
- Fine-tuning pipeline; inter-annotator agreement; cross-run regression tracking
- Append-only audit ledger — `EVIDENCE_CHAIN_INTEGRITY` stays `NOT_CHECKED`
  without a supplied chain, and no records are manufactured to make it pass

**Product-level, unchanged by this milestone:** `COMPLETE_ERASURE` is logical
removal of a tree, not sanitization; `ForensicRecoveryEngine` defects remain
`xfail(strict)` and that engine is unwired.

**Environmental:** 2 symlink skips on unprivileged Windows.

## O. Exact next recommended step

**Owner review and merge decision on `pre-phase23-repair`.**

The branch carries Phases 23–27, is green on every gate, and is neither merged
nor pushed — as instructed. It cannot advance further without a decision only
the owner can make.

Before merging, one item needs an explicit ruling:
`frontend/src/lib/api/contract-paths.ts` (section L). Keep the generated line
and the contract gate passes; revert it and the gate reports STALE until the
frontend consolidation regenerates it.

After merge, the brief's own sequence resumes: frontend integration, then
duplicate cleanup and restructuring, then the independent audit — each a
separate stage, none started here.

---

## Final status

**BACKEND_FROZEN**

477 passed / 0 failed, mypy clean on 109 source files, contract OK at 18 paths,
the closed loop traced stage by stage to real callers, the privilege boundary
verified control by control, the AI boundary enforced structurally, the
evaluation's limitations stated in the artifact itself, exactly one generated
frontend line, and the twin untouched.
