import pytest
from datetime import datetime
from oblivion.core.evidence.models import EvidencePackage
from oblivion.certificate.models import Certificate
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.certificate.verification import verify_certificate, VerificationStatus

@pytest.fixture
def sample_evidence():
    return EvidencePackage(
        operation_id="op-123",
        target_identity="file-path",
        target_hash="abc",
        storage_profile={"type": "ntfs"},
        policy={"mode": "complete"},
        start_timestamp=datetime.now(),
        end_timestamp=datetime.now(),
        operation_results={},
        recovery_test_result={},
        residual_scan_result={},
        assurance_result={},
        warnings=[],
        software_version="1.0.0"
    )

def test_certificate_verification_success(sample_evidence):
    signer = Ed25519SignerVerifier.generate()
    from oblivion.certificate.integrity import hash_integrity
    
    ev_hash = hash_integrity(sample_evidence)
    
    cert = Certificate(
        certificate_id="cert-1",
        evidence_id="op-123",
        evidence_hash=ev_hash,
        signature=signer.sign(ev_hash.encode('utf-8')).hex(),
        signer_id="signer-1",
        timestamp=datetime.now()
    )
    
    result = verify_certificate(cert, sample_evidence, signer.get_public_key_bytes())
    assert result.status == VerificationStatus.VALID

def test_certificate_verification_tampered(sample_evidence):
    signer = Ed25519SignerVerifier.generate()
    from oblivion.certificate.integrity import hash_integrity
    
    ev_hash = hash_integrity(sample_evidence)
    
    cert = Certificate(
        certificate_id="cert-1",
        evidence_id="op-123",
        evidence_hash=ev_hash,
        signature=signer.sign(ev_hash.encode('utf-8')).hex(),
        signer_id="signer-1",
        timestamp=datetime.now()
    )
    
    # Tamper with evidence
    sample_evidence.target_hash = "wrong"
    
    result = verify_certificate(cert, sample_evidence, signer.get_public_key_bytes())
    assert result.status == VerificationStatus.TAMPERED_EVIDENCE
