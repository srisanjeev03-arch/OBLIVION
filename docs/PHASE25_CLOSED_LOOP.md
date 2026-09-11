# Phase 25 — The Closed Loop

This document describes what is **implemented and tested** in this tree.
Anything not built is under "Not implemented" and is named as such.

## What changed

`BaselineManager`, the residual scanners, `AssuranceEngine`, evidence generation
and certificate issuance all worked before this phase and none of them called
each other. `ClosedLoopPipeline` connects them, so one operation now runs:

```
DISCOVER → BASELINE → RECOMMEND → AUTHORIZE → ERASE → VALIDATE
        → TEST RECOVERY → ANALYZE RESIDUALS → ASSESS ASSURANCE
        → GENERATE EVIDENCE → ISSUE CERTIFICATE → VERIFY CERTIFICATE
```

Every filesystem mutation goes through the Phase 24 privileged client, so
containment, policy and target identity are re-validated on the far side of the
boundary. The pipeline process never deletes anything itself.

## The three rules that shape it

**Every stage records what it did, including nothing.** A stage that was
skipped, refused or unavailable produces an outcome saying so. There is no path
where a stage silently does not happen and the pipeline continues as if it had.

**Later stages cannot invent earlier ones.** Assurance consumes the coverage the
recovery and residual stages actually reported. If a scan did not run, coverage
is `NOT_PERFORMED` and assurance is inconclusive *by construction* — not because
the pipeline chose caution, but because `AssuranceEngine` cannot reach a positive
verdict without evidence the analyses ran.

**A certificate needs more than a successful delete.** Issuance is refused
without all four of: a signing identity, an evidence record, a real execution
result, and a real assurance assessment.

## Stage reference

| Stage | What it establishes | When it does not run |
|---|---|---|
| DISCOVER | Target inspected via the privileged boundary | Service unreachable → `UNAVAILABLE` |
| BASELINE | Pre-operation state incl. SHA-256 | Capture failed → `FAILED`; later stages degrade |
| RECOMMEND | Dry-run plan. **Grants no authorization** | Planning error → `FAILED` |
| AUTHORIZE | A durable approval by a second actor | Not approved / self-approved → `REFUSED`, pipeline stops |
| ERASE | The destructive step, performed privileged | Refused or unreachable → nothing is destroyed |
| VALIDATE | Post-state, **re-observed** not trusted | No execution → `SKIPPED` |
| TEST RECOVERY | Which methods got the data back | No baseline → `UNAVAILABLE` |
| ANALYZE RESIDUALS | What the operation left behind | No baseline → `UNAVAILABLE` |
| ASSESS ASSURANCE | Verdict from real coverage | Always runs; inconclusive without coverage |
| GENERATE EVIDENCE | Persisted evidence record | Generation error → `FAILED`, no certificate |
| ISSUE CERTIFICATE | Signed certificate | Missing prerequisites → `REFUSED`/`UNAVAILABLE` |
| VERIFY CERTIFICATE | Independent verification | Only when a certificate exists |

VALIDATE deliberately re-observes the filesystem rather than trusting the
execution result. "The engine reported success" and "the target is actually
gone" are two different facts, and only the second is evidence.

## Authorization

Read from the **persisted operation record**, never from the caller:

- the operation must exist
- its state must be `READY`
- `approved_by` must be set
- `approved_by` must differ from `requested_by`

Failing any of these stops the pipeline before anything destructive, and the
target survives untouched. Holding the `operation.execute` permission is
necessary to reach the endpoint and **not sufficient** to run an operation.

## Residual analysis — what it actually looks for

No longer path-existence only. Four scanners:

| Scanner | Looks for | Confidence |
|---|---|---|
| `path_existence` | Is the target still at its path (`lexists`, so a dangling symlink counts as surviving) | HIGH |
| `content_copy_by_hash` | A byte-identical copy elsewhere in scope | HIGH |
| `name_remnants` | `file.txt~`, `.bak`, `~$file` beside the original | MEDIUM |
| `alternate_data_streams` | NTFS named streams a directory listing hides | MEDIUM |

`content_copy_by_hash` is the consequential one: erasing a named file does not
erase its content if a copy sits beside it, and no amount of path checking sees
that.

**Findings and coverage are separate axes.** A scanner that could not run
degrades coverage rather than contributing to "nothing was found". Coverage is
`PERFORMED` only when every scanner ran.

## Coverage vocabulary

One word, one meaning, used identically by the residual sweep and by recovery
testing. Audit finding M-2 was that `PERFORMED` previously meant "every scanner
ran" on one side and "at least one method was attempted" on the other.

| State | Meaning |
|---|---|
| `NOT_PERFORMED` | Never attempted |
| `UNAVAILABLE` | Attempted, but nothing this build supports could run here |
| `INCONCLUSIVE` | Ran but reached no determination |
| `PARTIAL` | Ran, but did not cover every supported method or scanner |
| `PERFORMED` | **Every unit of work this build supports** ran |

`PERFORMED` is complete coverage *of what this build supports*. It is never a
claim that unsupported techniques were applied — those are limitations, listed
by name in every report and never folded into the state.

