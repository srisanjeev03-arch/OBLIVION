# PHASE 23 — FINAL RECONCILIATION REPORT

## A. Exact HEAD

**`8744305`** — `test(phase23): reconcile stale pre-auth test contracts and close coverage gaps`

Lineage: `1358218` (pre-Phase-23) → `e4b5a37` (Phase 23) → **`8744305`** (this reconciliation).

`e4b5a37` is **not** the final validated commit: seven failures were reconciled and
two coverage gaps closed, so a commit was required.

This report is itself committed on top as a **documentation-only** commit so it
survives the worktree. That commit changes no code, no test and no configuration:
the validated tree — the one all the measurements below were taken against, and the
one being merge-gated — is **`8744305`**.

## B. Branch

`pre-phase23-repair`, in the linked worktree
`H:\final integration\OBLIVION\.claude\worktrees\pre-phase23-repair`.
**Not merged.** No remote configured. Working tree clean except untracked `test_file.txt`.

## C. Files Changed

`e4b5a37` vs `1358218`: 28 files, +3481 / −966.
`8744305` adds test-only changes to seven suites: `test_api_analyze.py`,
`test_auth_rbac.py`, `test_api_full.py`, `test_erasure.py`,
`test_recovery_engine.py`, `test_certificate_phase23.py`,
`test_certificate_api_phase23.py`. **No production source changed in the
reconciliation commit.**

### Environment checks

| Check | Result |
|---|---|
| `H:\OBLIVION` history modified | **No** — HEAD still `b91cc45`, no commits added, no history rewritten |
| `H:\OBLIVION` working tree | **Not clean, and not by this session** — see note below |
| Test fixtures referencing the twin | **None** |
| Private keys / secrets committed | **None** — all test key material generated at runtime |
| Credentials in tracked files | **None** |
| Destructive tests on real user data | **No** — scratch is `<repo>/.pytest-scratch`, per-test temp dir, containment enforced by `SafePathValidator` |

**Note on the twin's working tree.** `H:\OBLIVION` carries four uncommitted
modifications (`frontend/src/app/router.tsx`,
`frontend/src/components/auth/RouteGuards.tsx`,
`frontend/src/features/certificates/pages/Certificates.tsx`,
`.claude/settings.json`) plus an untracked `.claude/settings.json.bak-20260910`.
**None originate from this session**, established by measurement rather than
assertion:

1. The Phase 23 diff (`1358218..8744305 -- frontend/`) is **empty** — no phase of
   this work touched a single frontend file, and the frontend is BoltAI-owned
   per `CLAUDE.md`.
2. All three frontend files are **byte-identical between `H:\OBLIVION` and
   `H:\final integration\OBLIVION`**, so the edits exist equally in both copies
   and were not introduced into one of them here.
3. Their mtimes (01:07–01:08) precede this branch's first commit (10:33) by
   roughly nine and a half hours.

Point 2 also explains why the earlier A↔B reconciliation reported the two
checkouts as identical apart from `.claude/settings.json` and `test_file.txt`:
these frontend changes are present in *both*, so a comparison between them
cannot surface them. That finding was correct; it simply was not a statement
about either tree being clean.

The uncommitted frontend work is pre-existing and outside Phase 23's scope. It
is reported here rather than acted on, since this task forbids modifying the
frontend or the twin.

## D. Tests Before Reconciliation

262 passed · **7 failed** · 1 skipped · mypy clean (88 files) · contract OK (17 paths)
ruff: 192 (`src`), 56 (`tests`)

## E. Tests After Reconciliation

**286 passed · 0 failed · 1 skipped · 1 xfailed**
mypy clean (88 files) · contract OK (17 paths) · ruff 192 / 56 (unchanged)

- The **skip** is `test_erasure.py:100 "Symlink creation not supported"` —
  environmental (unprivileged Windows cannot create symlinks), unrelated to
  certificate or evidence security.
- The **xfail** is a documented product defect, `strict=True` so it fails loudly
  if it ever starts passing. Not skipped, not hidden.

## F. Classification of All Seven Failures

