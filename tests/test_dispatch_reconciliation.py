"""A dispatched destructive step whose outcome is lost must never read as READY.

The defect: the pipeline sent a destructive request, the privileged service
performed it, and then the reply could not be established - it failed
authentication, the exchange broke, or the result could not be written. The
request transaction rolled back, taking the attempt's audit records with it, and
the operation stayed READY. A later run found the target gone and recorded a
refusal over an act that had really happened.

The controls under test:

* the dispatch is journalled (READY -> ERASING, OPERATION_DISPATCH_STARTED) in its
  own committed transaction before anything is sent;
* an unestablished outcome moves the operation to RECONCILIATION_REQUIRED with
  OPERATION_OUTCOME_UNESTABLISHED, also committed on its own;
* nothing re-runs, re-approves or cancels an operation in that state, and the
  reconciler - never a later run - is what resolves it.

Faults are injected at the transport, the narrowest boundary: the real
privileged service still validates and really deletes, and the real client still
verifies. Only what happens to the reply is changed.
"""

from __future__ import annotations

import secrets
import threading

import pytest
from sqlalchemy import update

from oblivion.api import dependencies as api_dependencies
from oblivion.api.routes import operations as operations_route
from oblivion.api.routes import pipeline as pipeline_route
from oblivion.core.audit import (
    AuditActor,
    AuditEventType,
    AuditLog,
    AuditOutcome,
    AuditQuery,
)
from oblivion.core.pipeline import (
    ClosedLoopPipeline,
    DispatchConflictError,
    DispatchJournal,
    DispatchJournalError,
    DispatchOutcomeUnestablished,
    Stage,
    StageStatus,
)
from oblivion.core.pipeline.journal import DispatchFacts
from oblivion.core.safety.paths import decode_file_id
from oblivion.core.state.machine import State
from oblivion.core.state.reconciliation import OperationReconciler
from oblivion.persistence.database import get_session_factory
from oblivion.persistence.models.operation import OperationModel
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged import (
    InProcessTransport,
    PrivilegedClient,
    PrivilegedService,
    RequestAuthenticator,
    ServiceConfig,
    ServiceUnavailableError,
    TransportError,
)
from tests.test_api_pipeline import create_operation
from tests.test_pipeline_closed_loop import approve_operation, make_request
from tests.test_target_identity_binding import (  # noqa: F401 - autouse fixture
    approved_operation,
    configured_backend,
    write_target,
)

DISPATCH_RECORD_OUTCOME = DispatchJournal.record_outcome_unestablished

DESTRUCTIVE = {"delete_file", "delete_tree", "prepare_recovery_object"}


# ---------------------------------------------------------------------------
# Fault injection at the transport
# ---------------------------------------------------------------------------


class ReplyFault(InProcessTransport):
    """Runs the real service; then damages what comes back for destructive calls.

    ``execute=False`` fails the exchange before the service sees the request.
    """

    fault: str = "bad_mac"
    execute: bool = True

    def exchange(self, envelope):
        if envelope["request"]["operation"] not in DESTRUCTIVE:
            return super().exchange(envelope)
        if not self.execute:
            raise TransportError("Write failed with error 232")
        reply = super().exchange(envelope)
        if self.fault == "bad_mac":
            return dict(reply, mac="00" * 32)
        if self.fault == "no_mac":
            return {k: v for k, v in reply.items() if k != "mac"}
        if self.fault == "malformed":
            return ["not", "a", "response"]
        if self.fault == "broken_pipe":
            raise TransportError("Read failed with error 109 after 0 of 4 bytes")
        raise AssertionError(self.fault)


class Unreachable(InProcessTransport):
    """The pipe cannot be opened for destructive calls: nothing is ever sent."""

    def exchange(self, envelope):
        if envelope["request"]["operation"] in DESTRUCTIVE:
            raise ServiceUnavailableError("Privileged service pipe is not available")
        return super().exchange(envelope)


def fault(name: str, *, execute: bool = True) -> type[ReplyFault]:
    return type(f"ReplyFault_{name}", (ReplyFault,), {"fault": name, "execute": execute})


# ---------------------------------------------------------------------------
# Reading back, always in a session of its own
# ---------------------------------------------------------------------------


def state_of(operation_id: str) -> str:
    with get_session_factory()() as session:
        operation = OperationRepository(session).get_operation(operation_id)
        assert operation is not None
        return operation.state


def records(operation_id: str):
    with get_session_factory()() as session:
        return AuditLog(session).query(AuditQuery(operation_id=operation_id, limit=500))


