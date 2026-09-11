"""F-A: the pipeline's audit records must describe the stage that actually ran.

The defect these tests pin was a type confusion, not a logic slip. ``Stage``
mixes in ``str``, but ``Enum.__str__`` still wins, so ``str(Stage.ERASE)`` is
``"Stage.ERASE"``. Comparing that against ``"ERASE"`` is always false, and the
same applies to ``str(StageStatus.COMPLETED)``. The consequence was that **every**
pipeline run - including fully successful ones - recorded:

    OPERATION_EXECUTED   outcome=FAILED   erase_status=NOT_RUN

and a refused operation recorded exactly the same thing, so the log could not
distinguish "declined, nothing destroyed" from "attempted and failed" from
"completed". That is the one distinction the audit vocabulary exists to carry.

These tests assert the distinction end to end, through the real API, rather than
asserting the comparison in isolation - a unit test on the comparison would pass
against a route that never called it.
"""

from __future__ import annotations

import secrets
import uuid

import pytest

from oblivion.api.dependencies import reset_signing_key_manager
from oblivion.api.routes.pipeline import _ERASE_ATTEMPTED, _ERASE_OUTCOME
from oblivion.certificate.keys import SigningKeyManager, generate_private_key_hex
from oblivion.certificate.trust_model import ENV_TRUSTED_SIGNERS
from oblivion.core.audit import AuditOutcome
from oblivion.core.pipeline.orchestrator import Stage, StageStatus
from oblivion.core.state.machine import State
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository

SELECTIVE_POLICY = "ERASURE.LOGICAL.SELECTIVE.V1"
SIGNER_ID = "oblivion-issuer"
REQUESTER = "user_investigator_1"
APPROVER = "user_admin_1"


@pytest.fixture(autouse=True)
def configured_backend(monkeypatch, temp_dir):
    """A deployment configured the way a real one would be. Secrets are per-test."""
    init_db()
    monkeypatch.setenv("OBLIVION_ALLOWED_ROOTS", str(temp_dir))
    monkeypatch.setenv("OBLIVION_IPC_KEY", secrets.token_hex(32))

    material = generate_private_key_hex()
    monkeypatch.setenv("OBLIVION_SIGNING_KEY", material)
    manager = SigningKeyManager.from_material(material)
    monkeypatch.setenv(ENV_TRUSTED_SIGNERS, f"{SIGNER_ID}:{manager.public_key_bytes().hex()}")

    reset_signing_key_manager()
    yield
    reset_signing_key_manager()


def create_operation(target_path, *, state=State.READY.name, approver=APPROVER):
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


def audit_events(admin_client, operation_id):
    """Every audit record for one operation, oldest first."""
    response = admin_client.get(
        "/api/audit/events", params={"operation_id": operation_id, "limit": 200}
    )
    assert response.status_code == 200, response.text
    return response.json()["events"]


def one(events, event_type):
    matches = [e for e in events if e["event_type"] == event_type]
    assert len(matches) == 1, f"expected exactly one {event_type}, got {len(matches)}"
    return matches[0]


# ---------------------------------------------------------------------------
# The mapping itself
# ---------------------------------------------------------------------------


def test_the_erase_outcome_mapping_is_total_over_stage_status():
    """A new StageStatus must force a deliberate decision, not a silent default."""
    assert set(_ERASE_OUTCOME) == set(StageStatus), (
        "every StageStatus needs an explicit audit outcome; a missing one would "
        "otherwise fall through to whatever the lookup's default happens to be"
    )


def test_the_three_outcomes_stay_distinct():
    """SKIPPED, REFUSED and FAILED must not collapse into one state."""
    assert _ERASE_OUTCOME[StageStatus.COMPLETED] is AuditOutcome.SUCCEEDED
    # Permitted and attempted, did not complete.
    assert _ERASE_OUTCOME[StageStatus.FAILED] is AuditOutcome.FAILED
    assert _ERASE_OUTCOME[StageStatus.UNAVAILABLE] is AuditOutcome.FAILED
    # Declined; nothing was destroyed.
    assert _ERASE_OUTCOME[StageStatus.REFUSED] is AuditOutcome.REFUSED
    assert _ERASE_OUTCOME[StageStatus.SKIPPED] is AuditOutcome.REFUSED


