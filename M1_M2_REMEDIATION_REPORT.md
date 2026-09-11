# Remediation of Audit Findings M-1 and M-2

Scope: M-1 and M-2 only. No other finding was remediated, no frontend work, no
cleanup or restructuring, and no Phase 23–27 behaviour changed except where
directly required.

---

# PART A — M-1, replay protection

## A. Original finding

> Replay protection ineffective in default in-process deployment; the test
> validates a different configuration.

The API constructed a new `PrivilegedService` per request, and therefore a new
empty `ReplayCache`, so a nonce could be reused across requests undetected. The
existing test used one long-lived service fixture and so exercised the
named-pipe posture rather than the one the API actually builds.

## B. Root cause

Two separate mistakes, and the second is the one that made it invisible.

**The lifetime mistake.** `get_privileged_client` is a per-request FastAPI
dependency with no caching. Its in-process branch called
`build_service_from_env(validator)`, which constructs `PrivilegedService`, whose
`__init__` built `ReplayCache(config.max_request_age)`. Every request therefore
started with an empty memory of nonces.

**The test-shape mistake.** `test_a_replayed_request_is_refused` called
`service.handle(...)` twice on a single fixture instance. That is a true
statement about a long-lived service and says nothing about the HTTP path. A
green suite was consistent with a non-functional control.

## C. Remediation

The service stays per-request — it is cheap and its validator must track
configuration — and **the cache no longer does**.

| Change | File |
|---|---|
| `ServiceConfig.replay_cache` — optional injected cache | `privileged/service.py` |
| `build_service_from_env(..., replay_cache=...)` forwards it | `privileged/service.py` |
| `app.state.privileged_replay_cache = ReplayCache()` created in `create_app()` | `api/app.py` |
| `get_replay_cache(request)` reads it, raising if absent | `api/dependencies.py` |
| `get_privileged_client` injects it into the per-request service | `api/dependencies.py` |

`app.state` rather than a module-level global: the cache's lifetime is exactly
the application object's, two apps in one process (as the tests create) get two
independent caches, and nothing outlives the app that owns it. `get_replay_cache`
raises `REPLAY_CACHE_UNAVAILABLE` rather than quietly creating one — silently
handing back a fresh cache would restore the defect while appearing to work.

### A defect found while fixing the defect

The first implementation used `config.replay_cache or ReplayCache(...)`.
`ReplayCache` defines `__len__`, so an **empty cache is falsy** — the injected
cache was discarded and a private one built, reintroducing M-1 in exactly the
case that matters, the first request after startup. Every test still passed,
because the HTTP test had not been written yet.

Fixed to `if config.replay_cache is not None`, with the reasoning recorded at
the call site and pinned by `test_an_injected_cache_is_used_even_when_empty`.

## D. HTTP replay proof

Three tests exercise the real FastAPI dependency path, not a hand-built service.

`test_the_replay_cache_is_shared_across_http_requests` — asserts the app holds
one cache across requests and that a request records nonces into *that* object.
This assertion was false before the fix.

`test_a_replayed_nonce_is_refused_across_two_http_requests` — the end-to-end
proof. `new_nonce` is replaced with a rewindable deterministic source so request
2 presents the same nonces request 1 used:

| | Result |
|---|---|
| HTTP request 1 | `200`, `final_state COMPLETED`, target erased |
| HTTP request 2 (same nonces) | `ERASE` stage **REFUSED**, detail "Nonce has already been used" |
| Second target | **survives**, content intact |
| Certificate | `None` |

`test_a_fresh_nonce_still_works_after_a_replay_was_refused` — a refusal must not
wedge the service; a subsequent unused nonce completes normally.

The pre-existing service-level replay tests were **retained**, not replaced.

## E. Concurrency result

`ReplayCache.remember` now performs eviction, membership check and insert under
a single `threading.Lock`. The halves are only a control together: between a
bare check and a bare insert, a second thread bearing the same nonce would also
see "not seen".

`test_only_one_of_many_concurrent_threads_may_claim_a_nonce` releases 32 threads
simultaneously on one barrier and asserts **exactly one** is admitted and the
cache holds one entry. Deterministic — the barrier makes it a real race rather
than an interleaving that happens to occur.

## F. Cache lifecycle

| Deployment | Owner | Protection lasts |
|---|---|---|
| HTTP API (in-process) | `app.state.privileged_replay_cache` | Life of the FastAPI application |
| Named-pipe host | The host's long-lived `PrivilegedService` | Life of that host process |

**Bounded twice.** Expiry is the ordinary mechanism: a nonce is dropped once a
request carrying it would be refused as stale anyway, so retention is tied to
the freshness window with no gap between them. A hard ceiling
(`DEFAULT_MAX_ENTRIES = 100_000`) bounds memory by construction rather than by
an assumption about traffic.

