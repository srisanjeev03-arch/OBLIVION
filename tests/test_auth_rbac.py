"""Comprehensive test suite for Phase 19: Authentication, RBAC, and Separation of Duties."""
import datetime

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.core.auth.passwords import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from oblivion.core.auth.rbac import (
    Permission,
    Role,
    get_role_permissions,
    has_permission,
)
from oblivion.core.auth.sod import (
    SoDViolationError,
    validate_approval,
    validate_verification,
)
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.persistence.repositories.user_repo import UserRepository


@pytest.fixture(autouse=True)
def setup_test_auth_db():
    init_db()


@pytest.fixture
def auth_client():
    return TestClient(app)


class TestArgon2idPasswordHashing:
    def test_hash_and_verify_success(self):
        password = "ComplexSecurePassword_2026!#"
        hashed = hash_password(password)
        assert hashed.startswith("$argon2id$v=19$")
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password_fails(self):
        hashed = hash_password("CorrectPassword123")
        assert verify_password("WrongPassword123", hashed) is False

    def test_verify_malformed_hash_safe(self):
        assert verify_password("password", "not_a_valid_argon2_hash") is False
        assert verify_password("password", None) is False
        assert verify_password("", "$argon2id$v=19$m=65536,t=3,p=4$salt$key") is False


class TestSessionTokenCryptography:
    def test_opaque_session_token_generation_and_hashing(self):
        token = generate_session_token()
        assert len(token) >= 32
        h1 = hash_session_token(token)
        h2 = hash_session_token(token)
        assert len(h1) == 64
        assert h1 == h2
        # Different tokens produce distinct hashes
        token2 = generate_session_token()
        assert hash_session_token(token2) != h1


class TestFiveRolePermissionsMatrix:
    def test_admin_has_all_permissions(self):
        perms = get_role_permissions([Role.ADMIN.value])
        for p in Permission:
            assert p.value in perms
            assert has_permission([Role.ADMIN.value], p.value) is True

    def test_investigator_permissions(self):
        perms = get_role_permissions([Role.INVESTIGATOR.value])
        assert Permission.CASE_CREATE.value in perms
        assert Permission.FILE_ERASURE_REQUEST.value in perms
        assert Permission.RECOVERY_EXECUTE.value in perms
        # Cannot execute erasure or approve operations
        assert Permission.FILE_ERASURE_EXECUTE.value not in perms
        assert Permission.OPERATION_APPROVE.value not in perms
        assert Permission.USER_MANAGE.value not in perms

    def test_operator_permissions(self):
        perms = get_role_permissions([Role.OPERATOR.value])
        assert Permission.FILE_ERASURE_EXECUTE.value in perms
        assert Permission.OPERATION_EXECUTE.value in perms
        # Cannot approve or verify
        assert Permission.OPERATION_APPROVE.value not in perms
        assert Permission.OPERATION_VERIFY.value not in perms
        assert Permission.USER_MANAGE.value not in perms

    def test_auditor_permissions(self):
        perms = get_role_permissions([Role.AUDITOR.value])
        assert Permission.AUDIT_VIEW.value in perms
        assert Permission.AUDIT_VERIFY.value in perms
        assert Permission.EVIDENCE_VERIFY.value in perms
        # Cannot execute or approve
        assert Permission.FILE_ERASURE_EXECUTE.value not in perms
        assert Permission.OPERATION_APPROVE.value not in perms
        assert Permission.USER_MANAGE.value not in perms

    def test_viewer_permissions(self):
        perms = get_role_permissions([Role.VIEWER.value])
        assert Permission.CASE_VIEW.value in perms
        assert Permission.EVIDENCE_VIEW.value in perms
        assert Permission.OPERATION_VIEW.value in perms
        # Read-only: no modification or execution
        assert Permission.CASE_CREATE.value not in perms
        assert Permission.FILE_ERASURE_EXECUTE.value not in perms
        assert Permission.AUDIT_VERIFY.value not in perms
        assert Permission.USER_MANAGE.value not in perms


class TestSeparationOfDuties:
    def test_requester_cannot_approve_own_request(self):
        # When requester == approver, must raise SoDViolationError
        with pytest.raises(SoDViolationError) as exc_info:
            validate_approval(requested_by="user_investigator_1", approving_actor_id="user_investigator_1")
        assert "cannot approve their own operation" in str(exc_info.value)

    def test_distinct_approver_succeeds(self):
        # Distinct actors pass SoD check
        validate_approval(requested_by="user_investigator_1", approving_actor_id="admin_approver_1")

    def test_executor_cannot_verify_own_execution(self):
        # When executor == verifier, must raise SoDViolationError
        with pytest.raises(SoDViolationError) as exc_info:
            validate_verification(executed_by="user_operator_1", verifying_actor_id="user_operator_1")
        assert "cannot verify their own operation" in str(exc_info.value)

    def test_distinct_verifier_succeeds(self):
        validate_verification(executed_by="user_operator_1", verifying_actor_id="user_auditor_1")


