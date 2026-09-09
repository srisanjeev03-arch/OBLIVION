"""Tests for Certificate verification against Evidence packages."""
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
from oblivion.core.evidence.models import EvidencePackage


def _make_evidence() -> EvidencePackage:
    return EvidencePackage(
        operation_id="op-test-001",
        target_identity="file-abc",
        target_hash="a" * 64,
        storage_profile={"type": "ntfs", "fs": "ntfs"},
        policy={"mode": "COMPLETE_ERASURE", "policy_id": "policy-test"},
        start_timestamp=datetime(2026, 9, 7, 12, 0, 0),
        end_timestamp=datetime(2026, 9, 7, 12, 1, 0),
        operation_results={"status": "success", "files_processed": 1},
        recovery_test_result={"status": "skipped"},
        residual_scan_result={"status": "passed", "findings": []},
        assurance_result={"level": "HIGH", "score": 0.95},
        warnings=[],
        software_version="0.1.0-slice1",
    )


def _make_signed_cert(evidence: EvidencePackage) -> tuple[Certificate, bytes, Ed25519SignerVerifier]:
    """Build a Certificate that is properly bound to the evidence package."""
    from oblivion.certificate.integrity import hash_integrity
    signer = Ed25519SignerVerifier.generate()
    pub = signer.get_public_key_bytes()
    evidence_hash = hash_integrity(evidence)
    sig_bytes = signer.sign(evidence_hash.encode("utf-8"))
    cert = Certificate(
        certificate_id="cert-test-001",
        evidence_id="ev-test-001",
        evidence_hash=evidence_hash,
        signature=binascii.hexlify(sig_bytes).decode("ascii"),
        signer_id="signer-1",
        timestamp=datetime(2026, 9, 7, 12, 1, 0),
    )
    return cert, pub, signer


def test_verify_certificate_success():
    evidence = _make_evidence()
    cert, pub, _ = _make_signed_cert(evidence)
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.VALID
    assert result.certificate_id == "cert-test-001"


def test_verify_certificate_tampered_evidence():
    evidence = _make_evidence()
    cert, pub, _ = _make_signed_cert(evidence)
    # Tamper with the evidence after signing
    evidence.target_hash = "b" * 64
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.TAMPERED_EVIDENCE


def test_verify_certificate_wrong_public_key():
    evidence = _make_evidence()
    cert, _, _ = _make_signed_cert(evidence)
    other_signer = Ed25519SignerVerifier.generate()
    other_pub = other_signer.get_public_key_bytes()
    result = verify_certificate(cert, evidence, other_pub)
    assert result.status == VerificationStatus.INVALID_SIGNATURE


def test_verify_certificate_unsupported_version():
    evidence = _make_evidence()
    cert, pub, _ = _make_signed_cert(evidence)
    cert.version = "9.9.9"
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.UNSUPPORTED_VERSION


def test_verify_certificate_invalid_signature_encoding():
    evidence = _make_evidence()
    cert, pub, _ = _make_signed_cert(evidence)
    cert.signature = "not-hex-!!"
    result = verify_certificate(cert, evidence, pub)
    assert result.status == VerificationStatus.INCONCLUSIVE


def test_verify_evidence_only_tampered():
    evidence = _make_evidence()
    cert, _, _ = _make_signed_cert(evidence)
    evidence.target_identity = "tampered"
    result = verify_evidence_only(cert, evidence)
    assert result.status == VerificationStatus.TAMPERED_EVIDENCE
