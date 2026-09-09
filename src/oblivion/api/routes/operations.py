"""Operation endpoints with Authentication, Approval Gating & Separation of Duties."""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    DatabaseEventEmitter,
    get_db,
    get_recovery_vault,
    get_safe_validator,
    get_vault_key,
    require_permission,
)
from oblivion.api.schemas.operation import (
    CreateOperationRequest,
    OperationEventOut,
    OperationOut,
)
from oblivion.core.auth.sod import (
    SoDViolationError,
    validate_approval,
)
from oblivion.core.erasure.engine import ErasureEngine, ErasureMode
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.policy import PolicyEngine, PolicyError
from oblivion.core.safety.paths import SafePathValidator
from oblivion.persistence.models.operation import OperationEventModel
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.operation_repo import OperationRepository

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.post("", response_model=OperationOut, status_code=status.HTTP_202_ACCEPTED)
async def create_operation(
    request: CreateOperationRequest,
    current_user: UserModel = Depends(require_permission("operation.request")),
    validator: SafePathValidator = Depends(get_safe_validator),
    db: Session = Depends(get_db),
) -> OperationOut:
    """
    Creates an erasure operation in PENDING_APPROVAL state.
    Does NOT execute destructive deletion upon creation (Approval-gated lifecycle).
    """
    repo = OperationRepository(db)

    # 1. Validate Target exists in DB
    target = repo.get_target(request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "TARGET_NOT_FOUND", "message": f"Target '{request.target_id}' not found"},
        )

    # 2. Revalidate Target on filesystem
    is_dir_tree = request.mode == "COMPLETE_ERASURE"
    validation = validator.validate_target(target.canonical_path, is_directory_tree=is_dir_tree)
    if not validation["valid"]:
        error_msg = "; ".join(validation.get("errors", ["Target path invalid"]))
        error_code = "TARGET_INVALID"
        if any("system" in e.lower() or "protected" in e.lower() for e in validation.get("errors", [])):
            error_code = "PROTECTED_PATH"
        elif any("outside allowed" in e.lower() for e in validation.get("errors", [])):
            error_code = "TARGET_OUTSIDE_ALLOWED_SCOPE"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": error_code, "message": error_msg},
        )

    # 3. Validate confirmation
    if not request.confirmation.acknowledged_risk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "CONFIRMATION_REQUIRED", "message": "Destructive risk must be explicitly acknowledged"},
        )

    # 4. Server-Side Allowlisted Policy Validation
    try:
        policy_def = PolicyEngine.validate_operation_policy(
            policy_id=request.policy_id,
            mode=request.mode,
            target_type=target.target_type,
        )
    except PolicyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "POLICY_NOT_ALLOWED", "message": str(e)},
        )

    # 5. Create Operation Model in PENDING_APPROVAL state (Server-derived requester)
    operation_id = f"op_{uuid.uuid4().hex[:12]}"
    now = datetime.datetime.now(datetime.UTC)
    op_model = repo.create_operation(
        operation_id=operation_id,
        target_id=target.id,
        mode=request.mode,
        policy_id=policy_def.policy_id,
        state="PENDING_APPROVAL",
        actor_id=current_user.id,
        requested_by=current_user.id,
        created_at=now,
        started_at=now,
    )

    # 6. Record Creation Audit Event
    emitter = DatabaseEventEmitter(session=db)
    emitter.emit(
        event_type="OPERATION_REQUESTED",
        operation_id=operation_id,
        target_path=target.canonical_path,
        details={"state": "PENDING_APPROVAL", "mode": request.mode, "policy_id": request.policy_id, "requested_by": current_user.id},
    )
    db.flush()

    return OperationOut(
        id=op_model.id,
        target_id=op_model.target_id,
        mode=op_model.mode,
        state=op_model.state,
        policy_id=op_model.policy_id,
        progress_percent=0.0,
        warnings=[],
        error=None,
        actor_id=op_model.actor_id,
        created_at=op_model.created_at,
        started_at=op_model.started_at,
        completed_at=op_model.completed_at,
    )