| Test | File | Failure | Root cause | Class | Security impact | Action taken |
|---|---|---|---|---|---|---|
| `test_analyze_valid_file` | `test_api_analyze.py` | `401 not in (200,400,422,501)` | Builds a bare `TestClient(app)` with **no credential**; written before authentication was enforced | **STALE TEST** | **Positive** — the 401 *is* auth working; an anonymous caller must not enumerate the filesystem | Asserts 401; authenticated variant added |
| `test_analyze_target_outside_allowed_root` | `test_api_analyze.py` | `401 not in (400,422)` | Same, unauthenticated | **STALE TEST** | **Positive** — auth is checked before path policy, so anonymous callers cannot probe path existence | Asserts 401; authenticated variant added |
| `test_operation_approve_sod_violation_returns_403` | `test_auth_rbac.py` | `401 == 403` | Uses the file-local unauthenticated `auth_client`, and passes `?approver_id=inv_user_1` — the **client-supplied actor** contract deliberately removed | **STALE TEST** | **Strongly positive** — it asserted a contract where the caller names its own approver | Split in two: spoofed parameter is ignored; requester cannot approve own operation via server-derived identity |
| `test_selective_permanent_operation_lifecycle` | `test_api_full.py` | `1 >= 3` | Never calls approve or execute; asserts the **pre-approval-gate** flow where creation also ran the operation | **STALE TEST** | **Positive** — one event proves creation performs no destructive work | Asserts exactly 1 `OPERATION_REQUESTED` event, `PENDING_APPROVAL`, and target still present |
| `test_unauthorized_restore_blocked` | `test_api_full.py` | `500 == 200` | `OBLIVION_VAULT_KEY` unset → `get_vault_key` fails closed with `VAULT_KEY_UNAVAILABLE`. Despite its name the test never tested unauthorized restore | **ENVIRONMENT** | **Positive** — fail-closed working correctly | Renamed; now asserts the 500 fail-closed *and* the configured-key path with a test-only key |
| `test_nonexistent_target` | `test_erasure.py` | `0 > 0` on `failed` | Engine refuses at validation (identity cannot be established) and records **`blocked`**; the test expects `failed`, the contract of an older engine that attempted and caught `ValueError` | **STALE TEST** | **Positive** — refusing earlier is safer; the operation is still refused | Asserts `blocked` non-empty and `successful` empty; **no erasure semantics changed** |
| `test_recovery_engine_execution_success` | `test_recovery_engine.py` | `0 == 1` | **Two real defects**: invalid `READY → COMPLETED` transition, and export of literal `b"recovered-data-placeholder"` failing destination validation | **PRODUCT BUG** | Real, but confined to `ForensicRecoveryEngine`, which has **no caller** and is unwired | `xfail(strict=True)` with the full reason. A real fix means implementing forensic recovery = **Phase 25**, explicitly out of scope |

**Zero unexplained failures remain.**

## G. Explanation of the Six Deleted Tests

All six exercised `verify_certificate(cert, evidence, signer_public_key)` — the
signature in which the **caller supplies the verification key**, and which the
API populated from the certificate's own row. That is the self-verification flaw
Phase 23 exists to close, so the API was removed rather than preserved.
**No obsolete API was restored to make an old test pass.**

| Deleted file | Why it existed | Coverage now |
|---|---|---|
| `test_phase23_certificate_verification.py` (8 tests) | Phase 23 v1 verifier | All 8 mapped: ten-dimensions → `test_all_ten_dimensions_are_reported`; signature-without-trust → `test_unknown_signer_is_not_trusted_despite_a_valid_signature`; valid-requires-independent-proof → `test_complete_independent_context_yields_valid`; missing-evidence → `test_missing_evidence_is_not_checked_and_never_valid`; embedded-key → `test_embedded_key_cannot_establish_trust`; self-asserted chain → `test_valid_digest_does_not_imply_chain_integrity`; expired/revoked → `test_revoked_signer_fails` + `test_signer_outside_validity_window_fails`; **single-canonicalizer → newly added `test_compatibility_shim_is_the_same_canonicalizer`** |
| `test_certificate_verification_dimensions.py` (6) | Dimension matrix for the old signature | valid → `test_complete_independent_context_yields_valid`; missing evidence → `test_missing_evidence_is_not_checked_and_never_valid`; digest mismatch → `test_modified_evidence_fails_the_digest_dimension`; invalid signature → 14-way `test_altering_any_signed_field_breaks_the_signature`; unsupported version → `test_unsupported_version_is_inconclusive_not_valid` |
| `test_certificate_verification_security.py` (6) | Already **fully skipped** as superseded before Phase 23 | other-key → `test_known_signer_presenting_a_different_key_fails`; tampered evidence → `test_modified_evidence_fails_the_digest_dimension`; **malformed signature / empty key → newly added `test_malformed_crypto_material_never_crashes_and_never_passes` (6 variants)**; unsupported version → covered |
| `test_phase23_certificate_api.py` (1) | Old API response shape | `test_independent_context_yields_valid` + `test_without_expectations_the_result_is_inconclusive` |
| `test_certificate_verification.py` | Already **fully skipped** as superseded | Superseded twice over |
| `test_verification.py` | Already **fully skipped** as superseded | Superseded twice over |

