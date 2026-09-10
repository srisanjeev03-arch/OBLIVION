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
    get_privileged_client,
    get_safe_validator,
    get_signing_key_manager,
    get_trust_store,
    require_permission,
)
from oblivion.api.schemas.pipeline import (
    AssuranceStatusOut,
    OperationStateOut,
    PipelineResultOut,
    PipelineStage,
    PipelineStageOut,
    PipelineStageStatus,
    VerificationStatusOut,
)
from oblivion.certificate.keys import SigningKeyManager
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
        limitations=result.limitations,
        privilege_isolated=privileged.isolated,
    )
