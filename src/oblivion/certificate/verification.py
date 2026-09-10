"""Independent, fail-closed certificate verification.

The rule this module exists to enforce: **a certificate may not be the sole
source of the facts used to judge it.**

Before Phase 23 the API verified a certificate with the public key stored inside
that certificate and no trust anchor at all, so two dimensions asked the
certificate to vouch for itself. Every input that could make a certificate look
good now comes from somewhere the certificate does not control:

===========================  ==========================================
What is judged               Where the answer comes from
===========================  ==========================================
evidence digest              recomputed from the evidence record
signer trust                 the verifier's configured TrustStore
public-key consistency       the trusted key, not the embedded one
operation identity           an expectation supplied by the caller
target identity              an expectation supplied by the caller
chain integrity              the actual chain of prior records
===========================  ==========================================

When an input is genuinely unavailable the dimension reports ``NOT_CHECKED`` and
the aggregate becomes ``INCONCLUSIVE``. That is the honest answer, and it is
never upgraded to a pass for convenience.
"""

from __future__ import annotations

import binascii
from dataclasses import dataclass, field
from datetime import UTC, datetime

from oblivion.core.evidence.canonicalize import SUPPORTED_CANONICALIZATION_VERSIONS
from oblivion.core.evidence.record import (
    SUPPORTED_EVIDENCE_SCHEMA_VERSIONS,
    ChainStatus,
    EvidenceRecord,
    verify_evidence_chain,
)

from .models import HEX64, SUPPORTED_CERTIFICATE_VERSIONS, Certificate
from .signer import Ed25519SignerVerifier
from .trust_model import NullTrustStore, TrustStore
from .verification_model import (
    VERIFIER_VERSION,
    CertificateVerificationResult,
    CheckResult,
    DimensionResult,
    VerificationDimension,
    VerificationStatus,
)

#: Every dimension is required. There is no subset that can yield VALID - an
#: abandoned implementation aggregated over six and ignored failures in the rest,
#: which let a certificate bound to the wrong target verify.
REQUIRED_DIMENSIONS: frozenset[VerificationDimension] = frozenset(VerificationDimension)


@dataclass(frozen=True)
class VerificationContext:
    """What the *verifier* independently knows.

    Every field is optional because independent knowledge is often genuinely
    unavailable - but an absent field yields ``NOT_CHECKED``, never a pass. The
    verifier never invents an expectation, and never falls back to reading one
    out of the certificate.
    """

    #: Where signer trust comes from. Defaults to "nothing is configured".
    trust_store: TrustStore = field(default_factory=NullTrustStore)
    #: The evidence the certificate refers to, loaded independently.
    evidence: EvidenceRecord | None = None
    #: Prior records, oldest first, for chain verification.
    evidence_chain: tuple[EvidenceRecord, ...] | None = None
    #: Which operation the caller believes this certificate is about.
    expected_operation_id: str | None = None
    #: Which target the caller believes this certificate is about.
    expected_target_identity: str | None = None


def _structure(cert: Certificate) -> DimensionResult:
    problems: list[str] = []
    if not cert.certificate_id:
        problems.append("certificate_id is empty")
    if not cert.operation_id:
        problems.append("operation_id is empty")
    if not cert.evidence_id:
        problems.append("evidence_id is empty")
    if not cert.target_identity:
        problems.append("target_identity is empty")
    if not cert.signer_id:
        problems.append("signer_id is empty")
    if not HEX64.match(cert.evidence_digest or ""):
        problems.append("evidence_digest is not 64 lowercase hex characters")
    if not isinstance(cert.issued_at, datetime):
        problems.append("issued_at is not a datetime")

    try:
        if len(binascii.unhexlify(cert.public_key or "")) != 32:
            problems.append("public_key is not a 32-byte Ed25519 key")
    except (binascii.Error, ValueError):
        problems.append("public_key is not valid hex")

    try:
        if len(binascii.unhexlify(cert.signature or "")) != 64:
            problems.append("signature is not 64 bytes")
    except (binascii.Error, ValueError):
        problems.append("signature is not valid hex")

    if problems:
        return DimensionResult(
            VerificationDimension.STRUCTURE, CheckResult.FAIL, "; ".join(problems)
        )
    return DimensionResult(
        VerificationDimension.STRUCTURE,
        CheckResult.PASS,
        "All required certificate fields are present and well-formed.",
    )