**Recovery coverage** is measured against the methods this build can actually
perform (`filesystem_enumeration`, and `vault_round_trip` when a vault object is
probed). The five permanently-unavailable forensic methods are not gaps this
operation could have closed, so they do not drag coverage down — but they are
enumerated in `method_coverage.unavailable` on every result.

**Residual coverage** is measured against the four scanners, all of which are
supported; one that cannot run makes the sweep `PARTIAL`.

### What is recorded, not inferred

Neither report reduces to a boolean. Each carries named lists:

- `recovery_report.method_coverage` → `supported`, `attempted`, `successful`,
  `failed`, `unavailable`
- `residual_report.scanner_coverage` → `supported`, `ran`, `inconclusive`,
  `unavailable`

"Recovery testing was performed" is not a fact anyone can check.
"`filesystem_enumeration` ran and found nothing; five other methods were never
attempted" is.

### How assurance reads partial coverage

| Coverage | Assurance |
|---|---|
| Any required analysis `NOT_PERFORMED`, `UNAVAILABLE` or `INCONCLUSIVE` | `INCONCLUSIVE` — nothing to reason from |
| Any required analysis `PARTIAL` | **`PARTIAL`** — real evidence, incomplete search |
| All `PERFORMED`, non-critical residual findings present | `PARTIAL` |
| All `PERFORMED`, nothing found | `PASSED` |

A conclusive negative still overrides everything: a recovery method that
*recovered* the data, or a critical residual finding, yields `FAILED` regardless
of how complete the search was.

`PARTIAL` exists because discarding a genuine but incomplete search as
inconclusive would be as wrong as calling it `PASSED`.

### Residual limitations

Not performed, and reported as limitations on every operation:

- MFT record inspection (needs raw volume access)
- USN journal inspection (needs raw volume access)
- Volume shadow copy inspection
- Unallocated-space carving (needs raw volume access)
- Physical medium examination

## Recovery testing — and the claim never made

Results are scoped **per method**. The rule this enforces:

> A recovery method that found nothing is evidence about **that method**. It is
> not proof that the data is unrecoverable.

| Method | Status here |
|---|---|
| `filesystem_enumeration` | **Attempted.** Target present, or a byte-identical copy in scope, means the data is trivially recoverable |
| `vault_round_trip` | **Attempted** for CONTROLLED_RECOVERABLE. Success is the *correct* outcome — the mode promises recoverability |
| `mft_record`, `usn_journal`, `shadow_copy`, `unallocated_carving`, `physical_medium` | **Not attempted.** Named in the output, never silently omitted |

`RecoveryTestReport.universal_irrecoverability` is a permanently-`None` property
with a docstring explaining why it can never be otherwise. `MethodOutcome`
raises if a method that did not run tries to report a result, so an unavailable
capability cannot quietly strengthen a verdict.

## Assurance semantics

`AssuranceEngine` maps to the certificate result without rounding up:

| Assurance | Certificate result |
|---|---|
| `PASSED` | `COMPLETED` |
| `PARTIAL` | `PARTIAL` |
| `INCONCLUSIVE` | `INCONCLUSIVE` |
| `FAILED` | `FAILED` |

`INCONCLUSIVE` and `PARTIAL` stay themselves. A certificate that promoted them
to `COMPLETED` would be the exact fabrication this system exists to avoid.

## The API

`POST /api/operations/{operation_id}/pipeline` — permission `operation.execute`.

**No request body.** Target, mode, policy and approval come from the persisted
operation; the actor comes from the authenticated session. That shape is the
security property: there is no field in which to name a different path, so an
approved erasure cannot be redirected, and no field in which to name an actor,
so identity cannot be spoofed. Both are tested.

A `200` does not mean the target was erased — it means the pipeline ran and
reported what happened, which may be a refusal. Read `final_state` and the
per-stage statuses. A null `certificate_id` is a normal, meaningful outcome.

Re-running a concluded operation returns `409`: one act, one certificate.

## Evidence chain — the boundary, stated plainly

The pipeline persists evidence and loads the chain from storage for
verification, as an independent verifier would.

`EVIDENCE_CHAIN_INTEGRITY` still checks only what Phase 23 implements: digest
correctness, predecessor naming and predecessor-digest matching over a supplied
sequence. **It is not an append-only ledger** and cannot detect wholesale
reconstruction of history. That needs the later audit-log phase, and until it
exists the dimension stays `NOT_CHECKED` when no chain is supplied. No records
are manufactured to make it pass.

## Not implemented in this phase

- **Certificate issuance as its own endpoint.** Issuance happens inside the
  pipeline; there is no standalone `POST /api/certificates`.
- **Asynchronous execution.** The endpoint runs the pipeline synchronously. A
  long operation holds the request open; progress streaming is not built.
- **Automatic reconciliation on startup.** `OperationReconciler` exists and is
  tested, but nothing calls it during application start yet.
- **AI in the pipeline.** The Phase 26 advisory layer is deliberately not wired
  into this path. See `docs/PHASE26_AI_BOUNDARY.md`.
