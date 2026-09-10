"""Phase 24-D: reconciling operations that were interrupted mid-flight.

The situation these tests describe is a crash between performing a destructive
filesystem call and recording that it happened. The persisted state and the
filesystem then disagree, and neither one alone reveals it.

The property under test throughout: reconciliation reports what it can prove and
nothing more. In particular it never reports ``COMPLETED``, because completion
means the whole evidence-and-certificate pipeline finished, and an interrupted
operation did not.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

from oblivion.core.evidence.record import ObservationState
from oblivion.core.state.machine import (
    OperationStateMachine,
    State,
    StateMachineError,
)
from oblivion.core.state.reconciliation import (
    INTERRUPTIBLE_STATES,
    OperationReconciler,
    TargetPresence,
)
from oblivion.persistence.database import get_session_factory, init_db
from oblivion.persistence.repositories.operation_repo import OperationRepository


@pytest.fixture(autouse=True)
def database():
    init_db()


def make_operation(session, target_path, *, mode="SELECTIVE_PERMANENT", state="ERASING"):
    """Persist a target and an operation frozen in the given state."""
    suffix = uuid.uuid4().hex[:8]
    repo = OperationRepository(session)
    repo.create_target(
        target_id=f"tgt_{suffix}",
        path=str(target_path),
        canonical_path=str(target_path),
        target_type="file",
    )
    operation = repo.create_operation(
        operation_id=f"op_{suffix}",
        target_id=f"tgt_{suffix}",
        mode=mode,
        policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
        state=state,
    )
    session.commit()
    return operation


# ---------------------------------------------------------------------------
# The state itself
# ---------------------------------------------------------------------------


def test_reconciliation_required_is_not_terminal():
    """It means "nobody has established what happened yet", so something must look.

    Making it terminal would freeze operations in a state that asserts nothing
    and can never be resolved.
    """
    machine = OperationStateMachine(State.RECONCILIATION_REQUIRED)
    assert not machine.is_terminal()
    machine.transition_to(State.PARTIAL)
    assert machine.current_state is State.PARTIAL


def test_an_interrupted_stage_can_enter_reconciliation():
    machine = OperationStateMachine(State.READY)
    machine.transition_to(State.ERASING)
    machine.transition_to(State.RECONCILIATION_REQUIRED)
    assert machine.current_state is State.RECONCILIATION_REQUIRED


def test_reconciliation_never_returns_to_an_in_flight_state():
    """Deciding what happened does not resume the interrupted work."""
    machine = OperationStateMachine(State.RECONCILIATION_REQUIRED)
    with pytest.raises(StateMachineError):
        machine.transition_to(State.ERASING)


def test_approval_states_cannot_require_reconciliation():
    """Nothing destructive happens before READY.

    An interrupted approval is simply an operation that was never approved -
    routing it through reconciliation would imply there is filesystem damage to
    assess.
    """
    assert State.PENDING_APPROVAL.name not in INTERRUPTIBLE_STATES
    assert State.CREATED.name not in INTERRUPTIBLE_STATES
    machine = OperationStateMachine(State.PENDING_APPROVAL)
    with pytest.raises(StateMachineError):
        machine.transition_to(State.RECONCILIATION_REQUIRED)


# ---------------------------------------------------------------------------
# What reconciliation establishes
# ---------------------------------------------------------------------------


def test_a_vanished_target_means_the_destructive_step_ran(safe_validator, temp_dir):
    """Gone target, destructive mode: the deletion happened.

    PARTIAL rather than COMPLETED - the deletion is done, but verification,
    assurance and evidence are not, and only those make an operation complete.
    """
    target = temp_dir / "already-deleted.txt"
    session_factory = get_session_factory()

    with session_factory() as session:
        operation = make_operation(session, target)  # never created on disk
        result = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()

    assert result.presence is TargetPresence.ABSENT
    assert result.observation is ObservationState.OBSERVED
    assert result.resolved_state == State.PARTIAL.name
    assert result.resolved
    assert "No certificate may be issued" in result.detail


def test_a_surviving_target_means_nothing_was_destroyed(safe_validator, temp_dir):
    target = temp_dir / "survivor.txt"
    target.write_text("still here")
    session_factory = get_session_factory()

    with session_factory() as session:
        operation = make_operation(session, target)
        result = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()

    assert result.presence is TargetPresence.PRESENT
    assert result.resolved_state == State.FAILED.name
    assert "Nothing was destroyed" in result.detail
    assert target.exists()


def test_reconciliation_never_reports_completed(safe_validator, temp_dir):
    """The single most important thing this component must not do.

    COMPLETED asserts that erasure, verification, recovery testing, residual
    analysis, assurance, evidence and certification all happened. An interrupted
    operation did none of the later ones, so no observation can justify it.
    """
    session_factory = get_session_factory()
    outcomes = set()

    for name, exists in (("gone.txt", False), ("present.txt", True)):
        target = temp_dir / name
        if exists:
            target.write_text("x")
        with session_factory() as session:
            operation = make_operation(session, target)
            outcomes.add(
                OperationReconciler(session, safe_validator)
                .reconcile(operation)
                .resolved_state
            )
            session.commit()

    assert State.COMPLETED.name not in outcomes


def test_a_missing_target_record_is_inconclusive_not_failed(safe_validator, temp_dir):
    """Nothing to compare against is not the same as nothing having happened."""
    session_factory = get_session_factory()

    with session_factory() as session:
        operation = make_operation(session, temp_dir / "orphan.txt")
        operation.target_id = "tgt_does_not_exist"
        session.commit()

        result = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()

    assert result.resolved_state == State.INCONCLUSIVE.name
    assert result.observation is ObservationState.UNAVAILABLE
    assert not result.resolved


def test_an_unreadable_filesystem_is_inconclusive(safe_validator, temp_dir, monkeypatch):
    """Not knowing must never collapse into "the target is still there".

    That collapse would assert that nothing was destroyed, which is exactly what
    could not be established.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        operation = make_operation(session, temp_dir / "unreadable.txt")
        reconciler = OperationReconciler(session, safe_validator)

        def explode(_path):
            raise OSError("device not ready")

        monkeypatch.setattr("os.path.lexists", explode)
        result = reconciler.reconcile(operation)
        session.commit()

    assert result.presence is TargetPresence.UNDETERMINED
    assert result.observation is ObservationState.UNAVAILABLE
    assert result.resolved_state == State.INCONCLUSIVE.name