def _version_compatibility(cert: Certificate) -> DimensionResult:
    unsupported: list[str] = []
    if cert.version not in SUPPORTED_CERTIFICATE_VERSIONS:
        unsupported.append(f"certificate version {cert.version!r}")
    if cert.canonicalization_version not in SUPPORTED_CANONICALIZATION_VERSIONS:
        unsupported.append(f"canonicalization {cert.canonicalization_version!r}")
    if cert.evidence_schema_version not in SUPPORTED_EVIDENCE_SCHEMA_VERSIONS:
        unsupported.append(f"evidence schema {cert.evidence_schema_version!r}")

    if unsupported:
        # Inconclusive rather than invalid: an unreadable certificate has not
        # been shown to be forged, only to be beyond this verifier.
        return DimensionResult(
            VerificationDimension.VERSION_COMPATIBILITY,
            CheckResult.INCONCLUSIVE,
            (
                f"This verifier cannot interpret {', '.join(unsupported)}, so the "
                "certificate cannot be evaluated."
            ),
        )
    return DimensionResult(
        VerificationDimension.VERSION_COMPATIBILITY,
        CheckResult.PASS,
        f"Certificate {cert.version}, {cert.canonicalization_version}, "
        f"{cert.evidence_schema_version} are all supported.",
    )


def _evidence_availability(
    cert: Certificate, evidence: EvidenceRecord | None
) -> DimensionResult:
    if evidence is None:
        return DimensionResult(
            VerificationDimension.EVIDENCE_AVAILABILITY,
            CheckResult.NOT_CHECKED,
            (
                f"Evidence {cert.evidence_id} was not supplied to the verifier, so "
                "nothing the certificate claims about it could be checked."
            ),
            cert.evidence_id,
        )
    if evidence.evidence_id != cert.evidence_id:
        return DimensionResult(
            VerificationDimension.EVIDENCE_AVAILABILITY,
            CheckResult.FAIL,
            (
                f"Supplied evidence is {evidence.evidence_id}, but the certificate "
                f"refers to {cert.evidence_id}."
            ),
            evidence.evidence_id,
        )
    return DimensionResult(
        VerificationDimension.EVIDENCE_AVAILABILITY,
        CheckResult.PASS,
        "The referenced evidence record was supplied.",
        evidence.evidence_id,
    )


def _evidence_digest(
    cert: Certificate, evidence: EvidenceRecord | None
) -> DimensionResult:
    if evidence is None:
        return DimensionResult(
            VerificationDimension.EVIDENCE_DIGEST,
            CheckResult.NOT_CHECKED,
            "Without the evidence record its digest cannot be recomputed.",
        )
    try:
        actual = evidence.digest()
    except Exception as exc:  # canonicalization refused the content
        return DimensionResult(
            VerificationDimension.EVIDENCE_DIGEST,
            CheckResult.INCONCLUSIVE,
            f"The evidence could not be canonicalized ({type(exc).__name__}).",
        )
    if actual != cert.evidence_digest:
        return DimensionResult(
            VerificationDimension.EVIDENCE_DIGEST,
            CheckResult.FAIL,
            (
                "The evidence does not hash to the digest recorded in the "
                "certificate; it was modified after issuance."
            ),
            evidence.evidence_id,
        )
    return DimensionResult(
        VerificationDimension.EVIDENCE_DIGEST,
        CheckResult.PASS,
        "Recomputed evidence digest matches the certificate.",
        evidence.evidence_id,
    )


def _signature_validity(cert: Certificate, trusted_key: bytes | None) -> DimensionResult:
    """Purely mathematical: does the signature verify under some key?

    Prefers the independently trusted key. Falls back to the embedded key so the
    arithmetic can still be reported - but that fallback proves nothing about
    *who* signed, which is why SIGNER_TRUST is a separate dimension and why the
    detail says which key was used.
    """
    if trusted_key is not None:
        key = trusted_key
        provenance = "the trusted key from the verifier's TrustStore"
    else:
        try:
            key = binascii.unhexlify(cert.public_key or "")
        except (binascii.Error, ValueError):
            return DimensionResult(
                VerificationDimension.SIGNATURE_VALIDITY,
                CheckResult.FAIL,
                "The certificate's public key is not decodable.",
            )
        provenance = (
            "the key embedded in the certificate (no trusted key was available, "
            "so this establishes arithmetic only, not authorship)"
        )

    try:
        signature = binascii.unhexlify(cert.signature or "")
        payload = cert.signing_bytes()
    except (binascii.Error, ValueError, TypeError) as exc:
        return DimensionResult(
            VerificationDimension.SIGNATURE_VALIDITY,
            CheckResult.FAIL,
            f"The signature or payload could not be prepared ({type(exc).__name__}).",
        )

    if Ed25519SignerVerifier.verify(key, payload, signature):
        return DimensionResult(
            VerificationDimension.SIGNATURE_VALIDITY,
            CheckResult.PASS,
            f"Ed25519 signature verifies over the canonical payload using {provenance}.",
        )
    return DimensionResult(
        VerificationDimension.SIGNATURE_VALIDITY,
        CheckResult.FAIL,
        f"Ed25519 signature does not verify using {provenance}.",
    )