@router.post("/{operation_id}/approve", response_model=OperationOut, status_code=status.HTTP_200_OK)
async def approve_operation(
    operation_id: str,
    current_user: UserModel = Depends(require_permission("operation.approve")),
    db: Session = Depends(get_db),
) -> OperationOut:
    """
    Approves a pending operation subject to Separation of Duties enforcement.
    Requires ADMIN role / operation.approve permission.
    """
    repo = OperationRepository(db)
    op = repo.get_operation(operation_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "OPERATION_NOT_FOUND", "message": f"Operation '{operation_id}' not found"},
        )

    # 1. State check - terminal operations cannot be un-cancelled or approved
    terminal_states = {"COMPLETED", "FAILED", "PARTIAL", "CANCELLED", "INCONCLUSIVE"}
    if op.state in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "OPERATION_STATE_INVALID", "message": f"Cannot approve operation in terminal state '{op.state}'"},
        )

    if op.state == "READY":
        return OperationOut.model_validate(op)

    # 2. Separation of Duties check: Requester cannot approve own request
    try:
        validate_approval(requested_by=op.requested_by, approving_actor_id=current_user.id)
    except SoDViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "FORBIDDEN", "message": str(e)},
        )

    # 3. Transition to READY
    op.approved_by = current_user.id
    op.state = "READY"
    repo.append_event(
        event_id=f"evt_{uuid.uuid4().hex[:12]}",
        operation_id=operation_id,
        sequence=10,
        event_type="OPERATION_APPROVED",
        from_state="PENDING_APPROVAL",
        to_state="READY",
        payload=str({"approved_by": current_user.id}),
    )
    db.flush()

    return OperationOut(
        id=op.id,
        target_id=op.target_id,
        mode=op.mode,
        state=op.state,
        policy_id=op.policy_id,
        progress_percent=10.0,
        warnings=[op.warnings] if op.warnings else [],
        error=None,
        actor_id=op.actor_id,
        created_at=op.created_at,
        started_at=op.started_at,
        completed_at=op.completed_at,
    )


@router.post("/{operation_id}/execute", response_model=OperationOut, status_code=status.HTTP_200_OK)
async def execute_operation_endpoint(
    operation_id: str,
    current_user: UserModel = Depends(require_permission("operation.execute")),
    validator: SafePathValidator = Depends(get_safe_validator),
    vault: RecoveryVault = Depends(get_recovery_vault),
    vault_key: bytes = Depends(get_vault_key),
    db: Session = Depends(get_db),
) -> OperationOut:
    """
    Executes an approved operation.
    Requires OPERATOR role / operation.execute permission.
    Enforces that operation was approved prior to execution.
    """
    repo = OperationRepository(db)
    op = repo.get_operation(operation_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "OPERATION_NOT_FOUND", "message": f"Operation '{operation_id}' not found"},
        )

    # 1. Approval gating check
    if op.state != "READY" or op.approved_by is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "OPERATION_NOT_APPROVED",
                "message": f"Operation '{operation_id}' must be in READY state and approved prior to execution (current state: {op.state})",
            },
        )

    target = repo.get_target(op.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "TARGET_NOT_FOUND", "message": f"Target '{op.target_id}' not found"},
        )

    # 2. Revalidate Target on filesystem
    is_dir_tree = op.mode == "COMPLETE_ERASURE"
    validation = validator.validate_target(target.canonical_path, is_directory_tree=is_dir_tree)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "TARGET_INVALID", "message": "; ".join(validation.get("errors", ["Target path invalid"]))},
        )

    mode_map = {
        "COMPLETE_ERASURE": ErasureMode.COMPLETE_ERASURE,
        "SELECTIVE_PERMANENT": ErasureMode.SELECTIVE_PERMANENT,
        "CONTROLLED_RECOVERABLE": ErasureMode.CONTROLLED_RECOVERABLE,
    }
    erasure_mode = mode_map[op.mode]

    # 3. Initialize Erasure Engine
    emitter = DatabaseEventEmitter(session=db)
    engine = ErasureEngine(validator=validator, event_emitter=emitter)
    if erasure_mode == ErasureMode.CONTROLLED_RECOVERABLE:
        engine.set_vault(vault, vault_key)

    target_serial = validator.get_volume_serial(target.canonical_path) or "UNKNOWN"
    target_file_id = validator._get_file_id(target.canonical_path)

    # 4. Execute operation
    op.executed_by = current_user.id
    op_result = engine.execute_operation(
        mode=erasure_mode,
        operation_id=operation_id,
        target_path=target.canonical_path,
        target_serial=target_serial,
        target_file_id=target_file_id,
    )

    # 5. Update DB State
    final_state = op_result.get("status", "FAILED")
    op.state = final_state
    op.completed_at = datetime.datetime.now(datetime.UTC)
    if op_result.get("warnings"):
        op.warnings = "; ".join(op_result.get("warnings", []))
    if op_result.get("failed") or op_result.get("blocked"):
        errors = op_result.get("failed", []) + op_result.get("blocked", [])
        op.error_code = "ERASURE_ERROR" if op_result.get("failed") else "SAFETY_VIOLATION"

    db.flush()

    return OperationOut(
        id=op.id,
        target_id=op.target_id,
        mode=op.mode,
        state=op.state,
        policy_id=op.policy_id,
        progress_percent=100.0 if final_state == "COMPLETED" else 0.0,
        warnings=op_result.get("warnings", []),
        error={"code": op.error_code, "message": "; ".join(op_result.get("failed", []) or op_result.get("blocked", []))} if op.error_code else None,
        actor_id=op.actor_id,
        created_at=op.created_at,
        started_at=op.started_at,
        completed_at=op.completed_at,
    )


