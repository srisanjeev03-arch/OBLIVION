"""Phase 25: the pipeline endpoint, exercised through the real API.

The endpoint takes no request body on purpose, and several of these tests exist
to prove that the absence is load-bearing: a caller cannot name a different
target, cannot name a different actor, and cannot assert an outcome, because
there is nowhere to put any of those things.

Everything else here is the ordinary security surface - authentication,
authorization, and what happens when the privileged service is not configured.
"""

from __future__ import annotations

import os
import secrets
import uuid

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.api.dependencies import reset_signing_key_manager
from oblivion.certificate.keys import SigningKeyManager, generate_private_key_hex
from oblivion.certificate.trust_model import ENV_TRUSTED_SIGNERS
from oblivion.core.state.machine import State
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged import client as client_module

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
SIGNER_ID = "oblivion-issuer"
REQUESTER = "user_investigator_1"
APPROVER = "user_admin_1"


@pytest.fixture(autouse=True)
def configured_backend(monkeypatch, temp_dir):
    """A deployment configured the way a real one would be.

    Scoping is done with ``OBLIVION_ALLOWED_ROOTS`` rather than a dependency
    override, for two reasons. The shared ``authenticate_as_role`` helper calls
    ``app.dependency_overrides.clear()`` after logging in, so an override set
    here would be silently wiped by whichever role-client fixture the test
    requests. And the privileged service builds its own validator from the
    environment, so the env var is what makes the *service's* roots match the
    API's - which is the arrangement a real deployment has.

    Every secret is generated for this test. Nothing is hard-coded, and nothing
    survives the test.
    """
    init_db()
    monkeypatch.setenv("OBLIVION_ALLOWED_ROOTS", str(temp_dir))
    monkeypatch.setenv("OBLIVION_IPC_KEY", secrets.token_hex(32))

    material = generate_private_key_hex()
    monkeypatch.setenv("OBLIVION_SIGNING_KEY", material)
    manager = SigningKeyManager.from_material(material)
    monkeypatch.setenv(
        ENV_TRUSTED_SIGNERS, f"{SIGNER_ID}:{manager.public_key_bytes().hex()}"
    )

    reset_signing_key_manager()
    yield
    reset_signing_key_manager()


def create_operation(target_path, *, state=State.READY.name, approver=APPROVER):
    """Persist a target and an operation in the given approval state."""
    suffix = uuid.uuid4().hex[:8]
    session_factory = get_session_factory()
    with session_factory() as session:
        repo = OperationRepository(session)
        repo.create_target(
            target_id=f"tgt_{suffix}",
            path=str(target_path),
            canonical_path=str(target_path),
            target_type="file",
        )
        repo.create_operation(
            operation_id=f"op_{suffix}",
            target_id=f"tgt_{suffix}",
            mode="SELECTIVE_PERMANENT",
            policy_id=SELECTIVE_POLICY,
            state=state,
            requested_by=REQUESTER,
            approved_by=approver,
        )
        session.commit()
    return f"op_{suffix}"


# ---------------------------------------------------------------------------
# Authentication and authorization
# ---------------------------------------------------------------------------


def test_pipeline_requires_authentication(temp_dir):
    """An anonymous caller cannot run a destructive pipeline."""
    target = temp_dir / "anon.txt"
    target.write_text("must survive")
    operation_id = create_operation(target)

    anonymous = TestClient(app)
    response = anonymous.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 401
    assert target.exists()


def test_pipeline_forbidden_without_the_permission(viewer_client, temp_dir):
    """VIEWER cannot execute operations, and the file proves it."""
    target = temp_dir / "viewer.txt"
    target.write_text("must survive")
    operation_id = create_operation(target)

    response = viewer_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 403
    assert target.exists()


def test_auditor_cannot_execute(auditor_client, temp_dir):
    """Read-heavy roles are still not execution roles."""
    target = temp_dir / "auditor.txt"
    target.write_text("must survive")
    operation_id = create_operation(target)

    response = auditor_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 403
    assert target.exists()


# ---------------------------------------------------------------------------
# The happy path, through HTTP
# ---------------------------------------------------------------------------


