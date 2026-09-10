"""Certificate issuance, trust, and independent ten-dimension verification.

The single property behind every test here: **a certificate may not be the sole
source of the facts used to judge it.** Each dimension that could otherwise be
satisfied by the certificate talking about itself is checked against something
the certificate does not control.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from oblivion.certificate.issuer import (
    CertificateIssuanceError,
    CertificateIssuer,
    IssuanceRequest,
)
from oblivion.certificate.keys import SigningKeyManager, generate_private_key_hex
from oblivion.certificate.models import Certificate
from oblivion.certificate.trust_model import (
    NullTrustStore,
    StaticTrustStore,
    TrustedKey,
    load_trust_store_from_env,
)
from oblivion.certificate.verification import (
    REQUIRED_DIMENSIONS,
    VerificationContext,
    verify_certificate,
)
from oblivion.certificate.verification_model import (
    CheckResult,
    VerificationDimension,
    VerificationStatus,
)
from oblivion.core.evidence.generator import EvidenceGenerationContext, EvidenceGenerator
from oblivion.core.evidence.record import EvidenceRecord, TargetDescriptor

OPERATION_ID = "op_phase23"
TARGET_IDENTITY = "H:/scratch/secret.txt"
SIGNER_ID = "oblivion-issuer"

TARGET = TargetDescriptor(identity=TARGET_IDENTITY, target_type="file", filesystem="NTFS")


@pytest.fixture
def key_manager() -> SigningKeyManager:
    return SigningKeyManager.from_material(generate_private_key_hex())


@pytest.fixture
def issuer(key_manager: SigningKeyManager) -> CertificateIssuer:
    return CertificateIssuer(key_manager, signer_id=SIGNER_ID)


@pytest.fixture
def evidence() -> EvidenceRecord:
    return EvidenceGenerator().generate(
        EvidenceGenerationContext(
            operation_id=OPERATION_ID,
            target=TARGET,
            method="SELECTIVE_PERMANENT",
            policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
            execution_result={"status": "COMPLETED"},
            verification_result={"target_absent": True},
        )
    )


@pytest.fixture
def certificate(issuer: CertificateIssuer, evidence: EvidenceRecord) -> Certificate:
    return issuer.issue(IssuanceRequest(evidence=evidence, result="COMPLETED"))


@pytest.fixture
def trust_store(key_manager: SigningKeyManager) -> StaticTrustStore:
    """A verifier that has been configured to trust this issuer."""
    return StaticTrustStore.from_keys(
        [TrustedKey(signer_id=SIGNER_ID, public_key_bytes=key_manager.public_key_bytes())]
    )


def _full_context(evidence, trust_store, **overrides) -> VerificationContext:
    base = {
        "trust_store": trust_store,
        "evidence": evidence,
        "evidence_chain": (evidence,),
        "expected_operation_id": OPERATION_ID,
        "expected_target_identity": TARGET_IDENTITY,
    }
    base.update(overrides)
    return VerificationContext(**base)


# ---------------------------------------------------------------------------
# Issuance
# ---------------------------------------------------------------------------

def test_certificate_is_actually_issued(certificate):
    assert certificate.certificate_id
    assert certificate.operation_id == OPERATION_ID
    assert certificate.target_identity == TARGET_IDENTITY
    assert len(certificate.signature) == 128  # 64 bytes hex


def test_issued_certificate_binds_the_recomputed_evidence_digest(certificate, evidence):
    assert certificate.evidence_digest == evidence.digest()


def test_certificate_contains_no_private_key(certificate, key_manager):
    """The private key must not be reachable from anything published."""
    rendered = repr(certificate) + str(certificate.signing_payload())
    private_hex = key_manager._private_key.private_bytes_raw().hex()
    assert private_hex not in rendered
    assert certificate.public_key == key_manager.public_key_bytes().hex()


def test_issuance_requires_a_result(issuer, evidence):
    with pytest.raises(CertificateIssuanceError):
        issuer.issue(IssuanceRequest(evidence=evidence, result=""))


def test_issuer_requires_a_signer_id(key_manager):
    with pytest.raises(CertificateIssuanceError):
        CertificateIssuer(key_manager, signer_id="")


def test_certificate_names_the_stages_that_were_not_established(certificate):
    """A partial lifecycle must be visible in the certificate itself."""
    joined = " ".join(certificate.limitations)
    assert "recovery_test" in joined
    assert "residual_analysis" in joined
    assert "assurance" in joined


def test_certificate_survives_a_simulated_restart(evidence):
    """Signed before a restart, verified after one, using reloaded key material."""
    material = generate_private_key_hex()
    before = CertificateIssuer(SigningKeyManager.from_material(material), SIGNER_ID)
    cert = before.issue(IssuanceRequest(evidence=evidence, result="COMPLETED"))

    after_restart = SigningKeyManager.from_material(material)
    store = StaticTrustStore.from_keys(
        [
            TrustedKey(
                signer_id=SIGNER_ID, public_key_bytes=after_restart.public_key_bytes()
            )
        ]
    )

    result = verify_certificate(cert, _full_context(evidence, store))
    assert result.overall_status == VerificationStatus.VALID.value


# ---------------------------------------------------------------------------
# The happy path, and what it requires
# ---------------------------------------------------------------------------

def test_all_ten_dimensions_are_reported(certificate, evidence, trust_store):
    result = verify_certificate(certificate, _full_context(evidence, trust_store))
    assert {d.dimension for d in result.dimensions} == set(VerificationDimension)
    assert len(result.dimensions) == 10


def test_complete_independent_context_yields_valid(certificate, evidence, trust_store):
    result = verify_certificate(certificate, _full_context(evidence, trust_store))
    assert result.overall_status == VerificationStatus.VALID.value
    assert result.cannot_prove == ()
    assert result.signature_valid is True
    assert result.evidence_integrity is True
    assert result.signer_trusted is True


def test_result_carries_its_provenance(certificate, evidence, trust_store):
    result = verify_certificate(certificate, _full_context(evidence, trust_store))
    assert result.certificate_version == certificate.version
    assert result.verifier_version
    assert result.verified_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Independent expectations (VerificationContext)
# ---------------------------------------------------------------------------

def test_missing_operation_expectation_is_not_checked(certificate, evidence, trust_store):
    """Comparing the certificate's operation with itself proves nothing."""
    result = verify_certificate(
        certificate, _full_context(evidence, trust_store, expected_operation_id=None)
    )
    assert (
        result.dimension(VerificationDimension.OPERATION_CONSISTENCY).result
        is CheckResult.NOT_CHECKED
    )
    assert result.overall_status == VerificationStatus.INCONCLUSIVE.value


