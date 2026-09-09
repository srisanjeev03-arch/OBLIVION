import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.api.dependencies import get_safe_validator
from oblivion.core.auth.passwords import hash_password
from oblivion.core.auth.rbac import Role
from oblivion.core.safety.paths import SafePathValidator
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.user_repo import UserRepository


@pytest.fixture
def temp_dir():
    # C: is the protected system volume.  Destructive integration tests must
    # use the dedicated workspace volume instead.
    test_root = "H:\\OBLIVION"
    with tempfile.TemporaryDirectory(dir=test_root) as td:
        yield Path(td)

@pytest.fixture
def safe_validator(temp_dir):
    validator = SafePathValidator(allowed_roots=[str(temp_dir)])
    validator.system_volume_serial = "0x00000000"
    return validator

# Admin, Operator, Investigator, Auditor, Viewer role fixtures
# These fixtures create users with specific roles, login, and return auth headers

@pytest.fixture
def test_user_role(safe_validator, temp_dir, request):
    """Create a user with a specific role and return auth headers.

    Usage: parametrize with role name, e.g. pytest.param(Role.ADMIN, id='admin')
    """

    role_name = request.param
    init_db()
    session_factory = get_session_factory()
    with session_factory() as session:
        repo = UserRepository(session)
        repo.bootstrap_admin_if_needed()
        user = repo.create_user(
            username=f"test_{role_name.lower()}_{temp_dir.name}",
            password_hash=hash_password("testpass123"),
            role_names=[role_name],
        )
        session.commit()

    # Login to get token
    client = TestClient(app)
    app.dependency_overrides[get_safe_validator] = lambda: safe_validator
    login_resp = client.post("/api/auth/login", json={
        "username": user.username,
        "password": "testpass123",
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # Clear overrides
    app.dependency_overrides.clear()
    return headers

@pytest.fixture(
    params=[
        Role.ADMIN,
        Role.INVESTIGATOR,
        Role.OPERATOR,
        Role.AUDITOR,
        Role.VIEWER,
    ],
    ids=["admin", "investigator", "operator", "auditor", "viewer"],
)
def authenticated_client(request, safe_validator, temp_dir):
    """Parametrized fixture returning auth headers for each role."""
    headers = test_user_role(safe_validator, temp_dir, request)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def admin_client(safe_validator, temp_dir):
    """Authenticated admin client."""
    headers = test_user_role(safe_validator, temp_dir, Role.ADMIN)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def operator_client(safe_validator, temp_dir):
    """Authenticated operator client."""
    headers = test_user_role(safe_validator, temp_dir, Role.OPERATOR)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def investigator_client(safe_validator, temp_dir):
    """Authenticated investigator client."""
    headers = test_user_role(safe_validator, temp_dir, Role.INVESTIGATOR)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def auditor_client(safe_validator, temp_dir):
    """Authenticated auditor client."""
    headers = test_user_role(safe_validator, temp_dir, Role.AUDITOR)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def viewer_client(safe_validator, temp_dir):
    """Authenticated viewer client."""
    headers = test_user_role(safe_validator, temp_dir, Role.VIEWER)
    client = TestClient(app)
    client.headers.update(headers)
    return client

# Keep the old client fixture for backward compatibility but it now requires auth setup
@pytest.fixture
def client(safe_validator, temp_dir):
    init_db()
    app.dependency_overrides[get_safe_validator] = lambda: safe_validator
    os.environ["OBLIVION_ALLOWED_ROOTS"] = str(temp_dir)
    os.environ["OBLIVION_VAULT_DIR"] = str(temp_dir / "vault")
    session_factory = get_session_factory()
    username = f"legacy_admin_{temp_dir.name}"
    with session_factory() as session:
        repo = UserRepository(session)
        repo.create_user(username, hash_password("LegacyTestPass!"), [Role.ADMIN.value])
        session.commit()
    test_client = TestClient(app)
    login = test_client.post("/api/auth/login", json={"username": username, "password": "LegacyTestPass!"})
    assert login.status_code == 200
    test_client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
    yield test_client
    app.dependency_overrides.clear()
