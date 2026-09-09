"""Phase 23 acceptance tests for fail-closed certificate verification."""
from datetime import UTC, datetime

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from oblivion.certificate.integrity import hash_integrity
from oblivion.certificate.models import Certificate
from oblivion.certificate.trust_model import StaticTrustStore, TrustedKey
from oblivion.certificate.verification import verify_certificate
from oblivion.certificate.verification_model import CheckResult, VerificationDimension
from oblivion.core.evidence.canonical import canonicalize as compatibility_canonicalize
from oblivion.core.evidence.canonicalize import canonicalize
from oblivion.core.evidence.models import EvidencePackage


def _evidence() -> EvidencePackage:
    now = datetime.now(UTC)
    return EvidencePackage(
        operation_id="op-phase23",
        target_identity="C:/OblivionDemo/sample.txt",
        target_hash="a" * 64,
        storage_profile={}, policy={}, start_timestamp=now, end_timestamp=now,
        operation_results={"event_chain_verified": True}, recovery_test_result={},
        residual_scan_result={}, assurance_result={}, warnings=[], software_version="1.0.0",
    )


def _signed(evidence: EvidencePackage) -> tuple[Certificate, bytes]:
    private = ed25519.Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    digest = hash_integrity(evidence)
    return Certificate(
        certificate_id="cert-phase23", evidence_id="evidence-phase23", evidence_hash=digest,
        signature=private.sign(digest.encode("ascii")).hex(), signer_id="signer-phase23",
        timestamp=datetime.now(UTC), operation_id=evidence.operation_id,
        public_key=public.hex(),
    ), public


def _trust(key: bytes) -> StaticTrustStore:
    return StaticTrustStore([TrustedKey("signer-phase23", key, "AUDITOR", datetime(2020, 1, 1, tzinfo=UTC))])


def _by_dimension(result, dimension: VerificationDimension):
    return next(item for item in result.dimensions if item.dimension is dimension)


def test_all_ten_dimensions_are_reported_once():
    evidence = _evidence()
    certificate, key = _signed(evidence)
    result = verify_certificate(certificate, evidence, key, _trust(key))
    assert {item.dimension for item in result.dimensions} == set(VerificationDimension)
    assert len(result.dimensions) == 10


def test_signature_is_not_a_valid_certificate_without_trust_and_chain_proof():
    evidence = _evidence()
    certificate, key = _signed(evidence)
    result = verify_certificate(certificate, evidence, key)
    assert result.signature_valid is True
    assert result.overall_status == "INCONCLUSIVE"
    assert _by_dimension(result, VerificationDimension.SIGNER_TRUST).result is CheckResult.NOT_CHECKED
    assert _by_dimension(result, VerificationDimension.EVIDENCE_CHAIN_INTEGRITY).result is CheckResult.NOT_CHECKED


def test_valid_requires_independent_trust_and_chain_proof():
    evidence = _evidence()
    certificate, key = _signed(evidence)
    result = verify_certificate(certificate, evidence, key, _trust(key), CheckResult.PASS)
    assert result.overall_status == "VALID"
    assert result.valid is True


def test_missing_evidence_never_yields_valid_even_with_a_valid_signature():
    evidence = _evidence()
    certificate, key = _signed(evidence)
    result = verify_certificate(certificate, None, key, _trust(key), CheckResult.PASS)
    assert result.signature_valid is True
    assert result.overall_status == "INVALID"
    assert _by_dimension(result, VerificationDimension.EVIDENCE_AVAILABILITY).result is CheckResult.FAIL


def test_embedded_key_cannot_substitute_the_trusted_verification_key():
    evidence = _evidence()
    certificate, _key = _signed(evidence)
    other_key = ed25519.Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    result = verify_certificate(certificate, evidence, other_key, _trust(other_key), CheckResult.PASS)
    assert result.overall_status == "INVALID"
    assert _by_dimension(result, VerificationDimension.PUBLIC_KEY_CONSISTENCY).result is CheckResult.FAIL


def test_evidence_self_assertion_does_not_prove_the_event_chain():
    evidence = _evidence()
    certificate, key = _signed(evidence)
    result = verify_certificate(certificate, evidence, key, _trust(key))
    assert _by_dimension(result, VerificationDimension.EVIDENCE_CHAIN_INTEGRITY).result is CheckResult.NOT_CHECKED


def test_static_trust_store_rejects_expired_and_revoked_keys():
    evidence = _evidence()
    certificate, key = _signed(evidence)
    expired = StaticTrustStore([TrustedKey("signer-phase23", key, "AUDITOR", datetime(2020, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC))])
    assert verify_certificate(certificate, evidence, key, expired, CheckResult.PASS).overall_status == "INVALID"
    revoked = _trust(key)
    revoked.revoke_key("signer-phase23", "test")
    assert verify_certificate(certificate, evidence, key, revoked, CheckResult.PASS).overall_status == "INVALID"


def test_compatibility_import_uses_the_single_byte_canonicalizer():
    payload = {"nested": {"z": 1, "a": None}, "items": [2, 1]}
    assert compatibility_canonicalize(payload) == canonicalize(payload)