def types_of(operation_id: str) -> list[str]:
    return [r.event_type.value for r in records(operation_id)]


def only(operation_id: str, event_type: AuditEventType):
    matches = [r for r in records(operation_id) if r.event_type is event_type]
    assert len(matches) == 1, f"expected one {event_type.value}, got {len(matches)}"
    return matches[0]


def chain_intact() -> bool:
    with get_session_factory()() as session:
        return AuditLog(session).verify().intact


# ---------------------------------------------------------------------------
# Driving the core pipeline directly
# ---------------------------------------------------------------------------


def core_run(safe_validator, target, transport_cls, *, validator=None):
    """Run the real pipeline for a persisted, approved operation."""
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=validator or safe_validator, authenticator=authenticator)
    )
    client = PrivilegedClient(transport_cls(service), authenticator)
    session_factory = get_session_factory()
    with session_factory() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        request = make_request(
            operation_id,
            target,
            expected_volume_serial=stored.volume_serial,
            expected_file_id=decode_file_id(stored.file_id),
        )
        pipeline = ClosedLoopPipeline(
            session=session, validator=safe_validator, privileged=client
        )
        try:
            result = pipeline.run(request)
            session.commit()
            return operation_id, result, None
        except Exception as exc:  # noqa: BLE001 - returned for the test to inspect
            session.rollback()
            return operation_id, None, exc


def test_an_accepted_response_concludes_normally_with_one_dispatch_record(
    safe_validator, temp_dir
):
    target = temp_dir / "ok.txt"
    target.write_text("payload")

    operation_id, result, error = core_run(safe_validator, target, InProcessTransport)

    assert error is None
    assert not target.exists()
    assert result.outcome(Stage.ERASE).status is StageStatus.COMPLETED
    assert state_of(operation_id) == result.final_state == State.PARTIAL.name
    dispatch = only(operation_id, AuditEventType.OPERATION_DISPATCH_STARTED)
    assert dispatch.outcome is AuditOutcome.SUCCEEDED
    assert dispatch.safe_metadata["privileged_operation"] == "delete_file"
    assert dispatch.safe_metadata["from_state"] == State.READY.name
    assert AuditEventType.OPERATION_OUTCOME_UNESTABLISHED.value not in types_of(operation_id)


def test_a_refusal_before_dispatch_records_no_dispatch(safe_validator, temp_dir):
    """The approved object was substituted: refused locally, nothing sent."""
    target = temp_dir / "swapped.txt"
    target.write_text("original")
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    client = PrivilegedClient(ReplyFault(service), authenticator)

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        target.unlink()
        target.write_text("substituted")
        result = ClosedLoopPipeline(
            session=session, validator=safe_validator, privileged=client
        ).run(
            make_request(
                operation_id,
                target,
                expected_volume_serial=stored.volume_serial,
                expected_file_id=decode_file_id(stored.file_id),
            )
        )
        session.commit()

    assert target.read_text() == "substituted"
    assert result.outcome(Stage.ERASE).status is StageStatus.REFUSED
    assert state_of(operation_id) == State.FAILED.name
    assert AuditEventType.OPERATION_DISPATCH_STARTED.value not in types_of(operation_id)


def test_an_authenticated_refusal_after_dispatch_is_an_established_outcome(
    safe_validator, temp_dir
):
    """The service itself refuses (its roots exclude the target): FAILED, not uncertain."""
    from oblivion.core.safety.paths import SafePathValidator

    target = temp_dir / "outside-service-roots.txt"
    target.write_text("payload")
    elsewhere = temp_dir / "service-root"
    elsewhere.mkdir()
    narrow = SafePathValidator(allowed_roots=[str(elsewhere)])
    narrow.system_volume_serial = safe_validator.system_volume_serial

    operation_id, result, error = core_run(
        safe_validator, target, InProcessTransport, validator=narrow
    )

    assert error is None
    assert target.exists()
    assert result.outcome(Stage.ERASE).status is StageStatus.REFUSED
    assert state_of(operation_id) == State.FAILED.name
    only(operation_id, AuditEventType.OPERATION_DISPATCH_STARTED)
    assert AuditEventType.OPERATION_OUTCOME_UNESTABLISHED.value not in types_of(operation_id)


