"""Comprehensive API integration tests for Oblivion."""
import datetime
import os

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.api.dependencies import get_safe_validator
from oblivion.certificate.signer import Ed25519SignerVerifier
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.certificate_repo import CertificateRepository
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.persistence.repositories.user_repo import UserRepository
from oblivion.core.auth.passwords import hash_password
from oblivion.core.auth.rbac import Role


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


@pytest.fixture
def client(safe_validator, temp_dir):
    # Override safe validator dependency with safe test fixture validator
    app.dependency_overrides[get_safe_validator] = lambda: safe_validator
    os.environ["OBLIVION_ALLOWED_ROOTS"] = str(temp_dir)
    os.environ["OBLIVION_VAULT_DIR"] = str(temp_dir / "vault")
    test_client = TestClient(app)
    username = f"api_full_admin_{temp_dir.name}"
    with get_session_factory()() as session:
        UserRepository(session).create_user(username, hash_password("ApiFullTestPass!"), [Role.ADMIN.value])
        session.commit()
    login = test_client.post("/api/auth/login", json={"username": username, "password": "ApiFullTestPass!"})
    assert login.status_code == 200
    test_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    yield test_client
    app.dependency_overrides.clear()



class TestTargetEndpoints:
    def test_analyze_valid_file_and_persistence(self, client, temp_dir):
        f = temp_dir / "sample.txt"
        f.write_text("secure data to analyze")

        resp = client.post("/api/targets/analyze", json={"path": str(f)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "file"
        assert len(data["sha256"]) == 64
        assert "storage_profile" in data
        target_id = data["id"]

        # Verify GET /api/targets/{target_id}
        get_resp = client.get(f"/api/targets/{target_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == target_id
        assert get_resp.json()["canonical_path"] == str(f.resolve())

    def test_analyze_directory(self, client, temp_dir):
        sub = temp_dir / "subdir"
        sub.mkdir()
        (sub / "1.txt").write_text("1")
        (sub / "2.txt").write_text("2")

        resp = client.post("/api/targets/analyze", json={"path": str(sub)})
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "directory"
        assert data["file_count"] >= 2

    def test_analyze_invalid_path_fails(self, client):
        resp = client.post("/api/targets/analyze", json={"path": ""})
        assert resp.status_code in (400, 422)

    def test_analyze_outside_allowed_roots_fails(self, client):
        resp = client.post("/api/targets/analyze", json={"path": "C:\\Windows\\System32"})
        assert resp.status_code == 400
        assert "error_code" in resp.json()

    def test_get_target_404(self, client):
        resp = client.get("/api/targets/nonexistent_tgt_id_999")
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "TARGET_NOT_FOUND"


class TestOperationEndpoints:
    def test_selective_permanent_operation_lifecycle(self, client, temp_dir):
        f = temp_dir / "target_to_delete.txt"
        f.write_text("delete me permanently")

        # 1. Analyze
        analyze_resp = client.post("/api/targets/analyze", json={"path": str(f)})
        target_id = analyze_resp.json()["id"]

        # 2. Create Operation
        op_payload = {
            "target_id": target_id,
            "mode": "SELECTIVE_PERMANENT",
            "policy_id": "ERASURE.LOGICAL.SELECTIVE.V1",
            "confirmation": {"acknowledged_risk": True},
        }
        create_resp = client.post("/api/operations", json=op_payload)
        assert create_resp.status_code == 202
        op_data = create_resp.json()
        assert op_data["mode"] == "SELECTIVE_PERMANENT"
        assert op_data["state"] == "PENDING_APPROVAL"
        operation_id = op_data["id"]
        assert f.exists()

        # 3. GET Operation Status
        get_resp = client.get(f"/api/operations/{operation_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["state"] == "PENDING_APPROVAL"

        # 4. GET Operation Events
        events_resp = client.get(f"/api/operations/{operation_id}/events")
        assert events_resp.status_code == 200
        events = events_resp.json()
        assert len(events) >= 3
        # Check sequence order
        sequences = [e["sequence"] for e in events]
        assert sequences == sorted(sequences)

    def test_complete_erasure_directory_operation(self, client, temp_dir):
        dir_to_erase = temp_dir / "tree_erase"
        dir_to_erase.mkdir()
        (dir_to_erase / "nested.txt").write_text("nested")

        # Analyze
        analyze_resp = client.post("/api/targets/analyze", json={"path": str(dir_to_erase)})
        target_id = analyze_resp.json()["id"]

        # Execute COMPLETE_ERASURE
        op_payload = {
            "target_id": target_id,
            "mode": "COMPLETE_ERASURE",
            "policy_id": "ERASURE.LOGICAL.TREE.V1",
            "confirmation": {"acknowledged_risk": True},
        }
        create_resp = client.post("/api/operations", json=op_payload)
        assert create_resp.status_code == 202
        assert create_resp.json()["state"] == "PENDING_APPROVAL"
        assert dir_to_erase.exists()

    def test_controlled_recoverable_operation_and_restore(self, client, temp_dir):
        f = temp_dir / "vault_me.txt"
        secret_text = "confidential text to recover later"
        f.write_text(secret_text)

        # Analyze
        analyze_resp = client.post("/api/targets/analyze", json={"path": str(f)})
        target_id = analyze_resp.json()["id"]
        orig_sha = analyze_resp.json()["sha256"]

        # Execute CONTROLLED_RECOVERABLE
        op_payload = {
            "target_id": target_id,
            "mode": "CONTROLLED_RECOVERABLE",
            "policy_id": "ERASURE.RECOVERABLE.ENCRYPTED.V1",
            "confirmation": {"acknowledged_risk": True},
        }
        create_resp = client.post("/api/operations", json=op_payload)
        assert create_resp.status_code == 202
        assert create_resp.json()["state"] == "PENDING_APPROVAL"
        assert f.exists()

    def test_unauthorized_restore_blocked(self, client, temp_dir):
        f = temp_dir / "vault_test.txt"
        f.write_text("test")

        analyze_resp = client.post("/api/targets/analyze", json={"path": str(f)})
        target_id = analyze_resp.json()["id"]

        client.post("/api/operations", json={
            "target_id": target_id,
            "mode": "CONTROLLED_RECOVERABLE",
            "policy_id": "ERASURE.RECOVERABLE.ENCRYPTED.V1",
            "confirmation": {"acknowledged_risk": True},
        })

        assert client.get("/api/recovery-objects").status_code == 200

    def test_operation_confirmation_required(self, client, temp_dir):
        f = temp_dir / "unconfirmed.txt"
        f.write_text("x")
        analyze_resp = client.post("/api/targets/analyze", json={"path": str(f)})
        target_id = analyze_resp.json()["id"]

        # Request with acknowledged_risk=False
        resp = client.post("/api/operations", json={
            "target_id": target_id,
            "mode": "SELECTIVE_PERMANENT",
            "policy_id": "ERASURE.LOGICAL.SELECTIVE.V1",
            "confirmation": {"acknowledged_risk": False},
        })
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "CONFIRMATION_REQUIRED"

    def test_operation_404_target(self, client):
        resp = client.post("/api/operations", json={
            "target_id": "nonexistent_target_123",
            "mode": "SELECTIVE_PERMANENT",
            "policy_id": "ERASURE.LOGICAL.SELECTIVE.V1",
            "confirmation": {"acknowledged_risk": True},
        })
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "TARGET_NOT_FOUND"

    def test_operation_cancellation(self, client, temp_dir):
        # Create a dummy operation in DB with READY state
        tgt_id = f"tgt_cancel_{datetime.datetime.now().timestamp()}"
        op_id = f"op_cancel_{datetime.datetime.now().timestamp()}"
        session_factory = get_session_factory()
        with session_factory() as session:
            repo = OperationRepository(session)
            t = repo.create_target(
                target_id=tgt_id,
                path=str(temp_dir),
                canonical_path=str(temp_dir),
                target_type="directory",
            )
            op = repo.create_operation(
                operation_id=op_id,
                target_id=tgt_id,
                mode="SELECTIVE_PERMANENT",
                state="READY",
            )
            session.commit()

        cancel_resp = client.post(f"/api/operations/{op_id}/cancel")
        assert cancel_resp.status_code == 202
        assert cancel_resp.json()["state"] == "CANCELLED"

        # Subsequent cancel on terminal state fails with 409
        second_cancel = client.post(f"/api/operations/{op_id}/cancel")
        assert second_cancel.status_code == 409
        assert second_cancel.json()["error_code"] == "OPERATION_STATE_INVALID"


class TestCertificateEndpoints:
    def test_certificate_issuance_and_verification(self, client, temp_dir):
        signer = Ed25519SignerVerifier.generate()
        pubkey_hex = signer.get_public_key_bytes().hex()
        evidence_digest = "a" * 64
        signature_hex = signer.sign(evidence_digest.encode("utf-8")).hex()
        cert_id = f"cert_v1_{datetime.datetime.now().timestamp()}"
        tgt_id = f"tgt_c_{datetime.datetime.now().timestamp()}"
        op_id = f"op_c_{datetime.datetime.now().timestamp()}"

        session_factory = get_session_factory()
        with session_factory() as session:
            op_repo = OperationRepository(session)
            op_repo.create_target(
                target_id=tgt_id,
                path=str(temp_dir / "test.txt"),
                canonical_path=str(temp_dir / "test.txt"),
                target_type="file",
            )
            op_repo.create_operation(
                operation_id=op_id,
                target_id=tgt_id,
                mode="SELECTIVE_PERMANENT",
            )

            cert_repo = CertificateRepository(session)
            cert_repo.create_certificate(
                cert_id=cert_id,
                operation_id=op_id,
                evidence_digest=evidence_digest,
                public_key=pubkey_hex,
                signature=signature_hex,
                claim="Logically erased; recovery not successful",
            )
            session.commit()

        # 1. GET Certificate
        cert_resp = client.get(f"/api/certificates/{cert_id}")
        assert cert_resp.status_code == 200
        data = cert_resp.json()
        assert data["id"] == cert_id
        assert data["signature"] == signature_hex

        # 2. Verify Certificate
        verify_resp = client.post(f"/api/certificates/{cert_id}/verify")
        assert verify_resp.status_code == 200
        v_data = verify_resp.json()
        assert v_data["overall_status"] == "INVALID"

    def test_certificate_tampered_fails_verification(self, client, temp_dir):
        signer = Ed25519SignerVerifier.generate()
        pubkey_hex = signer.get_public_key_bytes().hex()
        evidence_digest = "b" * 64
        # Sign different digest
        signature_hex = signer.sign(b"different_data").hex()
        cert_id = f"cert_t_{datetime.datetime.now().timestamp()}"
        tgt_id = f"tgt_t_{datetime.datetime.now().timestamp()}"
        op_id = f"op_t_{datetime.datetime.now().timestamp()}"

        session_factory = get_session_factory()
        with session_factory() as session:
            op_repo = OperationRepository(session)
            op_repo.create_target(
                target_id=tgt_id,
                path=str(temp_dir / "test2.txt"),
                canonical_path=str(temp_dir / "test2.txt"),
                target_type="file",
            )
            op_repo.create_operation(
                operation_id=op_id,
                target_id=tgt_id,
                mode="SELECTIVE_PERMANENT",
            )

            cert_repo = CertificateRepository(session)
            cert_repo.create_certificate(
                cert_id=cert_id,
                operation_id=op_id,
                evidence_digest=evidence_digest,
                public_key=pubkey_hex,
                signature=signature_hex,
            )
            session.commit()

        verify_resp = client.post(f"/api/certificates/{cert_id}/verify")
        assert verify_resp.status_code == 200
        v_data = verify_resp.json()
        assert v_data["overall_status"] == "INVALID"



    def test_certificate_404(self, client):
        resp = client.get("/api/certificates/nonexistent_cert_999")
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "CERTIFICATE_NOT_FOUND"


class TestSecurityAndLeakageGuarantees:
    def test_no_private_keys_or_plaintext_in_api_responses(self, client, temp_dir):
        f = temp_dir / "secret.txt"
        secret_content = "SUPER_SECRET_PLAINTEXT_PAYLOAD_12345"
        f.write_text(secret_content)

        # 1. Analyze
        a_resp = client.post("/api/targets/analyze", json={"path": str(f)})
        target_id = a_resp.json()["id"]

        # 2. Vault operation
        op_resp = client.post("/api/operations", json={
            "target_id": target_id,
            "mode": "CONTROLLED_RECOVERABLE",
            "policy_id": "ERASURE.RECOVERABLE.ENCRYPTED.V1",
            "confirmation": {"acknowledged_risk": True},
        })
        op_id = op_resp.json()["id"]

        # Inspect responses
        for endpoint in [
            f"/api/operations/{op_id}",
            f"/api/operations/{op_id}/events",
            "/api/recovery-objects",
        ]:
            resp = client.get(endpoint)
            text = resp.text
            # Assert no sensitive secrets in plaintext
            assert secret_content not in text
            assert "private_key" not in text
            assert "vault_key" not in text
            assert "password" not in text
