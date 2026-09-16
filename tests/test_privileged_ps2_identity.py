"""PS-2: the privileged service requires the full approved identity for destructive work.

The attacker model is a compromised unprivileged API process that builds privileged
requests itself. Before this fix, a destructive request carrying a valid volume
serial and ``expected_file_id=None`` was accepted: the validator read the file
identity from disk and handed *that* to the engine, which then compared the object
with itself. A file substituted after approval would have been erased.

Every destructive operation is exercised against a real scratch target, and a
tripwire on the service's engine proves a refused request never reaches it.
"""

from __future__ import annotations

import datetime as _dt
import logging
import secrets
import sys

import pytest

from oblivion.core.pipeline import ClosedLoopPipeline, Stage, StageStatus
from oblivion.core.safety.paths import decode_file_id
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged import (
    InProcessTransport,
    PrivilegedClient,
    PrivilegedOperation,
    PrivilegedRequest,
    PrivilegedService,
    RequestAuthenticator,
    ResponseStatus,
    ServiceConfig,
)
from tests.test_pipeline_closed_loop import approve_operation, make_request
from tests.test_privileged_ipc import identity

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="File identity is only observable on Windows"
)

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
TREE_POLICY = "ERASURE.LOGICAL.TREE.V1"
RECOVERABLE_POLICY = "ERASURE.RECOVERABLE.ENCRYPTED.V1"
ACTOR = "user_operator_1"
MISSING = object()

DESTRUCTIVE_CASES = {
    "delete_file": (
        PrivilegedOperation.DELETE_FILE,
        SELECTIVE_POLICY,
        "SELECTIVE_PERMANENT",
        "file",
    ),
    "delete_tree": (PrivilegedOperation.DELETE_TREE, TREE_POLICY, "COMPLETE_ERASURE", "directory"),
    "prepare_recovery_object": (
        PrivilegedOperation.PREPARE_RECOVERY_OBJECT,
        RECOVERABLE_POLICY,
        "CONTROLLED_RECOVERABLE",
        "file",
    ),
}


@pytest.fixture(autouse=True)
def database():
    init_db()


@pytest.fixture
def authenticator() -> RequestAuthenticator:
    return RequestAuthenticator(secrets.token_bytes(32))


@pytest.fixture
def service(safe_validator, authenticator) -> PrivilegedService:
    return PrivilegedService(ServiceConfig(validator=safe_validator, authenticator=authenticator))


@pytest.fixture
def vault_service(safe_validator, authenticator, temp_dir) -> PrivilegedService:
    vault_root = temp_dir / "vault"
    vault_root.mkdir()
    return PrivilegedService(
        ServiceConfig(
            validator=safe_validator,
            authenticator=authenticator,
            vault_root=str(vault_root),
            vault_key=secrets.token_bytes(32),
        )
    )


def make_target(temp_dir, target_type):
    """A real target, plus a function that proves it is untouched."""
    if target_type == "directory":
        root = temp_dir / f"tree-{secrets.token_hex(3)}"
        root.mkdir()
        (root / "a.txt").write_text("alpha")
        (root / "nested").mkdir()
        (root / "nested" / "b.txt").write_text("beta")

        def untouched() -> bool:
            return (
                (root / "a.txt").read_text() == "alpha"
                and (root / "nested" / "b.txt").read_text() == "beta"
            )

        return root, untouched

    path = temp_dir / f"victim-{secrets.token_hex(3)}.txt"
    path.write_text("payload")
    return path, lambda: path.exists() and path.read_text() == "payload"


def build(case, target, *, serial=MISSING, file_id=MISSING):
    """A signed-ready request built directly, as a compromised API process could."""
    operation, policy, mode, target_type = DESTRUCTIVE_CASES[case]
    return PrivilegedRequest(
        request_id=f"req-{secrets.token_hex(4)}",
        nonce=secrets.token_hex(16),
        operation=operation,
        operation_id=f"op-{case}",
        policy_id=policy,
        mode=mode,
        target_path=str(target),
        target_type=target_type,
        actor_id=ACTOR,
        issued_at=_dt.datetime.now(_dt.timezone.utc),
        expected_volume_serial=None if serial is MISSING else serial,
        expected_file_id=None if file_id is MISSING else file_id,
    )


@pytest.fixture
def pick(service, vault_service):
    """The service each destructive operation needs (the vault one for prepare)."""

    def choose(case):
        return vault_service if case == "prepare_recovery_object" else service

    return choose


@pytest.fixture
def tripwire(monkeypatch):
    """Fails the test if a refused request ever reaches the erasure engine."""

    def arm(svc):
        def forbidden():
            raise AssertionError("the engine was reached for a request that must be refused")

        monkeypatch.setattr(svc, "_engine", forbidden)

    return arm


