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


REPO_ROOT = Path(__file__).resolve().parents[1]

#: Scratch area for destructive tests, inside the repository that owns them.
DEFAULT_TEST_ROOT = REPO_ROOT / ".pytest-scratch"


def resolve_destructive_test_root() -> str:
    """Root inside which destructive tests create their scratch directories.

    Resolution order:

    1. ``OBLIVION_TEST_ROOT`` - an explicit dedicated location, for running the
       suite against a purpose-built test volume.
    2. ``<repo>/.pytest-scratch`` - the default. The root belongs to the
       checkout under test, so the suite is self-contained: it needs no
       directory outside the repository and no second checkout.

    Why not the interpreter's temporary directory? On Windows that normally
    lives on the system volume, and ``SafePathValidator`` is built to refuse
    every target there (``is_system_volume``). Keeping the scratch area beside
    the code means that when the repository sits on a non-system volume - the
    normal case for a work checkout - the real volume-serial protection stays
    active for the whole run and the tests exercise the production guard.

    An earlier revision hardcoded a second checkout of this repository as the
    test root, which tied the suite to a directory outside the project and made
    it unrunnable without that directory present.
    """
    configured = os.environ.get("OBLIVION_TEST_ROOT")
    if configured:
        os.makedirs(configured, exist_ok=True)
        return configured
    os.makedirs(DEFAULT_TEST_ROOT, exist_ok=True)
    return str(DEFAULT_TEST_ROOT)


def _on_system_volume(validator: SafePathValidator, path: Path) -> bool:
    """True when ``path`` sits on the volume SafePathValidator protects."""
    if validator.system_volume_serial is None:
        return False
    return validator.get_volume_serial(str(path)) == validator.system_volume_serial


@pytest.fixture
def temp_dir():
    """An isolated scratch directory that destructive tests may operate inside.

    Created fresh per test and removed afterwards, so no test can reach data
    belonging to anyone. The directory is also the only allowed root given to
    the validator below, so containment is enforced by production code.
    """
    with tempfile.TemporaryDirectory(dir=resolve_destructive_test_root()) as td:
        yield Path(td)

@pytest.fixture
def safe_validator(temp_dir):
    """SafePathValidator scoped to ``temp_dir`` and nothing else.

    Containment, reparse-point rejection, ancestor checks and target-identity
    checks all remain exactly as production runs them.

    One conditional relaxation exists for the case where the checkout itself
    sits on the system volume. There the volume-serial branch of
    ``is_system_volume`` would refuse every target and no erasure test could
    run at all, so the serial reference is cleared - a state the validator
    already supports, because it is what non-Windows hosts get. Prefix
    protection for %SystemRoot% and %ProgramFiles% is untouched, so
    ``C:\\Windows`` stays rejected and the tests asserting that still exercise
    real code.

    When the repository lives on a non-system volume (the normal case) nothing
    is relaxed and the full production guard runs. ``OBLIVION_TEST_ROOT`` can
    point at a dedicated non-system volume to guarantee that.
    """
    validator = SafePathValidator(allowed_roots=[str(temp_dir)])
    if _on_system_volume(validator, temp_dir):
        validator.system_volume_serial = None
    return validator

# Admin, Operator, Investigator, Auditor, Viewer role fixtures
# These fixtures create users with specific roles, login, and return auth headers

def authenticate_as_role(safe_validator, temp_dir, role_name):
    """Create a user holding ``role_name`` and return real bearer headers.

    A plain function, not a fixture. The role-client fixtures below used to call
    the fixture directly, which modern pytest refuses ("Fixture called
    directly"), leaving every role client unusable. Authentication here goes
    through the real login endpoint, so the token is genuine and RBAC is
    exercised rather than bypassed.
    """
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
    headers = authenticate_as_role(safe_validator, temp_dir, request.param)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def admin_client(safe_validator, temp_dir):
    """Authenticated admin client."""
    headers = authenticate_as_role(safe_validator, temp_dir, Role.ADMIN)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def operator_client(safe_validator, temp_dir):
    """Authenticated operator client."""
    headers = authenticate_as_role(safe_validator, temp_dir, Role.OPERATOR)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def investigator_client(safe_validator, temp_dir):
    """Authenticated investigator client."""
    headers = authenticate_as_role(safe_validator, temp_dir, Role.INVESTIGATOR)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def auditor_client(safe_validator, temp_dir):
    """Authenticated auditor client."""
    headers = authenticate_as_role(safe_validator, temp_dir, Role.AUDITOR)
    client = TestClient(app)
    client.headers.update(headers)
    return client

@pytest.fixture
def viewer_client(safe_validator, temp_dir):
    """Authenticated viewer client."""
    headers = authenticate_as_role(safe_validator, temp_dir, Role.VIEWER)
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
