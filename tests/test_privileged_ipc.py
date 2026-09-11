"""Phase 24: the privileged execution boundary, exercised through real code.

Every test here drives the actual service - the real parser, the real MAC, the
real validator, the real erasure engine - against a disposable directory. None
of it is simulated, and nothing operates outside the per-test scratch root.

The suite is organised around the properties the boundary claims, because those
are what would matter if they were ever untrue:

* the operation set is closed, and no request can name code to run
* a request that is not authentic, fresh and single-use is not serviced
* containment, policy and target identity are decided by the *service*
* a restore never overwrites
* capabilities are reported honestly, including the ones that do not exist here
"""

from __future__ import annotations

import datetime as _dt
import inspect
import secrets
import sys
from pathlib import Path

import pytest

from oblivion.core.safety.paths import SafePathValidator
from oblivion.privileged import (
    DESTRUCTIVE_OPERATIONS,
    InProcessTransport,
    PrivilegedClient,
    PrivilegedOperation,
    PrivilegedRequest,
    PrivilegedService,
    ProtocolError,
    ReplayCache,
    RequestAuthenticator,
    ResponseStatus,
    ServiceConfig,
    ServiceState,
    build_service_from_env,
)
from oblivion.privileged import client as client_module
from oblivion.privileged import protocol as protocol_module
from oblivion.privileged import service as service_module
from oblivion.privileged import transport as transport_module
from oblivion.privileged import validation as validation_module
from oblivion.privileged.service import CapabilityState, ReplayCacheFull

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
TREE_POLICY = "ERASURE.LOGICAL.TREE.V1"
RECOVERABLE_POLICY = "ERASURE.RECOVERABLE.ENCRYPTED.V1"
ACTOR = "user_operator_1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ipc_key() -> str:
    """A fresh IPC key per test. Generated, never written down anywhere."""
    return secrets.token_hex(32)


@pytest.fixture
def authenticator(ipc_key: str) -> RequestAuthenticator:
    return RequestAuthenticator(bytes.fromhex(ipc_key))


@pytest.fixture
def service(safe_validator, authenticator) -> PrivilegedService:
    return PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )


@pytest.fixture
def vault_service(safe_validator, authenticator, temp_dir) -> PrivilegedService:
    vault_root = temp_dir / "vault"
    vault_root.mkdir()
    return PrivilegedService(
        ServiceConfig(
            validator=safe_validator,
            authenticator=authenticator,
            vault_root=str(vault_root),
            vault_key=bytes.fromhex(secrets.token_hex(32)),
        )
    )


@pytest.fixture
def client(service, authenticator) -> PrivilegedClient:
    return PrivilegedClient(InProcessTransport(service), authenticator)


@pytest.fixture
def vault_client(vault_service, authenticator) -> PrivilegedClient:
    return PrivilegedClient(InProcessTransport(vault_service), authenticator)


def identity(validator, path):
    """The (serial, file_id) pair a destructive request must carry."""
    return validator.get_volume_serial(str(path)), validator._get_file_id(str(path))


