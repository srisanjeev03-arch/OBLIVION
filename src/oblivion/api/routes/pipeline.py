"""The closed-loop pipeline endpoint.

One route, and deliberately no request body. Everything the pipeline acts on -
which target, which mode, which policy, whether it was approved and by whom - is
read from the persisted operation record. The actor comes from the authenticated
session.

That shape is the security property. There is no field in which a caller can
name a different path, so an approved erasure cannot be redirected at another
file; and there is no field in which a caller can name an actor, so identity
cannot be spoofed. Both would be possible with a "convenient" request body, and
neither is possible here.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    get_db,
    get_privileged_client,
    get_safe_validator,
    get_signing_key_manager,
    get_trust_store,
    require_permission,
    resolve_audit_actor,
)
from oblivion.api.schemas.error import ErrorResponse
from oblivion.api.schemas.pipeline import (
    AssuranceStatusOut,
    CoverageOut,
    OperationStateOut,
    PipelineResultOut,
    PipelineStage,
    PipelineStageOut,
    PipelineStageStatus,
    VerificationStatusOut,
)
from oblivion.certificate.keys import SigningKeyManager
from oblivion.certificate.trust_model import TrustStore
from oblivion.core.audit import (
    AuditActor,
    AuditEventType,
    AuditLog,
    AuditOutcome,
    append_independently,
)
from oblivion.core.pipeline import (
    ClosedLoopPipeline,
    DispatchConflictError,
    DispatchJournal,
    DispatchOutcomeUnestablished,
    PipelineRequest,
    PipelineResult,
)
from oblivion.core.pipeline.orchestrator import Stage, StageStatus
from oblivion.core.safety.paths import SafePathValidator, decode_file_id
from oblivion.core.state.machine import State
from oblivion.core.state.reconciliation import INTERRUPTIBLE_STATES
from oblivion.persistence.database import get_session_factory
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged.client import PrivilegedClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operations", tags=["pipeline"])

#: How an ERASE stage outcome maps onto the audit vocabulary.
#:
#: The three audit outcomes mean different things and are never collapsed:
#:
#: * ``SUCCEEDED`` - permitted, attempted, completed.
#: * ``FAILED``    - permitted and attempted, did not complete.
#: * ``REFUSED``   - the system declined; nothing was destroyed.
#:
#: ``UNAVAILABLE`` maps to FAILED rather than REFUSED: the operation had already
#: passed authorization, so the destructive step was permitted and simply could
#: not be carried out. ``SKIPPED`` maps to REFUSED because the pipeline only
#: skips ERASE when an earlier stage - authorization, in practice - declined, and
#: in that case nothing was destroyed.
#:
#: The mapping is total over ``StageStatus``; a new member added to that enum
#: without a decision here fails the test that asserts this table covers it,
#: rather than silently defaulting to one of the three.
_ERASE_OUTCOME: dict[StageStatus, AuditOutcome] = {
    StageStatus.COMPLETED: AuditOutcome.SUCCEEDED,
    StageStatus.FAILED: AuditOutcome.FAILED,
    StageStatus.UNAVAILABLE: AuditOutcome.FAILED,
    StageStatus.REFUSED: AuditOutcome.REFUSED,
    StageStatus.SKIPPED: AuditOutcome.REFUSED,
}

#: Stage outcomes that mean the destructive step was actually attempted. Only
#: these justify writing an `OPERATION_EXECUTED` record.
_ERASE_ATTEMPTED: frozenset[StageStatus] = frozenset(
    {StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.UNAVAILABLE}
)


@router.post(
    "/{operation_id}/pipeline",
    response_model=PipelineResultOut,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Not run. The operation is already concluded "
                "(OPERATION_ALREADY_CONCLUDED), was dispatched and is still in flight "
                "(OPERATION_IN_FLIGHT), awaits reconciliation "
                "(OPERATION_RECONCILIATION_REQUIRED), stopped being READY before this "
                "run could claim it (OPERATION_NOT_READY), or references a missing "
                "target (TARGET_NOT_FOUND). Nothing was dispatched by this request."
            ),
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": (
                "OPERATION_OUTCOME_UNESTABLISHED: the destructive step was dispatched "
                "but its outcome could not be established. The operation is now "
                "RECONCILIATION_REQUIRED and will not be run again until reconciled; "
                "`details` carries operation_id, state and reason_code."
            ),
        },
    },
)
async def run_pipeline(
    operation_id: str,
    current_user: UserModel = Depends(require_permission("operation.execute")),
    db: Session = Depends(get_db),
    validator: SafePathValidator = Depends(get_safe_validator),
    privileged: PrivilegedClient = Depends(get_privileged_client),
    key_manager: SigningKeyManager = Depends(get_signing_key_manager),
    trust_store: TrustStore = Depends(get_trust_store),
) -> PipelineResultOut:
    """Run an approved operation through the full closed loop.

    Requires ``operation.execute``. Holding that permission is necessary but not
    sufficient: the pipeline's own AUTHORIZE stage additionally requires a
    durable approval recorded by someone other than the requester, so a single
    actor cannot both request and run a destructive operation.

    A 200 does not mean the target was erased. It means the pipeline ran and
    reported what happened - which may be a refusal. Read ``final_state`` and the
    per-stage statuses.
    """
    repository = OperationRepository(db)
    operation = repository.get_operation(operation_id)
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": "OPERATION_NOT_FOUND",
                "message": f"Operation '{operation_id}' not found",
            },
        )

    target = repository.get_target(operation.target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "TARGET_NOT_FOUND",
                "message": (
                    "The operation references a target that no longer exists, so "
                    "there is nothing that can be safely acted upon."
                ),
            },
        )

    # Re-running a finished operation would produce a second certificate for one
    # act, so a terminal operation is refused rather than quietly repeated.
    terminal = {
        State.COMPLETED.name,
        State.PARTIAL.name,
        State.FAILED.name,
        State.INCONCLUSIVE.name,
        State.CANCELLED.name,
    }
    if operation.state in terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "OPERATION_ALREADY_CONCLUDED",
                "message": (
                    f"Operation is already in terminal state {operation.state}; "
                    "it will not be run again."
                ),
            },
        )

    actor = resolve_audit_actor(current_user, db)
    operation_id = operation.id
    target_identity = target.canonical_path

    # An operation that was dispatched and not concluded - in flight, or whose
    # outcome could not be established - is not run again. Running it would
    # either dispatch a second time or, finding the target gone, record a
    # refusal over an act that really happened.
    if operation.state in INTERRUPTIBLE_STATES:
        raise _refuse_pipeline(
            actor,
            operation_id,
            target_identity,
            reason_code=(
                "OPERATION_RECONCILIATION_REQUIRED"
                if operation.state == State.RECONCILIATION_REQUIRED.name
                else "OPERATION_IN_FLIGHT"
            ),
            message=(
                f"Operation is in state {operation.state}; its earlier dispatch has not "
                "been concluded, so it will not be run again."
            ),
            state=operation.state,
        )

    audit = AuditLog(db)

    # Recorded before anything destructive happens. If the process dies
    # mid-pipeline, the log still shows that this actor began an erasure against
    # this target - which is exactly the case where the record matters most.
    audit.append(
        AuditEventType.PIPELINE_STARTED,
        AuditOutcome.SUCCEEDED,
        actor,
        operation_id=operation_id,
        target_identity=target_identity,
        summary="Began the closed-loop pipeline.",
        safe_metadata={
            "mode": operation.mode,
            "policy_id": operation.policy_id or "",
            "requested_by": operation.requested_by,
            "approved_by": operation.approved_by,
            "executed_by": current_user.id,
        },
    )

    # Committed now, on its own. Everything below may raise, and a request that
    # raises is rolled back - which used to take this record with it, so an
    # erasure attempt could leave no trace. Committing also leaves the session
    # with no pending writes, which the dispatch journal's independent
    # transactions require.
    db.commit()

    journal = DispatchJournal(get_session_factory(), actor)
    pipeline = ClosedLoopPipeline(
        session=db,
        validator=validator,
        privileged=privileged,
        key_manager=key_manager,
        trust_store=trust_store,
        journal=journal,
    )
    pipeline_request = PipelineRequest(
        operation_id=operation_id,
        target_path=target_identity,
        target_type=target.target_type,
        mode=operation.mode,
        policy_id=operation.policy_id or "",
        # From the authenticated session. Never from the request.
        actor_id=current_user.id,
        # From the persisted target record, written at analysis. Never from
        # the request body and never re-read from disk here: the value has
        # to predate the approval for checking it to mean anything.
        expected_volume_serial=target.volume_serial,
        expected_file_id=decode_file_id(target.file_id),
    )

    try:
        result = pipeline.run(pipeline_request)
        _record_conclusion(audit, actor, operation_id, target_identity, result)
        db.commit()
    except DispatchOutcomeUnestablished as exc:
        # Already durable: the operation is RECONCILIATION_REQUIRED and the
        # journal recorded why. Nothing the pipeline measured afterwards is kept.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error_code": "OPERATION_OUTCOME_UNESTABLISHED",
                "message": (
                    "The destructive step was dispatched, but its outcome could not be "
                    "established. The operation requires reconciliation and will not "
                    "be run again until then."
                ),
                "details": {
                    "operation_id": operation_id,
                    "state": State.RECONCILIATION_REQUIRED.name,
                    "reason_code": exc.reason_code,
                },
            },
        ) from None
    except DispatchConflictError:
        db.rollback()
        raise _refuse_pipeline(
            actor,
            operation_id,
            target_identity,
            reason_code="OPERATION_NOT_READY",
            message=(
                "The operation stopped being READY before this run could dispatch it; "
                "nothing was dispatched by this request."
            ),
            state=None,
        ) from None
    except Exception as exc:
        db.rollback()
        _record_abort(journal, actor, operation_id, target_identity, exc)
        raise

    # Converted explicitly rather than relying on Pydantic to coerce the
    # strings. If the core ever produces a value the wire contract does not
    # name, this raises here instead of quietly shipping an unknown state to a
    # client that has no case for it.
    return PipelineResultOut(
        operation_id=result.operation_id,
        target_identity=result.target_identity,
        final_state=OperationStateOut(result.final_state),
        stages=[
            PipelineStageOut(
                stage=PipelineStage(outcome.stage.value),
                status=PipelineStageStatus(outcome.status.value),
                detail=outcome.detail,
            )
            for outcome in result.stages
        ],
        evidence_id=result.evidence_id,
        evidence_digest=result.evidence_digest,
        certificate_id=result.certificate_id,
        assurance_status=(
            AssuranceStatusOut(result.assurance_status)
            if result.assurance_status is not None
            else None
        ),
        verification_status=(
            VerificationStatusOut(result.verification_status)
            if result.verification_status is not None
            else None
        ),
        coverage=CoverageOut.model_validate(result.coverage)
        if result.coverage
        else CoverageOut(),
        limitations=result.limitations,
        privilege_isolated=privileged.isolated,
    )


def _record_conclusion(
    audit: AuditLog,
    actor: AuditActor,
    operation_id: str,
    target_identity: str,
    result: PipelineResult,
) -> None:
    """Record what the pipeline reported, inside the request transaction."""
    # The erase stage's own verdict, recorded as the engine gave it. A COMPLETED
    # here means the erase stage reported success and the post-state was
    # re-observed; it is not an assurance claim, and the assurance verdict is
    # recorded separately below precisely so the two cannot be conflated.
    #
    # Located by enum identity. `Stage` mixes in `str`, but `Enum.__str__` still
    # wins, so `str(Stage.ERASE)` is "Stage.ERASE" and comparing it against
    # "ERASE" is always false - which is exactly how every run came to record
    # `erase_status: NOT_RUN` with an outcome of FAILED while the stage had in
    # fact COMPLETED. Identity cannot drift that way; `.value` is used wherever
    # the wire form is wanted.
    erase = next((stage for stage in result.stages if stage.stage is Stage.ERASE), None)
    erase_status = erase.status if erase is not None else None

    # `OPERATION_EXECUTED` is written only when the destructive step was actually
    # attempted. Emitting it for an operation the pipeline refused would place a
    # record of an execution that never happened into an append-only log - the
    # precise class of false record this system exists to prevent. Where nothing
    # was executed, the refusal is carried by PIPELINE_CONCLUDED below.
    if erase_status is not None and erase_status in _ERASE_ATTEMPTED:
        audit.append(
            AuditEventType.OPERATION_EXECUTED,
            _ERASE_OUTCOME[erase_status],
            actor,
            operation_id=operation_id,
            target_identity=target_identity,
            evidence_id=result.evidence_id,
            summary=f"Erase stage reported {erase_status.value}.",
            safe_metadata={
                "erase_status": erase_status.value,
                "final_state": result.final_state,
            },
        )

    if result.evidence_id:
        audit.append(
            AuditEventType.EVIDENCE_RECORDED,
            AuditOutcome.SUCCEEDED,
            actor,
            operation_id=operation_id,
            evidence_id=result.evidence_id,
            summary="Persisted the evidence record for this operation.",
        )

    if result.certificate_id:
        audit.append(
            AuditEventType.CERTIFICATE_ISSUED,
            AuditOutcome.SUCCEEDED,
            actor,
            operation_id=operation_id,
            evidence_id=result.evidence_id,
            certificate_id=result.certificate_id,
            summary="Issued a signed certificate for this operation.",
        )

    # The conclusion, with the assurance verdict kept in its own field rather
    # than folded into the outcome. INCONCLUSIVE and PARTIAL are real answers,
    # and an audit record that rendered them as failure would misreport them.
    #
    # The outcome describes the *disposition of the destructive step*, not
    # whether the request returned 200. It was hard-coded SUCCEEDED, which meant
    # a refused operation and a completed one left identical conclusions in the
    # log. An erase that never ran is REFUSED here; one that ran and did not
    # complete is FAILED; neither is a success.
    audit.append(
        AuditEventType.PIPELINE_CONCLUDED,
        _ERASE_OUTCOME.get(erase_status, AuditOutcome.REFUSED)
        if erase_status is not None
        else AuditOutcome.REFUSED,
        actor,
        operation_id=operation_id,
        target_identity=result.target_identity,
        evidence_id=result.evidence_id,
        certificate_id=result.certificate_id,
        summary=f"Pipeline concluded in {result.final_state}.",
        safe_metadata={
            "final_state": result.final_state,
            "erase_status": erase_status.value if erase_status is not None else "NOT_RUN",
            # Kept as separate named fields. "The pipeline finished" and "the
            # assurance engine reached a positive verdict" are different facts,
            # and INCONCLUSIVE is a real answer rather than a failure.
            "assurance_status": result.assurance_status,
            "verification_status": result.verification_status,
        },
    )


def _refuse_pipeline(
    actor: AuditActor,
    operation_id: str,
    target_identity: str,
    *,
    reason_code: str,
    message: str,
    state: str | None,
) -> HTTPException:
    """Record a declined run in its own transaction, and return the 409 to raise."""
    append_independently(
        get_session_factory(),
        AuditEventType.OPERATION_EXECUTION_REFUSED,
        AuditOutcome.REFUSED,
        actor,
        operation_id=operation_id,
        target_identity=target_identity,
        summary=f"Pipeline refused before any destructive work: {reason_code}.",
        safe_metadata={"reason_code": reason_code, "state": state},
    )
    detail: dict[str, Any] = {"error_code": reason_code, "message": message}
    if state is not None:
        detail["details"] = {"state": state}
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _record_abort(
    journal: DispatchJournal,
    actor: AuditActor,
    operation_id: str,
    target_identity: str,
    exc: Exception,
) -> None:
    """Durably record a run that raised, after its transaction was rolled back.

    If the destructive step was dispatched, its result is now lost with the
    rollback, so the operation is marked for reconciliation. Otherwise nothing
    was dispatched, and the run is concluded as refused so PIPELINE_STARTED is
    not left without an ending. A failure here is logged and the original
    exception still propagates.
    """
    try:
        if journal.dispatched:
            journal.record_outcome_unestablished(
                reason_code="RESULT_NOT_RECORDED", error_type=type(exc).__name__
            )
        else:
            append_independently(
                get_session_factory(),
                AuditEventType.PIPELINE_CONCLUDED,
                AuditOutcome.REFUSED,
                actor,
                operation_id=operation_id,
                target_identity=target_identity,
                summary="Pipeline aborted before any destructive dispatch.",
                safe_metadata={
                    "erase_status": "NOT_RUN",
                    "aborted": True,
                    "error_type": type(exc).__name__,
                },
            )
    except Exception:
        logger.exception("pipeline.abort.not_recorded operation=%s", operation_id)