def test_an_approved_operation_runs_the_whole_loop(operator_client, temp_dir):
    """The end-to-end demonstration, driven entirely through the API."""
    target = temp_dir / "certified.txt"
    target.write_text("sensitive payload")
    operation_id = create_operation(target)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 200
    body = response.json()

    assert not target.exists()
    assert body["final_state"] == "COMPLETED"
    assert body["evidence_id"]
    assert body["certificate_id"]
    assert body["verification_status"] == "VALID"

    stages = {s["stage"]: s["status"] for s in body["stages"]}
    for stage in (
        "DISCOVER",
        "BASELINE",
        "AUTHORIZE",
        "ERASE",
        "VALIDATE",
        "TEST_RECOVERY",
        "ANALYZE_RESIDUALS",
        "ASSESS_ASSURANCE",
        "GENERATE_EVIDENCE",
        "ISSUE_CERTIFICATE",
        "VERIFY_CERTIFICATE",
    ):
        assert stages[stage] == "COMPLETED", f"{stage} was {stages[stage]}"


def test_the_response_states_whether_privilege_was_isolated(operator_client, temp_dir):
    """A deployment check should be able to see this rather than assume it.

    In this test the service runs in-process, so the honest answer is False.
    """
    target = temp_dir / "isolation.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()
    assert body["privilege_isolated"] is False


def test_the_response_exposes_what_was_actually_searched(operator_client, temp_dir):
    """Coverage is explicit on the wire, not inferable from an empty list.

    Audit finding M-2: a client reading only `assurance_status` could not tell a
    complete search from a single weak method. The coverage block names both the
    per-analysis state and the individual methods and scanners.
    """
    target = temp_dir / "coverage.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()
    coverage = body["coverage"]

    assert coverage["residual_analysis"] in (
        "NOT_PERFORMED",
        "UNAVAILABLE",
        "INCONCLUSIVE",
        "PARTIAL",
        "PERFORMED",
    )
    assert coverage["recovery_test"] in (
        "NOT_PERFORMED",
        "UNAVAILABLE",
        "INCONCLUSIVE",
        "PARTIAL",
        "PERFORMED",
    )

    methods = coverage["recovery_methods"]
    # The methods this build cannot perform are named, not silently omitted.
    assert "mft_record" in methods["unavailable"]
    assert "unallocated_carving" in methods["unavailable"]
    assert "filesystem_enumeration" in methods["attempted"]
    # Attempted is a strict subset of supported plus nothing invented.
    assert set(methods["attempted"]) <= set(methods["supported"])
    assert not set(methods["attempted"]) & set(methods["unavailable"])

    scanners = coverage["residual_scanners"]
    assert scanners["supported"], "scanner coverage must be reported by name"


def test_limitations_travel_with_the_result(operator_client, temp_dir):
    """The frontend must be able to render what was *not* established."""
    target = temp_dir / "limits.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()
    joined = " ".join(body["limitations"]).lower()

    assert "no overwrite" in joined
    assert "raw volume access" in joined


# ---------------------------------------------------------------------------
# The absence of a request body is load-bearing
# ---------------------------------------------------------------------------


def test_a_supplied_target_path_cannot_redirect_the_erasure(operator_client, temp_dir):
    """The target comes from the persisted operation, not from the caller.

    A caller that names another file must not be able to have it erased under
    an approval granted for something else. There is no field for it, and this
    proves the body is ignored rather than merely undocumented.
    """
    approved = temp_dir / "approved-target.txt"
    approved.write_text("this one was approved")
    bystander = temp_dir / "innocent-bystander.txt"
    bystander.write_text("this one was not")

    operation_id = create_operation(approved)

    response = operator_client.post(
        f"/api/operations/{operation_id}/pipeline",
        json={"target_path": str(bystander), "actor_id": "somebody-else"},
    )

    assert response.status_code == 200
    assert not approved.exists()  # the approved target was erased
    assert bystander.exists()  # the named one was not touched
    assert bystander.read_text() == "this one was not"


