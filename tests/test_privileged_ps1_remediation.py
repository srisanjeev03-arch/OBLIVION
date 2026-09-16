"""PS-1: the privileged pipe cannot be squatted, and its answers cannot be forged.

Two defects, two controls, both exercised through real code:

* the server used to close and recreate its pipe after every request, so a
  local process could take the name in the gap. It now holds one instance for
  its whole life; the squat attempts below are made against the real pipe.
* responses were unauthenticated, so whoever held the endpoint decided what the
  API believed had happened. Every response is now MACed under a key derived
  from the IPC secret and bound to the digest of the request it answers.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import secrets
import sys
import threading

import pytest

from oblivion.core.evidence.canonicalize import canonicalize
from oblivion.privileged import (
    InProcessTransport,
    PrivilegedClient,
    PrivilegedClientError,
    PrivilegedOperation,
    PrivilegedRequest,
    PrivilegedResponse,
    PrivilegedService,
    RequestAuthenticator,
    ResponseAuthenticationError,
    ResponseStatus,
    ServiceConfig,
)
from oblivion.privileged.service import RESPONSE_KEY_LABEL, RESPONSE_MAC_DOMAIN

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
ACTOR = "user_operator_1"

#: Deterministic vector inputs. Never a deployment key.
VECTOR_KEY = bytes(range(32))
VECTOR_NONCE = "00112233445566778899aabbccddeeff"


def fixed_request(**overrides) -> PrivilegedRequest:
    fields = {
        "request_id": "req-vector-1",
        "nonce": VECTOR_NONCE,
        "operation": PrivilegedOperation.DELETE_FILE,
        "operation_id": "op-vector-1",
        "policy_id": SELECTIVE_POLICY,
        "mode": "SELECTIVE_PERMANENT",
        "target_path": "C:/scratch/victim.txt",
        "target_type": "file",
        "actor_id": ACTOR,
        "issued_at": _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc),
        "expected_volume_serial": "ABCD1234",
        "expected_file_id": (1, 2, 3),
    }
    fields.update(overrides)
    return PrivilegedRequest(**fields)


def fixed_response(request: PrivilegedRequest, **overrides) -> PrivilegedResponse:
    fields = {
        "request_id": request.request_id,
        "operation": request.operation,
        "operation_id": request.operation_id,
        "status": ResponseStatus.COMPLETED,
        "result": {
            "status": "COMPLETED",
            "successful": ["C:/scratch/victim.txt"],
            "evidence_id": "ev-1",
            "completed_at": "2026-01-01T00:00:01+00:00",
            "target_path": "C:/scratch/victim.txt",
            "duration_seconds": 0.25,
        },
    }
    fields.update(overrides)
    return PrivilegedResponse(**fields)


@pytest.fixture
def vector_auth() -> RequestAuthenticator:
    return RequestAuthenticator(VECTOR_KEY)


def over_json(payload: dict) -> dict:
    """What actually arrives through the pipe."""
    return json.loads(json.dumps(payload))


# ---------------------------------------------------------------------------
# Construction, pinned against an independent computation
# ---------------------------------------------------------------------------


def test_response_mac_matches_the_documented_construction(vector_auth):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))

    digest = hashlib.sha256(request.to_bytes()).hexdigest()
    body = {k: v for k, v in sealed.items() if k != "mac"}
    derived = hmac.new(VECTOR_KEY, RESPONSE_KEY_LABEL, hashlib.sha256).digest()
    expected = hmac.new(
        derived,
        canonicalize(
            {"domain": RESPONSE_MAC_DOMAIN, "request_digest": digest, "response": body}
        ),
        hashlib.sha256,
    ).hexdigest()

    assert body["nonce"] == VECTOR_NONCE
    assert body["request_digest"] == digest
    assert sealed["mac"] == expected


def test_response_mac_known_answer(vector_auth):
    """A fixed vector, so any change to the construction is a visible break."""
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    assert request.digest() == (
        "2cf489896c3432bae2f7cb413975cebaa2129671c29915ca91e598cac6466aaa"
    )
    assert sealed["mac"] == (
        "30b37fb0e6bb78347ca692bae20866c306389612b3d0c8c7de51815dfe2cdc62"
    )


def test_request_and_response_keys_are_separated(vector_auth):
    """The derived response key is not the IPC secret, and requests are unchanged."""
    request = fixed_request()
    derived = hmac.new(VECTOR_KEY, RESPONSE_KEY_LABEL, hashlib.sha256).digest()
    assert derived != VECTOR_KEY

    # Existing request authentication: HMAC under the secret itself.
    assert vector_auth.sign(request) == hmac.new(
        VECTOR_KEY, request.to_bytes(), hashlib.sha256
    ).hexdigest()

    # The same response input under the undifferentiated secret does not verify.
    sealed = vector_auth.seal_response(request, fixed_response(request))
    body = {k: v for k, v in sealed.items() if k != "mac"}
    wrong_key_mac = hmac.new(
        VECTOR_KEY,
        canonicalize(
            {
                "domain": RESPONSE_MAC_DOMAIN,
                "request_digest": request.digest(),
                "response": body,
            }
        ),
        hashlib.sha256,
    ).hexdigest()
    with pytest.raises(ResponseAuthenticationError, match="MAC does not verify"):
        vector_auth.verify_response(request, {**body, "mac": wrong_key_mac})


# ---------------------------------------------------------------------------
# Acceptance and rejection
# ---------------------------------------------------------------------------


def test_a_legitimate_response_is_accepted(vector_auth):
    request = fixed_request()
    response = fixed_response(request)
    sealed = over_json(vector_auth.seal_response(request, response))

    accepted = vector_auth.verify_response(request, sealed)
    assert accepted == response


def test_a_response_without_a_mac_is_rejected(vector_auth):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    unsealed = {k: v for k, v in sealed.items() if k != "mac"}
    for missing in (unsealed, {**sealed, "mac": ""}, {**sealed, "mac": None}):
        with pytest.raises(ResponseAuthenticationError, match="no MAC"):
            vector_auth.verify_response(request, missing)


@pytest.mark.parametrize("bad_mac", ["00" * 32, "zz", "é" * 64, "\ud800"])
def test_an_invalid_mac_is_rejected(vector_auth, bad_mac):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    with pytest.raises(ResponseAuthenticationError, match="MAC does not verify"):
        vector_auth.verify_response(request, {**sealed, "mac": bad_mac})


def test_a_response_with_another_nonce_is_rejected(vector_auth):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    with pytest.raises(ResponseAuthenticationError, match="nonce does not match"):
        vector_auth.verify_response(request, {**sealed, "nonce": "ff" * 16})


@pytest.mark.parametrize(
    ("field", "value"),
    [("request_id", "req-other"), ("operation_id", "op-other")],
)
def test_a_response_with_another_request_identity_is_rejected(vector_auth, field, value):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    with pytest.raises(ResponseAuthenticationError, match="request identity"):
        vector_auth.verify_response(request, {**sealed, field: value})


def test_a_response_for_another_operation_is_rejected(vector_auth):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    with pytest.raises(ResponseAuthenticationError, match="operation does not match"):
        vector_auth.verify_response(request, {**sealed, "operation": "inspect_target"})


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda b: b.update(status="FAILED"), id="status-failed"),
        pytest.param(lambda b: b.update(status="REFUSED"), id="status-refused"),
        pytest.param(
            lambda b: b["result"].update(reconciliation_required=True),
            id="reconciliation-required",
        ),
        pytest.param(lambda b: b["result"].update(evidence_id="ev-forged"), id="evidence"),
        pytest.param(
            lambda b: b["result"].update(completed_at="2030-01-01T00:00:00+00:00"),
            id="timestamp",
        ),
        pytest.param(
            lambda b: b["result"].update(target_path="C:/scratch/other.txt"),
            id="target-identity",
        ),
        pytest.param(lambda b: b["result"].update(duration_seconds=0.26), id="float"),
        pytest.param(lambda b: b.update(message="all good"), id="message"),
        pytest.param(lambda b: b.update(refusals=["x"]), id="refusals"),
    ],
)
def test_payload_tampering_is_rejected(vector_auth, tamper):
    request = fixed_request()
    sealed = over_json(vector_auth.seal_response(request, fixed_response(request)))
    tamper(sealed)
    with pytest.raises(ResponseAuthenticationError, match="MAC does not verify"):
        vector_auth.verify_response(request, sealed)


def test_a_fabricated_completion_cannot_replace_a_refusal(vector_auth):
    """The endpoint turns a genuine REFUSED into COMPLETED."""
    request = fixed_request()
    refused = fixed_response(
        request, status=ResponseStatus.REFUSED, result={}, refusals=("identity changed",)
    )
    sealed = over_json(vector_auth.seal_response(request, refused))
    sealed.update(status="COMPLETED", refusals=[], result={"status": "COMPLETED"})
    with pytest.raises(ResponseAuthenticationError, match="MAC does not verify"):
        vector_auth.verify_response(request, sealed)


def test_a_valid_response_cannot_answer_a_different_request(vector_auth):
    """Replay of a genuine answer, with and without copying the binding fields."""
    first = fixed_request()
    sealed = vector_auth.seal_response(first, fixed_response(first))

    # A different request: different nonce.
    second = fixed_request(nonce="ff" * 16, request_id="req-vector-2")
    with pytest.raises(ResponseAuthenticationError, match="nonce does not match"):
        vector_auth.verify_response(second, sealed)

    # Same nonce and identifiers, different content (another target): the
    # response is bound to the first request's digest and must not transfer.
    substituted = fixed_request(target_path="C:/scratch/other.txt")
    with pytest.raises(ResponseAuthenticationError, match="not bound to this request"):
        vector_auth.verify_response(substituted, sealed)

    # Rewriting the digest field to match does not help: the MAC covers it.
    rebound = {**sealed, "request_digest": substituted.digest()}
    with pytest.raises(ResponseAuthenticationError, match="MAC does not verify"):
        vector_auth.verify_response(substituted, rebound)


@pytest.mark.parametrize(
    "payload",
    [None, [], "COMPLETED", 42],
)
def test_a_non_object_response_is_rejected(vector_auth, payload):
    with pytest.raises(ResponseAuthenticationError, match="not a JSON object"):
        vector_auth.verify_response(fixed_request(), payload)


@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda b: b.update(extra="field"), id="unknown-field"),
        pytest.param(lambda b: b.update(result=None), id="null-result"),
        pytest.param(lambda b: b.update(refusals=None), id="null-refusals"),
        pytest.param(lambda b: b.update(message=7), id="non-string-message"),
        pytest.param(lambda b: b.update(protocol_version="OBLIVION-PRIV-0"), id="version"),
        pytest.param(lambda b: b.pop("protocol_version"), id="missing-version"),
        pytest.param(lambda b: b.pop("message"), id="missing-message"),
    ],
)
def test_a_response_outside_the_contract_is_rejected(vector_auth, tamper):
    """Even a correctly MACed body must reconstruct to exactly what was sent."""
    request = fixed_request()
    body = {
        k: v
        for k, v in vector_auth.seal_response(request, fixed_response(request)).items()
        if k != "mac"
    }
    tamper(body)
    # Re-MAC with the real key, so only the contract check can reject it.
    body["mac"] = vector_auth._response_mac(request.digest(), body)
    with pytest.raises(ResponseAuthenticationError, match="canonically reconstructed"):
        vector_auth.verify_response(request, body)


@pytest.mark.parametrize("status", ["DONE", None])
def test_a_malformed_status_is_rejected(vector_auth, status):
    request = fixed_request()
    sealed = vector_auth.seal_response(request, fixed_response(request))
    with pytest.raises(ResponseAuthenticationError, match="malformed"):
        vector_auth.verify_response(request, {**sealed, "status": status})


# ---------------------------------------------------------------------------
# End to end through the client
# ---------------------------------------------------------------------------


class ForgingEndpoint:
    """Holds the pipe endpoint but not the service key.

    It sees the request, so it can copy the nonce, identifiers and digest. It
    cannot produce a MAC under the real key.
    """

    isolated = True

    def __init__(self, status: ResponseStatus, result: dict, *, seal: bool) -> None:
        self._status = status
        self._result = result
        self._seal = seal
        self._forger = RequestAuthenticator(secrets.token_bytes(32))

    def exchange(self, envelope: dict) -> dict:
        request = PrivilegedRequest.from_wire(envelope["request"])
        forged = PrivilegedResponse(
            request_id=request.request_id,
            operation=request.operation,
            operation_id=request.operation_id,
            status=self._status,
            result=self._result,
        )
        if self._seal:
            return over_json(self._forger.seal_response(request, forged))
        return {**forged.to_wire(), "nonce": request.nonce, "request_digest": request.digest()}


@pytest.mark.parametrize("seal", [False, True], ids=["unsealed", "wrong-key"])
@pytest.mark.parametrize(
    ("status", "result"),
    [
        (ResponseStatus.COMPLETED, {"status": "COMPLETED", "successful": ["x"]}),
        (ResponseStatus.FAILED, {"reconciliation_required": True}),
        (ResponseStatus.REFUSED, {}),
    ],
    ids=["completed", "reconciliation-required", "refused"],
)
def test_a_forging_endpoint_is_never_believed(status, result, seal):
    client = PrivilegedClient(
        ForgingEndpoint(status, result, seal=seal),
        RequestAuthenticator(secrets.token_bytes(32)),
    )
    with pytest.raises(PrivilegedClientError, match="response rejected"):
        client.delete_file(
            operation_id="op-forged",
            policy_id=SELECTIVE_POLICY,
            mode="SELECTIVE_PERMANENT",
            target_path="C:/scratch/victim.txt",
            target_type="file",
            actor_id=ACTOR,
            expected_volume_serial="ABCD1234",
            expected_file_id=(1, 2, 3),
        )


class ReplayingEndpoint:
    """Answers every request with one captured, genuine response."""

    isolated = True

    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def exchange(self, envelope: dict) -> dict:
        return dict(self._captured)


def test_a_captured_genuine_response_cannot_be_replayed(safe_validator, temp_dir):
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    target = temp_dir / "readable.txt"
    target.write_text("content")

    kwargs = {
        "operation_id": "op-replay",
        "policy_id": SELECTIVE_POLICY,
        "mode": "SELECTIVE_PERMANENT",
        "target_path": str(target),
        "target_type": "file",
        "actor_id": ACTOR,
    }
    captured: dict = {}

    class Recording(InProcessTransport):
        def exchange(self, envelope):
            captured.update(super().exchange(envelope))
            return captured

    genuine = PrivilegedClient(Recording(service), authenticator).inspect_target(**kwargs)
    assert genuine.status is ResponseStatus.COMPLETED

    replayer = PrivilegedClient(ReplayingEndpoint(captured), authenticator)
    with pytest.raises(PrivilegedClientError, match="nonce does not match"):
        replayer.inspect_target(**kwargs)


def test_the_service_does_not_seal_answers_to_unauthenticated_requests(
    safe_validator,
):
    """No MAC is ever produced over input the service could not authenticate."""
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    request = fixed_request()

    reply = service.respond(request, "00" * 32)
    assert reply["status"] == ResponseStatus.REFUSED.value
    assert "mac" not in reply

    impostor = PrivilegedClient(
        InProcessTransport(service), RequestAuthenticator(secrets.token_bytes(32))
    )
    with pytest.raises(PrivilegedClientError, match="no MAC"):
        impostor.send(fixed_request(nonce=secrets.token_hex(16)))


def test_an_unconfigured_service_fails_closed_at_the_client(safe_validator):
    service = PrivilegedService(ServiceConfig(validator=safe_validator, authenticator=None))
    client = PrivilegedClient(
        InProcessTransport(service), RequestAuthenticator(secrets.token_bytes(32))
    )
    with pytest.raises(PrivilegedClientError, match="no MAC"):
        client.send(fixed_request())


def test_a_replayed_request_gets_a_refusal_bound_only_to_itself(
    safe_validator, temp_dir
):
    """Replay protection still refuses; the refusal is authentic but not portable."""
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    target = temp_dir / "readable.txt"
    target.write_text("content")
    request = fixed_request(
        operation=PrivilegedOperation.INSPECT_TARGET,
        target_path=str(target),
        issued_at=_dt.datetime.now(_dt.timezone.utc),
        expected_volume_serial=None,
        expected_file_id=None,
    )
    mac = authenticator.sign(request)

    first = authenticator.verify_response(request, over_json(service.respond(request, mac)))
    second = authenticator.verify_response(request, over_json(service.respond(request, mac)))
    assert first.status is ResponseStatus.COMPLETED
    assert second.status is ResponseStatus.REFUSED
    assert any("Nonce has already been used" in r for r in second.refusals)

    other = fixed_request(nonce="ab" * 16)
    with pytest.raises(ResponseAuthenticationError):
        authenticator.verify_response(other, service.respond(request, mac))


def test_an_unencodable_result_becomes_an_authenticated_failure(
    safe_validator, temp_dir, monkeypatch
):
    """Never an unauthenticated copy of the real result, never a silent success."""
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    monkeypatch.setitem(
        service._handlers,
        PrivilegedOperation.INSPECT_TARGET,
        lambda request, outcome: {"analysis": {1, 2}},
    )
    target = temp_dir / "readable.txt"
    target.write_text("content")

    client = PrivilegedClient(InProcessTransport(service), authenticator)
    response = client.inspect_target(
        operation_id="op-unencodable",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )
    assert response.status is ResponseStatus.FAILED
    assert response.result == {"reconciliation_required": True}


# ---------------------------------------------------------------------------
# The persistent pipe (Windows only - skipped, never simulated, elsewhere)
# ---------------------------------------------------------------------------

windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="Named pipes are Windows-only"
)


def _pipe_name() -> str:
    return rf"\\.\pipe\oblivion-test-{secrets.token_hex(6)}"


def _try_squat(pipe_name: str, max_instances: int) -> int:
    """Attempt CreateNamedPipeW with a default DACL; return 0 on success, else the error."""
    import ctypes

    from oblivion.privileged.transport import (
        _INVALID_HANDLE_VALUE,
        _declare_signatures,
    )

    _declare_signatures()
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateNamedPipeW(
        pipe_name, 0x00000003, 0, max_instances, 4096, 4096, 0, None
    )
    if handle != _INVALID_HANDLE_VALUE and handle:
        kernel32.CloseHandle(handle)
        return 0
    return int(kernel32.GetLastError())


@pytest.fixture
def pipe_service(safe_validator):
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    return service, authenticator


def _start(server, connections: int):
    errors: list[BaseException] = []

    def run() -> None:
        try:
            server.serve_forever(max_connections=connections)
        except BaseException as exc:  # noqa: BLE001 - reported to the main thread
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def _inspect(client, target):
    return client.inspect_target(
        operation_id="op-pipe",
        policy_id=SELECTIVE_POLICY,
        mode="SELECTIVE_PERMANENT",
        target_path=str(target),
        target_type="file",
        actor_id=ACTOR,
    )


@windows_only
def test_the_pipe_survives_many_requests_and_cannot_be_squatted(
    pipe_service, temp_dir, monkeypatch
):
    """The PS-1 reproduction, inverted: every squat attempt between requests fails."""
    from oblivion.privileged.transport import (
        _ERROR_PIPE_BUSY,
        NamedPipeServer,
        NamedPipeTransport,
    )

    service, authenticator = pipe_service
    name = _pipe_name()
    server = NamedPipeServer(service, name)

    creations: list[int] = []
    real_create = server.create_pipe

    def counting_create(timeout_ms: int = 5000) -> int:
        handle = real_create(timeout_ms)
        creations.append(handle)
        return handle

    monkeypatch.setattr(server, "create_pipe", counting_create)
    handle = server.open(timeout_ms=10000)

    target = temp_dir / "piped.txt"
    target.write_text("content")
    requests = 4
    thread, errors = _start(server, requests)
    client = PrivilegedClient(NamedPipeTransport(name), authenticator)

    try:
        for index in range(requests):
            assert _try_squat(name, 1) == _ERROR_PIPE_BUSY
            assert _try_squat(name, 255) == _ERROR_PIPE_BUSY
            response = _inspect(client, target)
            assert response.status is ResponseStatus.COMPLETED
            if index == requests - 1:
                break  # the bounded loop now shuts down, which may release the name
            # Between requests: the old close/recreate gap. Still the same instance.
            assert server.handle == handle
            assert _try_squat(name, 1) == _ERROR_PIPE_BUSY
            assert _try_squat(name, 255) == _ERROR_PIPE_BUSY
    finally:
        thread.join(timeout=10)

    assert not errors, f"server thread failed: {errors}"
    assert creations == [handle], "the pipe must be created exactly once"
    assert server.handle is None  # closed on shutdown, and only then


@windows_only
def test_a_name_squatted_before_startup_is_refused_not_joined(pipe_service):
    import ctypes

    from oblivion.privileged.transport import (
        _INVALID_HANDLE_VALUE,
        NamedPipeServer,
        TransportError,
        _declare_signatures,
    )

    _declare_signatures()
    kernel32 = ctypes.windll.kernel32
    name = _pipe_name()
    squatter = kernel32.CreateNamedPipeW(name, 0x00000003, 0, 255, 4096, 4096, 0, None)
    assert squatter != _INVALID_HANDLE_VALUE and squatter
    try:
        server = NamedPipeServer(pipe_service[0], name)
        with pytest.raises(TransportError, match="CreateNamedPipeW failed"):
            server.open()
        assert server.handle is None
    finally:
        kernel32.CloseHandle(squatter)


@windows_only
def test_malformed_and_broken_exchanges_do_not_end_the_service(pipe_service, temp_dir):
    """Per-connection failures are answered or logged; the same instance serves on."""
    import ctypes

    from oblivion.privileged.transport import (
        NamedPipeServer,
        NamedPipeTransport,
        _encode,
        _read_framed,
        _write_all,
    )

    service, authenticator = pipe_service
    name = _pipe_name()
    server = NamedPipeServer(service, name)
    handle = server.open(timeout_ms=10000)
    thread, errors = _start(server, 4)
    kernel32 = ctypes.windll.kernel32

    def raw_connect() -> int:
        transport = NamedPipeTransport(name)
        return transport._connect()

    target = temp_dir / "piped.txt"
    target.write_text("content")
    client = PrivilegedClient(NamedPipeTransport(name), authenticator)

    try:
        # 1. A malformed request is refused structurally - and, having no
        #    authenticated request to bind to, the refusal is unsealed.
        raw = raw_connect()
        try:
            _write_all(raw, _encode({"request": {"operation": "execute_command"}, "mac": "x"}))
            reply = _read_framed(raw)
        finally:
            kernel32.CloseHandle(raw)
        assert reply["status"] == ResponseStatus.REFUSED.value
        assert "mac" not in reply

        # 2. A truncated frame: the server's read fails; it logs and continues.
        raw = raw_connect()
        _write_all(raw, b"\x00\x00")
        kernel32.CloseHandle(raw)

        # 3. A declared length over the cap is refused before allocation.
        raw = raw_connect()
        try:
            _write_all(raw, (2 * 1024 * 1024).to_bytes(4, "big"))
            reply = _read_framed(raw)
        finally:
            kernel32.CloseHandle(raw)
        assert reply["status"] == ResponseStatus.REFUSED.value

        # 4. The same instance still serves an authenticated request.
        assert server.handle == handle
        assert _inspect(client, target).status is ResponseStatus.COMPLETED
    finally:
        thread.join(timeout=10)

    assert not errors, f"server thread failed: {errors}"


@windows_only
def test_an_unusable_instance_stops_the_server_without_recreating_it(
    pipe_service, monkeypatch
):
    from oblivion.privileged.transport import NamedPipeServer, PipeInstanceError

    server = NamedPipeServer(pipe_service[0], _pipe_name())
    creations: list[int] = []
    monkeypatch.setattr(server, "create_pipe", lambda *a, **k: creations.append(1) or 0)
    server._handle = 0  # an invalid handle: ConnectNamedPipe fails outright

    with pytest.raises(PipeInstanceError, match="ConnectNamedPipe failed"):
        server.serve_forever(max_connections=5)
    assert creations == []
    assert server.handle is None


@windows_only
def test_the_pipe_keeps_its_restrictive_dacl(pipe_service):
    """Protected DACL; only SYSTEM, Administrators and the creating account."""
    import ctypes
    from ctypes import wintypes

    from oblivion.privileged.transport import NamedPipeServer, current_user_sid

    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32
    advapi32.GetSecurityInfo.restype = wintypes.DWORD
    advapi32.GetSecurityInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_wchar_p),
        ctypes.c_void_p,
    ]
    se_kernel_object, dacl_information = 6, 0x4

    server = NamedPipeServer(pipe_service[0], _pipe_name())
    handle = server.open()
    try:
        dacl = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        assert advapi32.GetSecurityInfo(
            handle, se_kernel_object, dacl_information, None, None,
            ctypes.byref(dacl), None, ctypes.byref(descriptor),
        ) == 0
        text = ctypes.c_wchar_p()
        try:
            assert advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                descriptor, 1, dacl_information, ctypes.byref(text), None
            )
            sddl = str(text.value)
        finally:
            kernel32.LocalFree(descriptor)
            if text:
                kernel32.LocalFree(ctypes.cast(text, ctypes.c_void_p))
    finally:
        server.close()

    assert sddl.startswith("D:P"), sddl
    trustees = {ace.rstrip(")").split(";")[-1] for ace in sddl[3:].split("(") if ace}
    assert trustees == {"SY", "BA", current_user_sid()}, sddl
    assert "WD" not in sddl and "AU" not in sddl and "BU" not in sddl