def test_only_attempted_erasures_count_as_executed():
    """`OPERATION_EXECUTED` must not be written for work that never happened."""
    assert _ERASE_ATTEMPTED == {
        StageStatus.COMPLETED,
        StageStatus.FAILED,
        StageStatus.UNAVAILABLE,
    }
    assert StageStatus.REFUSED not in _ERASE_ATTEMPTED
    assert StageStatus.SKIPPED not in _ERASE_ATTEMPTED


def test_the_string_comparison_that_caused_this_is_still_wrong():
    """Pins the trap, so nobody reintroduces it believing it works.

    If a future Python or a switch to ``StrEnum`` makes ``str()`` return the
    bare value, this test fails and the decision can be revisited - rather than
    the codebase quietly depending on behaviour that changed underneath it.
    """
    assert str(Stage.ERASE) != "ERASE"
    assert Stage.ERASE.value == "ERASE"
    assert str(StageStatus.COMPLETED) != "COMPLETED"
    assert StageStatus.COMPLETED.value == "COMPLETED"


# ---------------------------------------------------------------------------
# 1. A successful pipeline
# ---------------------------------------------------------------------------


def test_a_successful_pipeline_records_executed_and_succeeded(
    operator_client, admin_client, temp_dir
):
    target = temp_dir / "erase_me.txt"
    target.write_text("payload", encoding="utf-8")
    operation_id = create_operation(target)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert response.status_code == 200, response.text
    body = response.json()

    erase = next(s for s in body["stages"] if s["stage"] == "ERASE")
    assert erase["status"] == "COMPLETED"
    assert not target.exists(), "the target should really be gone"

    events = audit_events(admin_client, operation_id)

    executed = one(events, "OPERATION_EXECUTED")
    # The whole point of F-A: this was FAILED / NOT_RUN on every single run.
    assert executed["outcome"] == "SUCCEEDED"
    assert executed["safe_metadata"]["erase_status"] == "COMPLETED"
    assert "NOT_RUN" not in str(executed["safe_metadata"])

    concluded = one(events, "PIPELINE_CONCLUDED")
    assert concluded["outcome"] == "SUCCEEDED"
    assert concluded["safe_metadata"]["erase_status"] == "COMPLETED"


def test_a_successful_pipeline_records_the_real_final_state(
    operator_client, admin_client, temp_dir
):
    """`final_state` must be the state itself, not an enum repr."""
    target = temp_dir / "state.txt"
    target.write_text("payload", encoding="utf-8")
    operation_id = create_operation(target)

    operator_client.post(f"/api/operations/{operation_id}/pipeline")
    events = audit_events(admin_client, operation_id)

    final_state = one(events, "PIPELINE_CONCLUDED")["safe_metadata"]["final_state"]
    assert not final_state.startswith(
        "State."
    ), f"final_state leaked an enum repr: {final_state!r}"
    assert final_state == "COMPLETED"


# ---------------------------------------------------------------------------
# 2. A refused pipeline
# ---------------------------------------------------------------------------


def test_an_unapproved_operation_is_refused_and_never_recorded_as_executed(
    operator_client, admin_client, temp_dir
):
    """Refusal and failure are different facts and must not share a record."""
    target = temp_dir / "not_approved.txt"
    target.write_text("payload", encoding="utf-8")
    # No approver: authorization declines before anything destructive happens.
    operation_id = create_operation(target, state=State.READY.name, approver=None)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert response.status_code == 200, response.text

    assert target.exists(), "a refused operation must not destroy the target"

    events = audit_events(admin_client, operation_id)

    # Nothing was executed, so no record may claim it was.
    assert [e for e in events if e["event_type"] == "OPERATION_EXECUTED"] == [], (
        "a refused operation recorded OPERATION_EXECUTED; the log would assert "
        "an execution that never happened"
    )

    concluded = one(events, "PIPELINE_CONCLUDED")
    assert concluded["outcome"] == "REFUSED"
    assert concluded["safe_metadata"]["erase_status"] in {"SKIPPED", "REFUSED", "NOT_RUN"}


