"""A-1 and A-2: an approval binds to an object, and refusals are recorded.

**A-2.** The identity a destructive step checks against used to be read from the
filesystem moments before acting, so the comparison was between the object and
itself. A file swapped in after approval was therefore erased as though it were
the approved one. The identity is now observed when the target is analysed,
persisted on the target row, and that stored value - which predates the approval
- is what the erase step is held to.

**A-1.** Every refusal on ``POST /api/operations/{id}/execute`` used to return an
error and write nothing, so the log could not answer "did anyone try to execute
an unapproved operation?". Each refusal now records
``OPERATION_EXECUTION_REFUSED`` with outcome ``REFUSED``.

The attack test keeps the **path identical** throughout. Only the object at that
path changes, which is the whole point: a check that compares paths would pass
it, and did.

Everything runs against the real API, the real validator, the real engine and
the real privileged boundary. Files live in the per-test scratch directory and
nothing outside it is touched.
"""

from __future__ import annotations

import secrets
import uuid

import pytest
from fastapi.testclient import TestClient

from oblivion.api import app
from oblivion.api.dependencies import reset_signing_key_manager
from oblivion.certificate.keys import SigningKeyManager, generate_private_key_hex
from oblivion.certificate.trust_model import ENV_TRUSTED_SIGNERS
from oblivion.core.safety.paths import SafePathValidator, decode_file_id, encode_file_id
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
SIGNER_ID = "oblivion-issuer"


@pytest.fixture(autouse=True)
def configured_backend(monkeypatch, temp_dir):
    """A deployment configured the way a real one is.

    Scoped through ``OBLIVION_ALLOWED_ROOTS`` rather than a dependency override,
    because the shared role-client helper clears overrides after logging in and
    because the privileged service builds its own validator from the
    environment. Every secret is generated here and survives nothing.
    """
    init_db()
    monkeypatch.setenv("OBLIVION_ALLOWED_ROOTS", str(temp_dir))
    monkeypatch.setenv("OBLIVION_IPC_KEY", secrets.token_hex(32))
    monkeypatch.setenv("OBLIVION_VAULT_KEY", secrets.token_hex(32))

    material = generate_private_key_hex()
    monkeypatch.setenv("OBLIVION_SIGNING_KEY", material)
    manager = SigningKeyManager.from_material(material)
    monkeypatch.setenv(
        ENV_TRUSTED_SIGNERS, f"{SIGNER_ID}:{manager.public_key_bytes().hex()}"
    )
    reset_signing_key_manager()
    yield
    reset_signing_key_manager()


# ---------------------------------------------------------------------------
# Helpers - the real journey, through the real endpoints
# ---------------------------------------------------------------------------


def write_target(temp_dir, name="approved_object.txt", body="the approved payload"):
    path = temp_dir / f"{uuid.uuid4().hex[:8]}_{name}"
    path.write_text(body, encoding="utf-8")
    return path


