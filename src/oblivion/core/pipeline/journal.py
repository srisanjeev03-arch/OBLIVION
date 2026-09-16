"""A durable record of a destructive dispatch, kept outside the caller's transaction.

A destructive call cannot be recalled once it has been sent. If the request that
sent it then fails - the reply does not authenticate, the exchange breaks, or the
result cannot be written - the caller's transaction rolls back, and without this
module the operation would fall back to ``READY`` with no trace that anything
was sent. The next attempt would then find the target gone and record a refusal,
which is a false account of what happened.

So the dispatch is journalled in two independently committed steps:

1. **Before sending**: ``READY`` → ``ERASING`` plus ``OPERATION_DISPATCH_STARTED``.
   The state change is a compare-and-set on ``READY``, so two runs of one
   operation cannot both dispatch. If this cannot be written, nothing is sent.
2. **If the result cannot be established**: ``ERASING`` →
   ``RECONCILIATION_REQUIRED`` plus ``OPERATION_OUTCOME_UNESTABLISHED``. The
   operation is then neither completed nor failed; ``OperationReconciler``
   resolves it against the filesystem.

When the result *is* established, the caller's own transaction replaces
``ERASING`` with the final state, and nothing further is written here. If that
transaction is lost anyway, ``ERASING`` remains, which the reconciler already
treats as interrupted.

Independent commits need the caller's session to hold no uncommitted writes when
they happen; otherwise the two transactions contend for the same audit-chain
position and, on SQLite, the same write lock. Callers commit before dispatch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from oblivion.core.audit import AuditActor, AuditEventType, AuditLog, AuditOutcome
from oblivion.core.state.machine import OperationStateMachine, State
from oblivion.persistence.models.operation import OperationModel

logger = logging.getLogger(__name__)


class DispatchJournalError(Exception):
    """The dispatch could not be recorded durably, so it must not happen."""


class DispatchConflictError(DispatchJournalError):
    """The operation is no longer ``READY``; another run owns it or it has moved on."""


@dataclass(frozen=True)
class DispatchFacts:
    """What is known about a destructive step at the moment it is dispatched."""

    operation_id: str
    privileged_operation: str
    mode: str
    policy_id: str
    target_identity: str
    target_type: str
    expected_volume_serial: str | None
    expected_file_id: tuple[int, int, int] | None
    executed_by: str

    def metadata(self) -> dict[str, Any]:
        return {
            "privileged_operation": self.privileged_operation,
            "mode": self.mode,
            "policy_id": self.policy_id,
            "target_type": self.target_type,
            "expected_volume_serial": self.expected_volume_serial,
            "expected_file_id": (
                list(self.expected_file_id) if self.expected_file_id is not None else None
            ),
            "executed_by": self.executed_by,
        }


class DispatchJournal:
    """Records one run's dispatch. Use a fresh journal for every run."""

    def __init__(self, session_factory: sessionmaker[Session], actor: AuditActor) -> None:
        self._session_factory = session_factory
        self._actor = actor
        self._facts: DispatchFacts | None = None
        self._outcome_unestablished = False

    @property
    def dispatched(self) -> bool:
        """Whether this run durably recorded a dispatch."""
        return self._facts is not None

    @property
    def outcome_unestablished(self) -> bool:
        return self._outcome_unestablished

    def record_dispatch(self, facts: DispatchFacts) -> None:
        """Claim the operation and record the attempt, before anything is sent."""
        if self._facts is not None:
            raise DispatchJournalError("This journal has already recorded a dispatch")
        OperationStateMachine(State.READY).transition_to(State.ERASING)

        try:
            with self._session_factory() as session:
                claimed = session.execute(
                    update(OperationModel)
                    .where(
                        OperationModel.id == facts.operation_id,
                        OperationModel.state == State.READY.name,
                    )
                    .values(state=State.ERASING.name)
                    .execution_options(synchronize_session=False)
                ).rowcount
                if claimed != 1:
                    session.rollback()
                    raise DispatchConflictError(
                        f"Operation {facts.operation_id} is no longer READY, so this run "
                        "does not own it; nothing was dispatched."
                    )
                AuditLog(session).append(
                    AuditEventType.OPERATION_DISPATCH_STARTED,
                    AuditOutcome.SUCCEEDED,
                    self._actor,
                    operation_id=facts.operation_id,
                    target_identity=facts.target_identity,
                    summary=(
                        f"Dispatching {facts.privileged_operation} to the privileged "
                        "service. Its outcome is recorded separately."
                    ),
                    safe_metadata={
                        **facts.metadata(),
                        "from_state": State.READY.name,
                        "to_state": State.ERASING.name,
                    },
                )
                session.commit()
        except DispatchJournalError:
            raise
        except Exception as exc:  # noqa: BLE001 - any failure here forbids dispatch
            raise DispatchJournalError(
                f"The dispatch could not be recorded ({type(exc).__name__}); refusing "
                "to send a destructive request that would leave no durable trace."
            ) from exc

        self._facts = facts

    def record_outcome_unestablished(self, *, reason_code: str, error_type: str) -> None:
        """Mark the dispatched operation as needing reconciliation.

        ``error_type`` is a class name, never an exception message: messages can
        carry text that arrived from the far side of the boundary.
        """
        facts = self._facts
        if facts is None:
            raise DispatchJournalError("No dispatch was recorded, so there is nothing to mark")
        if self._outcome_unestablished:
            return

        with self._session_factory() as session:
            current = session.execute(
                select(OperationModel.state).where(OperationModel.id == facts.operation_id)
            ).scalar_one_or_none()
            moved = session.execute(
                update(OperationModel)
                .where(
                    OperationModel.id == facts.operation_id,
                    OperationModel.state == State.ERASING.name,
                )
                .values(state=State.RECONCILIATION_REQUIRED.name)
                .execution_options(synchronize_session=False)
            ).rowcount
            if moved != 1:
                # No longer ERASING: the result was already committed, or the
                # reconciler has resolved the operation. Either way the outcome
                # is recorded elsewhere, and claiming uncertainty would be false.
                session.rollback()
                logger.error(
                    "pipeline.dispatch.outcome_already_recorded operation=%s state=%s",
                    facts.operation_id,
                    current,
                )
                return
            AuditLog(session).append(
                AuditEventType.OPERATION_OUTCOME_UNESTABLISHED,
                AuditOutcome.FAILED,
                self._actor,
                operation_id=facts.operation_id,
                target_identity=facts.target_identity,
                summary=(
                    f"The outcome of {facts.privileged_operation} could not be "
                    "established; the operation requires reconciliation."
                ),
                safe_metadata={
                    **facts.metadata(),
                    "reason_code": reason_code,
                    "error_type": error_type,
                    "destructive_outcome": "UNESTABLISHED",
                    "from_state": State.ERASING.name,
                    "to_state": State.RECONCILIATION_REQUIRED.name,
                },
            )
            session.commit()

        self._outcome_unestablished = True
        logger.warning(
            "pipeline.dispatch.outcome_unestablished operation=%s reason=%s",
            facts.operation_id,
            reason_code,
        )