def test_the_client_cannot_assert_an_outcome(operator_client, temp_dir):
    """No request field can talk the server into a verdict it did not compute."""
    target = temp_dir / "verdict.txt"
    target.write_text("payload")
    operation_id = create_operation(target, state=State.PENDING_APPROVAL.name)

    body = operator_client.post(
        f"/api/operations/{operation_id}/pipeline",
        json={
            "final_state": "COMPLETED",
            "verification_status": "VALID",
            "certificate_id": "cert_fake",
        },
    ).json()

    assert body["final_state"] == "FAILED"
    assert body["certificate_id"] is None
    assert target.exists()


# ---------------------------------------------------------------------------
# Refusals and conflicts
# ---------------------------------------------------------------------------


def test_an_unapproved_operation_is_refused_at_the_authorize_stage(
    operator_client, temp_dir
):
    """Holding operation.execute is necessary but not sufficient."""
    target = temp_dir / "unapproved.txt"
    target.write_text("must survive")
    operation_id = create_operation(target, state=State.PENDING_APPROVAL.name)

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()
    stages = {s["stage"]: s["status"] for s in body["stages"]}

    assert stages["AUTHORIZE"] == "REFUSED"
    assert stages["ERASE"] == "SKIPPED"
    assert body["certificate_id"] is None
    assert target.exists()


def test_a_self_approved_operation_is_refused(operator_client, temp_dir):
    """Separation of duties survives the trip through HTTP."""
    target = temp_dir / "self.txt"
    target.write_text("must survive")
    operation_id = create_operation(target, approver=REQUESTER)

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()
    authorize = next(s for s in body["stages"] if s["stage"] == "AUTHORIZE")

    assert authorize["status"] == "REFUSED"
    assert "Separation of duties" in authorize["detail"]
    assert target.exists()


def test_an_unknown_operation_is_404(operator_client):
    response = operator_client.post("/api/operations/op_does_not_exist/pipeline")
    assert response.status_code == 404


def test_a_concluded_operation_is_not_run_again(operator_client, temp_dir):
    """One act, one certificate. Re-running would produce a second."""
    target = temp_dir / "already-done.txt"
    target.write_text("payload")
    operation_id = create_operation(target, state=State.COMPLETED.name)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 409
    assert response.json()["error_code"] == "OPERATION_ALREADY_CONCLUDED"
    assert target.exists()


def test_running_twice_is_refused_the_second_time(operator_client, temp_dir):
    """The guard holds against a real first run, not just a seeded state."""
    target = temp_dir / "twice.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    first = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    second = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert first.status_code == 200
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# Service availability
# ---------------------------------------------------------------------------


def test_without_an_ipc_key_the_endpoint_refuses(operator_client, temp_dir, monkeypatch):
    """No authentication for privileged work means no privileged work.

    503 rather than a quiet in-process fallback with an invented key: a
    deployment that forgot to configure IPC must fail loudly.
    """
    monkeypatch.delenv("OBLIVION_IPC_KEY", raising=False)

    target = temp_dir / "no-ipc.txt"
    target.write_text("must survive")
    operation_id = create_operation(target)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 503
    assert response.json()["error_code"] == "PRIVILEGED_SERVICE_UNAVAILABLE"
    assert target.exists()


def test_without_a_signing_key_the_endpoint_refuses(
    operator_client, temp_dir, monkeypatch
):
    """Fail-closed, and before anything destructive happens."""
    monkeypatch.delenv("OBLIVION_SIGNING_KEY", raising=False)
    monkeypatch.delenv("OBLIVION_SIGNING_KEY_FILE", raising=False)
    reset_signing_key_manager()

    target = temp_dir / "no-signing.txt"
    target.write_text("must survive")
    operation_id = create_operation(target)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 500
    assert response.json()["error_code"] == "SIGNING_KEY_UNAVAILABLE"
    assert target.exists()


# ---------------------------------------------------------------------------
# Replay protection, through the real HTTP dependency path (audit finding M-1)
# ---------------------------------------------------------------------------