@pytest.mark.parametrize(
    ("fault_name", "reason_code"),
    [
        ("bad_mac", "PRIVILEGED_RESPONSE_REJECTED"),
        ("no_mac", "PRIVILEGED_RESPONSE_REJECTED"),
        ("malformed", "PRIVILEGED_RESPONSE_REJECTED"),
        ("broken_pipe", "PRIVILEGED_EXCHANGE_FAILED"),
    ],
)
def test_an_executed_step_with_an_unestablished_reply_requires_reconciliation(
    safe_validator, temp_dir, fault_name, reason_code
):
    target = temp_dir / f"{fault_name}.txt"
    target.write_text("payload")

    operation_id, result, error = core_run(safe_validator, target, fault(fault_name))

    assert result is None
    assert isinstance(error, DispatchOutcomeUnestablished)
    assert error.reason_code == reason_code
    assert not target.exists(), "the service really performed the deletion"
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name

    only(operation_id, AuditEventType.OPERATION_DISPATCH_STARTED)
    unestablished = only(operation_id, AuditEventType.OPERATION_OUTCOME_UNESTABLISHED)
    assert unestablished.outcome is AuditOutcome.FAILED
    assert unestablished.target_identity == str(target)
    assert unestablished.safe_metadata["reason_code"] == reason_code
    assert unestablished.safe_metadata["destructive_outcome"] == "UNESTABLISHED"
    assert unestablished.safe_metadata["from_state"] == State.ERASING.name
    assert unestablished.safe_metadata["to_state"] == State.RECONCILIATION_REQUIRED.name
    assert unestablished.safe_metadata["privileged_operation"] == "delete_file"
    assert "Read failed" not in str(unestablished.safe_metadata), "no far-side text"
    assert AuditEventType.OPERATION_EXECUTED.value not in types_of(operation_id)
    assert chain_intact()


def test_a_request_that_never_arrived_is_still_not_assumed_safe(safe_validator, temp_dir):
    """The client cannot tell a lost request from a lost reply, so neither is guessed."""
    target = temp_dir / "never-arrived.txt"
    target.write_text("payload")

    operation_id, _, error = core_run(
        safe_validator, target, fault("broken_pipe", execute=False)
    )

    assert isinstance(error, DispatchOutcomeUnestablished)
    assert target.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name

    # The reconciler, looking at the filesystem, is what resolves it.
    with get_session_factory()() as session:
        operation = session.get(OperationModel, operation_id)
        outcome = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()
    assert outcome.resolved_state == State.FAILED.name
    assert state_of(operation_id) == State.FAILED.name


def test_an_unreachable_service_is_an_established_non_execution(safe_validator, temp_dir):
    """The pipe never opened, so nothing was sent: FAILED, not reconciliation."""
    target = temp_dir / "unreachable.txt"
    target.write_text("payload")

    operation_id, result, error = core_run(safe_validator, target, Unreachable)

    assert error is None
    assert target.exists()
    assert result.outcome(Stage.ERASE).status is StageStatus.UNAVAILABLE
    assert state_of(operation_id) == State.FAILED.name
    assert AuditEventType.OPERATION_OUTCOME_UNESTABLISHED.value not in types_of(operation_id)


def test_a_later_run_does_not_overwrite_an_unresolved_operation(safe_validator, temp_dir):
    """Observing the missing target must not turn the operation into FAILED."""
    target = temp_dir / "later-run.txt"
    target.write_text("payload")
    operation_id, _, error = core_run(safe_validator, target, fault("bad_mac"))
    assert isinstance(error, DispatchOutcomeUnestablished)

    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    with get_session_factory()() as session:
        result = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=PrivilegedClient(InProcessTransport(service), authenticator),
        ).run(make_request(operation_id, target))
        session.commit()

    assert result.outcome(Stage.AUTHORIZE).status is StageStatus.REFUSED
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name
    assert len([t for t in types_of(operation_id) if t == "OPERATION_DISPATCH_STARTED"]) == 1

    # Resolution comes from the reconciler: the target is gone, so PARTIAL -
    # never COMPLETED, because nothing after the erase was established.
    with get_session_factory()() as session:
        operation = session.get(OperationModel, operation_id)
        outcome = OperationReconciler(session, safe_validator).reconcile(operation)
        session.commit()
    assert outcome.resolved_state == State.PARTIAL.name


def test_the_journal_refuses_a_second_claim(safe_validator, temp_dir):
    """Two runs of one operation cannot both dispatch."""
    target = temp_dir / "claimed.txt"
    target.write_text("payload")
    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)

    facts = DispatchFacts(
        operation_id=operation_id,
        privileged_operation="delete_file",
        mode="SELECTIVE_PERMANENT",
        policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
        target_identity=str(target),
        target_type="file",
        expected_volume_serial=None,
        expected_file_id=None,
        executed_by="user_admin_1",
    )
    actor = AuditActor.system("test")
    first = DispatchJournal(get_session_factory(), actor)
    first.record_dispatch(facts)
    assert first.dispatched

    second = DispatchJournal(get_session_factory(), actor)
    with pytest.raises(DispatchConflictError):
        second.record_dispatch(facts)
    assert not second.dispatched
    assert state_of(operation_id) == State.ERASING.name
    assert types_of(operation_id).count("OPERATION_DISPATCH_STARTED") == 1


