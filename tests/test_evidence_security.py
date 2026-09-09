from datetime import datetime

import pytest

from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.core.evidence.engine import EvidenceEngine
from oblivion.core.evidence.models import EvidencePackage


@pytest.fixture
def signer():
    return Ed25519SignerVerifier.generate()

@pytest.fixture
def evidence_package():
    return EvidencePackage(
        operation_id="op-123",
        target_identity="target-1",
        target_hash="hash-1",
        storage_profile={"type": "ntfs"},
        policy={"mode": "COMPLETE_ERASURE"},
        start_timestamp=datetime.now(),
        end_timestamp=datetime.now(),
        operation_results={"success": True},
        recovery_test_result={"recoverable": False},
        residual_scan_result={"artifacts": []},
        assurance_result={"score": 1.0},
        warnings=[],
        software_version="0.1.0"
    )

def test_evidence_signing_and_verification(signer, evidence_package):
    engine = EvidenceEngine(signer)
    signed_data = engine.generate_signed_evidence(evidence_package)

    assert "signature" in signed_data
    assert "public_key" in signed_data

    is_valid = EvidenceEngine.verify_evidence(
        signed_data["evidence"],
        signed_data["signature"],
        signed_data["public_key"]
    )
    assert is_valid

def test_evidence_tampering_detection(signer, evidence_package):
    engine = EvidenceEngine(signer)
    signed_data = engine.generate_signed_evidence(evidence_package)

    # Tamper with the evidence data
    tampered_evidence = signed_data["evidence"].copy()
    tampered_evidence["target_identity"] = "tampered-identity"

    is_valid = EvidenceEngine.verify_evidence(
        tampered_evidence,
        signed_data["signature"],
        signed_data["public_key"]
    )
    assert not is_valid

def test_evidence_signature_tampering(signer, evidence_package):
    engine = EvidenceEngine(signer)
    signed_data = engine.generate_signed_evidence(evidence_package)

    # Tamper with the signature (flip a byte)
    tampered_signature = bytearray.fromhex(signed_data["signature"])
    tampered_signature[0] = tampered_signature[0] ^ 0xFF

    is_valid = EvidenceEngine.verify_evidence(
        signed_data["evidence"],
        tampered_signature.hex(),
        signed_data["public_key"]
    )
    assert not is_valid