At the ceiling the cache **refuses rather than evicting a live nonce**
(`ReplayCacheFull` → service refusal). Forgetting an unexpired nonce to make
room would silently re-open its replay window; a refused legitimate request is
recoverable, an accepted replay is not. Capacity is reclaimed as entries expire
— tested.

## G. Restart limitation — stated, not fixed

**Replay protection is process/service lifetime only. It is NOT
restart-persistent, and nothing claims otherwise.**

A restart empties the cache, so a captured request remains replayable for the
remainder of its freshness window (default five minutes). Bounding that window
is the mitigation. No persistent nonce store was introduced — the brief
permitted process-scoped protection provided the limitation is stated clearly,
and `docs/PHASE24_PRIVILEGED_SERVICE.md` now states it in those words.

This is audit finding F-3, which remains **open by design** and was not in scope.

---

# PART B — M-2, coverage semantics

## H. Original finding

> `PERFORMED` coverage is strict for residual, lenient for recovery; assurance
> `PASSED` reachable on one weak method.

## I. Root cause

One word meant two things:

- `ResidualScanReport.coverage` → `PERFORMED` only when **every** scanner ran.
- `RecoveryTestReport.coverage` → `PERFORMED` when **any** method was attempted.

Both fed the same `EvidenceCoverage`, which `DefaultAssuranceRule` reads as a
single notion of "the required analysis ran". A reader could not distinguish a
complete search from a single filesystem-level one.

## J. New coverage semantics

`AnalysisState` gains `PARTIAL`, and `PERFORMED` now means the same thing on
both sides: **every unit of work this build supports ran**.

| State | Meaning |
|---|---|
| `NOT_PERFORMED` | Never attempted |
| `UNAVAILABLE` | Attempted, but nothing supported could run here |
| `INCONCLUSIVE` | Ran but reached no determination |
| **`PARTIAL`** | Ran, but did not cover every supported method or scanner |
| `PERFORMED` | Every supported method or scanner ran |

Coverage is measured against what this build **supports**. The five permanently
unavailable forensic methods are not gaps this operation could have closed, so
they do not drag coverage down — but they are enumerated by name in every
result, never folded into `PERFORMED`.

`EvidenceCoverage` gains `blocking_shortfalls()` (nothing to reason from) and
`partial_shortfalls()` (real but incomplete), so the assurance rule can treat
them differently instead of collapsing both into "inconclusive".

Recovery coverage now mirrors the residual shape exactly: all supported
`PERFORMED` → `PERFORMED`; some ran → `PARTIAL`; none → `UNAVAILABLE`.

## K. Recovery coverage examples

| Situation | Coverage |
|---|---|
| Only unperformable methods offered | `UNAVAILABLE` |
| 1 of 2 supported ran (e.g. no vault object to probe) | **`PARTIAL`** |
| Both supported methods ran | `PERFORMED` |
| Supported method ran and did not recover | `PERFORMED`, method listed under `failed` |
| Supported method ran and recovered | `PERFORMED`, listed under `successful`, `data_was_recovered` true |

`method_coverage` records `supported`, `attempted`, `successful`, `failed`,
`unavailable` as name lists. "Recovery testing was performed" is not a fact
anyone can check; "`filesystem_enumeration` ran and found nothing; five other
methods were never attempted" is.

## L. Residual coverage examples

| Situation | Coverage |
|---|---|
| All four scanners ran | `PERFORMED` |
| ADS scanner unavailable (non-NTFS host) | **`PARTIAL`** |
| No baseline hash, so the content scanner cannot run | **`PARTIAL`** |
| No scanner could run | `UNAVAILABLE` |

`scanner_coverage` records `supported`, `ran`, `inconclusive`, `unavailable`.

## M. Assurance behaviour

| Coverage | Assurance |
|---|---|
| Any required `NOT_PERFORMED` / `UNAVAILABLE` / `INCONCLUSIVE` | `INCONCLUSIVE` |
| Any required `PARTIAL` | **`PARTIAL`** (new) |
| All `PERFORMED`, non-critical residual findings | `PARTIAL` |
| All `PERFORMED`, nothing found | `PASSED` |

Conclusive negatives still override everything: a method that *recovered* the
data, or a critical residual finding, yields `FAILED` regardless of coverage —
tested under `PARTIAL` coverage specifically.

**No artificial lowering.** On a Windows host where all four scanners and the
supported recovery method run, coverage is `PERFORMED` on both axes and the
result remains `PASSED`, exactly as before. The brief warned against inventing a
stricter policy to make the finding disappear; `PASSED` is still reachable and
still earned. What changed is that an incomplete search is now *sayable*.