def test_no_uncertainty_is_claimed_once_the_result_is_recorded(safe_validator, temp_dir):
    """A failure after the result was committed must not add a false record."""
    target = temp_dir / "already-recorded.txt"
    target.write_text("payload")
    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)

    journal = DispatchJournal(get_session_factory(), AuditActor.system("test"))
    journal.record_dispatch(
        DispatchFacts(
            operation_id=operation_id,
            privileged_operation="delete_file",
            mode="SELECTIVE_PERMANENT",
            policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
            target_identity=str(target),
            target_type="file",
            expected_volume_serial=None,
            expected_file_id=None,
            executed_by="user_admin_1",
        )
    )
    with get_session_factory()() as other:
        other.execute(
            update(OperationModel)
            .where(OperationModel.id == operation_id)
            .values(state=State.COMPLETED.name)
        )
        other.commit()

    journal.record_outcome_unestablished(reason_code="RESULT_NOT_RECORDED", error_type="X")

    assert state_of(operation_id) == State.COMPLETED.name
    assert "OPERATION_OUTCOME_UNESTABLISHED" not in types_of(operation_id)


def test_a_pipeline_that_loses_the_claim_dispatches_nothing(safe_validator, temp_dir):
    """The operation left READY after authorization: the run stops before sending."""
    target = temp_dir / "raced.txt"
    target.write_text("payload")
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    sent: list[str] = []

    class Recording(InProcessTransport):
        def exchange(self, envelope):
            sent.append(envelope["request"]["operation"])
            return super().exchange(envelope)

    class RacingJournal(DispatchJournal):
        def record_dispatch(self, facts):
            with get_session_factory()() as other:
                other.execute(
                    update(OperationModel)
                    .where(OperationModel.id == facts.operation_id)
                    .values(state=State.ERASING.name)
                )
                other.commit()
            super().record_dispatch(facts)

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        pipeline = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=PrivilegedClient(Recording(service), authenticator),
            journal=RacingJournal(get_session_factory(), AuditActor.system("test")),
        )
        with pytest.raises(DispatchConflictError):
            pipeline.run(
                make_request(
                    operation_id,
                    target,
                    expected_volume_serial=stored.volume_serial,
                    expected_file_id=decode_file_id(stored.file_id),
                )
            )
        session.rollback()

    assert "delete_file" not in sent
    assert target.exists()
    assert state_of(operation_id) == State.ERASING.name


def test_a_journal_that_cannot_write_forbids_dispatch(safe_validator, temp_dir):
    target = temp_dir / "no-journal.txt"
    target.write_text("payload")
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    sent: list[str] = []

    class Recording(InProcessTransport):
        def exchange(self, envelope):
            sent.append(envelope["request"]["operation"])
            return super().exchange(envelope)

    def broken_factory():
        raise OSError("database unavailable")

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        result = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=PrivilegedClient(Recording(service), authenticator),
            journal=DispatchJournal(broken_factory, AuditActor.system("test")),
        ).run(
            make_request(
                operation_id,
                target,
                expected_volume_serial=stored.volume_serial,
                expected_file_id=decode_file_id(stored.file_id),
            )
        )
        session.commit()

    erase = result.outcome(Stage.ERASE)
    assert erase.status is StageStatus.REFUSED
    assert "could not be recorded" in erase.detail
    assert "delete_file" not in sent
    assert target.exists()


# ---------------------------------------------------------------------------
# Through the API, where the request transaction really rolls back
# ---------------------------------------------------------------------------


def use_transport(monkeypatch, transport_cls):
    monkeypatch.setattr(api_dependencies, "InProcessTransport", transport_cls)