**Two genuine gaps were found and closed** (the single-canonicalizer pin and the
malformed-crypto-material robustness cases). Everything else was already covered.
Net security coverage is higher than before deletion.

## H. Ten Verification Dimensions

For each: what it trusts, and what happens when the input is absent.

| # | Dimension | Trusts | Certificate controls | Caller controls | TrustStore controls | Input absent → |
|---|---|---|---|---|---|---|
| 1 | STRUCTURE | nothing external | all fields | — | — | n/a (always evaluable) |
| 2 | VERSION_COMPATIBILITY | code constants | its declared versions | — | — | unsupported → `INCONCLUSIVE` |
| 3 | EVIDENCE_AVAILABILITY | server-loaded evidence | the `evidence_id` it claims | — | — | `NOT_CHECKED` |
| 4 | EVIDENCE_DIGEST | **recomputed** from evidence | the digest it claims | — | — | `NOT_CHECKED` |
| 5 | SIGNATURE_VALIDITY | trusted key when available | signature + embedded key | — | supplies the preferred key | falls back to embedded key, and the detail says it establishes *arithmetic only, not authorship* |
| 6 | PUBLIC_KEY_CONSISTENCY | **TrustStore key** | its embedded key (a claim) | — | the authoritative key | `NOT_CHECKED` — never self-compared |
| 7 | SIGNER_TRUST | **TrustStore only** | its `signer_id` (a claim) | — | the verdict | `NOT_CHECKED` |
| 8 | EVIDENCE_CHAIN_INTEGRITY | actual prior records | nothing | — | — | `NOT_CHECKED` |
| 9 | OPERATION_CONSISTENCY | **caller's expectation** | its `operation_id` | the expectation | — | `NOT_CHECKED` |
| 10 | TARGET_CONSISTENCY | **caller's expectation** | its `target_identity` | the expectation | — | `NOT_CHECKED` |

**No certificate-controlled field serves as its own trust anchor.** Dimensions
6, 7, 9 and 10 are the ones that could be self-satisfied, and each takes its
answer from the TrustStore or the caller.

### Aggregation rule (verified against the implementation)

Outcomes are collected into a **set**, so the verdict is order-independent:

- any required `FAIL` → **INVALID**
- otherwise any required `INCONCLUSIVE` → **INCONCLUSIVE**
- otherwise any required `NOT_CHECKED` → **INCONCLUSIVE**
- a required dimension entirely missing → **INCONCLUSIVE**
- only all ten `PASS` → **VALID**

Each of the nine mandated negative cases was executed and none produced `VALID`:
`NOT_CHECKED`→PASS, `UNAVAILABLE` evidence→positive observation, missing
evidence, unknown signer, wrong expected operation ID, wrong expected target
identity, tampered evidence, invalid signature, corrupted chain.

## I. Certificate Trust Model — **VERIFIED**

- The embedded public key is a **claim**, compared against the TrustStore's key,
  never against itself.
- A valid signature by an unknown signer yields `SIGNER_TRUST = NOT_CHECKED` →
  overall `INCONCLUSIVE`, never `VALID`.
- A known signer presenting a different key → `FAIL` on both dimensions 6 and 7.
- Trust-store lookup returning nothing → `NOT_CHECKED`, never `PASS`.
- **No hardcoded trust anchor exists**; searched and confirmed. Unconfigured
  deployments get `NullTrustStore`; malformed configuration fails closed with
  `TRUST_STORE_INVALID`.
- Signing keys are **loaded, never generated at runtime**.
  `Ed25519SignerVerifier.generate()` still exists as a classmethod but has **no
  production caller** (residual observation, §Q).

## J. Evidence Model — **VERIFIED**

`ObservationState` = `OBSERVED | INFERRED | NOT_CHECKED | UNAVAILABLE`.
`NOT_CHECKED` and `UNAVAILABLE` **cannot carry a value** — enforced in
`__post_init__`, not merely documented. Requesting an unrecorded observation
returns `NOT_CHECKED`, never `None`-as-absence.

