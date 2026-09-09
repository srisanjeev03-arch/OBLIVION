"""Deterministic verification of Certificates and Evidence."""
import binascii
from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .models import Certificate
from oblivion.core.evidence.models import EvidencePackage
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.certificate.integrity import hash_integrity

# Supported certificate versions
SUPPORTED_CERTIFICATE_VERSIONS = {"1.0.0"}


class VerificationStatus(Enum):
    """Enumeration of all possible verification outcomes."""
    VALID = "VALID"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    TAMPERED_EVIDENCE = "TAMPERED_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"
    MISSING_REFERENCE = "MISSING_REFERENCE"
    UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"


@dataclass
class VerificationResult:
    """Structured verification result."""
    status: VerificationStatus
    details: str = ""
    certificate_id: Optional[str] = None


def verify_certificate(
    cert: Certificate,
    evidence: EvidencePackage,
    signer_public_key: bytes
) -> VerificationResult:
    """Verifies a certificate against an evidence package.

    Performs the following checks in order:
    1. Version compatibility.
    2. Evidence-hash integrity (detect tampering of the evidence package).
    3. Ed25519 signature validity against the evidence hash.
    """

    # 0. Version compatibility check
    if cert.version not in SUPPORTED_CERTIFICATE_VERSIONS:
        return VerificationResult(
            VerificationStatus.UNSUPPORTED_VERSION,
            f"Certificate version {cert.version} is not supported.",
            certificate_id=cert.certificate_id,
        )

    # 1. Hash evidence and compare (detect tampering)
    try:
        calculated_hash = hash_integrity(evidence)
    except Exception as e:
        return VerificationResult(
            VerificationStatus.INCONCLUSIVE,
            f"Failed to canonicalize/hash evidence: {str(e)}",
            certificate_id=cert.certificate_id,
        )

    if calculated_hash != cert.evidence_hash:
        return VerificationResult(
            VerificationStatus.TAMPERED_EVIDENCE,
            f"Evidence hash mismatch. Expected {cert.evidence_hash}, calculated {calculated_hash}.",
            certificate_id=cert.certificate_id,
        )

    # 2. Verify Ed25519 signature on the evidence hash
    try:
        sig_bytes = binascii.unhexlify(cert.signature)
    except (binascii.Error, ValueError) as e:
        return VerificationResult(
            VerificationStatus.INCONCLUSIVE,
            f"Invalid signature encoding: {str(e)}",
            certificate_id=cert.certificate_id,
        )

    data_bytes = cert.evidence_hash.encode("utf-8")

    try:
        is_valid_sig = Ed25519SignerVerifier.verify(
            signer_public_key,
            data_bytes,
            sig_bytes,
        )
    except Exception as e:
        return VerificationResult(
            VerificationStatus.INCONCLUSIVE,
            f"Signature verification failed to execute: {str(e)}",
            certificate_id=cert.certificate_id,
        )

    if not is_valid_sig:
        return VerificationResult(
            VerificationStatus.INVALID_SIGNATURE,
            "Ed25519 signature did not validate against the evidence hash.",
            certificate_id=cert.certificate_id,
        )

    return VerificationResult(
        VerificationStatus.VALID,
        "Certificate and evidence verified successfully.",
        certificate_id=cert.certificate_id,
    )


def verify_evidence_only(
    cert: Certificate,
    evidence: EvidencePackage,
) -> VerificationResult:
    """Verify only the evidence-hash binding (no signature check).

    Useful when the signature/keys are unavailable but integrity of the
    evidence still needs to be checked.
    """
    try:
        calculated_hash = hash_integrity(evidence)
    except Exception as e:
        return VerificationResult(
            VerificationStatus.INCONCLUSIVE,
            f"Failed to canonicalize/hash evidence: {str(e)}",
            certificate_id=cert.certificate_id,
        )

    if calculated_hash != cert.evidence_hash:
        return VerificationResult(
            VerificationStatus.TAMPERED_EVIDENCE,
            f"Evidence hash mismatch. Expected {cert.evidence_hash}, calculated {calculated_hash}.",
            certificate_id=cert.certificate_id,
        )

    return VerificationResult(
        VerificationStatus.VALID,
        "Evidence hash matches certificate (signature not checked).",
        certificate_id=cert.certificate_id,
    )