@router.get("/{operation_id}", response_model=OperationOut, status_code=status.HTTP_200_OK)
async def get_operation(
    operation_id: str,
    current_user: UserModel = Depends(require_permission("operation.view")),
    db: Session = Depends(get_db),
) -> OperationOut:
    """Get operation status and details (requires operation.view permission)."""
    repo = OperationRepository(db)
    op = repo.get_operation(operation_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "OPERATION_NOT_FOUND", "message": f"Operation '{operation_id}' not found"},
        )

    return OperationOut(
        id=op.id,
        target_id=op.target_id,
        mode=op.mode,
        state=op.state,
        policy_id=op.policy_id,
        progress_percent=100.0 if op.state == "COMPLETED" else (50.0 if op.state in ("ERASING", "VERIFYING") else 0.0),
        warnings=[op.warnings] if op.warnings else [],
        error={"code": op.error_code, "message": "Operation failed"} if op.error_code else None,
        actor_id=op.actor_id,
        created_at=op.created_at,
        started_at=op.started_at,
        completed_at=op.completed_at,
    )


@router.post("/{operation_id}/cancel", response_model=OperationOut, status_code=status.HTTP_202_ACCEPTED)
async def cancel_operation(
    operation_id: str,
    current_user: UserModel = Depends(require_permission("operation.request")),
    db: Session = Depends(get_db),
) -> OperationOut:
    """Request operation cancellation (requires operation.request permission)."""
    repo = OperationRepository(db)
    op = repo.get_operation(operation_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "OPERATION_NOT_FOUND", "message": f"Operation '{operation_id}' not found"},
        )

    terminal_states = {"COMPLETED", "FAILED", "PARTIAL", "CANCELLED", "INCONCLUSIVE"}
    if op.state in terminal_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "OPERATION_STATE_INVALID", "message": f"Cannot cancel operation in terminal state '{op.state}'"},
        )

    irreversible_states = {"ERASING", "VERIFYING"}
    if op.state in irreversible_states:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "OPERATION_STATE_INVALID", "message": f"Cannot cancel operation during active state '{op.state}'"},
        )

    op.state = "CANCELLED"
    op.completed_at = datetime.datetime.now(datetime.UTC)
    repo.append_event(
        event_id=f"evt_{uuid.uuid4().hex[:12]}",
        operation_id=operation_id,
        sequence=99,
        event_type="OPERATION_CANCELLED",
        from_state="READY",
        to_state="CANCELLED",
    )
    db.flush()

    return OperationOut(
        id=op.id,
        target_id=op.target_id,
        mode=op.mode,
        state=op.state,
        policy_id=op.policy_id,
        progress_percent=0.0,
        warnings=["Operation cancelled by user request"],
        error=None,
        actor_id=op.actor_id,
        created_at=op.created_at,
        started_at=op.started_at,
        completed_at=op.completed_at,
    )


@router.get("/{operation_id}/events", response_model=list[OperationEventOut], status_code=status.HTTP_200_OK)
async def get_operation_events(
    operation_id: str,
    current_user: UserModel = Depends(require_permission("operation.view")),
    db: Session = Depends(get_db),
) -> list[OperationEventOut]:
    """Retrieve audit and lifecycle events for an operation (requires operation.view permission)."""
    repo = OperationRepository(db)
    op = repo.get_operation(operation_id)
    if not op:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "OPERATION_NOT_FOUND", "message": f"Operation '{operation_id}' not found"},
        )

    events = db.query(OperationEventModel).filter_by(operation_id=operation_id).order_by(OperationEventModel.sequence.asc()).all()
    return [OperationEventOut.model_validate(e) for e in events]