def wire_request(**overrides):
    """A complete, well-formed request payload that individual tests bend."""
    payload = {
        "protocol_version": "OBLIVION-PRIV-1",
        "request_id": "req-1",
        "nonce": secrets.token_hex(8),
        "operation": "inspect_target",
        "operation_id": "op-1",
        "policy_id": SELECTIVE_POLICY,
        "mode": "SELECTIVE_PERMANENT",
        "target_path": "C:/scratch/file.txt",
        "target_type": "file",
        "expected_volume_serial": None,
        "expected_file_id": None,
        "actor_id": ACTOR,
        "issued_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "params": {},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# The operation set is closed
# ---------------------------------------------------------------------------


def test_operation_allowlist_is_exactly_the_six_documented_operations():
    """docs/PRIVILEGE_BOUNDARY.md enumerates these and forbids anything else.

    Pinned as an equality rather than a subset check: a new privileged operation
    must be a deliberate, reviewed change to this list, not something that
    appears because a module grew a method.
    """
    assert {o.value for o in PrivilegedOperation} == {
        "inspect_target",
        "delete_file",
        "delete_tree",
        "prepare_recovery_object",
        "restore_recovery_object",
        "scan_scope",
    }


@pytest.mark.parametrize(
    "operation",
    [
        "execute_command",
        "powershell",
        "cmd",
        "run",
        "exec",
        "shell",
        "DELETE_FILE",
        "Delete_File",
        " delete_file",
        "delete_file ",
        "delete_file;inspect_target",
        "",
    ],
)
def test_operation_outside_the_allowlist_never_parses(operation):
    """Including case variants and whitespace padding of a *valid* name.

    A parser that trimmed or lowercased would turn 'Delete_File' into a real
    operation, which is exactly the kind of helpfulness a privilege boundary
    cannot afford.
    """
    with pytest.raises(ProtocolError, match="allowlist|must be a string"):
        PrivilegedRequest.from_wire(wire_request(operation=operation))


def test_every_operation_has_a_handler(service):
    """Dispatch must cover the enum, so no operation falls through.

    Reaching into the private map is deliberate: the alternative is discovering
    a missing handler in production, where the fallback refuses but the caller
    has already been told the operation is supported.
    """
    assert set(service._handlers) == set(PrivilegedOperation)


@pytest.mark.parametrize(
    "module",
    [
        protocol_module,
        validation_module,
        service_module,
        transport_module,
        client_module,
    ],
)
def test_no_module_in_the_privileged_package_can_execute_a_command(module):
    """The strongest claim this package makes, asserted against its own source.

    Checks for execution *constructs* rather than for words: the protocol module
    legitimately contains the string 'powershell' in its list of markers to
    refuse, and a naive word search would flag that while missing an actual
    ``subprocess`` import.
    """
    source = inspect.getsource(module)
    for construct in (
        "import subprocess",
        "subprocess.",
        "os.system",
        "os.popen",
        "os.exec",
        "os.spawn",
        "shell=True",
        "eval(",
        "exec(",
        "__import__(",
    ):
        assert construct not in source, (
            f"{module.__name__} contains {construct!r}; the privileged boundary "
            "must contain no execution primitive at all"
        )


# ---------------------------------------------------------------------------
# Parsing is total and fail-closed
# ---------------------------------------------------------------------------


def test_unknown_field_is_refused_rather_than_ignored():
    with pytest.raises(ProtocolError, match="Unknown field"):
        PrivilegedRequest.from_wire(wire_request(allow_overwrite=True))


def test_naive_timestamp_is_refused():
    """A timestamp without an offset cannot be compared across processes."""
    with pytest.raises(ProtocolError, match="timezone"):
        PrivilegedRequest.from_wire(
            wire_request(issued_at=_dt.datetime.now().isoformat())
        )


def test_unsupported_protocol_version_is_refused():
    with pytest.raises(ProtocolError, match="protocol version"):
        PrivilegedRequest.from_wire(wire_request(protocol_version="OBLIVION-PRIV-0"))


@pytest.mark.parametrize(
    "param_name",
    [
        "vault_key",
        "vaultkey",
        "password",
        "api_key",
        "private_key",
        "recovery_key",
        "signing_key",
        "session_token",
        "db_credential",
        "connection_string",
    ],
)
def test_no_parameter_may_name_secret_material(param_name):
    """The service holds its own secrets; the boundary carries none.

    Refused by name before the value is even looked at, so a request cannot
    smuggle a substitute vault key past a handler that would otherwise use it.
    """
    with pytest.raises(ProtocolError, match="secret material"):
        PrivilegedRequest.from_wire(
            wire_request(
                operation="restore_recovery_object",
                params={param_name: "anything"},
            )
        )


def test_operation_cannot_receive_a_parameter_it_does_not_declare():
    with pytest.raises(ProtocolError, match="accepts no parameter"):
        PrivilegedRequest.from_wire(
            wire_request(operation="delete_file", params={"object_id": "obj-1"})
        )


def test_restore_requires_both_of_its_parameters():
    with pytest.raises(ProtocolError, match="requires parameter"):
        PrivilegedRequest.from_wire(
            wire_request(
                operation="restore_recovery_object", params={"object_id": "obj-1"}
            )
        )


@pytest.mark.parametrize(
    "hostile_path",
    [
        "C:/scratch/f.txt && del C:/Windows",
        "C:/scratch/f.txt | powershell",
        "$(whoami)",
        "C:/scratch/`whoami`",
        "C:/scratch/f.txt > C:/out.txt",
    ],
)
def test_command_markers_in_a_path_are_refused(hostile_path):
    """Defence in depth: no handler shells out, and such a value is still refused."""
    with pytest.raises(ProtocolError, match="command-execution marker"):
        PrivilegedRequest.from_wire(wire_request(target_path=hostile_path))


def test_malformed_payloads_never_crash_the_parser():
    for payload in (None, [], "delete_file", 42, {"operation": None}):
        with pytest.raises(ProtocolError):
            PrivilegedRequest.from_wire(payload)


# ---------------------------------------------------------------------------
# Authentication and integrity
# ---------------------------------------------------------------------------


def test_a_correctly_signed_request_is_serviced(client, temp_dir):
    target = temp_dir / "readable.txt"
    target.write_text("content")

    response = client.inspect_target(
        operation_id="op-inspect",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.COMPLETED
    assert response.result["analysis"]


def test_a_wrong_mac_is_refused(service, temp_dir):
    """A request from a process that does not hold the key is not serviced."""
    target = temp_dir / "readable.txt"
    target.write_text("content")

    request = PrivilegedRequest.from_wire(
        wire_request(target_path=str(target), operation="inspect_target")
    )
    response = service.handle(request, "00" * 32)
    assert response.status is ResponseStatus.REFUSED
    assert any("MAC does not verify" in r for r in response.refusals)


def test_altering_a_signed_request_invalidates_it(service, authenticator, temp_dir):
    """The MAC covers the canonical bytes, so no field can change after signing.

    This is the property that makes it safe for the service to act on the
    request it verified: verification and use are over the same bytes.
    """
    target = temp_dir / "readable.txt"
    target.write_text("content")

    original = PrivilegedRequest.from_wire(wire_request(target_path=str(target)))
    mac = authenticator.sign(original)

    tampered = PrivilegedRequest.from_wire(
        wire_request(
            target_path=str(target),
            nonce=original.nonce,
            request_id=original.request_id,
            operation="delete_file",
            issued_at=original.issued_at.isoformat(),
        )
    )
    response = service.handle(tampered, mac)
    assert response.status is ResponseStatus.REFUSED


def test_service_without_a_key_is_unavailable_and_refuses_everything(safe_validator):
    """No fallback secret. A misconfigured service does nothing at all."""
    unconfigured = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=None)
    )
    assert unconfigured.state is ServiceState.UNAVAILABLE_NO_KEY
    assert not unconfigured.available

    response = unconfigured.handle(PrivilegedRequest.from_wire(wire_request()), "mac")
    assert response.status is ResponseStatus.REFUSED
    assert any("UNAVAILABLE_NO_KEY" in r for r in response.refusals)