def test_a_non_destructive_mode_is_never_credited_with_a_deletion(
    safe_validator, temp_dir
):
    """An absent target does not mean a read-only operation deleted it."""
    session_factory = get_session_factory()

    with session_factory() as session:
        operation = make_operation(
            session, temp_dir / "analysed.txt", mode="ANALYZE_ONLY"
        )
        result = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()

    assert result.destructive is False
    assert result.resolved_state == State.FAILED.name
    assert "performs no destruction" in result.detail


def test_a_dangling_symlink_counts_as_present(safe_validator, temp_dir):
    """An entry that still exists was not removed.

    ``exists`` follows the link and would report a dangling symlink as absent,
    crediting the operation with a deletion it did not perform. ``lexists`` looks
    at the entry itself.
    """
    target = temp_dir / "link.txt"
    try:
        os.symlink(temp_dir / "no-such-file.txt", target)
    except OSError:
        pytest.skip("Symlink creation not supported")

    session_factory = get_session_factory()
    with session_factory() as session:
        operation = make_operation(session, target)
        result = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()

    assert result.presence is TargetPresence.PRESENT
    assert result.resolved_state == State.FAILED.name


# ---------------------------------------------------------------------------
# Sweeping and recording
# ---------------------------------------------------------------------------


def test_only_interrupted_operations_are_swept(safe_validator, temp_dir):
    """A completed or pending operation is not something to reconcile."""
    session_factory = get_session_factory()

    with session_factory() as session:
        make_operation(session, temp_dir / "a.txt", state="ERASING")
        make_operation(session, temp_dir / "b.txt", state="COMPLETED")
        make_operation(session, temp_dir / "c.txt", state="PENDING_APPROVAL")

        found = {
            op.state
            for op in OperationReconciler(
                session, safe_validator
            ).interrupted_operations()
        }

    assert "ERASING" in found
    assert "COMPLETED" not in found
    assert "PENDING_APPROVAL" not in found


def test_reconciliation_appends_an_audit_event(safe_validator, temp_dir):
    """Including when it establishes nothing.

    A reconciliation that failed to determine anything is still something that
    happened to the operation; without a record, the next attempt cannot tell a
    first look from a repeated failure.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        operation = make_operation(session, temp_dir / "audited.txt")
        OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()
        operation_id = operation.id

    with session_factory() as session:
        reloaded = OperationRepository(session).get_operation(operation_id)
        events = [e for e in reloaded.events if e.event_type == "OPERATION_RECONCILED"]

    assert len(events) == 1
    assert events[0].from_state == "ERASING"
    assert events[0].to_state == State.PARTIAL.name
    payload = json.loads(events[0].payload)
    assert payload["presence"] == "ABSENT"
    assert payload["observation"] == "OBSERVED"


def test_reconcile_all_resolves_every_interrupted_operation(safe_validator, temp_dir):
    session_factory = get_session_factory()
    present = temp_dir / "present.txt"
    present.write_text("x")

    with session_factory() as session:
        make_operation(session, temp_dir / "gone-1.txt", state="ERASING")
        make_operation(session, temp_dir / "gone-2.txt", state="VERIFYING")
        make_operation(session, present, state="CERTIFYING")

        results = OperationReconciler(session, safe_validator).reconcile_all()
        session.commit()

    assert len(results) >= 3
    assert all(r.resolved_state != State.COMPLETED.name for r in results)

    with session_factory() as session:
        remaining = OperationReconciler(
            session, safe_validator
        ).interrupted_operations()
    assert remaining == []
