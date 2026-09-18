"""No API route performs a destructive or restoring filesystem mutation itself.

`/execute` and recovery restore used to run the erasure engine inside the API
process. Both now send a structured, authenticated request to the privileged
service, which re-validates everything and performs the mutation. These tests
drive the real routes with the real service behind the in-process transport, and
inject faults only at that transport.

The in-process transport is not an isolation boundary - it says so through
``isolated`` - but it runs exactly the code the named-pipe host runs, so what is
proven here about validation, refusal and recording holds for both.
"""

from __future__ import annotations

import hashlib
import inspect
import secrets
import traceback
import uuid
from pathlib import Path

import pytest

from oblivion.api import dependencies as api_dependencies
from oblivion.api.routes import operations as operations_route
from oblivion.api.routes import pipeline as pipeline_route
from oblivion.api.routes import recovery as recovery_route
from oblivion.core.audit import AuditEventType, AuditLog, AuditOutcome, AuditQuery
from oblivion.core.erasure import engine as engine_module
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import State
from oblivion.persistence.database import get_session_factory
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged import (
    InProcessTransport,
    PrivilegedClient,
    PrivilegedOperation,
    RequestAuthenticator,
    ResponseStatus,
    ServiceUnavailableError,
    build_service_from_env,
)
from tests.test_api_pipeline import create_operation
from tests.test_target_identity_binding import (  # noqa: F401 - autouse fixture
    analyze,
    approve,
    approved_operation,
    configured_backend,
    write_target,
)

RECOVERABLE_POLICY = "ERASURE.RECOVERABLE.ENCRYPTED.V1"
DESTRUCTIVE = {"delete_file", "delete_tree", "prepare_recovery_object"}


@pytest.fixture(autouse=True)
def vault_env(monkeypatch, temp_dir):
    """One vault, resolved identically by the API and the privileged service."""
    vault = temp_dir / "vault"
    monkeypatch.setenv("OBLIVION_VAULT_ROOT", str(vault))
    monkeypatch.delenv("OBLIVION_VAULT_DIR", raising=False)
    return vault


def use_transport(monkeypatch, transport_cls):
    monkeypatch.setattr(api_dependencies, "InProcessTransport", transport_cls)


class Recording(InProcessTransport):
    sent: list[dict] = []

    def exchange(self, envelope):
        type(self).sent.append(envelope["request"])
        return super().exchange(envelope)


def recording(monkeypatch) -> type[Recording]:
    cls = type("RecordingTransport", (Recording,), {"sent": []})
    use_transport(monkeypatch, cls)
    return cls


def events(operation_id: str):
    with get_session_factory()() as session:
        return AuditLog(session).query(AuditQuery(operation_id=operation_id, limit=500))


def kinds(operation_id: str) -> list[str]:
    return [r.event_type.value for r in events(operation_id)]


def restore_events(destination: Path):
    with get_session_factory()() as session:
        rows = AuditLog(session).query(AuditQuery(limit=100_000))
    return [r for r in rows if r.target_identity == str(destination)]


def state_of(operation_id: str) -> str:
    with get_session_factory()() as session:
        return OperationRepository(session).get_operation(operation_id).state


def chain_intact() -> bool:
    with get_session_factory()() as session:
        return AuditLog(session).verify().intact


# ---------------------------------------------------------------------------
# No route carries a mutation of its own
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", [operations_route, recovery_route, pipeline_route])
def test_no_route_module_can_mutate_the_filesystem_itself(module):
    source = inspect.getsource(module)
    for construct in (
        "ErasureEngine",
        "execute_operation(",
        "restore_recovery_object(object_id",
        "verify_and_decrypt",
        ".store(",
        "shutil",
        "os.remove",
        "os.unlink",
        "os.replace",
        ".unlink(",
        "rmtree",
        "get_vault_key",
    ):
        assert construct not in source, f"{module.__name__} contains {construct!r}"