## N. API / schema changes

`POST /api/operations/{operation_id}/pipeline` gains a `coverage` object —
purely additive, no field removed or renamed:

```
coverage:
  residual_analysis: NOT_PERFORMED | UNAVAILABLE | INCONCLUSIVE | PARTIAL | PERFORMED
  recovery_test:     (same enum)
  recovery_methods:  { supported, attempted, successful, failed, unavailable }
  residual_scanners: { supported, ran, inconclusive, unavailable }
```

Explicit enums and named lists, so a client never infers coverage from list
emptiness or a boolean. The field description tells a reader directly that
`PASSED` with `PARTIAL` recovery coverage means no artifacts were found by the
methods that ran — not that every method was tried.

`docs/OPENAPI.yaml` regenerated. **No frontend file changed**: no route was
added, so the generated path and policy modules are byte-identical.

---

# PART C — Validation

## O. Regression results

| | Before | After |
|---|---|---|
| Tests passed | 477 | **505** |
| Failed | 0 | **0** |
| Skipped | 2 (symlink, environmental) | 2 (unchanged) |
| xfailed | 1 (documented) | 1 (unchanged) |

+28 tests. **No test was deleted, weakened or modified** except the additions
described above; the pre-existing service-level replay tests were retained
alongside the new HTTP ones.

Security suites re-run together: **270 passed** (privileged IPC, coverage
semantics, pipeline API, assurance, certificate, certificate API, auth/RBAC, AI
boundary).

New tests: 4 for M-1 (HTTP replay ×3, injected-cache regression) + 3 for cache
concurrency/bounds, 20 for M-2 coverage semantics, 1 API coverage contract.

## P. mypy

```
Success: no issues found in 109 source files
```

## Q. OpenAPI

```
OK: docs/OPENAPI.yaml matches the running application (18 paths)
```

Ruff: **clean on every file changed**. `api/app.py` retains 6 pre-existing
findings (`E501` on the long description literal, `ARG001` on FastAPI's required
`request` parameters in exception handlers) — all on lines this change does not
touch; the `I001` this change introduced was fixed by hand.

## R. Security invariants

All thirteen re-verified after the change:

| # | Invariant | Status |
|---|---|---|
| 1 | AI advisory-only | Holds — AI package untouched; 44 boundary tests pass |
| 2 | Certificate verification independently trusted | Holds — verification untouched |
| 3 | Unknown signer cannot produce VALID | Holds |
| 4 | Missing evidence cannot produce VALID | Holds |
| 5 | NOT_CHECKED cannot become PASS | Holds |
| 6 | INCONCLUSIVE cannot become PASS | Holds |
| 7 | Operation/target identity externally checked | Holds |
| 8 | Frontend cannot execute destructive operations | Holds |
| 9 | Audit actor identity server-derived | Holds |
| 10 | SafePathValidator authoritative | Holds |
| 11 | Privileged operations behind the service boundary | Holds |
| 12 | **Replay protection effective for the default HTTP service lifetime** | **Now holds** — proven by HTTP test |
| 13 | **Coverage semantics never overstate forensic coverage** | **Now holds** — `PARTIAL` is distinct and reaches assurance |

Invariants 12 and 13 were the two that did not hold before this change.

## S. Known limitations

**Carried forward, unchanged and out of scope:**

- **F-3** — nonce cache is not restart-persistent. Now documented explicitly as
  process/service lifetime only. A captured request stays replayable for the
  remainder of its freshness window after a restart.
- **L-1** — the AI structural AST control is a denylist and would not catch
  `importlib.import_module`. Untouched.
- **F-2** — signer validity window is evaluated against the certificate's own
  `issued_at`. Untouched.
- **F-1** — `SIGNATURE_VALIDITY` may PASS on the certificate's embedded key when
  no trusted key is configured; cannot yield `VALID`. Untouched.

**Introduced by this change, and deliberate:**

- At `DEFAULT_MAX_ENTRIES` the cache refuses new work rather than forgetting a
  live nonce. Reaching it requires roughly 300 sustained requests/second within
  one freshness window — far above this workload — and refusing is the correct
  direction when it happens.
- `PARTIAL` assurance is a new observable outcome. Clients that treated anything
  other than `PASSED`/`FAILED` as an error will see it; the pipeline already
  emitted `PARTIAL` for non-critical residual findings, so the value itself is
  not new to the contract.
- Coverage is measured against *supported* methods. A future build that adds a
  forensic method will move coverage to `PARTIAL` until that method runs — which
  is the intended behaviour, and is why the state exists.