def _public_key_consistency(
    cert: Certificate, trusted_key: bytes | None
) -> DimensionResult:
    if trusted_key is None:
        return DimensionResult(
            VerificationDimension.PUBLIC_KEY_CONSISTENCY,
            CheckResult.NOT_CHECKED,
            (
                f"No trusted key is configured for signer {cert.signer_id!r}, so the "
                "embedded key cannot be compared with anything independent. "
                "Comparing it with itself would prove nothing."
            ),
        )
    try:
        embedded = binascii.unhexlify(cert.public_key or "")
    except (binascii.Error, ValueError):
        return DimensionResult(
            VerificationDimension.PUBLIC_KEY_CONSISTENCY,
            CheckResult.FAIL,
            "The certificate's public key is not decodable.",
        )
    if embedded == trusted_key:
        return DimensionResult(
            VerificationDimension.PUBLIC_KEY_CONSISTENCY,
            CheckResult.PASS,
            "The embedded public key matches the key the TrustStore holds for this signer.",
        )
    return DimensionResult(
        VerificationDimension.PUBLIC_KEY_CONSISTENCY,
        CheckResult.FAIL,
        (
            "The embedded public key differs from the key the TrustStore holds "
            f"for signer {cert.signer_id!r}."
        ),
    )


def _signer_trust(cert: Certificate, context: VerificationContext) -> DimensionResult:
    try:
        embedded = binascii.unhexlify(cert.public_key or "")
    except (binascii.Error, ValueError):
        embedded = b""

    try:
        verdict = context.trust_store.is_trusted(cert.signer_id, embedded, cert.issued_at)
    except Exception as exc:
        return DimensionResult(
            VerificationDimension.SIGNER_TRUST,
            CheckResult.INCONCLUSIVE,
            f"The TrustStore could not be consulted ({type(exc).__name__}).",
        )

    details = {
        CheckResult.PASS: f"Signer {cert.signer_id!r} is trusted by this verifier.",
        CheckResult.FAIL: (
            f"Signer {cert.signer_id!r} is untrusted, revoked, outside its validity "
            "window, or presented a key that does not match the trusted one."
        ),
        CheckResult.NOT_CHECKED: (
            f"No configured trust anchor covers signer {cert.signer_id!r}. A valid "
            "signature does not make its own key trusted."
        ),
        CheckResult.INCONCLUSIVE: (
            f"Trust in signer {cert.signer_id!r} could not be determined."
        ),
    }
    return DimensionResult(VerificationDimension.SIGNER_TRUST, verdict, details[verdict])


def _chain_integrity(context: VerificationContext) -> DimensionResult:
    chain = context.evidence_chain
    if not chain:
        return DimensionResult(
            VerificationDimension.EVIDENCE_CHAIN_INTEGRITY,
            CheckResult.NOT_CHECKED,
            (
                "No evidence chain was supplied. A correct digest on the current "
                "record establishes that record's integrity and nothing about the "
                "history preceding it."
            ),
        )
    verification = verify_evidence_chain(list(chain))
    if verification.status is ChainStatus.INTACT:
        return DimensionResult(
            VerificationDimension.EVIDENCE_CHAIN_INTEGRITY,
            CheckResult.PASS,
            verification.reason,
        )
    if verification.status is ChainStatus.BROKEN:
        return DimensionResult(
            VerificationDimension.EVIDENCE_CHAIN_INTEGRITY,
            CheckResult.FAIL,
            verification.reason,
            verification.first_invalid_evidence_id,
        )
    return DimensionResult(
        VerificationDimension.EVIDENCE_CHAIN_INTEGRITY,
        CheckResult.NOT_CHECKED,
        verification.reason,
        verification.first_invalid_evidence_id,
    )


def _operation_consistency(
    cert: Certificate, context: VerificationContext
) -> DimensionResult:
    expected = context.expected_operation_id
    if expected is None:
        return DimensionResult(
            VerificationDimension.OPERATION_CONSISTENCY,
            CheckResult.NOT_CHECKED,
            (
                "The caller supplied no expected operation identity. Comparing the "
                "certificate's operation_id with itself would establish nothing."
            ),
        )
    if cert.operation_id != expected:
        return DimensionResult(
            VerificationDimension.OPERATION_CONSISTENCY,
            CheckResult.FAIL,
            (
                f"The certificate is for operation {cert.operation_id!r}, but "
                f"{expected!r} was expected."
            ),
        )
    evidence = context.evidence
    if evidence is not None and evidence.operation_id != expected:
        return DimensionResult(
            VerificationDimension.OPERATION_CONSISTENCY,
            CheckResult.FAIL,
            (
                f"The evidence is for operation {evidence.operation_id!r}, but "
                f"{expected!r} was expected."
            ),
            evidence.evidence_id,
        )
    return DimensionResult(
        VerificationDimension.OPERATION_CONSISTENCY,
        CheckResult.PASS,
        f"Certificate and evidence both match the expected operation {expected!r}.",
    )