@pytest.fixture
def engine_callers(monkeypatch):
    """Records which module called each destructive or restoring engine method."""
    callers: list[str] = []

    def spy(name):
        original = getattr(engine_module.ErasureEngine, name)

        def wrapper(self, *args, **kwargs):
            frames = [Path(f.filename).as_posix() for f in traceback.extract_stack()[:-1]]
            callers.append(next(f for f in reversed(frames) if "/oblivion/" in f))
            return original(self, *args, **kwargs)

        monkeypatch.setattr(engine_module.ErasureEngine, name, wrapper)

    spy("execute_operation")
    spy("restore_recovery_object")
    return callers


# ---------------------------------------------------------------------------
# /execute
# ---------------------------------------------------------------------------


def test_execute_completes_through_the_privileged_service(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch, engine_callers
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    transport = recording(monkeypatch)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "COMPLETED"
    assert not path.exists()
    assert state_of(operation_id) == "COMPLETED"

    sent = [r for r in transport.sent if r["operation"] in DESTRUCTIVE]
    assert len(sent) == 1 and sent[0]["operation"] == "delete_file"
    assert sent[0]["expected_volume_serial"] and sent[0]["expected_file_id"]
    assert engine_callers and all(c.endswith("oblivion/privileged/service.py") for c in engine_callers)

    recorded = kinds(operation_id)
    assert recorded.count("OPERATION_DISPATCH_STARTED") == 1
    executed = [r for r in events(operation_id) if r.event_type is AuditEventType.OPERATION_EXECUTED]
    assert len(executed) == 1 and executed[0].outcome is AuditOutcome.SUCCEEDED
    assert executed[0].safe_metadata["privileged_operation"] == "delete_file"
    assert chain_intact()


def test_execute_no_longer_needs_the_vault_key_for_deletion(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    monkeypatch.delenv("OBLIVION_VAULT_KEY", raising=False)
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 200, response.text
    assert not path.exists()


def test_the_service_enforces_identity_even_if_the_api_check_is_bypassed(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    """A compromised API skips its own identity check; the service still refuses."""
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    path.unlink()
    path.write_text("substituted after approval", encoding="utf-8")
    monkeypatch.setattr(SafePathValidator, "revalidate_handle", lambda *a, **k: True)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "FAILED"
    assert body["error"]["code"] == "PRIVILEGED_REFUSED"
    assert path.read_text(encoding="utf-8") == "substituted after approval"
    recorded = kinds(operation_id)
    assert "OPERATION_EXECUTED" not in recorded
    refused = [
        r
        for r in events(operation_id)
        if r.event_type is AuditEventType.OPERATION_EXECUTION_REFUSED
    ]
    assert refused and refused[-1].safe_metadata["error_code"] == "PRIVILEGED_REFUSED"


def test_execute_with_an_unreachable_service_fails_without_sending(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    class Unreachable(InProcessTransport):
        def exchange(self, envelope):
            if envelope["request"]["operation"] in DESTRUCTIVE:
                raise ServiceUnavailableError("pipe not available")
            return super().exchange(envelope)

    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    use_transport(monkeypatch, Unreachable)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "FAILED"
    assert response.json()["error"]["code"] == "PRIVILEGED_SERVICE_UNAVAILABLE"
    assert path.exists()
    executed = [r for r in events(operation_id) if r.event_type is AuditEventType.OPERATION_EXECUTED]
    assert len(executed) == 1 and executed[0].outcome is AuditOutcome.FAILED
    assert "OPERATION_OUTCOME_UNESTABLISHED" not in kinds(operation_id)


def test_execute_with_a_rejected_reply_requires_reconciliation(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    class BadMac(InProcessTransport):
        def exchange(self, envelope):
            reply = super().exchange(envelope)
            if envelope["request"]["operation"] in DESTRUCTIVE:
                reply = dict(reply, mac="00" * 32)
            return reply

    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    use_transport(monkeypatch, BadMac)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 502, response.text
    assert response.json()["error_code"] == "OPERATION_OUTCOME_UNESTABLISHED"
    assert response.json()["details"]["reason_code"] == "PRIVILEGED_RESPONSE_REJECTED"
    assert not path.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name
    recorded = kinds(operation_id)
    assert "OPERATION_EXECUTED" not in recorded
    assert recorded.count("OPERATION_OUTCOME_UNESTABLISHED") == 1


class HandlerFaultAfterDeleting(InProcessTransport):
    """The real service deletes, then its handler raises: an authentic FAILED
    response that says the work may have happened."""

    def __init__(self, service):
        super().__init__(service)
        real = service._handlers[PrivilegedOperation.DELETE_FILE]

        def delete_then_fail(request, outcome):
            real(request, outcome)
            raise RuntimeError("handler fault after the unlink")

        service._handlers[PrivilegedOperation.DELETE_FILE] = delete_then_fail


def test_execute_treats_an_authentic_uncertain_failure_as_reconciliation(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    use_transport(monkeypatch, HandlerFaultAfterDeleting)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 502, response.text
    assert response.json()["details"]["reason_code"] == "PRIVILEGED_OUTCOME_UNCERTAIN"
    assert not path.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name


def test_the_pipeline_treats_an_authentic_uncertain_failure_as_reconciliation(
    operator_client, temp_dir, monkeypatch
):
    target = temp_dir / "pipeline-uncertain.txt"
    target.write_text("payload")
    operation_id = create_operation(target)
    use_transport(monkeypatch, HandlerFaultAfterDeleting)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 502, response.text
    assert response.json()["details"]["reason_code"] == "PRIVILEGED_OUTCOME_UNCERTAIN"
    assert not target.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name
    assert "PIPELINE_CONCLUDED" not in kinds(operation_id)


def request_recoverable(investigator_client, admin_client, path):
    target_id = analyze(investigator_client, path)
    response = investigator_client.post(
        "/api/operations",
        json={
            "target_id": target_id,
            "mode": "CONTROLLED_RECOVERABLE",
            "policy_id": RECOVERABLE_POLICY,
            "confirmation": {"acknowledged_risk": True},
        },
    )
    assert response.status_code == 202, response.text
    operation_id = response.json()["id"]
    approve(admin_client, operation_id)
    return operation_id


def test_execute_without_a_service_vault_reports_it_and_keeps_the_file(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    monkeypatch.delenv("OBLIVION_VAULT_KEY", raising=False)
    path = write_target(temp_dir)
    operation_id = request_recoverable(investigator_client, admin_client, path)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "FAILED"
    assert response.json()["error"]["code"] == "VAULT_UNAVAILABLE"
    assert path.exists()


# ---------------------------------------------------------------------------
# Recovery restore
# ---------------------------------------------------------------------------


@pytest.fixture
def vaulted(investigator_client, admin_client, operator_client, temp_dir):
    """A real recovery object, created by the real recoverable execution."""
    path = write_target(temp_dir, body="the protected payload")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    operation_id = request_recoverable(investigator_client, admin_client, path)
    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "COMPLETED", response.text
    assert not path.exists()

    listed = admin_client.get("/api/recovery-objects")
    assert listed.status_code == 200, listed.text
    objects = [o for o in listed.json() if o["operation_id"] == operation_id]
    assert len(objects) == 1
    return {"object_id": objects[0]["id"], "sha256": digest, "body": "the protected payload"}


def restore(client, object_id, destination, **extra):
    return client.post(
        f"/api/recovery-objects/{object_id}/restore",
        json={"destination": str(destination), **extra},
    )


def outcomes(destination):
    return [(r.event_type.value, r.outcome.value) for r in restore_events(destination)]


def test_restore_succeeds_through_the_privileged_service(
    admin_client, vaulted, temp_dir, monkeypatch, engine_callers
):
    destination = temp_dir / "restored.txt"
    transport = recording(monkeypatch)

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "COMPLETED" and body["integrity_verified"] is True
    assert body["sha256"] == vaulted["sha256"]
    assert destination.read_text(encoding="utf-8") == vaulted["body"]
    assert [r["operation"] for r in transport.sent] == ["restore_recovery_object"]
    assert any(c.endswith("oblivion/privileged/service.py") for c in engine_callers)
    assert outcomes(destination) == [
        ("RECOVERY_RESTORE_REQUESTED", "SUCCEEDED"),
        ("RECOVERY_RESTORE_PERFORMED", "SUCCEEDED"),
    ]
    assert chain_intact()


def test_restore_of_an_unknown_object_is_not_found(admin_client, temp_dir):
    destination = temp_dir / "unknown.txt"

    response = restore(admin_client, "op_000000000000-deadbeef", destination)

    assert response.status_code == 404, response.text
    assert response.json()["error_code"] == "RECOVERY_OBJECT_NOT_FOUND"
    assert not destination.exists()
    assert outcomes(destination) == [
        ("RECOVERY_RESTORE_REQUESTED", "SUCCEEDED"),
        ("RECOVERY_RESTORE_PERFORMED", "REFUSED"),
    ]


@pytest.mark.parametrize("object_id", ["..", "a..b", "..%5Coutside", "-leading", "a b"])
def test_restore_refuses_a_malformed_object_id(admin_client, temp_dir, object_id):
    destination = temp_dir / f"bad-id-{uuid.uuid4().hex[:6]}.txt"

    response = restore(admin_client, object_id, destination)

    assert response.status_code in (404, 405), response.text
    assert not destination.exists()


def test_the_service_refuses_a_malformed_object_id_on_its_own(temp_dir, safe_validator, vault_env):
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    env = {
        "OBLIVION_IPC_KEY": authenticator._key.hex(),
        "OBLIVION_VAULT_KEY": "11" * 32,
        "OBLIVION_VAULT_ROOT": str(vault_env),
    }
    client = PrivilegedClient(
        InProcessTransport(build_service_from_env(safe_validator, env)), authenticator
    )
    response = client.restore_recovery_object(
        operation_id="restore_direct",
        policy_id=RECOVERABLE_POLICY,
        mode="CONTROLLED_RECOVERABLE",
        target_path=str(temp_dir / "x.txt"),
        target_type="file",
        actor_id="user_operator_1",
        params={"object_id": "..\\..\\elsewhere", "destination_path": str(temp_dir / "x.txt")},
    )
    assert response.status is ResponseStatus.REFUSED
    assert any("vault identifier" in r for r in response.refusals)


def test_restore_never_overwrites_an_existing_destination(admin_client, vaulted, temp_dir):
    destination = temp_dir / "occupied.txt"
    destination.write_text("keep me", encoding="utf-8")

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == "RECOVERY_DESTINATION_EXISTS"
    assert destination.read_text(encoding="utf-8") == "keep me"
    assert outcomes(destination) == [("RECOVERY_RESTORE_REQUESTED", "REFUSED")]


@pytest.mark.parametrize("exists", [True, False])
def test_restore_refuses_an_overwrite_request(admin_client, vaulted, temp_dir, exists):
    destination = temp_dir / f"overwrite-{exists}.txt"
    if exists:
        destination.write_text("keep me", encoding="utf-8")

    response = restore(admin_client, vaulted["object_id"], destination, allow_overwrite=True)

    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == "RESTORE_OVERWRITE_NOT_PERMITTED"
    if exists:
        assert destination.read_text(encoding="utf-8") == "keep me"
    else:
        assert not destination.exists()


def test_restore_refuses_a_destination_outside_the_roots(admin_client, vaulted, temp_dir):
    destination = temp_dir.parent / f"escaped-{uuid.uuid4().hex[:6]}.txt"

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == "RECOVERY_RESTORE_REFUSED"
    assert not destination.exists()
    assert outcomes(destination)[-1] == ("RECOVERY_RESTORE_PERFORMED", "REFUSED")


def test_restore_refuses_a_destination_behind_a_junction(admin_client, vaulted, temp_dir):
    import _winapi

    outside = temp_dir.parent / f"junction-target-{uuid.uuid4().hex[:6]}"
    outside.mkdir()
    junction = temp_dir / "jn"
    try:
        _winapi.CreateJunction(str(outside), str(junction))
    except OSError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"junction creation unavailable: {exc}")
    destination = junction / "through.txt"
    try:
        response = restore(admin_client, vaulted["object_id"], destination)
        assert response.status_code == 400, response.text
        assert not (outside / "through.txt").exists()
    finally:
        junction.rmdir()
        outside.rmdir()


def test_restore_refuses_a_missing_destination_directory(admin_client, vaulted, temp_dir):
    destination = temp_dir / "no-such-dir" / "restored.txt"

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 400, response.text
    assert not destination.parent.exists()


def test_a_tampered_object_is_not_restored(admin_client, vaulted, temp_dir, vault_env):
    payload = vault_env / f"{vaulted['object_id']}.payload"
    data = bytearray(payload.read_bytes())
    data[-1] ^= 0x01
    payload.write_bytes(bytes(data))
    destination = temp_dir / "tampered.txt"

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 400, response.text
    assert response.json()["error_code"] == "RECOVERY_TEST_FAILED"
    assert not destination.exists()
    assert not list(temp_dir.glob("tampered.txt.tmp_*"))
    assert outcomes(destination)[-1] == ("RECOVERY_RESTORE_PERFORMED", "FAILED")


def test_restore_with_a_rejected_reply_is_never_reported_as_success(
    admin_client, vaulted, temp_dir, monkeypatch
):
    class BadMac(InProcessTransport):
        def exchange(self, envelope):
            reply = super().exchange(envelope)
            if envelope["request"]["operation"] == "restore_recovery_object":
                reply = dict(reply, mac="00" * 32)
            return reply

    destination = temp_dir / "uncertain.txt"
    use_transport(monkeypatch, BadMac)

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 502, response.text
    assert response.json()["error_code"] == "RESTORE_OUTCOME_UNESTABLISHED"
    assert destination.exists(), "the service really wrote it; only the reply was lost"
    recorded = outcomes(destination)
    assert recorded == [
        ("RECOVERY_RESTORE_REQUESTED", "SUCCEEDED"),
        ("OPERATION_OUTCOME_UNESTABLISHED", "FAILED"),
    ]
    assert ("RECOVERY_RESTORE_PERFORMED", "SUCCEEDED") not in recorded


def test_restore_with_an_unreachable_service_writes_nothing(
    admin_client, vaulted, temp_dir, monkeypatch
):
    class Unreachable(InProcessTransport):
        def exchange(self, envelope):
            raise ServiceUnavailableError("pipe not available")

    destination = temp_dir / "unreachable.txt"
    use_transport(monkeypatch, Unreachable)

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 503, response.text
    assert not destination.exists()
    assert outcomes(destination)[-1] == ("RECOVERY_RESTORE_PERFORMED", "FAILED")


def test_restore_with_no_service_vault_is_unavailable(admin_client, vaulted, temp_dir, monkeypatch):
    monkeypatch.delenv("OBLIVION_VAULT_KEY", raising=False)
    destination = temp_dir / "no-vault.txt"

    response = restore(admin_client, vaulted["object_id"], destination)

    assert response.status_code == 503, response.text
    assert response.json()["error_code"] == "VAULT_UNAVAILABLE"
    assert not destination.exists()


def test_restore_requires_the_recovery_permission(viewer_client, temp_dir):
    destination = temp_dir / "viewer.txt"

    response = restore(viewer_client, "op_000000000000-deadbeef", destination)

    assert response.status_code == 403, response.text
    assert not destination.exists()


def test_the_engine_never_replaces_a_destination_that_appears_late(
    temp_dir, safe_validator, vault_env, monkeypatch
):
    """The existence check is advisory; the final placement itself refuses."""
    from oblivion.core.erasure.engine import ErasureEngine
    from oblivion.core.erasure.events import EngineEventEmitter
    from oblivion.core.erasure.vault import RecoveryVault

    key = secrets.token_bytes(32)
    vault = RecoveryVault(str(vault_env), safe_validator, key)
    vault.store(
        "obj-late",
        "op-late",
        b"restored bytes",
        {"original_sha256": hashlib.sha256(b"restored bytes").hexdigest()},
    )
    engine = ErasureEngine(safe_validator, EngineEventEmitter())
    engine.set_vault(vault, key)

    destination = temp_dir / "late.txt"
    destination.write_text("arrived first", encoding="utf-8")
    real_exists = engine_module.os.path.exists
    monkeypatch.setattr(
        engine_module.os.path,
        "exists",
        lambda p: False if str(p) == str(destination) else real_exists(p),
    )

    result = engine.restore_recovery_object(
        "obj-late", str(destination), key, authorized=True, allow_overwrite=False
    )

    assert result["status"] == "BLOCKED"
    assert destination.read_text(encoding="utf-8") == "arrived first"
    assert not list(temp_dir.glob("late.txt.tmp_*"))
