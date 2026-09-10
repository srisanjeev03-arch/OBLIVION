"""Result types for multi-dimensional certificate verification.

Ten dimensions, four states, and an aggregate. The shape is the point: a single
boolean cannot say "the signature is mathematically fine but nobody trusts the
signer", and that distinction is the whole reason this module exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

#: Identifies the verifier implementation that produced a result. Recorded so a
#: stored result can be traced to the logic that produced it.
VERIFIER_VERSION = "oblivion-verifier-2"


class VerificationDimension(str, Enum):
    """The ten orthogonal questions asked of a certificate.

    These are not reducible. An earlier abandoned implementation aggregated over
    six of them and ignored failures in the other four, which meant a
    certificate bound to the wrong target could still verify.
    """

    STRUCTURE = "STRUCTURE"
    VERSION_COMPATIBILITY = "VERSION_COMPATIBILITY"
    EVIDENCE_AVAILABILITY = "EVIDENCE_AVAILABILITY"
    EVIDENCE_DIGEST = "EVIDENCE_DIGEST"
    SIGNATURE_VALIDITY = "SIGNATURE_VALIDITY"
    PUBLIC_KEY_CONSISTENCY = "PUBLIC_KEY_CONSISTENCY"
    SIGNER_TRUST = "SIGNER_TRUST"
    EVIDENCE_CHAIN_INTEGRITY = "EVIDENCE_CHAIN_INTEGRITY"
    OPERATION_CONSISTENCY = "OPERATION_CONSISTENCY"
    TARGET_CONSISTENCY = "TARGET_CONSISTENCY"


class CheckResult(str, Enum):
    """Outcome of one dimension.

    ``NOT_CHECKED`` and ``INCONCLUSIVE`` are distinct on purpose: the first means
    the verifier had no input for the question, the second that it had input and
    still could not decide. Neither is a pass.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_CHECKED = "NOT_CHECKED"
    INCONCLUSIVE = "INCONCLUSIVE"


class VerificationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass(frozen=True)
class DimensionResult:
    """One dimension's verdict, with the reason it reached that verdict."""

    dimension: VerificationDimension
    result: CheckResult
    detail: str
    evidence_ref: str | None = None


@dataclass(frozen=True)
class CertificateVerificationResult:
    """The complete report for one certificate."""

    certificate_id: str
    overall_status: str
    dimensions: tuple[DimensionResult, ...]
    cannot_prove: tuple[str, ...] = ()
    certificate_version: str | None = None
    verifier_version: str = VERIFIER_VERSION
    verified_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: Convenience views. None means the question was not answered.
    signature_valid: bool | None = None
    evidence_integrity: bool | None = None
    signer_trusted: bool | None = None

    @property
    def valid(self) -> bool:
        return self.overall_status == VerificationStatus.VALID.value

    def dimension(self, dimension: VerificationDimension) -> DimensionResult:
        for item in self.dimensions:
            if item.dimension is dimension:
                return item
        raise KeyError(f"Dimension {dimension.value} is missing from the result")


@dataclass(frozen=True)
class VerificationResult:
    """Narrow result for the raw-evidence signature helper."""

    valid: bool
    status: str
    reason: str = ""
    certificate_id: str | None = None


__all__ = [
    "VERIFIER_VERSION",
    "CertificateVerificationResult",
    "CheckResult",
    "DimensionResult",
    "VerificationDimension",
    "VerificationResult",
    "VerificationStatus",
]
