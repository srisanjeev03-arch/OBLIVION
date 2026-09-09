"""Security-focused tests for Certificate verification."""
import binascii
from datetime import datetime
import pytest

from oblivion.certificate.verification import (
    verify_certificate,
    verify_evidence_only,
    VerificationStatus,
)
from oblivion.certificate.models import Certificate
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.certificate.integrity import hash_integrity
from oblivion.core.evidence.models import EvidencePackage


def _evidence() -> EvidencePackage:
    return EvidencePackage(
        operation_id="op-sec-001",
        target_identity="file-x",
        target_hash="1" * 64,
        storage_profile={"type": "ntfs"},
        policy={"mode": "COMPLETE_ERASURE", "policy_id": "p1"},
        start_timestamp=datetime(2026, 9, 7, 0, 0, 0),
        end_timestamp=datetime(2026, 9, 7, 0, 1, 0),
        operation_results={"status": "success"},
        recovery_test_result={"status": "skipped"},
        residual_scan_result={"status": "passed", "findings": []},
        assurance_result={"level": "HIGH", "score": 0.9},
        warnings=[],
        software_version="0.1.0-slice1",
    )


def _signed_cert(evidence: EvidencePackage, *, signer: Ed25519SignerVerifier | None = None):
    signer = signer or Ed25519SignerVerifier.generate()
    pub = signer.get_public_key_bytes()
    h = hash_integrity(evidence)
    sig = signer.sign(h.encode("utf-8"))
    cert = Certificate(
        certificate_id="cert-sec-001",
        evidence_id="ev-sec-001",
        evidence_hash=h,
        signature=binascii.hexlify(sig).decode("ascii"),
        signer_id="signer-x",
        timestamp=datetime(2026, 9, 7, 0, 1, 0),
    )
    return cert, pub


def test_signature_signed_with_other_key_fails():
    """A certificate signed with key A must not verify with key B's public key."""
    evidence = _evidence()
    signer_a = Ed25519SignerVerifier.generate()
    cert, _ = _signed_cert(evidence, signer=signer_a)
    pub_b = Ed25519SignerVerifier.generate().get_public_key_bytes()
    result = verify_certificate(cert, evidence, pub_b)
    assert result.status == VerificationStatus.INVALID_SIGNATURE


def test_evidence_tampered_after_signing_detected():
    """Modifying any field of the evidence must be detected as tampering."""
    evidence = _evidence()
    cert, pub = _signed_cert(evidence)
    evidence.assurance_result = {"level": "NONE", "score": 0.0}  # type: ignore[assignment]
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.TAMPERED_EVIDENCE


def test_malformed_signature_hex_is_inconclusive():
    evidence = _evidence()
    cert, pub = _signed_cert(evidence)
    cert.signature = "@@@not_hex@@@"
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.INCONCLUSIVE


def test_empty_public_key_does_not_crash_and_returns_invalid_or_inconclusive():
    evidence = _evidence()
    cert, _ = _signed_cert(evidence)
    result = verify_certificate(cert, evidence, b"")
    assert result.status in (
        VerificationStatus.INVALID_SIGNATURE,
        VerificationStatus.INCONCLUSIVE,
    )


def test_evidence_only_check_ignores_signature_mismatch_but_detects_evidence_tamper():
    evidence = _evidence()
    cert, _ = _signed_cert(evidence)
    # Sign a tampered evidence — evidence-only check should still catch the tamper.
    evidence.target_hash = "f" * 64
    result = verify_evidence_only(cert, evidence)
    assert result.status == VerificationStatus.TAMPERED_EVIDENCE


def test_unsupported_version_rejected():
    evidence = _evidence()
    cert, pub = _signed_cert(evidence)
    cert.version = "0.0.0"
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.UNSUPPORTED_VERSION
