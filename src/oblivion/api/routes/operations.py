"""Operation endpoints with Authentication, Approval Gating & Separation of Duties."""
import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    DatabaseEventEmitter,
    get_db,
    resolve_audit_actor,
    get_recovery_vault,
    get_safe_validator,
    get_vault_key,
    require_permission,
)
from oblivion.api.schemas.operation import (
    CreateOperationRequest,
    OperationEventOut,
    OperationOut,
    OperationPageOut,
)
from oblivion.core.audit import (
    AuditActor,
    AuditEventType,
    AuditLog,
    AuditOutcome,
    append_independently,
)
from oblivion.core.auth.sod import (
    SoDViolationError,
    validate_approval,
)
from oblivion.core.erasure.engine import ErasureEngine, ErasureMode
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.policy import PolicyEngine, PolicyError
from oblivion.core.state.machine import State
from oblivion.core.safety.paths import SafePathValidator, decode_file_id
from oblivion.persistence.database import get_session_factory
from oblivion.persistence.models.operation import OperationEventModel
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.operation_repo import OperationRepository

router = APIRouter(prefix="/api/operations", tags=["operations"])

#: Hard ceiling on a listing page, so a read cannot be turned into a denial of
#: service against the database.
_MAX_PAGE = 200

#: Every state the machine can actually reach. A filter naming anything else is
#: refused rather than returning an empty page, which would read as "there are
#: no operations in that state" when the truth is "that state does not exist".
_KNOWN_STATES: frozenset[str] = frozenset(member.name for member in State)

#: Progress shown for a listed operation, derived from its persisted state.
#:
#: Deliberately coarse and deliberately not invented: the operations table
#: stores no progress column, so anything finer would be a number this system
#: never measured. A terminal state is 100% complete in the sense that nothing
#: further will happen to it - not in the sense that it succeeded.
_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        State.COMPLETED.name,
        State.FAILED.name,
        State.PARTIAL.name,
        State.INCONCLUSIVE.name,
        State.CANCELLED.name,
    }
)


