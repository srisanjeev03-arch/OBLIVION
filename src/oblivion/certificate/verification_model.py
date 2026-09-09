"""Data models for Multi-Dimensional Certificate and Evidence Verification."""
from dataclasses import dataclass, field
from enum import Enum


class VerificationDimension(str, Enum):
    """The ten orthogonal dimensions of forensic certificate verification."""
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
    """Result of evaluating a single verification dimension."""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_CHECKED = "NOT_CHECKED"
    INCONCLUSIVE = "INCONCLUSIVE"


class VerificationStatus(str, Enum):
    """Overall aggregate verification status."""
    VALID = "VALID"
    INVALID = "INVALID"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class DimensionResult:
    """Result for one specific verification dimension."""
    dimension: VerificationDimension
    result: CheckResult
    detail: str
    evidence_ref: str | None = None


@dataclass
class CertificateVerificationResult:
    """Complete multi-dimensional verification report for a certificate."""
    certificate_id: str
    overall_status: str  # VALID | INVALID | INCONCLUSIVE
    dimensions: list[DimensionResult]
    signature_valid: bool | None = None
    evidence_integrity: bool | None = None
    signer_trusted: bool | None = None
    cannot_prove: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Backward-compatible boolean indicating overall VALID status."""
        return self.overall_status == VerificationStatus.VALID.value

    @property
    def status(self) -> str:
        """Backward-compatible status string."""
        return self.overall_status


@dataclass
class VerificationResult:
    """Backward-compatible verification result for legacy tests."""
    valid: bool
    status: str
    evidence_integrity: bool = True
    signature_valid: bool = True
    reason: str = ""
    certificate_id: str | None = None


__all__ = [
    "CertificateVerificationResult",
    "CheckResult",
    "DimensionResult",
    "VerificationDimension",
    "VerificationResult",
    "VerificationStatus",
]
