# Certificate Self-Reference — Analysis and Repair Design

**Status: DOCUMENTED, NOT REPAIRED.** No verifier change is made here; Phase 23
proper will implement the design in the last section.
**Last verified: 2026-09-10, against `api/routes/certificates.py` and `certificate/verification.py`.**

---

## 1. The problem in one sentence

The API verifies a certificate using the public key **stored inside that same
certificate**, so four of the ten verification dimensions ask the certificate to
vouch for itself.

## 2. Where each key comes from today

### The certificate's public key

`CertificateModel.public_key` — a hex column on the `certificates` row, written
at issuance. Because certificate issuance has no caller anywhere in the codebase
(`create_certificate` is never invoked), no row is currently produced by the
product itself.

### The verifier's "independent" key

`api/routes/certificates.py`:

```python
pubkey_bytes = binascii.unhexlify(cert_model.public_key)
res = verify_certificate(cert_dataclass, evidence_pkg, pubkey_bytes)
```

The third argument is named `signer_public_key` and is documented in
`verification.py` as "the independently supplied key". It is read from the row
being verified. There is no independent source.

### The trust anchor

None exists. `verify_certificate`'s `trust_store` parameter is not passed, so it
defaults to `NullTrustStore`, which returns `NOT_CHECKED` for every signer.

## 3. Can a certificate verify itself?

**Yes, cryptographically — and that is exactly the defect.**

Anyone able to write a `certificates` row can:

1. generate an Ed25519 keypair;
2. sign the evidence digest with the private key;
3. store the matching public key in `public_key` on the same row.

`SIGNATURE_VALIDITY` then passes (the signature really does verify under the key
supplied) and `PUBLIC_KEY_CONSISTENCY` passes trivially (the key is compared with
itself). Nothing in the request path distinguishes that forgery from a
certificate signed by the deployment's real identity.

**What stops it becoming a false VALID today:** aggregation is correctly
fail-closed. `SIGNER_TRUST` is `NOT_CHECKED` under `NullTrustStore`, and any
`NOT_CHECKED` forces the overall result to `INCONCLUSIVE`. So the current system
never returns a false `VALID` — it returns `INCONCLUSIVE` for *every* certificate,
including genuine ones. The verifier is honest and inert rather than wrong.

## 4. How signer identity is established

Before this preparation phase: it was not. `get_signer()` called
`Ed25519SignerVerifier.generate()` per process, so "the signer" was a different
identity after every restart and `Certificate.signer_id` had nothing stable
behind it.

After Task 6: `certificate/keys.py` loads a configured identity and derives a
stable `key_id` from the public key (`sha256(public_key)[:16]`). A verifier can
now name the key it expects. The trust decision itself is still not implemented.

## 5. The ten dimensions — independence status

The ten-dimension model is authoritative and is **not** reduced.

| # | Dimension | Independent today? | Why / what it needs |
|---|---|---|---|
| 1 | `STRUCTURE` | Yes | Pure syntax over the certificate. |
| 2 | `VERSION_COMPATIBILITY` | Yes | Compared against a code constant. |
| 3 | `EVIDENCE_AVAILABILITY` | Yes | Presence check. Nothing generates evidence yet. |
| 4 | `EVIDENCE_DIGEST` | Yes | Recomputed via `canonical_hash`. Weakened by null-dropping in `canonicalize()`. |
| 5 | `SIGNATURE_VALIDITY` | **No** | Verified with the certificate's own key. Needs a key resolved from configuration. |
| 6 | `PUBLIC_KEY_CONSISTENCY` | **No** | Compares the embedded key to itself. Needs a TrustStore lookup by `signer_id`/`key_id`. |
| 7 | `SIGNER_TRUST` | **No** | `NullTrustStore` → `NOT_CHECKED`. Needs configured trust anchors. |
| 8 | `EVIDENCE_CHAIN_INTEGRITY` | **No** | Caller-supplied; the Phase 25 ledger does not exist. |
| 9 | `OPERATION_CONSISTENCY` | Partial | Compares `cert.operation_id` to `evidence.operation_id` — both from the same artifact pair. Needs a caller-supplied expectation. |
| 10 | `TARGET_CONSISTENCY` | **No** | Only checks that `target_hash` is 64 hex characters. Syntactic, not consistency. Needs a caller-supplied expectation. |

## 6. How the missing inputs will be supplied

### Verification key and signer trust

From deployment configuration, never from the certificate. The verifier resolves
`cert.signer_id` (and/or the `key_id` from Task 6) against a `TrustStore` built
from configured trust anchors, and verifies the signature with **the key the
TrustStore returned**. The certificate's embedded key then becomes what it should
always have been: a *claim* to be compared against the trusted key, which is
precisely what `PUBLIC_KEY_CONSISTENCY` is for.