def test_build_from_env_without_a_key_yields_an_unavailable_service(safe_validator):
    built = build_service_from_env(safe_validator, env={})
    assert built.state is ServiceState.UNAVAILABLE_NO_KEY


def test_build_from_env_rejects_a_malformed_ipc_key(safe_validator):
    with pytest.raises(Exception, match="hex-encoded"):
        build_service_from_env(safe_validator, env={"OBLIVION_IPC_KEY": "not-hex!!"})


def test_build_from_env_rejects_a_short_ipc_key(safe_validator):
    with pytest.raises(Exception, match="at least 32 bytes"):
        build_service_from_env(safe_validator, env={"OBLIVION_IPC_KEY": "aabb"})


def test_a_wrong_length_vault_key_is_treated_as_absent(safe_validator, ipc_key):
    """Never padded, stretched or hashed into shape.

    Deriving a usable key from malformed input would make a misconfiguration
    look like a working vault, which is worse than having no vault.
    """
    built = build_service_from_env(
        safe_validator,
        env={"OBLIVION_IPC_KEY": ipc_key, "OBLIVION_VAULT_KEY": "aabbcc"},
    )
    vault = next(c for c in built.capabilities() if c.name == "recovery_vault")
    assert vault.state is CapabilityState.UNAVAILABLE