def test_api_a_rejected_reply_is_durable_and_reported_as_unestablished(
    operator_client, temp_dir, monkeypatch
):
    target = temp_dir / "api-bad-mac.txt"
    target.write_text("payload")
    operation_id = create_operation(target)
    use_transport(monkeypatch, fault("bad_mac"))

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 502, response.text
    body = response.json()
    assert body["error_code"] == "OPERATION_OUTCOME_UNESTABLISHED"
    assert set(body) == {"error_code", "message", "details"}, "ErrorResponse shape"
    assert body["details"] == {
        "operation_id": operation_id,
        "state": State.RECONCILIATION_REQUIRED.name,
        "reason_code": "PRIVILEGED_RESPONSE_REJECTED",
    }
    assert not target.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name

    kinds = types_of(operation_id)
    assert kinds == [
        "PIPELINE_STARTED",
        "OPERATION_DISPATCH_STARTED",
        "OPERATION_OUTCOME_UNESTABLISHED",
    ], "the attempt survives the rollback; nothing claims an execution result"
    dispatch = only(operation_id, AuditEventType.OPERATION_DISPATCH_STARTED)
    assert dispatch.actor.actor_id == only(
        operation_id, AuditEventType.PIPELINE_STARTED
    ).actor.actor_id
    assert chain_intact()


def test_api_an_unresolved_operation_is_not_run_approved_or_cancelled_again(
    operator_client, admin_client, temp_dir, monkeypatch
):
    target = temp_dir / "api-rerun.txt"
    target.write_text("payload")
    operation_id = create_operation(target)
    use_transport(monkeypatch, fault("bad_mac"))
    assert operator_client.post(f"/api/operations/{operation_id}/pipeline").status_code == 502

    use_transport(monkeypatch, InProcessTransport)
    rerun = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert rerun.status_code == 409, rerun.text
    assert rerun.json() == {
        "error_code": "OPERATION_RECONCILIATION_REQUIRED",
        "message": rerun.json()["message"],
        "details": {"state": State.RECONCILIATION_REQUIRED.name},
    }

    approve = admin_client.post(f"/api/operations/{operation_id}/approve")
    assert approve.status_code == 409, approve.text

    cancel = admin_client.post(f"/api/operations/{operation_id}/cancel")
    assert cancel.status_code == 409, cancel.text

    execute = admin_client.post(f"/api/operations/{operation_id}/execute")
    assert execute.status_code in (403, 409), execute.text

    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name
    kinds = types_of(operation_id)
    assert kinds.count("OPERATION_DISPATCH_STARTED") == 1
    assert "PIPELINE_CONCLUDED" not in kinds
    assert "OPERATION_CANCELLED" not in kinds
    refused = [
        r
        for r in records(operation_id)
        if r.event_type is AuditEventType.OPERATION_EXECUTION_REFUSED
    ]
    assert refused and refused[0].safe_metadata["reason_code"] == (
        "OPERATION_RECONCILIATION_REQUIRED"
    )


def test_api_a_result_lost_after_an_authenticated_reply_requires_reconciliation(
    operator_client, temp_dir, monkeypatch
):
    """The reply was fine; recording it failed and the transaction rolled back."""
    target = temp_dir / "api-lost-result.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    def failing_conclusion(*args, **kwargs):
        raise RuntimeError("audit store went away")

    monkeypatch.setattr(pipeline_route, "_record_conclusion", failing_conclusion)

    with pytest.raises(RuntimeError, match="audit store went away"):
        operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert not target.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name
    unestablished = only(operation_id, AuditEventType.OPERATION_OUTCOME_UNESTABLISHED)
    assert unestablished.safe_metadata["reason_code"] == "RESULT_NOT_RECORDED"
    assert unestablished.safe_metadata["error_type"] == "RuntimeError"
    kinds = types_of(operation_id)
    assert "EVIDENCE_RECORDED" not in kinds and "PIPELINE_CONCLUDED" not in kinds
    assert chain_intact()


def test_api_an_abort_before_dispatch_is_concluded_and_leaves_ready(
    operator_client, temp_dir, monkeypatch
):
    target = temp_dir / "api-abort.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    class DiscoverBreaks(InProcessTransport):
        def exchange(self, envelope):
            raise RuntimeError("unexpected failure before dispatch")

    use_transport(monkeypatch, DiscoverBreaks)

    with pytest.raises(RuntimeError):
        operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert target.exists()
    assert state_of(operation_id) == State.READY.name
    kinds = types_of(operation_id)
    assert kinds == ["PIPELINE_STARTED", "PIPELINE_CONCLUDED"]
    concluded = only(operation_id, AuditEventType.PIPELINE_CONCLUDED)
    assert concluded.outcome is AuditOutcome.REFUSED
    assert concluded.safe_metadata["aborted"] is True
    assert "OPERATION_DISPATCH_STARTED" not in kinds