def analyze(investigator_client, path):
    """Analyse through the real route, which is what records the identity."""
    response = investigator_client.post("/api/targets/analyze", json={"path": str(path)})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def request_operation(investigator_client, target_id):
    response = investigator_client.post(
        "/api/operations",
        json={
            "target_id": target_id,
            "mode": "SELECTIVE_PERMANENT",
            "policy_id": SELECTIVE_POLICY,
            "confirmation": {"acknowledged_risk": True},
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def approve(admin_client, operation_id):
    response = admin_client.post(f"/api/operations/{operation_id}/approve")
    assert response.status_code == 200, response.text


def approved_operation(investigator_client, admin_client, path):
    """Analyse, request and approve. Returns (operation_id, target_id)."""
    target_id = analyze(investigator_client, path)
    operation_id = request_operation(investigator_client, target_id)
    approve(admin_client, operation_id)
    return operation_id, target_id


def stored_target(target_id):
    """Read the persisted target back in a session of its own."""
    with get_session_factory()() as session:
        target = OperationRepository(session).get_target(target_id)
        assert target is not None
        return {
            "volume_serial": target.volume_serial,
            "file_id": target.file_id,
            "canonical_path": target.canonical_path,
        }


def substitute(path, body="a DIFFERENT object at the very same path"):
    """Replace the object at ``path``. The path does not change; the object does."""
    path.unlink()
    path.write_text(body, encoding="utf-8")
    return path


def audit_events(auditor_client, operation_id):
    response = auditor_client.get(
        "/api/audit/events", params={"operation_id": operation_id, "limit": 100}
    )
    assert response.status_code == 200, response.text
    return response.json()["events"]


def operation_state(client, operation_id):
    response = client.get(f"/api/operations/{operation_id}")
    assert response.status_code == 200, response.text
    return response.json()["state"]


# ---------------------------------------------------------------------------
# Provenance: the identity exists, and it comes from analysis
# ---------------------------------------------------------------------------


def test_analysis_records_the_target_identity(investigator_client, temp_dir):
    """The value the whole fix rests on is written where it can outlive a request."""
    path = write_target(temp_dir)
    target_id = analyze(investigator_client, path)

    stored = stored_target(target_id)
    assert stored["volume_serial"] is not None
    assert stored["file_id"] is not None
    assert decode_file_id(stored["file_id"]) is not None


def test_the_recorded_identity_is_the_identity_of_that_object(
    investigator_client, temp_dir
):
    path = write_target(temp_dir)
    target_id = analyze(investigator_client, path)

    validator = SafePathValidator(allowed_roots=[str(temp_dir)])
    stored = stored_target(target_id)
    assert stored["volume_serial"] == validator.get_volume_serial(str(path))
    assert stored["file_id"] == encode_file_id(validator._get_file_id(str(path)))


def test_the_identity_survives_a_database_reload(investigator_client, temp_dir):
    """Not an in-memory object: read it back through a brand new session."""
    path = write_target(temp_dir)
    target_id = analyze(investigator_client, path)
    first = stored_target(target_id)

    # A separate session factory call - nothing from the analysis request is
    # still in scope, so anything read here came from the database.
    second = stored_target(target_id)
    assert second == first
    assert second["volume_serial"] is not None and second["file_id"] is not None


def test_re_analysing_does_not_overwrite_a_recorded_identity(
    investigator_client, temp_dir
):
    """The stored identity must predate the approval, so nothing may refresh it.

    Re-analysing the same unchanged object returns the same target, and the row
    keeps the identity it was created with. If a later analysis could rewrite
    it, an attacker could refresh the expectation to match a substitution.
    """
    path = write_target(temp_dir)
    target_id = analyze(investigator_client, path)
    before = stored_target(target_id)

    again = analyze(investigator_client, path)
    assert again == target_id
    assert stored_target(target_id) == before


# ---------------------------------------------------------------------------
# A-2: the attack, against the pipeline endpoint
# ---------------------------------------------------------------------------


def test_substituting_the_object_after_approval_is_refused_by_the_pipeline(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    """The exact attack the audit demonstrated. Same path, different object."""
    path = write_target(temp_dir)
    operation_id, target_id = approved_operation(investigator_client, admin_client, path)
    original = stored_target(target_id)

    substitute(path)
    assert path.exists(), "the substituted object must be in place for the attack"

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert response.status_code == 200, response.text
    body = response.json()

    erase = next(s for s in body["stages"] if s["stage"] == "ERASE")
    assert erase["status"] == "REFUSED", erase
    assert "not the object that was approved" in erase["detail"]

    # The substituted object survives, with its content intact.
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "a DIFFERENT object at the very same path"

    # The operation did not become a success.
    assert body["final_state"] != "COMPLETED"
    assert operation_state(operator_client, operation_id) != "COMPLETED"

    # Nothing claims an execution happened.
    events = audit_events(auditor_client, operation_id)
    assert not [e for e in events if e["event_type"] == "OPERATION_EXECUTED"]
    concluded = [e for e in events if e["event_type"] == "PIPELINE_CONCLUDED"]
    assert concluded and concluded[0]["outcome"] == "REFUSED"

    # And the identity that was checked is still the one recorded at analysis.
    assert stored_target(target_id) == original


def test_a_refused_substitution_issues_no_certificate(
    investigator_client, admin_client, operator_client, temp_dir
):
    """A rejected execution stays rejected all the way through the state machine."""
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    substitute(path)

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()

    assert body.get("certificate_id") is None
    assert body["final_state"] != "COMPLETED"
    for stage_name in ("TEST_RECOVERY", "ANALYZE_RESIDUALS", "ISSUE_CERTIFICATE"):
        stage = next((s for s in body["stages"] if s["stage"] == stage_name), None)
        if stage is not None:
            assert stage["status"] != "COMPLETED", stage


# ---------------------------------------------------------------------------
# A-2: the attack, against the execute endpoint
# ---------------------------------------------------------------------------


def test_substituting_the_object_after_approval_is_refused_by_execute(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    substitute(path)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == "TARGET_IDENTITY_MISMATCH"

    assert path.exists()
    assert path.read_text(encoding="utf-8") == "a DIFFERENT object at the very same path"
    assert operation_state(operator_client, operation_id) != "COMPLETED"

    events = audit_events(auditor_client, operation_id)
    refusals = [e for e in events if e["event_type"] == "OPERATION_EXECUTION_REFUSED"]
    assert refusals, "the refused execution must be recorded"
    assert refusals[0]["outcome"] == "REFUSED"
    assert refusals[0]["safe_metadata"]["reason_code"] == "TARGET_IDENTITY_MISMATCH"
    assert not [e for e in events if e["event_type"] == "OPERATION_EXECUTED"]


# ---------------------------------------------------------------------------
# Identity mutation: each component, and absence
# ---------------------------------------------------------------------------


def test_a_changed_file_identity_is_refused(
    investigator_client, admin_client, operator_client, temp_dir
):
    """Only the file id differs - the volume is the same one."""
    path = write_target(temp_dir)
    operation_id, target_id = approved_operation(investigator_client, admin_client, path)
    before = decode_file_id(stored_target(target_id)["file_id"])

    substitute(path)
    after = SafePathValidator(allowed_roots=[str(temp_dir)])._get_file_id(str(path))
    assert before != after, "the substitution must actually change the file identity"

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 409
    assert response.json()["error_code"] == "TARGET_IDENTITY_MISMATCH"
    assert path.exists()


def test_a_changed_volume_serial_is_refused(
    investigator_client, admin_client, operator_client, temp_dir
):
    """The object is untouched; the volume it was approved on is not this one."""
    path = write_target(temp_dir)
    operation_id, target_id = approved_operation(investigator_client, admin_client, path)

    with get_session_factory()() as session:
        target = OperationRepository(session).get_target(target_id)
        target.volume_serial = "0XDEADBEEF"
        session.commit()

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 409
    assert response.json()["error_code"] == "TARGET_IDENTITY_MISMATCH"
    assert path.exists(), "an object on an unexpected volume must not be erased"


def test_an_unestablished_identity_is_refused_not_assumed(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    """Absence must fail closed. A target with no identity cannot be executed."""
    path = write_target(temp_dir)
    operation_id, target_id = approved_operation(investigator_client, admin_client, path)

    with get_session_factory()() as session:
        target = OperationRepository(session).get_target(target_id)
        target.volume_serial = None
        target.file_id = None
        session.commit()

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 409
    assert response.json()["error_code"] == "TARGET_IDENTITY_UNAVAILABLE"
    assert path.exists()

    refusals = [
        e
        for e in audit_events(auditor_client, operation_id)
        if e["event_type"] == "OPERATION_EXECUTION_REFUSED"
    ]
    assert refusals[0]["safe_metadata"]["reason_code"] == "TARGET_IDENTITY_UNAVAILABLE"


def test_the_pipeline_also_refuses_an_unestablished_identity(
    investigator_client, admin_client, operator_client, temp_dir
):
    path = write_target(temp_dir)
    operation_id, target_id = approved_operation(investigator_client, admin_client, path)

    with get_session_factory()() as session:
        target = OperationRepository(session).get_target(target_id)
        target.volume_serial = None
        target.file_id = None
        session.commit()

    body = operator_client.post(f"/api/operations/{operation_id}/pipeline").json()
    erase = next(s for s in body["stages"] if s["stage"] == "ERASE")
    assert erase["status"] == "REFUSED"
    assert "No target identity was recorded" in erase["detail"]
    assert path.exists()


# ---------------------------------------------------------------------------
# Positive control: the fix must not break legitimate execution
# ---------------------------------------------------------------------------


def test_an_unchanged_object_is_erased_normally_by_the_pipeline(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert response.status_code == 200, response.text
    body = response.json()

    erase = next(s for s in body["stages"] if s["stage"] == "ERASE")
    assert erase["status"] == "COMPLETED", erase
    assert not path.exists(), "the approved object should have been erased"
    assert body["final_state"] == "COMPLETED"

    events = audit_events(auditor_client, operation_id)
    executed = [e for e in events if e["event_type"] == "OPERATION_EXECUTED"]
    assert len(executed) == 1
    assert executed[0]["outcome"] == "SUCCEEDED"
    assert not [e for e in events if e["event_type"] == "OPERATION_EXECUTION_REFUSED"]


def test_an_unchanged_object_is_erased_normally_by_execute(
    investigator_client, admin_client, operator_client, temp_dir
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 200, response.text
    assert not path.exists()
    assert response.json()["state"] == "COMPLETED"


def test_the_identity_still_matches_after_a_reload_between_approval_and_execution(
    investigator_client, admin_client, operator_client, temp_dir
):
    """analysis -> persist -> reload -> approval -> execution, still bound."""
    path = write_target(temp_dir)
    target_id = analyze(investigator_client, path)

    reloaded = stored_target(target_id)
    assert reloaded["volume_serial"] is not None

    operation_id = request_operation(investigator_client, target_id)
    approve(admin_client, operation_id)

    assert stored_target(target_id) == reloaded
    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 200, response.text
    assert not path.exists()


# ---------------------------------------------------------------------------
# A-1: every refusal on /execute is recorded
# ---------------------------------------------------------------------------


def test_an_unauthorised_execute_attempt_is_recorded(
    investigator_client, admin_client, viewer_client, auditor_client, temp_dir
):
    """A principal without operation.execute is refused, and it is written down."""
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    response = viewer_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 403

    denials = [
        e
        for e in auditor_client.get(
            "/api/audit/events", params={"event_type": "AUTH_ACCESS_DENIED", "limit": 100}
        ).json()["events"]
        if e["safe_metadata"].get("required_permission") == "operation.execute"
    ]
    assert denials, "a refused destructive attempt must not be invisible"
    assert denials[0]["outcome"] == "REFUSED"
    assert path.exists()


def test_executing_an_unapproved_operation_is_recorded(
    investigator_client, operator_client, auditor_client, temp_dir
):
    path = write_target(temp_dir)
    target_id = analyze(investigator_client, path)
    operation_id = request_operation(investigator_client, target_id)  # never approved

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 409
    assert response.json()["error_code"] == "OPERATION_NOT_APPROVED"
    assert path.exists()

    events = audit_events(auditor_client, operation_id)
    refusals = [e for e in events if e["event_type"] == "OPERATION_EXECUTION_REFUSED"]
    assert refusals and refusals[0]["outcome"] == "REFUSED"
    assert refusals[0]["safe_metadata"]["reason_code"] == "OPERATION_NOT_APPROVED"
    assert not [e for e in events if e["event_type"] == "OPERATION_EXECUTED"]


def test_executing_an_unknown_operation_is_recorded(operator_client, auditor_client):
    unknown = f"op_{uuid.uuid4().hex[:12]}"
    response = operator_client.post(f"/api/operations/{unknown}/execute")
    assert response.status_code == 404

    refusals = [
        e
        for e in audit_events(auditor_client, unknown)
        if e["event_type"] == "OPERATION_EXECUTION_REFUSED"
    ]
    assert refusals, "probing the destructive endpoint must leave a trace"
    assert refusals[0]["safe_metadata"]["reason_code"] == "OPERATION_NOT_FOUND"


def test_an_invalid_target_at_execution_is_recorded(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    """The approved object is gone entirely - safety revalidation refuses."""
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    path.unlink()

    response = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert response.status_code == 400
    assert response.json()["error_code"] == "TARGET_INVALID"

    events = audit_events(auditor_client, operation_id)
    refusals = [e for e in events if e["event_type"] == "OPERATION_EXECUTION_REFUSED"]
    assert refusals and refusals[0]["safe_metadata"]["reason_code"] == "TARGET_INVALID"
    assert not [e for e in events if e["event_type"] == "OPERATION_EXECUTED"]


def test_a_refusal_is_never_recorded_as_a_failed_execution(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    """REFUSED, FAILED and SUCCEEDED stay three different things.

    The temptation when adding refusal auditing is to reuse OPERATION_EXECUTED
    with a failed outcome. That would assert an execution happened, which is the
    false record this log exists to prevent.
    """
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)
    substitute(path)

    operator_client.post(f"/api/operations/{operation_id}/execute")

    events = audit_events(auditor_client, operation_id)
    assert not [e for e in events if e["event_type"] == "OPERATION_EXECUTED"]
    refusals = [e for e in events if e["event_type"] == "OPERATION_EXECUTION_REFUSED"]
    assert refusals
    assert {e["outcome"] for e in refusals} == {"REFUSED"}


def test_the_refusal_record_names_the_actor_operation_and_target(
    investigator_client, admin_client, operator_client, auditor_client, temp_dir
):
    path = write_target(temp_dir)
    operation_id, target_id = approved_operation(investigator_client, admin_client, path)
    canonical = stored_target(target_id)["canonical_path"]
    substitute(path)

    operator_client.post(f"/api/operations/{operation_id}/execute")

    refusal = next(
        e
        for e in audit_events(auditor_client, operation_id)
        if e["event_type"] == "OPERATION_EXECUTION_REFUSED"
    )
    assert refusal["operation_id"] == operation_id
    assert refusal["target_identity"] == canonical
    assert refusal["actor_id"], "the actor must be recorded"
    assert refusal["actor_source"] == "AUTHENTICATED_SESSION"


# ---------------------------------------------------------------------------
# No second destructive path may skip the binding
# ---------------------------------------------------------------------------


def test_both_destructive_endpoints_refuse_a_substituted_object(
    investigator_client, admin_client, operator_client, temp_dir
):
    """Whichever route an operator reaches for, the binding applies.

    ``/execute`` and ``/pipeline`` are the only two published routes that can
    destroy anything; both are checked here so a fix to one cannot leave the
    other open.
    """
    exec_path = write_target(temp_dir, name="via_execute.txt")
    exec_op, _ = approved_operation(investigator_client, admin_client, exec_path)
    substitute(exec_path)
    assert operator_client.post(f"/api/operations/{exec_op}/execute").status_code == 409
    assert exec_path.exists()

    pipe_path = write_target(temp_dir, name="via_pipeline.txt")
    pipe_op, _ = approved_operation(investigator_client, admin_client, pipe_path)
    substitute(pipe_path)
    body = operator_client.post(f"/api/operations/{pipe_op}/pipeline").json()
    erase = next(s for s in body["stages"] if s["stage"] == "ERASE")
    assert erase["status"] == "REFUSED"
    assert pipe_path.exists()