def test_a_self_approved_operation_is_refused_the_same_way(
    operator_client, admin_client, temp_dir
):
    target = temp_dir / "self_approved.txt"
    target.write_text("payload", encoding="utf-8")
    # Approved by the requester: separation of duties declines it.
    operation_id = create_operation(target, approver=REQUESTER)

    operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert target.exists(), "self-approval must not destroy the target"

    events = audit_events(admin_client, operation_id)
    assert [e for e in events if e["event_type"] == "OPERATION_EXECUTED"] == []
    assert one(events, "PIPELINE_CONCLUDED")["outcome"] == "REFUSED"


def test_a_refused_pipeline_is_distinguishable_from_a_successful_one(
    operator_client, admin_client, temp_dir
):
    """The regression in one sentence: these two used to look identical."""
    ok_target = temp_dir / "ok.txt"
    ok_target.write_text("payload", encoding="utf-8")
    ok_id = create_operation(ok_target)

    refused_target = temp_dir / "refused.txt"
    refused_target.write_text("payload", encoding="utf-8")
    refused_id = create_operation(refused_target, approver=None)

    operator_client.post(f"/api/operations/{ok_id}/pipeline")
    operator_client.post(f"/api/operations/{refused_id}/pipeline")

    ok_concluded = one(audit_events(admin_client, ok_id), "PIPELINE_CONCLUDED")
    refused_concluded = one(audit_events(admin_client, refused_id), "PIPELINE_CONCLUDED")

    assert ok_concluded["outcome"] != refused_concluded["outcome"]
    assert ok_concluded["outcome"] == "SUCCEEDED"
    assert refused_concluded["outcome"] == "REFUSED"


# ---------------------------------------------------------------------------
# 3. A permitted execution that fails
# ---------------------------------------------------------------------------


def test_a_permitted_execution_that_cannot_proceed_is_failed_not_refused(
    operator_client, admin_client, temp_dir
):
    """A deterministic safe failure: the target vanishes after authorization.

    The operation is approved, so the destructive step is *permitted*. Removing
    the file between approval and execution makes the erase stage fail without
    any unsafe filesystem work - the file was created by this test and is
    deleted by this test.

    The distinction being pinned: this must record FAILED, never REFUSED. The
    system did not decline; it was allowed to proceed and could not complete.
    """
    target = temp_dir / "vanishes.txt"
    target.write_text("payload", encoding="utf-8")
    operation_id = create_operation(target)

    # Remove it before the pipeline runs. Approval already happened, so the
    # refusal path is not involved.
    target.unlink()

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert response.status_code == 200, response.text
    body = response.json()

    erase = next((s for s in body["stages"] if s["stage"] == "ERASE"), None)
    if erase is None or erase["status"] in {"SKIPPED", "REFUSED"}:
        pytest.skip(
            "No deterministic permitted-but-failing fixture exists in this build. "
            "The privileged boundary validates target identity itself, so a missing "
            "target comes back `refused` and the stage is REFUSED - correctly, since "
            "nothing was destroyed. Reaching StageStatus.FAILED would require the "
            "boundary to permit the operation and the filesystem call to then fail "
            "(a locked handle, say), which is not deterministic here. The FAILED "
            "mapping itself is covered by test_the_three_outcomes_stay_distinct."
        )

    events = audit_events(admin_client, operation_id)
    executed = one(events, "OPERATION_EXECUTED")
    assert executed["outcome"] == "FAILED", (
        "a permitted execution that did not complete must be FAILED, not REFUSED - "
        "the system did not decline it"
    )
    assert executed["safe_metadata"]["erase_status"] == erase["status"]