def test_api_a_successful_run_is_unchanged_apart_from_the_dispatch_record(
    operator_client, temp_dir
):
    target = temp_dir / "api-success.txt"
    target.write_text("payload")
    operation_id = create_operation(target)

    response = operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert response.status_code == 200, response.text
    assert response.json()["final_state"] == State.COMPLETED.name
    assert state_of(operation_id) == State.COMPLETED.name
    assert types_of(operation_id) == [
        "PIPELINE_STARTED",
        "OPERATION_DISPATCH_STARTED",
        "OPERATION_EXECUTED",
        "EVIDENCE_RECORDED",
        "CERTIFICATE_ISSUED",
        "PIPELINE_CONCLUDED",
    ]
    assert chain_intact()


# ---------------------------------------------------------------------------
# The in-process execute route has the same exposure
# ---------------------------------------------------------------------------


def test_execute_a_lost_result_requires_reconciliation(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    real = operations_route.AuditLog

    class FailingOnExecuted(real):
        def append(self, event_type, *args, **kwargs):
            if event_type is AuditEventType.OPERATION_EXECUTED:
                raise RuntimeError("audit store went away")
            return super().append(event_type, *args, **kwargs)

    monkeypatch.setattr(operations_route, "AuditLog", FailingOnExecuted)

    with pytest.raises(RuntimeError, match="audit store went away"):
        operator_client.post(f"/api/operations/{operation_id}/execute")

    assert not path.exists()
    assert state_of(operation_id) == State.RECONCILIATION_REQUIRED.name
    only(operation_id, AuditEventType.OPERATION_DISPATCH_STARTED)
    unestablished = only(operation_id, AuditEventType.OPERATION_OUTCOME_UNESTABLISHED)
    assert unestablished.safe_metadata["reason_code"] == "RESULT_NOT_RECORDED"
    assert chain_intact()


def test_execute_success_records_the_dispatch_once(
    investigator_client, admin_client, operator_client, temp_dir
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "COMPLETED"
    assert state_of(operation_id) == "COMPLETED"
    kinds = types_of(operation_id)
    assert kinds.count("OPERATION_DISPATCH_STARTED") == 1
    assert kinds.count("OPERATION_EXECUTED") == 1
    assert kinds.index("OPERATION_DISPATCH_STARTED") < kinds.index("OPERATION_EXECUTED")


def test_execute_refuses_an_operation_it_cannot_claim(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    real = operations_route.DispatchJournal

    class Raced(real):
        def record_dispatch(self, facts):
            with get_session_factory()() as other:
                other.execute(
                    update(OperationModel)
                    .where(OperationModel.id == facts.operation_id)
                    .values(state=State.ERASING.name)
                )
                other.commit()
            super().record_dispatch(facts)

    monkeypatch.setattr(operations_route, "DispatchJournal", Raced)

    response = operator_client.post(f"/api/operations/{operation_id}/execute")

    assert response.status_code == 409, response.text
    assert response.json()["error_code"] == "OPERATION_NOT_READY"
    assert path.exists()
    assert state_of(operation_id) == State.ERASING.name


# ---------------------------------------------------------------------------
# When the uncertainty itself cannot be recorded, ERASING is the backstop
# ---------------------------------------------------------------------------


class UnrecordableUncertainty(DispatchJournal):
    """Claims and records the dispatch, then cannot record the uncertainty."""

    def record_outcome_unestablished(self, *, reason_code, error_type):
        raise RuntimeError("audit store unavailable")


def reconcile(safe_validator, operation_id):
    with get_session_factory()() as session:
        reconciler = OperationReconciler(session, safe_validator)
        assert operation_id in {op.id for op in reconciler.interrupted_operations()}
        outcome = reconciler.reconcile(session.get(OperationModel, operation_id))
        session.commit()
    return outcome


def claim_facts(operation_id, target):
    return DispatchFacts(
        operation_id=operation_id,
        privileged_operation="delete_file",
        mode="SELECTIVE_PERMANENT",
        policy_id="ERASURE.LOGICAL.SELECTIVE.V1",
        target_identity=str(target),
        target_type="file",
        expected_volume_serial=None,
        expected_file_id=None,
        executed_by="user_admin_1",
    )


def test_core_an_unrecordable_uncertainty_leaves_erasing_for_the_reconciler(
    safe_validator, temp_dir
):
    target = temp_dir / "unrecordable.txt"
    target.write_text("payload")
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
        pipeline = ClosedLoopPipeline(
            session=session,
            validator=safe_validator,
            privileged=PrivilegedClient(fault("bad_mac")(service), authenticator),
            journal=UnrecordableUncertainty(
                get_session_factory(), AuditActor.system("test")
            ),
        )
        with pytest.raises(RuntimeError, match="audit store unavailable"):
            pipeline.run(
                make_request(
                    operation_id,
                    target,
                    expected_volume_serial=stored.volume_serial,
                    expected_file_id=decode_file_id(stored.file_id),
                )
            )
        session.rollback()

    assert not target.exists()
    assert state_of(operation_id) == State.ERASING.name
    assert types_of(operation_id) == ["OPERATION_DISPATCH_STARTED"]

    outcome = reconcile(safe_validator, operation_id)
    assert outcome.previous_state == State.ERASING.name
    assert outcome.resolved_state == State.PARTIAL.name
    assert state_of(operation_id) == State.PARTIAL.name


def test_the_reconciler_resolves_an_erasing_operation_whose_target_survived(
    safe_validator, temp_dir
):
    """ERASING with the target present: nothing was destroyed, so FAILED."""
    target = temp_dir / "survived.txt"
    target.write_text("payload")
    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
    DispatchJournal(get_session_factory(), AuditActor.system("test")).record_dispatch(
        claim_facts(operation_id, target)
    )

    outcome = reconcile(safe_validator, operation_id)

    assert outcome.resolved_state == State.FAILED.name
    assert target.exists()


def test_api_an_unrecordable_uncertainty_is_still_never_retried(
    operator_client, admin_client, safe_validator, temp_dir, monkeypatch
):
    """Both the result and the uncertainty record are lost; ERASING still holds."""
    target = temp_dir / "api-unrecordable.txt"
    target.write_text("payload")
    operation_id = create_operation(target)
    use_transport(monkeypatch, fault("bad_mac"))
    monkeypatch.setattr(
        pipeline_route.DispatchJournal,
        "record_outcome_unestablished",
        UnrecordableUncertainty.record_outcome_unestablished,
    )

    with pytest.raises(RuntimeError, match="audit store unavailable"):
        operator_client.post(f"/api/operations/{operation_id}/pipeline")

    assert not target.exists()
    assert state_of(operation_id) == State.ERASING.name
    assert types_of(operation_id) == ["PIPELINE_STARTED", "OPERATION_DISPATCH_STARTED"]

    monkeypatch.setattr(
        pipeline_route.DispatchJournal,
        "record_outcome_unestablished",
        DISPATCH_RECORD_OUTCOME,
    )
    use_transport(monkeypatch, InProcessTransport)

    rerun = operator_client.post(f"/api/operations/{operation_id}/pipeline")
    assert rerun.status_code == 409, rerun.text
    assert rerun.json()["error_code"] == "OPERATION_IN_FLIGHT"
    assert rerun.json()["details"] == {"state": State.ERASING.name}
    assert admin_client.post(f"/api/operations/{operation_id}/approve").status_code == 409
    assert admin_client.post(f"/api/operations/{operation_id}/cancel").status_code == 409
    execute = operator_client.post(f"/api/operations/{operation_id}/execute")
    assert execute.status_code == 409, execute.text
    assert execute.json()["error_code"] == "OPERATION_NOT_APPROVED"

    assert state_of(operation_id) == State.ERASING.name
    kinds = types_of(operation_id)
    assert kinds.count("OPERATION_DISPATCH_STARTED") == 1
    assert "OPERATION_CANCELLED" not in kinds
    assert "OPERATION_APPROVED" not in kinds
    assert target.exists() is False

    assert reconcile(safe_validator, operation_id).resolved_state == State.PARTIAL.name


def test_execute_an_unrecordable_uncertainty_keeps_the_original_error(
    investigator_client, admin_client, operator_client, temp_dir, monkeypatch
):
    path = write_target(temp_dir)
    operation_id, _ = approved_operation(investigator_client, admin_client, path)

    real_log = operations_route.AuditLog

    class FailingOnExecuted(real_log):
        def append(self, event_type, *args, **kwargs):
            if event_type is AuditEventType.OPERATION_EXECUTED:
                raise RuntimeError("result store went away")
            return super().append(event_type, *args, **kwargs)

    monkeypatch.setattr(operations_route, "AuditLog", FailingOnExecuted)
    monkeypatch.setattr(
        operations_route.DispatchJournal,
        "record_outcome_unestablished",
        UnrecordableUncertainty.record_outcome_unestablished,
    )

    with pytest.raises(RuntimeError, match="result store went away"):
        operator_client.post(f"/api/operations/{operation_id}/execute")

    assert not path.exists()
    assert state_of(operation_id) == State.ERASING.name
    assert "OPERATION_OUTCOME_UNESTABLISHED" not in types_of(operation_id)


# ---------------------------------------------------------------------------
# Concurrent claims
# ---------------------------------------------------------------------------


def test_concurrent_journals_admit_exactly_one_dispatch(temp_dir):
    target = temp_dir / "contended.txt"
    target.write_text("payload")
    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
    facts = claim_facts(operation_id, target)

    contenders = 8
    barrier = threading.Barrier(contenders)
    outcomes: list[str] = []
    guard = threading.Lock()

    def claim() -> None:
        journal = DispatchJournal(get_session_factory(), AuditActor.system("race"))
        barrier.wait()
        try:
            journal.record_dispatch(facts)
            outcome = "claimed"
        except DispatchJournalError as exc:
            outcome = type(exc).__name__
        with guard:
            outcomes.append(outcome)

    threads = [threading.Thread(target=claim) for _ in range(contenders)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(outcomes) == contenders
    assert outcomes.count("claimed") == 1, outcomes
    assert state_of(operation_id) == State.ERASING.name
    assert types_of(operation_id) == ["OPERATION_DISPATCH_STARTED"]
    assert chain_intact()


def test_concurrent_pipelines_send_the_destructive_request_once(safe_validator, temp_dir):
    target = temp_dir / "double-run.txt"
    target.write_text("payload")
    authenticator = RequestAuthenticator(secrets.token_bytes(32))
    service = PrivilegedService(
        ServiceConfig(validator=safe_validator, authenticator=authenticator)
    )
    sent: list[str] = []
    guard = threading.Lock()

    class Recording(InProcessTransport):
        def exchange(self, envelope):
            if envelope["request"]["operation"] in DESTRUCTIVE:
                with guard:
                    sent.append(envelope["request"]["operation"])
            return super().exchange(envelope)

    runs = 2
    barrier = threading.Barrier(runs)

    class Synchronised(DispatchJournal):
        def record_dispatch(self, facts):
            barrier.wait()
            super().record_dispatch(facts)

    with get_session_factory()() as session:
        operation_id = approve_operation(session, target)
        repo = OperationRepository(session)
        stored = repo.get_target(repo.get_operation(operation_id).target_id)
    request = make_request(
        operation_id,
        target,
        expected_volume_serial=stored.volume_serial,
        expected_file_id=decode_file_id(stored.file_id),
    )
    outcomes: list[str] = []

    def run() -> None:
        with get_session_factory()() as session:
            pipeline = ClosedLoopPipeline(
                session=session,
                validator=safe_validator,
                privileged=PrivilegedClient(Recording(service), authenticator),
                journal=Synchronised(get_session_factory(), AuditActor.system("race")),
            )
            try:
                result = pipeline.run(request)
                session.commit()
                outcome = result.outcome(Stage.ERASE).status.value
            except DispatchConflictError:
                session.rollback()
                outcome = "CONFLICT"
        with guard:
            outcomes.append(outcome)

    threads = [threading.Thread(target=run) for _ in range(runs)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert sorted(outcomes) == ["COMPLETED", "CONFLICT"], outcomes
    assert sent == ["delete_file"]
    assert not target.exists()
    assert state_of(operation_id) == State.PARTIAL.name
    assert types_of(operation_id).count("OPERATION_DISPATCH_STARTED") == 1
    assert chain_intact()


# ---------------------------------------------------------------------------
# The contract says what the routes do
# ---------------------------------------------------------------------------


def test_the_openapi_contract_documents_refusal_and_unestablished_outcomes():
    from oblivion.api import app

    spec = app.openapi()
    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    pipeline = spec["paths"]["/api/operations/{operation_id}/pipeline"]["post"]
    execute = spec["paths"]["/api/operations/{operation_id}/execute"]["post"]

    def schema(operation, code):
        return operation["responses"][code]["content"]["application/json"]["schema"]

    assert schema(pipeline, "409") == error_ref
    assert schema(pipeline, "502") == error_ref
    assert schema(execute, "409") == error_ref
    assert "OPERATION_RECONCILIATION_REQUIRED" in pipeline["responses"]["409"]["description"]
    assert "OPERATION_IN_FLIGHT" in pipeline["responses"]["409"]["description"]
    assert "OPERATION_OUTCOME_UNESTABLISHED" in pipeline["responses"]["502"]["description"]
    assert spec["components"]["schemas"]["ErrorResponse"]["required"] == [
        "error_code",
        "message",
    ]