class TestAuthenticationEndpoints:
    def test_login_success_and_me_endpoint(self, auth_client):
        session_factory = get_session_factory()
        password = "OperatorPassword_123"
        unique_username = f"op_user_test_{datetime.datetime.now().timestamp()}"
        with session_factory() as session:
            repo = UserRepository(session)
            repo.create_user(
                username=unique_username,
                password_hash=hash_password(password),
                role_names=[Role.OPERATOR.value],
            )
            session.commit()

        # 1. Login
        login_resp = auth_client.post("/api/auth/login", json={
            "username": unique_username,
            "password": password,
        })
        assert login_resp.status_code == 200
        data = login_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        token = data["access_token"]
        assert "password" not in login_resp.text
        assert "password_hash" not in login_resp.text

        # 2. Get /api/auth/me
        me_resp = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["username"] == unique_username
        assert Role.OPERATOR.value in me_data["roles"]
        assert Permission.OPERATION_EXECUTE.value in me_data["permissions"]

        # 3. Logout
        logout_resp = auth_client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_resp.status_code == 200

        # 4. Subsequent access with revoked token returns 401
        revoked_resp = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert revoked_resp.status_code == 401
        assert revoked_resp.json()["error_code"] == "SESSION_INVALID"

    def test_login_wrong_password_returns_401(self, auth_client):
        resp = auth_client.post("/api/auth/login", json={
            "username": "nonexistent_or_wrong",
            "password": "wrong_password",
        })
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_CREDENTIALS"

    def test_unauthenticated_request_returns_401(self, auth_client):
        resp = auth_client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "UNAUTHENTICATED"


class TestAdminBootstrapSafety:
    def test_safe_admin_bootstrap_never_admin_admin(self):
        session_factory = get_session_factory()
        with session_factory() as session:
            repo = UserRepository(session)
            # Ensure bootstrap does not use default admin/admin
            admin = repo.bootstrap_admin_if_needed()
            if admin:
                assert verify_password("admin", admin.password_hash) is False


class TestSoDInOperationWorkflow:
    def test_spoofed_approver_identity_is_ignored(self, admin_client, temp_dir):
        # Create operation requested by 'inv_user_1'
        session_factory = get_session_factory()
        op_id = f"op_sod_{datetime.datetime.now().timestamp()}"
        tgt_id = f"tgt_sod_{datetime.datetime.now().timestamp()}"
        with session_factory() as session:
            repo = OperationRepository(session)
            repo.create_target(tgt_id, str(temp_dir), str(temp_dir), "file")
            repo.create_operation(
                operation_id=op_id,
                target_id=tgt_id,
                mode="SELECTIVE_PERMANENT",
                requested_by="inv_user_1",
                state="CREATED",
            )
            session.commit()

        # The approver is derived from the authenticated session, never from the
        # request. This previously passed ?approver_id=inv_user_1, a contract in
        # which the caller named its own actor identity - exactly what must not
        # be supported. The query parameter below is deliberately retained and
        # deliberately ignored: it proves that supplying it changes nothing.
        resp = admin_client.post(
            f"/api/operations/{op_id}/approve?approver_id=inv_user_1"
        )
        # The authenticated admin is not the requester, so separation of duties
        # permits the approval and the spoofed identity has no effect.
        assert resp.status_code == 200
        assert resp.json()["state"] == "READY"

    def test_requester_cannot_approve_their_own_operation(self, admin_client, temp_dir):
        """Separation of duties, using the server-derived actor identity."""
        session_factory = get_session_factory()
        op_id = f"op_sod_self_{datetime.datetime.now().timestamp()}"
        tgt_id = f"tgt_sod_self_{datetime.datetime.now().timestamp()}"

        # Discover who the authenticated caller actually is.
        me = admin_client.get("/api/auth/me").json()

        with session_factory() as session:
            repo = OperationRepository(session)
            repo.create_target(tgt_id, str(temp_dir), str(temp_dir), "file")
            repo.create_operation(
                operation_id=op_id,
                target_id=tgt_id,
                mode="SELECTIVE_PERMANENT",
                requested_by=me["id"],
                state="PENDING_APPROVAL",
            )
            session.commit()

        resp = admin_client.post(f"/api/operations/{op_id}/approve")
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"