The three cases stay distinguishable:

| Situation | Representation |
|---|---|
| Scan ran, found nothing | `OBSERVED` with an empty findings value |
| Scan never happened | `NOT_CHECKED` |
| Scan failed / impossible here | `UNAVAILABLE` with a reason |

**`EvidenceCoverage` (pre-Phase-23) re-audited:** every field defaults to
`NOT_PERFORMED`, so a caller supplying nothing has proved nothing;
`DefaultAssuranceRule` returns `INCONCLUSIVE/LOW` on empty input, and
`PASSED` requires every required analysis to have actually run. Verified still
holding — 15 assurance tests pass. Phase 23 did not weaken it.

## K. Canonicalization Model — **VERIFIED**

**Exactly one implementation**: `core/evidence/canonicalize.py`, versioned
`OBLIVION-CANON-1` and recorded in every signed artifact.
`canonical.py` is a pure re-export, now **pinned by a test** asserting the
function objects are identical. (`core/safety/paths.py` has an unrelated *path*
canonicalizer — different concern, pre-existing.)

| Property | Status |
|---|---|
| Nulls preserved | **Yes** — dropping them made two documents share a digest |
| Ordering deterministic | Yes, keys sorted |
| Unicode ordering | **UTF-16 code unit** (RFC 8785), not code point — pinned by test |
| Number serialization | Integers exact; floats shortest round-trip; NaN/Inf rejected |
| Datetime serialization | ISO-8601, deterministic |
| Round-trip stability | Verified — reloaded evidence hashes identically |
| Competing implementation | **None** |

**Stated deviation:** not every ES6 exponent edge case is reproduced. The format
is versioned so a strict-JCS codec can arrive as `OBLIVION-CANON-2` without
invalidating anything already signed.

## L. Persistence Result — **VERIFIED**

Full chain exercised through real code:
generate → canonicalize → hash → issue → persist → reload → verify.

New `test_reloaded_certificate_is_byte_identical_to_the_issued_one` asserts
stable `certificate_id`, `operation_id`, `target_identity`, `evidence_digest`,
`signer_id`, `key_id`; that reloaded evidence still hashes to the recorded
digest; that `issued_at` retains its timezone; and that the signature still
verifies over the reloaded canonical payload.

**Timezone handling** was a real bug found during Phase 23: SQLite does not
retain the offset even for `DateTime(timezone=True)`, so `issued_at` reloaded
naive, changed `isoformat()`, and broke the certificate's own signature — a
storage artifact indistinguishable from tampering. Normalised to UTC on load.

## M. TrustStore Result — **VERIFIED**

Trusted / unknown / explicitly-denied / revoked / outside-validity-window /
wrong-key are all distinct and tested. Unknown ≠ untrusted: unknown is
`NOT_CHECKED`, denial is `FAIL`. No dev-vs-production divergence: the same
`load_trust_store_from_env` runs everywhere, and the only difference is what an
operator configures.

## N. Operation / Target Context Result — **VERIFIED**

`VerificationContext` carries `expected_operation_id` and
`expected_target_identity`. Certificate operation A + expected B → **FAIL** →
`INVALID`. Certificate target A + expected B → **FAIL** → `INVALID`. Expectation
absent → `NOT_CHECKED` → `INCONCLUSIVE`. The certificate cannot supply the
expectation it is judged against; the `NOT_CHECKED` detail text says so.

## O. API Authorization Result — **VERIFIED**

| Requirement | Result |
|---|---|
| Authentication required | Yes — anonymous → **401** |
| Authorization server-side | Yes — `require_permission("evidence.verify")`; VIEWER → **403**, AUDITOR → 200 |
| Actor identity from session | Yes — no request field carries actor identity anywhere in `api/` |
| Frontend role gating trusted | **No** — enforced server-side only |
| Malformed / unknown IDs | Safe **404**, no stack trace |
| Client can force a verdict | **No** — request model is `extra="forbid"`; seven injection attempts (`overall_status`, `signer_trusted`, `evidence_integrity`, `signature_valid`, `verification_result`, `trust_store`, `actor_id`) all **422** |
| Missing evidence → VALID | **Impossible** — `NOT_CHECKED` → `INCONCLUSIVE` |
| Private key returned | **Never** — `private_key` appears nowhere in `api/` or `persistence/` |