# ---------------------------------------------------------------------------
# Replay and freshness
# ---------------------------------------------------------------------------


def test_a_replayed_request_is_refused(service, authenticator, temp_dir):
    """Correctly formed and correctly signed, and still refused the second time."""
    target = temp_dir / "readable.txt"
    target.write_text("content")

    request = PrivilegedRequest.from_wire(wire_request(target_path=str(target)))
    mac = authenticator.sign(request)

    first = service.handle(request, mac)
    second = service.handle(request, mac)

    assert first.status is ResponseStatus.COMPLETED
    assert second.status is ResponseStatus.REFUSED
    assert any("Nonce has already been used" in r for r in second.refusals)


def test_a_stale_request_is_refused(service, authenticator, temp_dir):
    target = temp_dir / "readable.txt"
    target.write_text("content")

    old = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=1)).isoformat()
    request = PrivilegedRequest.from_wire(
        wire_request(target_path=str(target), issued_at=old)
    )
    response = service.handle(request, authenticator.sign(request))
    assert response.status is ResponseStatus.REFUSED
    assert any("stale" in r for r in response.refusals)


def test_a_request_dated_in_the_future_is_refused(service, authenticator, temp_dir):
    target = temp_dir / "readable.txt"
    target.write_text("content")

    ahead = (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(hours=1)).isoformat()
    request = PrivilegedRequest.from_wire(
        wire_request(target_path=str(target), issued_at=ahead)
    )
    response = service.handle(request, authenticator.sign(request))
    assert response.status is ResponseStatus.REFUSED


def test_only_one_of_many_concurrent_threads_may_claim_a_nonce():
    """check-and-insert is atomic, so a race cannot admit the same nonce twice.

    A barrier releases every thread at once, which is what makes this a real
    race rather than a sequence that happens to interleave. Without the lock,
    several threads would see "not seen" between the check and the insert.
    """
    import threading

    cache = ReplayCache()
    thread_count = 32
    barrier = threading.Barrier(thread_count)
    results: list[bool] = []
    guard = threading.Lock()

    def claim() -> None:
        barrier.wait()
        outcome = cache.remember("contended-nonce")
        with guard:
            results.append(outcome)

    threads = [threading.Thread(target=claim) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(results) == thread_count
    assert sum(1 for r in results if r) == 1, (
        "exactly one thread may record the nonce; the rest must see a replay"
    )
    assert len(cache) == 1


def test_the_cache_refuses_rather_than_forgetting_a_live_nonce():
    """At capacity it fails closed.

    Evicting an unexpired nonce to make room would silently re-open its replay
    window, which is worse than refusing work.
    """
    cache = ReplayCache(max_entries=3)
    for index in range(3):
        assert cache.remember(f"n{index}") is True

    with pytest.raises(ReplayCacheFull, match="still live"):
        cache.remember("one-too-many")

    # And the nonces it already holds are still refused as replays.
    assert cache.remember("n0") is False


def test_capacity_is_reclaimed_once_entries_expire():
    """The bound is a ceiling on *live* nonces, not a permanent limit."""
    cache = ReplayCache(_dt.timedelta(minutes=5), max_entries=2)
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)

    assert cache.remember("a", now=now) is True
    assert cache.remember("b", now=now) is True
    with pytest.raises(ReplayCacheFull):
        cache.remember("c", now=now)

    later = now + _dt.timedelta(minutes=10)
    assert cache.remember("c", now=later) is True


def test_an_injected_cache_is_used_even_when_empty():
    """Regression guard for a truthiness bug found while fixing M-1.

    ``ReplayCache`` defines ``__len__``, so an empty cache is falsy. Selecting it
    with ``or`` silently discarded the injected cache and built a private one -
    which reintroduced M-1 in exactly the case that matters, the first request
    after startup, while every test still passed.
    """
    shared = ReplayCache()
    assert len(shared) == 0
    assert not shared, "an empty cache is falsy; that is what made `or` unsafe"

    validator = SafePathValidator(allowed_roots=[str(Path.cwd())])
    service = PrivilegedService(
        ServiceConfig(
            validator=validator,
            authenticator=RequestAuthenticator(bytes.fromhex(secrets.token_hex(32))),
            replay_cache=shared,
        )
    )
    assert service._replay is shared