def test_mismatched_operation_expectation_fails(certificate, evidence, trust_store):
    result = verify_certificate(
        certificate,
        _full_context(evidence, trust_store, expected_operation_id="op_something_else"),
    )
    assert (
        result.dimension(VerificationDimension.OPERATION_CONSISTENCY).result
        is CheckResult.FAIL
    )
    assert result.overall_status == VerificationStatus.INVALID.value


def test_missing_target_expectation_is_not_checked(certificate, evidence, trust_store):
    result = verify_certificate(
        certificate, _full_context(evidence, trust_store, expected_target_identity=None)
    )
    assert (
        result.dimension(VerificationDimension.TARGET_CONSISTENCY).result
        is CheckResult.NOT_CHECKED
    )
    assert result.overall_status == VerificationStatus.INCONCLUSIVE.value


def test_mismatched_target_expectation_fails(certificate, evidence, trust_store):
    result = verify_certificate(
        certificate,
        _full_context(evidence, trust_store, expected_target_identity="H:/other.txt"),
    )
    assert (
        result.dimension(VerificationDimension.TARGET_CONSISTENCY).result
        is CheckResult.FAIL
    )
    assert result.overall_status == VerificationStatus.INVALID.value


# ---------------------------------------------------------------------------
# Trust
# ---------------------------------------------------------------------------

def test_unknown_signer_is_not_trusted_despite_a_valid_signature(certificate, evidence):
    """The central rule: signature arithmetic is not authorship."""
    result = verify_certificate(certificate, _full_context(evidence, NullTrustStore()))
    assert (
        result.dimension(VerificationDimension.SIGNATURE_VALIDITY).result
        is CheckResult.PASS
    )
    assert (
        result.dimension(VerificationDimension.SIGNER_TRUST).result
        is CheckResult.NOT_CHECKED
    )
    assert result.overall_status == VerificationStatus.INCONCLUSIVE.value


def test_embedded_key_cannot_establish_trust(certificate, evidence):
    """A certificate cannot make its own key trusted by carrying it."""
    result = verify_certificate(certificate, _full_context(evidence, NullTrustStore()))
    assert result.signer_trusted is not True
    assert (
        result.dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY).result
        is CheckResult.NOT_CHECKED
    )


