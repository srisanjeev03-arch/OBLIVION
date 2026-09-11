"""The certificate verification endpoint, end to end.

This module doubles as the Phase 23 exit demonstration: it drives the real
implementation paths - generate evidence, canonicalize it, hash it, issue a
certificate, persist both, load them back, and verify through the HTTP API with
an independent verification context. Nothing here is simulated.
"""

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.certificate.issuer import CertificateIssuer, IssuanceRequest
from oblivion.certificate.keys import SigningKeyManager, generate_private_key_hex
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.certificate.trust_model import ENV_TRUSTED_SIGNERS
from oblivion.core.evidence.generator import EvidenceGenerationContext, EvidenceGenerator
from oblivion.core.evidence.record import TargetDescriptor
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.certificate_repo import CertificateRepository
from oblivion.persistence.repositories.operation_repo import OperationRepository

SIGNER_ID = "oblivion-issuer"


@pytest.fixture
def issued(monkeypatch, temp_dir):
    """A real operation, evidence and certificate, persisted and trusted.

    Returns everything a caller needs to verify it independently.
    """
    init_db()

    target_path = temp_dir / "certified.txt"
    target_path.write_text("payload")
    target_identity = str(target_path)

    suffix = uuid.uuid4().hex[:8]
    target_id = f"tgt_{suffix}"
    operation_id = f"op_{suffix}"

    material = generate_private_key_hex()
    key_manager = SigningKeyManager.from_material(material)

    session_factory = get_session_factory()
    with session_factory() as session:
        operations = OperationRepository(session)
        operations.create_target(
            target_id=target_id,
            path=target_identity,
            canonical_path=target_identity,
            target_type="file",
        )
        operations.create_operation(
            operation_id=operation_id,
            target_id=target_id,
            mode="SELECTIVE_PERMANENT",
            policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
            state="COMPLETED",
        )

        evidence = EvidenceGenerator().generate(
            EvidenceGenerationContext(
                operation_id=operation_id,
                target=TargetDescriptor(
                    identity=target_identity, target_type="file", filesystem="NTFS"
                ),
                method="SELECTIVE_PERMANENT",
                policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
                execution_result={"status": "COMPLETED"},
                verification_result={"target_absent": True},
                limitations=("Logical deletion only; no sanitization performed.",),
            )
        )
        certificate = CertificateIssuer(key_manager, SIGNER_ID).issue(
            IssuanceRequest(evidence=evidence, result="COMPLETED")
        )

        repo = CertificateRepository(session)
        repo.save_evidence(evidence)
        repo.save_certificate(certificate)
        session.commit()

    # The verifier trusts this signer because it was configured to, not because
    # the certificate says so.
    monkeypatch.setenv(
        ENV_TRUSTED_SIGNERS, f"{SIGNER_ID}:{key_manager.public_key_bytes().hex()}"
    )

    return {
        "certificate_id": certificate.certificate_id,
        "operation_id": operation_id,
        "target_identity": target_identity,
        "evidence_id": evidence.evidence_id,
        "evidence_digest": evidence.digest(),
        "key_manager": key_manager,
    }


def _verify(client, certificate_id, body=None):
    return client.post(f"/api/certificates/{certificate_id}/verify", json=body or {})


# ---------------------------------------------------------------------------
# Persistence round trip
# ---------------------------------------------------------------------------