The existing `certificate/trust_model.py` already supports this: it has
revocation, validity windows and constant-time comparison, and returns the
four-valued `CheckResult` the aggregator expects. It needs a loader that
populates it from configuration, not a rewrite.

### Expected operation and target identity

From the caller, not from the artifact. A verifier that wants to know "is this
the certificate for operation X over target Y?" must state X and Y; the verifier
then compares the evidence against those expectations. When the caller supplies
no expectation, the honest result is `NOT_CHECKED` — which aggregates to
`INCONCLUSIVE` — not a pass.

### Evidence-chain integrity

Deferred to Phase 25. Until an independent ledger exists, the input remains
explicit and `NOT_CHECKED` is the correct value. An assertion embedded in the
evidence must never be accepted as proof of its own integrity.

## 7. `VerificationContext` — decision (Task 7)

**Decision: ADOPT the concept. Do not copy the code. Implement in Phase 23.**

The abandoned nested tree (`OBLIVION/OBLIVION`) contains one genuinely better
idea than the authoritative implementation:

```python
@dataclass
class VerificationContext:
    trust_store: Optional[TrustStore] = None
    expected_operation_id: Optional[str] = None
    expected_target_identity: Optional[str] = None
    require_signer_trust: bool = True
```

It separates *what the certificate claims* from *what the verifier independently
expects*, which is the precise shape of the fix for dimensions 6, 9 and 10.

### Why the code itself is rejected

Executed against a well-formed certificate, that implementation raises
`TypeError: 'str' object cannot be interpreted as an integer`. It is incoherent
work-in-progress:

| Defect | Detail |
|---|---|
| Crashes on valid input | `_check_structure` calls `cert.timestamp.replace('Z','+00:00')` on a `datetime`. |
| Model mismatch | Its `Certificate` has no `public_key` field, yet three checks dereference it. |
| Wrong TrustStore API | Calls `trust_store.get_signer(...)`; its own `trust.py` defines `get(...)`. |
| Wrong dataclass args | `TrustedSigner(..., name=...)`; the field is `description`. |
| Wrong signer usage | `Ed25519SignerVerifier(public_key_bytes)` then a 2-arg `verify`; `verify` is a static 3-arg method and `__init__` takes a *private* key. |
| No tests | Zero Phase 23 tests, against 15 passing in the authoritative tree. |

### Explicitly rejected, per the brief

- **Its six-dimension aggregation.** `REQUIRED_DIMENSIONS` contains only six
  entries, and the aggregation loop ignores every dimension outside that set. A
  `FAIL` on `PUBLIC_KEY_CONSISTENCY`, `EVIDENCE_CHAIN_INTEGRITY`,
  `OPERATION_CONSISTENCY` or `TARGET_CONSISTENCY` would **not** make a
  certificate `INVALID`. A certificate bound to the wrong target would verify.
  This is a security regression against the authoritative
  `any(result is FAIL) -> INVALID` rule and must not be ported.
- **Chain integrity returning `PASS` when no binding exists** ("chain check not
  applicable") — fail-open where the authoritative code correctly returns
  `NOT_CHECKED`.
- **`verify_certificate_simple()`**, which builds a TrustStore from a
  caller-supplied key and adds it as trusted — reintroducing the very
  self-reference this is meant to remove.
- **Its signing convention** (signature over raw digest bytes). The authoritative
  tree already has two incompatible conventions; a third must not be added.
- **Its `TrustStore`**, which lacks the revocation and validity windows that
  `trust_model.py` already has.

### What to port

| Item | Action |
|---|---|
| `VerificationContext` with expected operation/target | Reimplement cleanly against `CheckResult` and the ten-dimension model |
| Trust-store-backed public-key consistency | Reimplement against `trust_model.TrustStore` |
| `parse_public_key_bytes()` (hex **or** PEM) | Port the function; it is small and correct |
| `TrustedSigner.key_id()` | Superseded by `keys.derive_key_id()` from Task 6 |
| Evidence structural validation | Merge into the existing `STRUCTURE` check |

## 8. Prerequisites before the repair can land

1. Certificate issuance must exist, so there is something real to verify.
2. Evidence generation must exist, so dimensions 3, 4, 9 and 10 have input.
3. The two signing conventions in the authoritative tree must be unified
   (`EvidenceEngine` signs canonical bytes; `verification.py` signs the hex
   digest string).
4. `canonicalize()` must stop dropping `None` values, which currently lets two
   semantically different evidence packages share a digest.

Until those exist, `INCONCLUSIVE` remains the correct and honest verdict for
every certificate this system can produce.
