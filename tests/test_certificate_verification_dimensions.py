import datetime

import pytest

from oblivion.certificate.models import Certificate
from oblivion.certificate.verification import verify_certificate
from oblivion.certificate.verification_model import (
    CheckResult,
    VerificationDimension,
)
from oblivion.core.evidence.models import EvidencePackage


@pytest.fixture
def mock_signer_key():
    from cryptography.hazmat.primitives.asymmetric import ed25519
    private_key = ed25519.Ed25519PrivateKey.generate()
    return private_key

@pytest.fixture
def public_key_bytes(mock_signer_key):
    from cryptography.hazmat.primitives import serialization
    return mock_signer_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )

@pytest.fixture
def valid_evidence():
    return EvidencePackage(
        operation_id="op_123",
        target_identity="test_file.txt",
        target_hash="a" * 64,  # Valid 64-char hex hash
        storage_profile={},
        policy={},
        start_timestamp=datetime.datetime.now(datetime.UTC),
        end_timestamp=datetime.datetime.now(datetime.UTC),
        operation_results={},
        recovery_test_result={},
        residual_scan_result={},
        assurance_result={},
        warnings=[],
        software_version="1.0.0"
    )

@pytest.fixture
def valid_certificate(valid_evidence, mock_signer_key):
    from oblivion.certificate.integrity import hash_integrity

    evidence_hash = hash_integrity(valid_evidence)
    signature = mock_signer_key.sign(evidence_hash.encode("utf-8"))

    return Certificate(
        certificate_id="cert_123",
        evidence_id=valid_evidence.operation_id,  # Match evidence operation_id for consistency
        evidence_hash=evidence_hash,
        signature=signature.hex(),
        signer_id="signer_123",
        timestamp=datetime.datetime.now(datetime.UTC),
        version="1.0.0"
    )

def test_case_1_valid_certificate(valid_certificate, valid_evidence, public_key_bytes):
    """CASE 1: Valid certificate + complete evidence."""
    # Note: signer trust is currently NOT_CHECKED as TrustStore is a placeholder
    res = verify_certificate(valid_certificate, valid_evidence, public_key_bytes)
    assert res.overall_status == "INCONCLUSIVE" # Because of NOT_CHECKED dimensions
    assert any(d.dimension == VerificationDimension.SIGNATURE_VALIDITY and d.result == CheckResult.PASS for d in res.dimensions)
    assert any(d.dimension == VerificationDimension.EVIDENCE_DIGEST and d.result == CheckResult.PASS for d in res.dimensions)
    assert res.signature_valid is True
    assert res.evidence_integrity is True

def test_case_2_valid_signature_missing_evidence(valid_certificate, public_key_bytes):
    """CASE 2: Valid signature + missing evidence."""
    res = verify_certificate(valid_certificate, None, public_key_bytes)
    assert res.overall_status == "INVALID" # Because EVIDENCE_AVAILABILITY is FAIL
    assert any(d.dimension == VerificationDimension.EVIDENCE_AVAILABILITY and d.result == CheckResult.FAIL for d in res.dimensions)
    assert res.evidence_integrity is False

def test_case_3_valid_signature_digest_mismatch(valid_certificate, valid_evidence, public_key_bytes):
    """CASE 3: Valid signature + evidence available + digest mismatch."""
    valid_evidence.target_hash = "tampered_hash"
    res = verify_certificate(valid_certificate, valid_evidence, public_key_bytes)
    assert res.overall_status == "INVALID"
    assert any(d.dimension == VerificationDimension.EVIDENCE_DIGEST and d.result == CheckResult.FAIL for d in res.dimensions)
    assert res.evidence_integrity is False

def test_case_4_invalid_signature(valid_certificate, valid_evidence, public_key_bytes):
    """CASE 4: Invalid signature."""
    valid_certificate.signature = "0" * 128
    res = verify_certificate(valid_certificate, valid_evidence, public_key_bytes)
    assert res.overall_status == "INVALID"
    assert any(d.dimension == VerificationDimension.SIGNATURE_VALIDITY and d.result == CheckResult.FAIL for d in res.dimensions)
    assert res.signature_valid is False

def test_case_5_unsupported_version(valid_certificate, valid_evidence, public_key_bytes):
    """CASE 5: Unsupported certificate version."""
    valid_certificate.version = "2.0.0"
    res = verify_certificate(valid_certificate, valid_evidence, public_key_bytes)
    assert res.overall_status == "INVALID"
    assert any(d.dimension == VerificationDimension.VERSION_COMPATIBILITY and d.result == CheckResult.FAIL for d in res.dimensions)

def test_security_invariant_1_signature_valid_but_missing_evidence_not_valid(valid_certificate, public_key_bytes):
    """Security Invariant 1: signature_valid == true AND evidence_availability != PASS MUST NOT produce VALID."""
    res = verify_certificate(valid_certificate, None, public_key_bytes)
    assert res.signature_valid is True
    assert res.overall_status != "VALID"