# ---------------------------------------------------------------------------
# The complete identity is accepted on every destructive path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_complete_identity_is_accepted(case, pick, authenticator, safe_validator, temp_dir):
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, file_id = identity(safe_validator, target)
    request = build(case, target, serial=serial, file_id=file_id)

    response = svc.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.COMPLETED, response.refusals
    assert response.result.get("status") == "COMPLETED", response.result
    assert not target.exists()


# ---------------------------------------------------------------------------
# Anything less is refused before any filesystem work
# ---------------------------------------------------------------------------


def valid(safe_validator, target):
    serial, file_id = identity(safe_validator, target)
    assert serial is not None and file_id is not None
    return serial, file_id


MISSING_SHAPES = {
    "file_id_none": lambda s, f: {"serial": s, "file_id": None},
    "file_id_absent": lambda s, f: {"serial": s},
    "serial_absent": lambda s, f: {"file_id": f},
    "serial_none": lambda s, f: {"serial": None, "file_id": f},
    "serial_empty": lambda s, f: {"serial": "", "file_id": f},
    "serial_blank": lambda s, f: {"serial": "   ", "file_id": f},
    "both_absent": lambda s, f: {},
}


@pytest.mark.parametrize("shape", MISSING_SHAPES)
@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_missing_identity_component_is_refused_before_mutation(
    case, shape, pick, authenticator, safe_validator, temp_dir, tripwire
):
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, file_id = valid(safe_validator, target)
    request = build(case, target, **MISSING_SHAPES[shape](serial, file_id))
    tripwire(svc)

    response = svc.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.REFUSED
    assert untouched()
    assert any("fail-closed" in r for r in response.refusals), response.refusals
    if shape == "both_absent":
        joined = " ".join(response.refusals)
        assert "no expected volume serial" in joined
        assert "no expected file identity" in joined


@pytest.mark.parametrize(
    "bad_file_id",
    [(), (1, 2), (1, 2, 3, 4), (1, 2, -3), (True, 1, 2), ("1", 2, 3), (1.0, 2, 3), [1, 2, 3]],
    ids=["empty", "two", "four", "negative", "bool", "str", "float", "list"],
)
@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_malformed_file_identity_is_refused_before_mutation(
    case, bad_file_id, pick, authenticator, safe_validator, temp_dir, tripwire
):
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, _ = valid(safe_validator, target)
    request = build(case, target, serial=serial, file_id=bad_file_id)
    tripwire(svc)

    response = svc.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.REFUSED
    assert untouched()
    assert any("malformed expected file identity" in r for r in response.refusals)


@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_refusal_goes_through_the_existing_refusal_path(
    case, pick, authenticator, safe_validator, temp_dir, tripwire, caplog
):
    """Logged as a validation refusal, with no path or identity in the log line."""
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, _ = valid(safe_validator, target)
    request = build(case, target, serial=serial, file_id=None)
    tripwire(svc)

    with caplog.at_level(logging.INFO, logger="oblivion.privileged.service"):
        response = svc.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.REFUSED
    assert untouched()
    refused = [r for r in caplog.records if "privileged.request.refused" in r.getMessage()]
    assert refused, "the refusal must be logged by the service's existing refusal path"
    assert all(str(target) not in r.getMessage() for r in refused)
    assert serial not in " ".join(response.refusals)


# ---------------------------------------------------------------------------
# The existing mismatch behaviour is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_different_file_identity_is_still_refused_as_a_substitution(
    case, pick, authenticator, safe_validator, temp_dir, tripwire
):
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, file_id = valid(safe_validator, target)
    other = (file_id[0], file_id[1], file_id[2] + 1)
    request = build(case, target, serial=serial, file_id=other)
    tripwire(svc)

    response = svc.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.REFUSED
    assert untouched()
    assert any("File identity changed" in r for r in response.refusals)


@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_different_volume_serial_is_still_refused(
    case, pick, authenticator, safe_validator, temp_dir, tripwire
):
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, file_id = valid(safe_validator, target)
    request = build(case, target, serial=f"{serial}-other", file_id=file_id)
    tripwire(svc)

    response = svc.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.REFUSED
    assert untouched()
    assert any("volume serial does not match" in r for r in response.refusals)