def _target_consistency(
    cert: Certificate, context: VerificationContext
) -> DimensionResult:
    expected = context.expected_target_identity
    if expected is None:
        return DimensionResult(
            VerificationDimension.TARGET_CONSISTENCY,
            CheckResult.NOT_CHECKED,
            (
                "The caller supplied no expected target identity. Checking that the "
                "certificate agrees with itself would establish nothing."
            ),
        )
    if cert.target_identity != expected:
        return DimensionResult(
            VerificationDimension.TARGET_CONSISTENCY,
            CheckResult.FAIL,
            (
                f"The certificate is for target {cert.target_identity!r}, but "
                f"{expected!r} was expected."
            ),
        )
    evidence = context.evidence
    if evidence is not None and evidence.target.identity != expected:
        return DimensionResult(
            VerificationDimension.TARGET_CONSISTENCY,
            CheckResult.FAIL,
            (
                f"The evidence is for target {evidence.target.identity!r}, but "
                f"{expected!r} was expected."
            ),
            evidence.evidence_id,
        )
    return DimensionResult(
        VerificationDimension.TARGET_CONSISTENCY,
        CheckResult.PASS,
        f"Certificate and evidence both match the expected target {expected!r}.",
    )


def _aggregate(dimensions: tuple[DimensionResult, ...]) -> str:
    """Deterministic and order-independent.

    Works on the set of outcomes for the required dimensions, so reordering the
    checks cannot change the verdict, and a dimension that was never produced is
    caught rather than skipped.
    """
    produced = {d.dimension for d in dimensions}
    if REQUIRED_DIMENSIONS - produced:
        # A required dimension that was never evaluated cannot be ignored.
        return VerificationStatus.INCONCLUSIVE.value

    outcomes = {d.result for d in dimensions if d.dimension in REQUIRED_DIMENSIONS}
    if CheckResult.FAIL in outcomes:
        return VerificationStatus.INVALID.value
    if CheckResult.INCONCLUSIVE in outcomes:
        return VerificationStatus.INCONCLUSIVE.value
    if CheckResult.NOT_CHECKED in outcomes:
        return VerificationStatus.INCONCLUSIVE.value
    return VerificationStatus.VALID.value


def verify_certificate(
    cert: Certificate, context: VerificationContext | None = None
) -> CertificateVerificationResult:
    """Verify a certificate against independently supplied facts.

    Passing no context means the verifier knows nothing independently, which
    yields ``INCONCLUSIVE`` - not ``VALID``.
    """
    ctx = context if context is not None else VerificationContext()

    trusted = ctx.trust_store.lookup(cert.signer_id)
    trusted_key = trusted.public_key_bytes if trusted is not None else None

    dimensions: tuple[DimensionResult, ...] = (
        _structure(cert),
        _version_compatibility(cert),
        _evidence_availability(cert, ctx.evidence),
        _evidence_digest(cert, ctx.evidence),
        _signature_validity(cert, trusted_key),
        _public_key_consistency(cert, trusted_key),
        _signer_trust(cert, ctx),
        _chain_integrity(ctx),
        _operation_consistency(cert, ctx),
        _target_consistency(cert, ctx),
    )

    cannot_prove = tuple(
        f"{d.dimension.value}: {d.detail}"
        for d in dimensions
        if d.result in (CheckResult.NOT_CHECKED, CheckResult.INCONCLUSIVE)
    )

    def _view(dimension: VerificationDimension) -> bool | None:
        for item in dimensions:
            if item.dimension is dimension:
                if item.result is CheckResult.PASS:
                    return True
                if item.result is CheckResult.FAIL:
                    return False
                return None
        return None

    return CertificateVerificationResult(
        certificate_id=cert.certificate_id,
        overall_status=_aggregate(dimensions),
        dimensions=dimensions,
        cannot_prove=cannot_prove,
        certificate_version=cert.version,
        verifier_version=VERIFIER_VERSION,
        verified_at=datetime.now(UTC),
        signature_valid=_view(VerificationDimension.SIGNATURE_VALIDITY),
        evidence_integrity=_view(VerificationDimension.EVIDENCE_DIGEST),
        signer_trusted=_view(VerificationDimension.SIGNER_TRUST),
    )


__all__ = [
    "REQUIRED_DIMENSIONS",
    "VerificationContext",
    "verify_certificate",
]