def test_replay_cache_forgets_nonces_once_they_can_no_longer_be_used():
    """Bounded memory, without opening a window where a replay would work.

    The cache retains a nonce for exactly as long as a request bearing it could
    still pass the freshness check.
    """
    cache = ReplayCache(_dt.timedelta(minutes=5))
    now = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)

    assert cache.remember("n1", now=now) is True
    assert cache.remember("n1", now=now) is False
    assert len(cache) == 1

    later = now + _dt.timedelta(minutes=10)
    assert cache.remember("n2", now=later) is True
    assert len(cache) == 1  # n1 evicted; a request carrying it is stale anyway


# ---------------------------------------------------------------------------
# The service decides containment, policy and identity for itself
# ---------------------------------------------------------------------------


def test_a_target_outside_the_services_roots_is_refused(client, temp_dir):
    outside = temp_dir.parent / "not-in-scope.txt"
    response = client.inspect_target(
        operation_id="op-outside",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(outside),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.REFUSED
    assert any("outside allowed roots" in r for r in response.refusals)


def test_path_traversal_out_of_the_root_is_refused(client, temp_dir):
    response = client.inspect_target(
        operation_id="op-traversal",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(temp_dir / ".." / ".." / "escaped.txt"),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.REFUSED


@pytest.mark.skipif(sys.platform != "win32", reason="Windows system paths")
def test_a_system_path_is_refused(client):
    """Refused by the service, whatever the caller claims about it."""
    response = client.inspect_target(
        operation_id="op-system",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path="C:\\Windows\\System32",
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.REFUSED


def test_a_non_allowlisted_policy_is_refused(client, temp_dir):
    target = temp_dir / "f.txt"
    target.write_text("x")
    response = client.inspect_target(
        operation_id="op-policy",
        policy_id="ERASURE.MADE.UP.V9",
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.REFUSED
    assert any("not allowlisted" in r for r in response.refusals)


def test_a_policy_incompatible_with_the_mode_is_refused(client, temp_dir):
    target = temp_dir / "f.txt"
    target.write_text("x")
    response = client.inspect_target(
        operation_id="op-mode",
        policy_id=SELECTIVE_POLICY,
        mode="COMPLETE_ERASURE",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.REFUSED
    assert any("does not support mode" in r for r in response.refusals)


def test_a_destructive_request_without_a_target_identity_is_refused(client, temp_dir):
    """Fail-closed: 'delete this path' is not a complete instruction."""
    target = temp_dir / "victim.txt"
    target.write_text("x")

    response = client.delete_file(
        operation_id="op-noidentity",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.REFUSED
    assert any("expected volume serial" in r for r in response.refusals)
    assert target.exists()


def test_a_substituted_file_is_refused(client, safe_validator, temp_dir):
    """The object at the path is no longer the object that was approved.

    This is the TOCTOU case: same name, different file. The boundary refuses
    before the engine is reached, and the engine checks again before it acts.
    """
    target = temp_dir / "victim.txt"
    target.write_text("original")
    serial, file_id = identity(safe_validator, target)

    if file_id is None:  # non-Windows: file identity is unavailable, not faked
        pytest.skip("File identity is not available on this platform")

    target.unlink()
    target.write_text("substituted")

    response = client.delete_file(
        operation_id="op-toctou",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
        expected_volume_serial=serial,
        expected_file_id=file_id,
    )

    assert response.status is ResponseStatus.REFUSED
    assert any("identity changed" in r for r in response.refusals)
    assert target.exists()


# ---------------------------------------------------------------------------
# Real operations
# ---------------------------------------------------------------------------


def test_delete_file_actually_deletes(client, safe_validator, temp_dir):
    target = temp_dir / "victim.txt"
    target.write_text("payload")
    serial, file_id = identity(safe_validator, target)

    response = client.delete_file(
        operation_id="op-delete",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
        expected_volume_serial=serial,
        expected_file_id=file_id,
    )

    assert response.status is ResponseStatus.COMPLETED
    assert response.result["status"] == "COMPLETED"
    assert not target.exists()


def test_delete_tree_actually_removes_the_tree(client, safe_validator, temp_dir):
    tree = temp_dir / "tree"
    tree.mkdir()
    (tree / "a.txt").write_text("a")
    (tree / "b.txt").write_text("b")
    serial, file_id = identity(safe_validator, tree)

    response = client.delete_tree(
        operation_id="op-tree",
        policy_id=TREE_POLICY,
        mode="COMPLETE_ERASURE",
        target_path=str(tree),
        target_type="directory",
        actor_id=ACTOR,
        expected_volume_serial=serial,
        expected_file_id=file_id,
    )

    assert response.status is ResponseStatus.COMPLETED
    assert not tree.exists()


def test_a_completed_response_reports_how_long_the_work_took(client, temp_dir):
    """Timing is recorded for later optimisation, as the brief asks."""
    target = temp_dir / "timed.txt"
    target.write_text("x")

    response = client.inspect_target(
        operation_id="op-timed",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.result["duration_seconds"] >= 0


# ---------------------------------------------------------------------------
# Restore never overwrites
# ---------------------------------------------------------------------------


def test_restore_refuses_an_existing_destination(vault_client, temp_dir):
    """A restore that overwrites is a destructive operation in disguise."""
    occupied = temp_dir / "already-here.txt"
    occupied.write_text("do not clobber me")

    response = vault_client.restore_recovery_object(
        operation_id="op-restore",
        policy_id=RECOVERABLE_POLICY,
        mode="CONTROLLED_RECOVERABLE",
        target_path=str(temp_dir),
        target_type="file",
        actor_id=ACTOR,
        params={"object_id": "obj-1", "destination_path": str(occupied)},
    )

    assert response.status is ResponseStatus.REFUSED
    assert any("never overwrites" in r for r in response.refusals)
    assert occupied.read_text() == "do not clobber me"


def test_restore_refuses_a_destination_outside_the_roots(vault_client, temp_dir):
    response = vault_client.restore_recovery_object(
        operation_id="op-restore-out",
        policy_id=RECOVERABLE_POLICY,
        mode="CONTROLLED_RECOVERABLE",
        target_path=str(temp_dir),
        target_type="file",
        actor_id=ACTOR,
        params={
            "object_id": "obj-1",
            "destination_path": str(temp_dir.parent / "escaped.txt"),
        },
    )
    assert response.status is ResponseStatus.REFUSED


def test_restore_without_a_configured_vault_reports_the_capability(client, temp_dir):
    """Not a crash and not a success: an explicit unavailable capability."""
    response = client.restore_recovery_object(
        operation_id="op-novault",
        policy_id=RECOVERABLE_POLICY,
        mode="CONTROLLED_RECOVERABLE",
        target_path=str(temp_dir),
        target_type="file",
        actor_id=ACTOR,
        params={
            "object_id": "obj-1",
            "destination_path": str(temp_dir / "restored.txt"),
        },
    )
    assert response.status is ResponseStatus.COMPLETED
    assert response.result["error"] == "VAULT_UNAVAILABLE"
    assert response.result["capability"] == CapabilityState.UNAVAILABLE.value


# ---------------------------------------------------------------------------
# Honest capability reporting
# ---------------------------------------------------------------------------


def test_media_sanitization_is_reported_unavailable(service):
    """The most important honest claim this system makes.

    This build performs no overwrite of any kind. A capability report implying
    sanitization would be the single most misleading thing it could say.
    """
    capability = next(
        c for c in service.capabilities() if c.name == "media_sanitization"
    )
    assert capability.state is CapabilityState.UNAVAILABLE
    assert "no overwrite" in capability.detail.lower()


def test_raw_volume_access_is_reported_unavailable(service):
    """The API process must not acquire raw physical-drive handles, and neither
    does the privileged service in this build - so recovery testing is
    filesystem-level and says so."""
    capability = next(c for c in service.capabilities() if c.name == "raw_volume_access")
    assert capability.state is CapabilityState.UNAVAILABLE


def test_vault_capability_follows_actual_configuration(service, vault_service):
    unconfigured = next(c for c in service.capabilities() if c.name == "recovery_vault")
    configured = next(
        c for c in vault_service.capabilities() if c.name == "recovery_vault"
    )
    assert unconfigured.state is CapabilityState.UNAVAILABLE
    assert configured.state is CapabilityState.SUPPORTED


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def test_in_process_transport_admits_it_provides_no_isolation(client):
    """Honesty a caller can assert on, rather than a deployment assumption."""
    assert client.isolated is False


def test_malformed_envelope_is_rejected_by_the_transport(service):
    from oblivion.privileged.transport import TransportError

    transport = InProcessTransport(service)
    with pytest.raises(TransportError, match="Malformed privileged request"):
        transport.exchange({"request": {"operation": "execute_command"}, "mac": "x"})


@pytest.mark.skipif(sys.platform != "win32", reason="Named pipes are Windows-only")
def test_unreachable_pipe_raises_service_unavailable():
    """Unreachable is not a refusal: the caller learned nothing about the request."""
    from oblivion.privileged.transport import (
        NamedPipeTransport,
        ServiceUnavailableError,
    )

    # A short connect budget: this pipe is genuinely absent rather than starting
    # up, so the test asserts the give-up path rather than the waiting path.
    transport = NamedPipeTransport(
        r"\\.\pipe\oblivion-does-not-exist", connect_timeout_seconds=0.2
    )
    with pytest.raises(ServiceUnavailableError):
        transport.exchange({"request": {}, "mac": ""})


@pytest.mark.skipif(sys.platform != "win32", reason="Named pipes are Windows-only")
def test_named_pipe_round_trip(service, authenticator, temp_dir):
    """A real request over a real pipe, in a second thread.

    Skipped rather than faked if the environment will not create the pipe: a
    passing simulation of IPC would prove nothing about IPC.
    """
    import ctypes
    import threading

    from oblivion.privileged.transport import (
        NamedPipeServer,
        NamedPipeTransport,
        TransportError,
    )

    pipe_name = rf"\\.\pipe\oblivion-test-{secrets.token_hex(6)}"
    target = temp_dir / "piped.txt"
    target.write_text("content")

    # The pipe is created on this thread before any client exists, so the test
    # asserts the exchange rather than racing service startup. Only the blocking
    # accept runs in the background.
    try:
        server = NamedPipeServer(service, pipe_name)
        handle = server.create_pipe(timeout_ms=10000)
    except TransportError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"Named pipe unavailable in this environment: {exc}")

    errors: list[BaseException] = []

    def serve() -> None:
        try:
            server.accept_once(handle)
        except BaseException as exc:  # noqa: BLE001 - reported to the main thread
            errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

    request = PrivilegedRequest.from_wire(
        wire_request(target_path=str(target), operation="inspect_target")
    )
    envelope = {"request": request.to_wire(), "mac": authenticator.sign(request)}

    try:
        payload = NamedPipeTransport(pipe_name).exchange(envelope)
    finally:
        thread.join(timeout=10)
        ctypes.windll.kernel32.CloseHandle(handle)

    assert not errors, f"server thread failed: {errors}"
    assert payload["status"] == ResponseStatus.COMPLETED.value
    assert payload["result"]["analysis"]


# ---------------------------------------------------------------------------
# Structural pins
# ---------------------------------------------------------------------------


def test_destructive_operations_are_exactly_the_ones_that_destroy():
    assert {o.value for o in DESTRUCTIVE_OPERATIONS} == {
        "delete_file",
        "delete_tree",
        "prepare_recovery_object",
    }


def test_a_refusal_always_explains_itself(service, authenticator, temp_dir):
    """An unexplained refusal is a bug, not a safe default.

    The pipeline above records refusals as evidence, and a refusal with no
    reason would produce an evidence record asserting that something was
    refused without saying what was wrong.
    """
    outside = temp_dir.parent / "nope.txt"
    request = PrivilegedRequest.from_wire(wire_request(target_path=str(outside)))
    response = service.handle(request, authenticator.sign(request))

    assert response.status is ResponseStatus.REFUSED
    assert response.refusals
    assert all(r.strip() for r in response.refusals)
