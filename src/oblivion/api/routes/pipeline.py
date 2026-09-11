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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    get_db,
    resolve_audit_actor,
    get_privileged_client,
    get_safe_validator,
    get_signing_key_manager,
    get_trust_store,
    require_permission,
)
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
from oblivion.core.audit import AuditEventType, AuditLog, AuditOutcome
from oblivion.certificate.trust_model import TrustStore
from oblivion.core.pipeline import ClosedLoopPipeline, PipelineRequest
from oblivion.core.safety.paths import SafePathValidator
from oblivion.core.state.machine import State
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.operation_repo import OperationRepository
from oblivion.privileged.client import PrivilegedClient

router = APIRouter(prefix="/api/operations", tags=["pipeline"])


@router.post(
    "/{operation_id}/pipeline",
    response_model=PipelineResultOut,
    status_code=status.HTTP_200_OK,
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

    pipeline = ClosedLoopPipeline(
        session=db,
        validator=validator,
        privileged=privileged,
        key_manager=key_manager,
        trust_store=trust_store,
    )

    audit = AuditLog(db)
    actor = resolve_audit_actor(current_user, db)

    # Recorded before anything destructive happens, and committed with the rest
    # of the request. If the process dies mid-pipeline, the log still shows that
    # this actor began an erasure against this target - which is exactly the
    # case where the record matters most.
    audit.append(
        AuditEventType.PIPELINE_STARTED,
        AuditOutcome.SUCCEEDED,
        actor,
        operation_id=operation.id,
        target_identity=target.canonical_path,
        summary="Began the closed-loop pipeline.",
        safe_metadata={
            "mode": operation.mode,
            "policy_id": operation.policy_id or "",
            "requested_by": operation.requested_by,
            "approved_by": operation.approved_by,
            "executed_by": current_user.id,
        },
    )

    result = pipeline.run(
        PipelineRequest(
            operation_id=operation.id,
            target_path=target.canonical_path,
            target_type=target.target_type,
            mode=operation.mode,
            policy_id=operation.policy_id or "",
            # From the authenticated session. Never from the request.
            actor_id=current_user.id,
        )
    )

    # The erase stage's own verdict, recorded as the engine gave it. A COMPLETED
    # here means the erase stage reported success and the post-state was
    # re-observed; it is not an assurance claim, and the assurance verdict is
    # recorded separately below precisely so the two cannot be conflated.
    erase_status = next(
        (str(stage.status) for stage in result.stages if str(stage.stage) == "ERASE"),
        "NOT_RUN",
    )
    audit.append(
        AuditEventType.OPERATION_EXECUTED,
        AuditOutcome.SUCCEEDED if erase_status == "COMPLETED" else AuditOutcome.FAILED,
        actor,
        operation_id=operation.id,
        target_identity=target.canonical_path,
        evidence_id=result.evidence_id,
        summary=f"Erase stage reported {erase_status}.",
        safe_metadata={
            "erase_status": erase_status,
            "final_state": str(result.final_state),
        },
    )

    if result.evidence_id:
        audit.append(
            AuditEventType.EVIDENCE_RECORDED,
            AuditOutcome.SUCCEEDED,
            actor,
            operation_id=operation.id,
            evidence_id=result.evidence_id,
            summary="Persisted the evidence record for this operation.",
        )

    if result.certificate_id:
        audit.append(
            AuditEventType.CERTIFICATE_ISSUED,
            AuditOutcome.SUCCEEDED,
            actor,
            operation_id=operation.id,
            evidence_id=result.evidence_id,
            certificate_id=result.certificate_id,
            summary="Issued a signed certificate for this operation.",
        )

    # The conclusion, with the assurance verdict kept in its own field rather
    # than folded into the outcome. INCONCLUSIVE and PARTIAL are real answers,
    # and an audit record that rendered them as failure would misreport them.
    audit.append(
        AuditEventType.PIPELINE_CONCLUDED,
        AuditOutcome.SUCCEEDED,
        actor,
        operation_id=operation.id,
        target_identity=result.target_identity,
        evidence_id=result.evidence_id,
        certificate_id=result.certificate_id,
        summary=f"Pipeline concluded in {result.final_state}.",
        safe_metadata={
            "final_state": str(result.final_state),
            # Kept as separate named fields. "The pipeline finished" and "the
            # assurance engine reached a positive verdict" are different facts,
            # and INCONCLUSIVE is a real answer rather than a failure.
            "assurance_status": result.assurance_status,
            "verification_status": result.verification_status,
        },
    )

    db.commit()

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