def test_explicitly_denied_signer_fails(certificate, evidence, trust_store):
    trust_store.deny(SIGNER_ID)
    result = verify_certificate(certificate, _full_context(evidence, trust_store))
    assert result.dimension(VerificationDimension.SIGNER_TRUST).result is CheckResult.FAIL
    assert result.overall_status == VerificationStatus.INVALID.value


def test_revoked_signer_fails(certificate, evidence, trust_store):
    trust_store.revoke(SIGNER_ID, "key compromised")
    result = verify_certificate(certificate, _full_context(evidence, trust_store))
    assert result.dimension(VerificationDimension.SIGNER_TRUST).result is CheckResult.FAIL


def test_signer_outside_validity_window_fails(certificate, evidence, key_manager):
    expired = StaticTrustStore.from_keys(
        [
            TrustedKey(
                signer_id=SIGNER_ID,
                public_key_bytes=key_manager.public_key_bytes(),
                valid_until=datetime.now(UTC) - timedelta(days=1),
            )
        ]
    )
    result = verify_certificate(certificate, _full_context(evidence, expired))
    assert result.dimension(VerificationDimension.SIGNER_TRUST).result is CheckResult.FAIL


def test_known_signer_presenting_a_different_key_fails(certificate, evidence):
    """Claiming a trusted identity with the wrong key is a failure, not unknown."""
    other = SigningKeyManager.from_material(generate_private_key_hex())
    store = StaticTrustStore.from_keys(
        [TrustedKey(signer_id=SIGNER_ID, public_key_bytes=other.public_key_bytes())]
    )
    result = verify_certificate(certificate, _full_context(evidence, store))
    assert (
        result.dimension(VerificationDimension.PUBLIC_KEY_CONSISTENCY).result
        is CheckResult.FAIL
    )
    assert result.dimension(VerificationDimension.SIGNER_TRUST).result is CheckResult.FAIL
    assert result.overall_status == VerificationStatus.INVALID.value


def test_trust_store_loads_from_configuration(key_manager):
    store = load_trust_store_from_env(
        {
            "OBLIVION_TRUSTED_SIGNERS": (
                f"{SIGNER_ID}:{key_manager.public_key_bytes().hex()}"
            )
        }
    )
    assert store.lookup(SIGNER_ID) is not None


def test_unconfigured_trust_store_trusts_nothing():
    store = load_trust_store_from_env({})
    assert store.lookup("anyone") is None
    assert store.is_trusted("anyone", b"\x00" * 32) is CheckResult.NOT_CHECKED


# ---------------------------------------------------------------------------
# Evidence binding
# ---------------------------------------------------------------------------

def test_missing_evidence_is_not_checked_and_never_valid(certificate, trust_store):
    result = verify_certificate(
        certificate,
        VerificationContext(
            trust_store=trust_store,
            expected_operation_id=OPERATION_ID,
            expected_target_identity=TARGET_IDENTITY,
        ),
    )
    assert (
        result.dimension(VerificationDimension.EVIDENCE_AVAILABILITY).result
        is CheckResult.NOT_CHECKED
    )
    assert (
        result.dimension(VerificationDimension.EVIDENCE_DIGEST).result
        is CheckResult.NOT_CHECKED
    )
    assert result.overall_status != VerificationStatus.VALID.value


def test_modified_evidence_fails_the_digest_dimension(certificate, evidence, trust_store):
    tampered = EvidenceRecord.from_canonical_dict(
        {**evidence.to_canonical_dict(), "method": "COMPLETE_ERASURE"}
    )
    result = verify_certificate(certificate, _full_context(tampered, trust_store))
    assert (
        result.dimension(VerificationDimension.EVIDENCE_DIGEST).result is CheckResult.FAIL
    )
    assert result.overall_status == VerificationStatus.INVALID.value


def test_wrong_evidence_record_fails_availability(certificate, trust_store):
    other = EvidenceGenerator().generate(
        EvidenceGenerationContext(
            operation_id=OPERATION_ID, target=TARGET, method="SELECTIVE_PERMANENT"
        )
    )
    result = verify_certificate(certificate, _full_context(other, trust_store))
    assert (
        result.dimension(VerificationDimension.EVIDENCE_AVAILABILITY).result
        is CheckResult.FAIL
    )