def _progress_for(state: str) -> float:
    """Coarse progress from the persisted state. Never a fabricated percentage."""
    if state in _TERMINAL_STATES:
        return 100.0
    if state == State.READY.name:
        return 10.0
    return 0.0


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
    AuditLog(db).append(
        AuditEventType.OPERATION_CREATED,
        AuditOutcome.SUCCEEDED,
        resolve_audit_actor(current_user, db),
        operation_id=operation_id,
        target_identity=target.canonical_path,
        summary="Requested an erasure operation; awaiting a second actor's approval.",
        safe_metadata={
            "mode": request.mode,
            "policy_id": policy_def.policy_id,
            "state": "PENDING_APPROVAL",
            # The requester is recorded here as well as in the operation row,
            # so the separation-of-duties pair can be reconstructed from the
            # audit log alone, without trusting the mutable operation record.
            "requested_by": current_user.id,
        },
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


@router.get("", response_model=OperationPageOut, status_code=status.HTTP_200_OK)
async def list_operations(
    state: str | None = Query(None, max_length=32),
    operation_id: str | None = Query(None, max_length=64),
    requested_by: str | None = Query(None, max_length=64),
    target_id: str | None = Query(None, max_length=64),
    limit: int = Query(50, ge=1, le=_MAX_PAGE),
    offset: int = Query(0, ge=0),
    # Declared for its dependency, not its value: evaluating `require_permission`
    # is what enforces authorization. Removing the parameter would remove the
    # gate, so the unused-argument warning is silenced deliberately rather than
    # by dropping the guard.
    current_user: UserModel = Depends(  # noqa: ARG001
        require_permission("operation.view")
    ),
    db: Session = Depends(get_db),
) -> OperationPageOut:
    """List persisted operations (requires ``operation.view``).

    This closes the gap that forced an operator to paste an operation ID into
    the address bar: the console had a ledger and the contract published no way
    to fill it.

    Filtering is applied in the database, and every field returned comes from a
    persisted row. Nothing is synthesised - no identifier, no state, no
    progress. An operation that does not exist does not appear.

    Authorization is the existing model, unchanged: ``operation.view`` is held
    by ADMIN, INVESTIGATOR, OPERATOR, AUDITOR and VIEWER, and this route exposes
    only operation records. It is not a general database listing, and it exposes
    no audit, evidence or certificate material - those keep their own
    permissions (``audit.view``, ``evidence.view``).

    An unrecognised ``state`` is refused rather than ignored: a filter silently
    dropped returns more than was asked for while looking like it returned
    exactly what was asked for.
    """
    if state is not None and state not in _KNOWN_STATES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error_code": "UNKNOWN_OPERATION_STATE",
                "message": f"'{state}' is not an operation state this system can reach",
            },
        )

    repo = OperationRepository(db)
    rows, total = repo.list_operations(
        state=state,
        operation_id=operation_id,
        requested_by=requested_by,
        target_id=target_id,
        limit=limit,
        offset=offset,
    )

    return OperationPageOut(
        operations=[
            OperationOut(
                id=row.id,
                target_id=row.target_id,
                mode=row.mode,
                state=row.state,
                policy_id=row.policy_id,
                progress_percent=_progress_for(row.state),
                warnings=[row.warnings] if row.warnings else [],
                error=None,
                actor_id=row.actor_id,
                created_at=row.created_at,
                started_at=row.started_at,
                completed_at=row.completed_at,
            )
            for row in rows
        ],
        returned=len(rows),
        total=total,
        limit=limit,
        offset=offset,
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
        # Committed separately: this request raises 403 and its transaction is
        # rolled back, but a refused self-approval is precisely the event an
        # auditor needs to see. It must outlive the request that caused it.
        append_independently(
            get_session_factory(),
            AuditEventType.OPERATION_APPROVAL_REFUSED,
            AuditOutcome.REFUSED,
            resolve_audit_actor(current_user, db),
            operation_id=operation_id,
            summary="Approval refused: separation of duties.",
            safe_metadata={"requested_by": op.requested_by, "reason": str(e)},
        )
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
    AuditLog(db).append(
        AuditEventType.OPERATION_APPROVED,
        AuditOutcome.SUCCEEDED,
        resolve_audit_actor(current_user, db),
        operation_id=operation_id,
        summary="Approved the operation.",
        safe_metadata={
            # Both halves of the duty split, in one immutable record.
            "requested_by": op.requested_by,
            "approved_by": current_user.id,
            "to_state": "READY",
        },
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


def _refuse_execution(
    *,
    reason_code: str,
    message: str,
    actor: AuditActor,
    operation_id: str,
    status_code: int,
    target_identity: str | None = None,
    safe_metadata: dict[str, Any] | None = None,
) -> HTTPException:
    """Record a declined execution attempt, and return the error to raise.

    Written in a transaction of its own for the same reason a refused approval
    is: this request is about to fail and roll back, and an attempt to run a
    destructive operation that was turned away is exactly what an auditor needs
    to find later. Before this existed, every refusal on this endpoint left no
    trace at all (audit finding A-1), so the log could not answer "did anyone
    try to execute an unapproved operation?".

    The event is ``OPERATION_EXECUTION_REFUSED`` with outcome ``REFUSED``, never
    ``OPERATION_EXECUTED`` with a failed outcome: nothing was executed, and an
    append-only log must not record an execution that did not happen.
    """
    append_independently(
        get_session_factory(),
        AuditEventType.OPERATION_EXECUTION_REFUSED,
        AuditOutcome.REFUSED,
        actor,
        operation_id=operation_id,
        target_identity=target_identity,
        summary=f"Execution refused before any destructive work: {reason_code}.",
        safe_metadata={"reason_code": reason_code, **(safe_metadata or {})},
    )
    return HTTPException(
        status_code=status_code,
        detail={"error_code": reason_code, "message": message},
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
    # Resolved once: every refusal below records who was turned away, and the
    # actor must come from the authenticated session, never from the request.
    actor = resolve_audit_actor(current_user, db)

    repo = OperationRepository(db)
    op = repo.get_operation(operation_id)
    if not op:
        raise _refuse_execution(
            reason_code="OPERATION_NOT_FOUND",
            message=f"Operation '{operation_id}' not found",
            actor=actor,
            operation_id=operation_id,
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # 1. Approval gating check
    if op.state != "READY" or op.approved_by is None:
        raise _refuse_execution(
            reason_code="OPERATION_NOT_APPROVED",
            message=(
                f"Operation '{operation_id}' must be in READY state and approved prior "
                f"to execution (current state: {op.state})"
            ),
            actor=actor,
            operation_id=operation_id,
            status_code=status.HTTP_409_CONFLICT,
            safe_metadata={"state": op.state, "approved": op.approved_by is not None},
        )

    target = repo.get_target(op.target_id)
    if not target:
        raise _refuse_execution(
            reason_code="TARGET_NOT_FOUND",
            message=f"Target '{op.target_id}' not found",
            actor=actor,
            operation_id=operation_id,
            status_code=status.HTTP_404_NOT_FOUND,
            safe_metadata={"target_id": op.target_id},
        )

    # 2. Revalidate Target on filesystem
    is_dir_tree = op.mode == "COMPLETE_ERASURE"
    validation = validator.validate_target(target.canonical_path, is_directory_tree=is_dir_tree)
    if not validation["valid"]:
        raise _refuse_execution(
            reason_code="TARGET_INVALID",
            message="; ".join(validation.get("errors", ["Target path invalid"])),
            actor=actor,
            operation_id=operation_id,
            status_code=status.HTTP_400_BAD_REQUEST,
            target_identity=target.canonical_path,
        )

    # 2b. Bind execution to the identity recorded when the target was analysed.
    #
    # This value predates the approval, which is the whole point. The previous
    # revision read the "expected" identity from the filesystem a few lines below
    # and handed it to the engine, so the engine compared the object with itself
    # and a file swapped in after approval was erased as though it were the
    # approved one (audit finding A-2).
    expected_serial = target.volume_serial
    expected_file_id = decode_file_id(target.file_id)

    if expected_serial is None or expected_file_id is None:
        raise _refuse_execution(
            reason_code="TARGET_IDENTITY_UNAVAILABLE",
            message=(
                "No target identity was recorded when this target was analysed, so the "
                "object on disk cannot be checked against the one that was approved. "
                "Re-analyse the target before executing."
            ),
            actor=actor,
            operation_id=operation_id,
            status_code=status.HTTP_409_CONFLICT,
            target_identity=target.canonical_path,
            safe_metadata={
                "expected_volume_serial_present": expected_serial is not None,
                "expected_file_id_present": expected_file_id is not None,
            },
        )

    if not validator.revalidate_handle(
        target.canonical_path, expected_serial, expected_file_id
    ):
        raise _refuse_execution(
            reason_code="TARGET_IDENTITY_MISMATCH",
            message=(
                "The object at this path is not the object that was approved: its "
                "identity no longer matches the one recorded at analysis. Refusing "
                "rather than erasing a substituted object."
            ),
            actor=actor,
            operation_id=operation_id,
            status_code=status.HTTP_409_CONFLICT,
            target_identity=target.canonical_path,
            safe_metadata={"target_identity_verified": False},
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

    # 4. Execute operation.
    #
    # The engine revalidates the handle itself immediately before it acts. It is
    # given the identity recorded at analysis - not one read from disk here - so
    # that its check compares the object against what was approved rather than
    # against itself.
    op.executed_by = current_user.id
    op_result = engine.execute_operation(
        mode=erasure_mode,
        operation_id=operation_id,
        target_path=target.canonical_path,
        target_serial=expected_serial,
        target_file_id=expected_file_id,
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

    # The engine's own verdict, recorded as given. A COMPLETED here means the
    # erasure step reported success - it is not an assurance claim, and nothing
    # in this record should be read as one.
    AuditLog(db).append(
        AuditEventType.OPERATION_EXECUTED,
        AuditOutcome.SUCCEEDED if final_state == "COMPLETED" else AuditOutcome.FAILED,
        resolve_audit_actor(current_user, db),
        operation_id=operation_id,
        target_identity=target.canonical_path,
        summary=f"Executed the approved operation; engine reported {final_state}.",
        safe_metadata={
            "final_state": final_state,
            "requested_by": op.requested_by,
            "approved_by": op.approved_by,
            "executed_by": current_user.id,
            "error_code": op.error_code,
        },
    )
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
    AuditLog(db).append(
        AuditEventType.OPERATION_CANCELLED,
        AuditOutcome.SUCCEEDED,
        resolve_audit_actor(current_user, db),
        operation_id=operation_id,
        summary="Cancelled the operation before execution.",
        safe_metadata={"cancelled_by": current_user.id},
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