class _ReplayableNonces:
    """A deterministic nonce source that can be rewound.

    Replaces ``new_nonce`` so a second HTTP request draws exactly the same
    sequence the first one did. That is what makes a replay reproducible through
    the real endpoint: the client mints nonces internally, so a test cannot
    otherwise choose them.
    """

    def __init__(self) -> None:
        self.index = 0

    def __call__(self) -> str:
        self.index += 1
        return f"replaytest{self.index:04d}"

    def rewind(self) -> None:
        self.index = 0


def test_the_replay_cache_is_shared_across_http_requests(operator_client, temp_dir):
    """The application holds one cache, not one per request.

    This is the direct statement of audit finding M-1. Before the fix the
    dependency built a new service - and a new empty cache - for every request,
    so the identity asserted here was false.
    """
    first = operator_client.app.state.privileged_replay_cache
    target = temp_dir / "shared-cache.txt"
    target.write_text("payload")
    operator_client.post(f"/api/operations/{create_operation(target)}/pipeline")
    second = operator_client.app.state.privileged_replay_cache

    assert first is second
    assert len(second) > 0, "the request should have recorded nonces in it"


def test_a_replayed_nonce_is_refused_across_two_http_requests(
    operator_client, temp_dir, monkeypatch
):
    """The end-to-end proof that replay protection survives the request boundary.

    Request 1 runs normally and its nonces are recorded. The nonce source is then
    rewound so request 2 presents the *same* nonces to the privileged service.
    Every privileged call in request 2 must be refused as a replay - and, the
    part that actually matters, its target must survive untouched.
    """
    nonces = _ReplayableNonces()
    monkeypatch.setattr(client_module, "new_nonce", nonces)

    first_target = temp_dir / "replay-first.txt"
    first_target.write_text("payload one")
    second_target = temp_dir / "replay-second.txt"
    second_target.write_text("payload two")

    # Request 1: ordinary, successful operation.
    nonces.rewind()
    first = operator_client.post(
        f"/api/operations/{create_operation(first_target)}/pipeline"
    )
    assert first.status_code == 200
    assert first.json()["final_state"] == "COMPLETED"
    assert not first_target.exists()

    # Request 2: same nonce sequence, different operation and target.
    nonces.rewind()
    second = operator_client.post(
        f"/api/operations/{create_operation(second_target)}/pipeline"
    )
    assert second.status_code == 200
    body = second.json()

    stages = {s["stage"]: s for s in body["stages"]}
    assert stages["ERASE"]["status"] == "REFUSED"
    assert "Nonce has already been used" in stages["ERASE"]["detail"]

    # The security-relevant outcome: nothing was destroyed by the replay.
    assert second_target.exists()
    assert second_target.read_text() == "payload two"
    assert body["certificate_id"] is None
    assert body["final_state"] != "COMPLETED"


def test_a_fresh_nonce_still_works_after_a_replay_was_refused(
    operator_client, temp_dir, monkeypatch
):
    """Replay refusal must not wedge the service for legitimate callers."""
    nonces = _ReplayableNonces()
    monkeypatch.setattr(client_module, "new_nonce", nonces)

    first_target = temp_dir / "recover-first.txt"
    first_target.write_text("one")
    replay_target = temp_dir / "recover-replay.txt"
    replay_target.write_text("two")
    fresh_target = temp_dir / "recover-fresh.txt"
    fresh_target.write_text("three")

    nonces.rewind()
    operator_client.post(f"/api/operations/{create_operation(first_target)}/pipeline")

    nonces.rewind()  # replayed - must be refused
    operator_client.post(f"/api/operations/{create_operation(replay_target)}/pipeline")
    assert replay_target.exists()

    # No rewind: the sequence continues into values never seen before.
    fresh = operator_client.post(
        f"/api/operations/{create_operation(fresh_target)}/pipeline"
    )
    assert fresh.status_code == 200
    assert fresh.json()["final_state"] == "COMPLETED"
    assert not fresh_target.exists()


def test_no_private_key_material_appears_in_the_response(operator_client, temp_dir):
    """The response carries public material only."""
    target = temp_dir / "nokey.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    private_hex = os.environ["OBLIVION_SIGNING_KEY"]
    assert private_hex not in response.text
    assert "private" not in response.text.lower()
