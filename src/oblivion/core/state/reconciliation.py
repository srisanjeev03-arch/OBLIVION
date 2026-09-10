"""Resolving operations that were interrupted mid-flight.

A destructive filesystem call cannot be recalled once it has returned. If the
process stops between performing one and recording it, the persisted operation
state and the filesystem disagree - and the disagreement is not detectable by
looking at either one alone.

This module looks at both and says what it can prove:

* the target is gone, and the operation was destructive → the destructive step
  ran; the operation is ``PARTIAL``, because the stages after it did not
* the target is still there → the destructive step did not run; the operation is
  ``FAILED``, and nothing was destroyed
* the filesystem cannot answer → ``INCONCLUSIVE``

What it deliberately never returns is ``COMPLETED``. Completion in this system
means the whole pipeline finished - erasure, verification, recovery test,
residual analysis, assurance, evidence, certificate. An interrupted operation
did not do those things, and a reconciler that marked it complete would be
manufacturing the one claim the product exists to make truthfully.

Observation states are reused from the evidence model rather than reinvented, so
"we looked and saw" and "we could not look" stay distinguishable here exactly as
they do in evidence.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from oblivion.core.evidence.record import ObservationState
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import State
from oblivion.persistence.models.operation import (
    OperationEventModel,
    OperationModel,
    TargetModel,
)

logger = logging.getLogger(__name__)

#: Modes whose whole point is that the target stops existing. Only for these
#: does the target's absence mean the destructive step ran.
DESTRUCTIVE_MODES: Final[frozenset[str]] = frozenset(
    {"SELECTIVE_PERMANENT", "COMPLETE_ERASURE", "CONTROLLED_RECOVERABLE"}
)

#: States in which the process may stop with work genuinely in flight. Approval
#: states are excluded: nothing destructive happens before READY, so an
#: interrupted approval is simply an operation that was never approved.
INTERRUPTIBLE_STATES: Final[frozenset[str]] = frozenset(
    {
        State.ERASING.name,
        State.VERIFYING.name,
        State.RECOVERY_TEST.name,
        State.RESIDUAL_SCAN.name,
        State.RESIDUAL_ANALYSIS.name,
        State.ASSESSING.name,
        State.CERTIFYING.name,
        State.RECONCILIATION_REQUIRED.name,
    }
)


class TargetPresence(str, Enum):
    """What the filesystem says about the target now."""

    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class ReconciliationResult:
    """What was established about one interrupted operation.

    ``observation`` carries the evidence model's distinction: ``OBSERVED`` means
    the filesystem was read successfully, ``UNAVAILABLE`` means it could not be.
    A caller must not treat the second as though it were the first.
    """

    operation_id: str
    previous_state: str
    resolved_state: str
    presence: TargetPresence
    observation: ObservationState
    detail: str
    destructive: bool

    @property
    def resolved(self) -> bool:
        """Whether a definite outcome was reached.

        ``INCONCLUSIVE`` is a real answer about the operation, but it is not a
        resolution: the operation still needs a human or a better observation.
        """
        return self.resolved_state != State.INCONCLUSIVE.name


class OperationReconciler:
    """Reconciles persisted operation state against the actual filesystem."""

    def __init__(self, session: Session, validator: SafePathValidator) -> None:
        self._session = session
        self._validator = validator

    def interrupted_operations(self) -> list[OperationModel]:
        """Operations whose recorded state implies work that is no longer running.

        Anything found here after a clean start was interrupted: nothing is
        executing yet, so a non-terminal in-flight state cannot be current.
        """
        statement = select(OperationModel).where(
            OperationModel.state.in_(sorted(INTERRUPTIBLE_STATES))
        )
        return list(self._session.execute(statement).scalars().all())

    def observe_target(self, canonical_path: str) -> tuple[TargetPresence, str]:
        """Ask the filesystem whether the target is there, without guessing.

        ``lexists`` rather than ``exists``: a dangling symlink is still an entry
        that was not removed, and reporting it absent would credit the operation
        with a deletion it did not perform.
        """
        try:
            if os.path.lexists(canonical_path):
                return (
                    TargetPresence.PRESENT,
                    "Target is still present on the filesystem.",
                )
            return (TargetPresence.ABSENT, "Target is no longer present.")
        except OSError as exc:
            # Not knowing is a distinct answer from knowing it is there. Folding
            # this into PRESENT would assert that nothing was destroyed, which
            # is precisely what could not be established.
            return (
                TargetPresence.UNDETERMINED,
                f"Filesystem could not be read to establish presence: {exc}",
            )

    def reconcile(self, operation: OperationModel) -> ReconciliationResult:
        """Establish what happened to one interrupted operation."""
        previous_state = operation.state
        target = self._session.get(TargetModel, operation.target_id)
        destructive = operation.mode in DESTRUCTIVE_MODES

        if target is None:
            return self._record(
                operation,
                previous_state,
                State.INCONCLUSIVE,
                TargetPresence.UNDETERMINED,
                ObservationState.UNAVAILABLE,
                "The operation's target record is missing, so its filesystem "
                "state cannot be compared against anything.",
                destructive,
            )

        presence, detail = self.observe_target(target.canonical_path)

        if presence is TargetPresence.UNDETERMINED:
            return self._record(
                operation,
                previous_state,
                State.INCONCLUSIVE,
                presence,
                ObservationState.UNAVAILABLE,
                detail,
                destructive,
            )

        if not destructive:
            # A non-destructive operation performs no deletion, so whatever the
            # filesystem shows, no destruction is attributable to it. It was
            # interrupted, and that is all that can be said.
            return self._record(
                operation,
                previous_state,
                State.FAILED,
                presence,
                ObservationState.OBSERVED,
                f"{operation.mode} performs no destruction; the operation was "
                f"interrupted before completing. {detail}",
                destructive,
            )

        if presence is TargetPresence.ABSENT:
            # The destructive step ran. The stages that turn a deletion into an
            # evidenced, certified operation did not - so this is PARTIAL, never
            # COMPLETED.
            return self._record(
                operation,
                previous_state,
                State.PARTIAL,
                presence,
                ObservationState.OBSERVED,
                "The destructive step completed - the target is gone - but the "
                "operation was interrupted before verification, assurance and "
                "evidence could be produced. No certificate may be issued for "
                "this operation.",
                destructive,
            )

        return self._record(
            operation,
            previous_state,
            State.FAILED,
            presence,
            ObservationState.OBSERVED,
            "The target is still present, so the destructive step did not run. "
            "Nothing was destroyed by this operation.",
            destructive,
        )

    def reconcile_all(self) -> list[ReconciliationResult]:
        """Reconcile every interrupted operation. Returns what was established."""
        results = [self.reconcile(op) for op in self.interrupted_operations()]
        if results:
            logger.info(
                "operation.reconciliation.completed count=%d unresolved=%d",
                len(results),
                sum(1 for r in results if not r.resolved),
            )
        return results

    def _record(
        self,
        operation: OperationModel,
        previous_state: str,
        resolved: State,
        presence: TargetPresence,
        observation: ObservationState,
        detail: str,
        destructive: bool,
    ) -> ReconciliationResult:
        """Persist the outcome and append an audit event for it.

        The event is appended whatever the outcome, including ``INCONCLUSIVE``:
        a reconciliation that established nothing is still a thing that happened
        to this operation, and leaving no trace would make the next reconciler
        unable to tell a first attempt from a repeated failure.
        """
        operation.state = resolved.name

        self._session.add(
            OperationEventModel(
                id=f"evt_{uuid.uuid4().hex[:16]}",
                operation_id=operation.id,
                sequence=1 + len(operation.events),
                event_type="OPERATION_RECONCILED",
                from_state=previous_state,
                to_state=resolved.name,
                payload=json.dumps(
                    {
                        "detail": detail,
                        "presence": presence.value,
                        "observation": observation.value,
                        "destructive_mode": destructive,
                    },
                    separators=(",", ":"),
                ),
            )
        )

        return ReconciliationResult(
            operation_id=operation.id,
            previous_state=previous_state,
            resolved_state=resolved.name,
            presence=presence,
            observation=observation,
            detail=detail,
            destructive=destructive,
        )