def test_a_substituted_file_at_the_same_path_is_refused(
    service, authenticator, safe_validator, temp_dir, tripwire
):
    """The attack PS-2 enabled, now closed from both directions."""
    target = temp_dir / "approved.txt"
    target.write_text("approved object")
    serial, file_id = valid(safe_validator, target)
    target.unlink()
    target.write_text("substituted object")
    tripwire(service)

    for stated in (file_id, None):
        request = build("delete_file", target, serial=serial, file_id=stated)
        response = service.handle(request, authenticator.sign(request))
        assert response.status is ResponseStatus.REFUSED

    assert target.read_text() == "substituted object"


# ---------------------------------------------------------------------------
# The same over the wire, through the real client and transport
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", DESTRUCTIVE_CASES)
def test_a_wire_request_with_a_null_file_identity_is_refused(
    case, pick, authenticator, safe_validator, temp_dir, tripwire
):
    """A null identity parses (it is well-formed) and is then refused by the service."""
    svc = pick(case)
    target, untouched = make_target(temp_dir, DESTRUCTIVE_CASES[case][3])
    serial, _ = valid(safe_validator, target)
    wire = build(case, target, serial=serial, file_id=None).to_wire()
    assert wire["expected_file_id"] is None
    request = PrivilegedRequest.from_wire(wire)
    tripwire(svc)

    client = PrivilegedClient(InProcessTransport(svc), authenticator)
    response = client.send(request)

    assert response.status is ResponseStatus.REFUSED
    assert untouched()


# ---------------------------------------------------------------------------
# Non-destructive operations do not need a file identity
# ---------------------------------------------------------------------------


def test_inspect_and_scan_need_no_identity(service, authenticator, temp_dir):
    target = temp_dir / "readable.txt"
    target.write_text("content")
    client = PrivilegedClient(InProcessTransport(service), authenticator)
    common = {
        "operation_id": "op-read",
        "policy_id": SELECTIVE_POLICY,
        "mode": "SELECTIVE_PERMANENT",
        "target_path": str(target),
        "target_type": "file",
        "actor_id": ACTOR,
    }

    assert client.inspect_target(**common).status is ResponseStatus.COMPLETED
    assert client.scan_scope(**common).status is ResponseStatus.COMPLETED
    assert target.read_text() == "content"


def test_restore_is_not_subject_to_the_destructive_identity_rule(
    service, authenticator, temp_dir
):
    client = PrivilegedClient(InProcessTransport(service), authenticator)
    response = client.restore_recovery_object(
        operation_id="op-restore",
        policy_id=RECOVERABLE_POLICY,
        mode="CONTROLLED_RECOVERABLE",
        target_path=str(temp_dir),
        target_type="file",
        actor_id=ACTOR,
        params={"object_id": "obj-1", "destination_path": str(temp_dir / "restored.txt")},
    )
    assert not any("identity" in r for r in response.refusals), response.refusals
    assert response.status is ResponseStatus.COMPLETED
    assert response.result["error"] == "VAULT_UNAVAILABLE"


# ---------------------------------------------------------------------------
# Production call paths always send both halves
# ---------------------------------------------------------------------------


class Recording(InProcessTransport):
    def __init__(self, service):
        super().__init__(service)
        self.sent: list[dict] = []

    def exchange(self, envelope):
        self.sent.append(envelope["request"])
        return super().exchange(envelope)


def test_the_pipeline_sends_the_full_recorded_identity(
    service, authenticator, safe_validator, temp_dir
):
    target = temp_dir / "pipeline.txt"
    target.write_text("payload")
    transport = Recording(service)

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        result = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=PrivilegedClient(transport, authenticator),
        ).run(
            make_request(
                operation_id,
                target,
                expected_volume_serial=stored.volume_serial,
                expected_file_id=decode_file_id(stored.file_id),
            )
        )
        session.commit()

    destructive = [r for r in transport.sent if r["operation"] == "delete_file"]
    assert len(destructive) == 1
    assert destructive[0]["expected_volume_serial"] == stored.volume_serial
    assert tuple(destructive[0]["expected_file_id"]) == decode_file_id(stored.file_id)
    assert result.outcome(Stage.ERASE).status is StageStatus.COMPLETED
    assert not target.exists()


def test_the_pipeline_never_sends_a_destructive_request_without_a_file_identity(
    service, authenticator, safe_validator, temp_dir
):
    target = temp_dir / "pipeline-no-id.txt"
    target.write_text("payload")
    transport = Recording(service)

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        result = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=PrivilegedClient(transport, authenticator),
        ).run(
            make_request(
                operation_id,
                target,
                expected_volume_serial=stored.volume_serial,
                expected_file_id=None,
            )
        )
        session.commit()

    assert not [r for r in transport.sent if r["operation"] == "delete_file"]
    assert result.outcome(Stage.ERASE).status is StageStatus.REFUSED
    assert target.read_text() == "payload"
