"""API contract tests for Phase 23 certificate verification."""
from uuid import uuid4

from fastapi.testclient import TestClient

from oblivion.api.app import app
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.core.auth.passwords import hash_password
from oblivion.core.auth.rbac import Role
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.certificate_repo import CertificateRepository
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.persistence.repositories.user_repo import UserRepository


def test_verification_api_returns_all_dimensions_and_never_promotes_missing_evidence():
    init_db()
    suffix = uuid4().hex[:12]
    username = f"phase23_api_{suffix}"
    operation_id = f"op_phase23_{suffix}"
    certificate_id = f"cert_phase23_{suffix}"
    signer = Ed25519SignerVerifier.generate()
    digest = "a" * 64
    with get_session_factory()() as session:
        users = UserRepository(session)
        users.create_user(username, hash_password("Phase23TestPass!"), [Role.ADMIN.value])
        operations = OperationRepository(session)
        target_id = f"target_phase23_{suffix}"
        operations.create_target(target_id, "C:/OblivionDemo/example.txt", "C:/OblivionDemo/example.txt", "file")
        operations.create_operation(operation_id, target_id, "SELECTIVE_PERMANENT")
        CertificateRepository(session).create_certificate(
            certificate_id, operation_id, digest, signer.get_public_key_bytes().hex(), signer.sign(digest.encode("ascii")).hex(), key_id="phase23-signer"
        )
        session.commit()

    client = TestClient(app)
    login = client.post("/api/auth/login", json={"username": username, "password": "Phase23TestPass!"})
    assert login.status_code == 200
    response = client.post(f"/api/certificates/{certificate_id}/verify", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "INVALID"
    assert len(body["dimensions"]) == 10
    assert {item["result"] for item in body["dimensions"]} <= {"PASS", "FAIL", "NOT_CHECKED", "INCONCLUSIVE"}
    dimensions = {item["dimension"]: item["result"] for item in body["dimensions"]}
    assert dimensions["SIGNATURE_VALIDITY"] == "PASS"
    assert dimensions["EVIDENCE_AVAILABILITY"] == "FAIL"