## P. Known Limitations

| # | Limitation | Status |
|---|---|---|
| 1 | Signing key in env var / on disk; no secret-management platform | **KNOWN LIMITATION**, documented |
| 2 | `OBLIVION-CANON-1` is JCS-aligned, not full RFC 8785 numbers | **KNOWN LIMITATION**, versioned |
| 3 | Legacy `1.0.0` certificates → `INCONCLUSIVE` (unsupported version) | **KNOWN LIMITATION** — never verifiable anyway (ephemeral keys) |
| 4 | Certificate issuance has no HTTP route | **DEFERRED** to Phase 25, deliberately |
| 5 | `EvidencePackage` / `hash_integrity` remain for legacy `/api/evidence/verify` | **PARTIAL** — untouched, not extended |
| 6 | `ForensicRecoveryEngine` defects | **PRODUCT BUG**, xfail(strict), Phase 25 |
| 7 | `COMPLETE_ERASURE` performs no sanitization | **STUB**, unchanged, documented |
| 8 | Assurance engine still unwired | **DEFERRED** to Phase 25 |
| 9 | ruff not at zero (192 `src`, 56 `tests`) | **KNOWN** — pre-existing style debt outside Phase 23 files |

## Q. Security Findings

**No security regression was found.** Targeted searches returned clean:

| Search | Result |
|---|---|
| Hardcoded keys / embedded trusted public keys | **None** |
| Per-process signing key generation in production | **None** — loaded only; `generate_private_key_hex()` is an operator helper with no runtime caller |
| Fallback signing secrets | **None** |
| Plaintext credentials in tracked files | **None** |
| Verifier accepting a caller-supplied trust key | **None** — removed with the old signature |
| Certificate-controlled trust decisions | **None** |
| `signature_valid` used as overall validity | **No** — reported only; aggregation is independent |
| `NOT_CHECKED` / `INCONCLUSIVE` → `PASS` conversion | **None** |
| Missing evidence → `PASS` | **None** |
| Broad `except` around verification | **4 sites**, all degrade to `INCONCLUSIVE` or `NOT_CHECKED`; none can produce `PASS` |
| Test-only auth bypass leaking into production | **None** |
| Frontend-controlled actor identity | **None** |
| Insecure path operations added by Phase 23 | **None** — Phase 23 touches no filesystem code |

### §13 — Audit / evidence boundary, stated honestly

`EVIDENCE_CHAIN_INTEGRITY` is **implemented only for evidence-record chains**:
digest correctness, predecessor naming, and predecessor-digest matching over a
supplied sequence. It does **not** provide an append-only ledger, so it cannot
detect wholesale reconstruction of the history — that requires the later
audit-log phase.

Accordingly the dimension reports `NOT_CHECKED` whenever no chain is supplied,
and **no fake audit records were created to make it pass**. A lone record that
references a missing predecessor is `UNVERIFIABLE`, not `INTACT`. The dimension
is reported as implemented for what it actually checks and no more.

### Residual observations (not regressions)

1. `Ed25519SignerVerifier.generate()` remains defined with no production caller —
   dead but harmless. Left alone under the no-unrelated-refactoring rule.
2. `test_file.txt` remains untracked, produced by `test_crypto.py` writing to CWD.
   Pre-existing hygiene defect, not committed.

## R. Merge Recommendation

**READY_TO_MERGE**

All seven failures are resolved or explicitly classified with a documented
reason; the branch contains zero unexplained failures. Coverage lost with the six
deleted suites has been mapped test-by-test and the two genuine gaps closed. No
security regression was found, and the self-verification flaw the phase targeted
is demonstrably closed through real code paths.

The single skip is environmental and unrelated to certificate or evidence
security. The single xfail is a pre-existing, out-of-scope product defect in an
unwired engine, marked strict so it cannot be silently fixed or silently rot.

---

```
HEAD:            8744305 (on pre-phase23-repair; e4b5a37 superseded)
TESTS:           286 passed, 0 failed, 1 skipped (env: symlink), 1 xfailed (documented)
MYPY:            clean - 88 source files
CONTRACT:        OK - docs/OPENAPI.yaml matches the application, 17 paths
SECURITY:        No regression found; 13 targeted searches clean
MERGE STATUS:    READY_TO_MERGE  (not merged by me)
PHASE 24 STATUS: NOT STARTED
```