def test_reloaded_certificate_is_byte_identical_to_the_issued_one(issued):
    """Storage must not alter a signed artifact in any way.

    If persistence changed the canonical payload - reordered a key, dropped a
    null, or lost a timezone offset - the certificate would fail its own
    signature after a restart, and the failure would be indistinguishable from
    tampering. This asserts the exact identity of every signed field.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        repo = CertificateRepository(session)
        reloaded = repo.load_certificate(issued["certificate_id"])
        reloaded_evidence = repo.load_evidence(issued["evidence_id"])

    assert reloaded is not None
    assert reloaded_evidence is not None

    # Stable identifiers and digests
    assert reloaded.certificate_id == issued["certificate_id"]
    assert reloaded.operation_id == issued["operation_id"]
    assert reloaded.target_identity == issued["target_identity"]
    assert reloaded.evidence_digest == issued["evidence_digest"]
    assert reloaded.signer_id == SIGNER_ID
    assert reloaded.key_id == issued["key_manager"].key_id

    # The evidence still hashes to what the certificate recorded.
    assert reloaded_evidence.digest() == reloaded.evidence_digest

    # Timezone survived the round trip, so the signed payload is unchanged.
    assert reloaded.issued_at.tzinfo is not None
    assert reloaded.signing_bytes()

    # And the signature still verifies against the reloaded payload.
    from oblivion.certificate.signer import Ed25519SignerVerifier

    assert Ed25519SignerVerifier.verify(
        issued["key_manager"].public_key_bytes(),
        reloaded.signing_bytes(),
        bytes.fromhex(reloaded.signature),
    )


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_verify_requires_authentication(issued):
    """No credential, no verification."""
    anonymous = TestClient(app)
    response = anonymous.post(
        f"/api/certificates/{issued['certificate_id']}/verify", json={}
    )
    assert response.status_code == 401


def test_verify_forbidden_without_the_permission(issued, viewer_client):
    """VIEWER holds evidence.view but not evidence.verify."""
    response = _verify(viewer_client, issued["certificate_id"])
    assert response.status_code == 403


def test_verify_allowed_for_auditor(issued, auditor_client):
    response = _verify(auditor_client, issued["certificate_id"])
    assert response.status_code == 200


def test_unknown_certificate_is_404(auditor_client):
    response = _verify(auditor_client, "cert_does_not_exist")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# The demonstration: a full independent verification
# ---------------------------------------------------------------------------

def test_independent_context_yields_valid(issued, auditor_client):
    """Persist, reload, and verify against externally supplied expectations."""
    response = _verify(
        auditor_client,
        issued["certificate_id"],
        {
            "expected_operation_id": issued["operation_id"],
            "expected_target_identity": issued["target_identity"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["overall_status"] == "VALID"
    assert len(body["dimensions"]) == 10
    assert {d["result"] for d in body["dimensions"]} == {"PASS"}
    assert body["cannot_prove"] == []
    assert body["signature_valid"] is True
    assert body["evidence_integrity"] is True
    assert body["signer_trusted"] is True
    assert body["verifier_version"]
    assert body["verified_at"]


def test_without_expectations_the_result_is_inconclusive(issued, auditor_client):
    """No independent expectation means those dimensions cannot be checked."""
    body = _verify(auditor_client, issued["certificate_id"]).json()
    assert body["overall_status"] == "INCONCLUSIVE"
    named = " ".join(body["cannot_prove"])
    assert "OPERATION_CONSISTENCY" in named
    assert "TARGET_CONSISTENCY" in named


def test_wrong_expected_operation_is_invalid(issued, auditor_client):
    body = _verify(
        auditor_client,
        issued["certificate_id"],
        {
            "expected_operation_id": "op_not_this_one",
            "expected_target_identity": issued["target_identity"],
        },
    ).json()
    assert body["overall_status"] == "INVALID"


def test_wrong_expected_target_is_invalid(issued, auditor_client):
    body = _verify(
        auditor_client,
        issued["certificate_id"],
        {
            "expected_operation_id": issued["operation_id"],
            "expected_target_identity": "H:/somewhere/else.txt",
        },
    ).json()
    assert body["overall_status"] == "INVALID"


def test_untrusted_signer_is_not_valid(issued, auditor_client, monkeypatch):
    """Remove the trust anchor; the signature still verifies, trust does not."""
    monkeypatch.delenv(ENV_TRUSTED_SIGNERS, raising=False)
    body = _verify(
        auditor_client,
        issued["certificate_id"],
        {
            "expected_operation_id": issued["operation_id"],
            "expected_target_identity": issued["target_identity"],
        },
    ).json()

    assert body["overall_status"] == "INCONCLUSIVE"
    assert body["signature_valid"] is True
    assert body["signer_trusted"] is not True


def test_modified_evidence_makes_the_certificate_invalid(issued, auditor_client):
    """Tamper with the stored evidence; the recomputed digest stops matching."""
    session_factory = get_session_factory()
    with session_factory() as session:
        repo = CertificateRepository(session)
        row = repo.get_evidence_record(issued["evidence_id"])
        payload = json.loads(row.payload)
        payload["method"] = "COMPLETE_ERASURE"
        row.payload = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        session.commit()

    body = _verify(
        auditor_client,
        issued["certificate_id"],
        {
            "expected_operation_id": issued["operation_id"],
            "expected_target_identity": issued["target_identity"],
        },
    ).json()
    assert body["overall_status"] == "INVALID"
    assert body["evidence_integrity"] is False


# ---------------------------------------------------------------------------
# The client cannot talk the server into a verdict
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "injected",
    [
        {"overall_status": "VALID"},
        {"signer_trusted": True},
        {"evidence_integrity": True},
        {"signature_valid": True},
        {"verification_result": True},
        {"trust_store": "everything"},
        {"actor_id": "someone-else"},
    ],
)
def test_client_cannot_inject_a_verdict(issued, auditor_client, injected):
    """The request schema forbids unknown fields, so none of these reach logic."""
    response = _verify(auditor_client, issued["certificate_id"], injected)
    assert response.status_code == 422


def test_client_cannot_force_valid_by_omitting_everything(issued, auditor_client):
    body = _verify(auditor_client, issued["certificate_id"], {}).json()
    assert body["overall_status"] != "VALID"


def test_no_private_key_is_ever_returned(issued, auditor_client):
    """The response and the certificate resource must carry public material only."""
    private_hex = issued["key_manager"]._private_key.private_bytes_raw().hex()

    verification = _verify(auditor_client, issued["certificate_id"]).text
    assert private_hex not in verification

    fetched = auditor_client.get(f"/api/certificates/{issued['certificate_id']}")
    assert fetched.status_code == 200
    assert private_hex not in fetched.text
    assert "private" not in fetched.json()


# ---------------------------------------------------------------------------
# F-B: limitations are part of the signed payload and must be published
# ---------------------------------------------------------------------------


def test_fetching_a_certificate_returns_its_signed_limitations(issued, auditor_client):
    """A certificate without its limitations reads as a stronger claim.

    `limitations` was already inside the canonical payload the signature covers,
    and was already persisted - it simply was not published. A reader fetching
    the certificate therefore could not see the statements that stop it being
    overclaimed, which is the one thing this product must never allow.
    """
    response = auditor_client.get(f"/api/certificates/{issued['certificate_id']}")
    assert response.status_code == 200, response.text
    body = response.json()

    assert "limitations" in body, "the signed limitations must be published"
    assert isinstance(body["limitations"], list)
    assert body["limitations"], "a certificate signed with limitations must return them"

    published = " ".join(body["limitations"])
    # The limitation the evidence carried.
    assert "no sanitization performed" in published
    # And the issuer's own scope statement, which is the one that stops a reader
    # treating a certificate as proof of things the evidence never established.
    assert "attests only to what the evidence records" in published
    assert "Not established" in published


def test_published_limitations_match_the_signed_payload(issued, auditor_client):
    """What the API returns must be what the signature actually covers."""
    session_factory = get_session_factory()
    with session_factory() as session:
        reloaded = CertificateRepository(session).load_certificate(
            issued["certificate_id"]
        )
    assert reloaded is not None

    body = auditor_client.get(f"/api/certificates/{issued['certificate_id']}").json()

    assert body["limitations"] == list(reloaded.limitations)
    # And the signed payload still carries them, unchanged by publication.
    assert reloaded.signing_payload()["limitations"] == list(reloaded.limitations)


def test_publishing_limitations_did_not_change_the_signature(issued, auditor_client):
    """Adding a response field must not touch canonicalization or signing."""
    session_factory = get_session_factory()
    with session_factory() as session:
        repo = CertificateRepository(session)
        reloaded = repo.load_certificate(issued["certificate_id"])
    assert reloaded is not None

    # The certificate still verifies against its own signer, byte for byte.
    # The public key is passed explicitly - `verify` takes it as an argument
    # rather than reading ambient state, which is what keeps a verifier from
    # accidentally trusting whatever key happens to be configured.
    assert Ed25519SignerVerifier.verify(
        issued["key_manager"].public_key_bytes(),
        reloaded.signing_bytes(),
        bytes.fromhex(reloaded.signature),
    ), "the signature must still cover the unchanged canonical payload"

    # And the end-to-end verdict is unaffected by the new response field.
    result = _verify(
        auditor_client,
        issued["certificate_id"],
        {
            "expected_operation_id": issued["operation_id"],
            "expected_target_identity": issued["target_identity"],
        },
    ).json()
    assert result["overall_status"] == "VALID"
    assert len(result["dimensions"]) == 10


def test_a_client_cannot_supply_limitations(issued, auditor_client):
    """The field is returned from storage, never accepted from a caller."""
    from oblivion.api.schemas.certificate import CertificateVerificationRequest

    assert "limitations" not in CertificateVerificationRequest.model_fields
    # And the verification request forbids unknown fields outright.
    response = _verify(
        auditor_client,
        issued["certificate_id"],
        {"limitations": ["no limits at all"]},
    )
    assert response.status_code == 422