def test_valid_digest_does_not_imply_chain_integrity(certificate, evidence, trust_store):
    """Object integrity and chain integrity are different properties."""
    result = verify_certificate(
        certificate, _full_context(evidence, trust_store, evidence_chain=None)
    )
    assert (
        result.dimension(VerificationDimension.EVIDENCE_DIGEST).result is CheckResult.PASS
    )
    assert (
        result.dimension(VerificationDimension.EVIDENCE_CHAIN_INTEGRITY).result
        is CheckResult.NOT_CHECKED
    )
    assert result.overall_status == VerificationStatus.INCONCLUSIVE.value


# ---------------------------------------------------------------------------
# Tampering with the certificate itself
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "field,value",
    [
        ("operation_id", "op_forged"),
        ("target_identity", "H:/forged.txt"),
        ("evidence_digest", "b" * 64),
        ("result", "FORGED"),
        ("method", "COMPLETE_ERASURE"),
        ("signer_id", "someone-else"),
        ("key_id", "0000000000000000"),
    ],
)
def test_altering_any_signed_field_breaks_the_signature(
    certificate, evidence, trust_store, field, value
):
    """The signature covers the whole payload, not just the evidence digest."""
    forged = replace(certificate, **{field: value})
    result = verify_certificate(forged, _full_context(evidence, trust_store))
    assert (
        result.dimension(VerificationDimension.SIGNATURE_VALIDITY).result
        is CheckResult.FAIL
    )
    assert result.overall_status == VerificationStatus.INVALID.value


def test_unsupported_version_is_inconclusive_not_valid(certificate, evidence, trust_store):
    legacy = replace(certificate, version="1.0.0")
    result = verify_certificate(legacy, _full_context(evidence, trust_store))
    assert (
        result.dimension(VerificationDimension.VERSION_COMPATIBILITY).result
        is CheckResult.INCONCLUSIVE
    )
    assert result.overall_status != VerificationStatus.VALID.value


def test_malformed_structure_fails(certificate, evidence, trust_store):
    broken = replace(certificate, evidence_digest="not-a-digest")
    result = verify_certificate(broken, _full_context(evidence, trust_store))
    assert result.dimension(VerificationDimension.STRUCTURE).result is CheckResult.FAIL
    assert result.overall_status == VerificationStatus.INVALID.value


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def test_all_ten_dimensions_are_required():
    assert REQUIRED_DIMENSIONS == frozenset(VerificationDimension)
    assert len(REQUIRED_DIMENSIONS) == 10


def test_six_dimension_subset_cannot_produce_valid():
    """Regression against the abandoned implementation's fail-open aggregation.

    It aggregated over six dimensions and ignored failures in the other four, so
    a certificate bound to the wrong target verified. Any such subset is a
    strict subset of REQUIRED_DIMENSIONS, so no subset can satisfy it.
    """
    six = {
        VerificationDimension.STRUCTURE,
        VerificationDimension.VERSION_COMPATIBILITY,
        VerificationDimension.EVIDENCE_AVAILABILITY,
        VerificationDimension.EVIDENCE_DIGEST,
        VerificationDimension.SIGNATURE_VALIDITY,
        VerificationDimension.SIGNER_TRUST,
    }
    assert six < REQUIRED_DIMENSIONS
    for ignored in (
        VerificationDimension.PUBLIC_KEY_CONSISTENCY,
        VerificationDimension.EVIDENCE_CHAIN_INTEGRITY,
        VerificationDimension.OPERATION_CONSISTENCY,
        VerificationDimension.TARGET_CONSISTENCY,
    ):
        assert ignored in REQUIRED_DIMENSIONS


def test_no_context_at_all_is_inconclusive(certificate):
    """A verifier that knows nothing independently cannot return VALID."""
    result = verify_certificate(certificate)
    assert result.overall_status == VerificationStatus.INCONCLUSIVE.value
    assert result.cannot_prove


def test_cannot_prove_names_each_specific_limitation(certificate):
    result = verify_certificate(certificate)
    joined = " ".join(result.cannot_prove)
    assert VerificationDimension.SIGNER_TRUST.value in joined
    assert VerificationDimension.OPERATION_CONSISTENCY.value in joined
    assert "verification incomplete" not in joined.lower()


def test_a_fail_outranks_an_inconclusive(certificate, evidence, trust_store):
    """FAIL wins regardless of what else is unknown, and of ordering."""
    forged = replace(certificate, operation_id="op_forged")
    result = verify_certificate(
        forged,
        VerificationContext(
            trust_store=trust_store,
            evidence=evidence,
            expected_operation_id="op_forged",
        ),
    )
    assert CheckResult.FAIL in {d.result for d in result.dimensions}
    assert result.overall_status == VerificationStatus.INVALID.value
