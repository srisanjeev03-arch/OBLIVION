"""Recovery object endpoints.

Listing reads vault metadata. Restoring writes a file, so it is performed by the
privileged service, never by this process: the route validates what it can,
records the request, asks the service, and records the authenticated answer.
"""
import logging
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import (
    get_db,
    get_privileged_client,
    get_recovery_vault,
    get_safe_validator,
    require_permission,
    resolve_audit_actor,
)
from oblivion.api.schemas.error import ErrorResponse
from oblivion.api.schemas.recovery import (
    RecoveryObjectOut,
    RestoreRequest,
    RestoreResponse,
)
from oblivion.core.audit import (
    AuditActor,
    AuditEventType,
    AuditOutcome,
    append_independently,
)
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.safety.paths import PathSafetyError, SafePathValidator
from oblivion.persistence.database import get_session_factory
from oblivion.persistence.models.user import UserModel
from oblivion.privileged.client import PrivilegedResponseRejectedError
from oblivion.privileged.protocol import ResponseStatus
from oblivion.privileged.transport import ServiceUnavailableError
from oblivion.privileged.validation import is_recovery_object_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recovery-objects", tags=["recovery"])

#: The policy and mode a restore is issued under. Restoring an object is part of
#: the controlled-recoverable workflow, and the privileged service checks that
#: pairing like any other.
_RESTORE_POLICY = "ERASURE.RECOVERABLE.ENCRYPTED.V1"
_RESTORE_MODE = "CONTROLLED_RECOVERABLE"


@router.get("", response_model=list[RecoveryObjectOut], status_code=status.HTTP_200_OK)
async def list_recovery_objects(
    current_user: UserModel = Depends(require_permission("recovery.view")),
    vault: RecoveryVault = Depends(get_recovery_vault),
) -> list[RecoveryObjectOut]:
    """List sealed recovery objects metadata (requires recovery.view permission, no secret leakage)."""
    objects: list[RecoveryObjectOut] = []
    vault_path = vault.vault_root

    if not vault_path.exists():
        return objects

    for meta_file in vault_path.glob("*.json"):
        obj_id = meta_file.stem
        try:
            metadata = vault.get_metadata(obj_id)
            objects.append(
                RecoveryObjectOut(
                    id=metadata.get("object_id", obj_id),
                    operation_id=metadata.get("operation_id", "unknown"),
                    status="SEALED",
                    original_sha256=metadata.get("original_sha256", ""),
                    original_size=metadata.get("original_size"),
                    created_at=metadata.get("created_at"),
                )
            )
        except Exception:
            continue

    return objects


def _error(status_code: int, error_code: str, message: str, **details: Any) -> HTTPException:
    body: dict[str, Any] = {"error_code": error_code, "message": message}
    if details:
        body["details"] = details
    return HTTPException(status_code=status_code, detail=body)


def _record(
    actor: AuditActor,
    event_type: AuditEventType,
    outcome: AuditOutcome,
    restore_id: str,
    destination: str,
    recovery_id: str,
    summary: str,
    **metadata: Any,
) -> None:
    """Committed on its own: this request may still fail after the act happened."""
    append_independently(
        get_session_factory(),
        event_type,
        outcome,
        actor,
        operation_id=restore_id,
        target_identity=destination,
        summary=summary,
        safe_metadata={"recovery_object_id": recovery_id, **metadata},
    )


@router.post(
    "/{recovery_id}/restore",
    response_model=RestoreResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Invalid destination, or the privileged service could not restore it.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "RECOVERY_OBJECT_NOT_FOUND: no such object in the vault.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "RECOVERY_DESTINATION_EXISTS or RESTORE_OVERWRITE_NOT_PERMITTED: a restore "
                "never replaces an existing file."
            ),
        },
        status.HTTP_502_BAD_GATEWAY: {
            "model": ErrorResponse,
            "description": (
                "RESTORE_OUTCOME_UNESTABLISHED: the restore was sent but its result could "
                "not be established. Check the destination before retrying."
            ),
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "The privileged service or its vault is unavailable.",
        },
    },
)
async def restore_recovery_object(
    recovery_id: str,
    request: RestoreRequest,
    http_request: Request,
    current_user: UserModel = Depends(require_permission("recovery.execute")),
    validator: SafePathValidator = Depends(get_safe_validator),
    db: Session = Depends(get_db),
) -> RestoreResponse:
    """
    Restore a controlled-recoverable object to a new, validated destination.
    Requires recovery.execute. The privileged service performs the restore and
    independently validates the object and the destination. A restore never
    overwrites: an existing destination, or allow_overwrite=true, is refused.
    """
    actor = resolve_audit_actor(current_user, db)
    restore_id = f"restore_{uuid.uuid4().hex[:16]}"

    if not is_recovery_object_id(recovery_id):
        raise _error(
            status.HTTP_404_NOT_FOUND,
            "RECOVERY_OBJECT_NOT_FOUND",
            "No recovery object has that identifier.",
        )

    try:
        dest_path = validator.canonicalize(request.destination)
    except PathSafetyError:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "RECOVERY_DESTINATION_INVALID",
            "The destination path is not valid.",
        ) from None

    def refuse(code: str, http_status: int, message: str) -> HTTPException:
        _record(
            actor,
            AuditEventType.RECOVERY_RESTORE_REQUESTED,
            AuditOutcome.REFUSED,
            restore_id,
            dest_path,
            recovery_id,
            f"Restore refused before dispatch: {code}.",
            reason_code=code,
        )
        return _error(http_status, code, message)

    if request.allow_overwrite:
        raise refuse(
            "RESTORE_OVERWRITE_NOT_PERMITTED",
            status.HTTP_409_CONFLICT,
            "A restore never overwrites an existing file; choose a new destination.",
        )
    if os.path.exists(dest_path):
        raise refuse(
            "RECOVERY_DESTINATION_EXISTS",
            status.HTTP_409_CONFLICT,
            "The destination already exists; a restore never overwrites.",
        )

    # Only now is the privileged boundary involved. The checks above are advice;
    # the service repeats every one of them for itself.
    privileged = get_privileged_client(http_request, validator)

    _record(
        actor,
        AuditEventType.RECOVERY_RESTORE_REQUESTED,
        AuditOutcome.SUCCEEDED,
        restore_id,
        dest_path,
        recovery_id,
        "Restore dispatched to the privileged service. Its outcome is recorded separately.",
    )

    def performed(outcome: AuditOutcome, summary: str, **metadata: Any) -> None:
        _record(
            actor,
            AuditEventType.RECOVERY_RESTORE_PERFORMED,
            outcome,
            restore_id,
            dest_path,
            recovery_id,
            summary,
            **metadata,
        )

    try:
        response = privileged.restore_recovery_object(
            operation_id=restore_id,
            policy_id=_RESTORE_POLICY,
            mode=_RESTORE_MODE,
            target_path=dest_path,
            target_type="file",
            actor_id=current_user.id,
            params={"object_id": recovery_id, "destination_path": dest_path},
        )
    except ServiceUnavailableError:
        performed(
            AuditOutcome.FAILED,
            "The privileged service could not be reached; nothing was sent.",
            reason_code="PRIVILEGED_SERVICE_UNAVAILABLE",
        )
        raise _error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "PRIVILEGED_SERVICE_UNAVAILABLE",
            "The privileged service could not be reached; nothing was restored.",
        ) from None
    except Exception as exc:
        reason = (
            "PRIVILEGED_RESPONSE_REJECTED"
            if isinstance(exc, PrivilegedResponseRejectedError)
            else "PRIVILEGED_EXCHANGE_FAILED"
        )
        _unestablished(actor, restore_id, dest_path, recovery_id, reason, type(exc).__name__)
        raise _error(
            status.HTTP_502_BAD_GATEWAY,
            "RESTORE_OUTCOME_UNESTABLISHED",
            "The restore was sent but its result could not be established. Check the "
            "destination before retrying.",
            restore_id=restore_id,
            reason_code=reason,
        ) from None

    result = response.result
    if response.status is ResponseStatus.REFUSED:
        performed(
            AuditOutcome.REFUSED,
            "The privileged service refused the restore; nothing was written.",
            refusal_count=len(response.refusals),
        )
        exists = any("already exists" in r for r in response.refusals)
        raise _error(
            status.HTTP_409_CONFLICT if exists else status.HTTP_400_BAD_REQUEST,
            "RECOVERY_DESTINATION_EXISTS" if exists else "RECOVERY_RESTORE_REFUSED",
            "; ".join(response.refusals) or response.message,
        )

    if response.status is ResponseStatus.FAILED:
        if result.get("reconciliation_required"):
            _unestablished(
                actor, restore_id, dest_path, recovery_id,
                "PRIVILEGED_OUTCOME_UNCERTAIN", "PrivilegedResponse",
            )
            raise _error(
                status.HTTP_502_BAD_GATEWAY,
                "RESTORE_OUTCOME_UNESTABLISHED",
                "The privileged service could not confirm the restore. Check the "
                "destination before retrying.",
                restore_id=restore_id,
                reason_code="PRIVILEGED_OUTCOME_UNCERTAIN",
            )
        performed(AuditOutcome.FAILED, "The privileged service failed the restore.")
        raise _error(
            status.HTTP_400_BAD_REQUEST, "RECOVERY_TEST_FAILED", response.message or "Restore failed"
        )

    engine_status = result.get("status")
    error = str(result.get("error", ""))
    if engine_status == "COMPLETED":
        performed(
            AuditOutcome.SUCCEEDED,
            "Restored the object and verified it against the original hash.",
            sha256=result.get("sha256"),
            integrity_verified=bool(result.get("integrity_verified")),
        )
        return RestoreResponse(
            status="COMPLETED",
            destination=str(result.get("destination", dest_path)),
            sha256=str(result.get("sha256", "")),
            integrity_verified=bool(result.get("integrity_verified")),
        )

    if engine_status == "BLOCKED":
        performed(AuditOutcome.REFUSED, "The restore was blocked; nothing was written.", reason=error)
        if error == "RECOVERY_OBJECT_NOT_FOUND":
            raise _error(
                status.HTTP_404_NOT_FOUND, error, "No recovery object has that identifier."
            )
        if error == "VAULT_UNAVAILABLE":
            raise _error(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                error,
                "The privileged service has no vault configured.",
            )
        raise _error(status.HTTP_409_CONFLICT, "RECOVERY_DESTINATION_EXISTS", error or "Restore blocked")

    performed(AuditOutcome.FAILED, "The restore did not complete; nothing was left in place.")
    raise _error(status.HTTP_400_BAD_REQUEST, "RECOVERY_TEST_FAILED", error or "Restoration failed")


def _unestablished(
    actor: AuditActor,
    restore_id: str,
    destination: str,
    recovery_id: str,
    reason_code: str,
    error_type: str,
) -> None:
    try:
        _record(
            actor,
            AuditEventType.OPERATION_OUTCOME_UNESTABLISHED,
            AuditOutcome.FAILED,
            restore_id,
            destination,
            recovery_id,
            "The outcome of the restore could not be established.",
            reason_code=reason_code,
            error_type=error_type,
            restore_outcome="UNESTABLISHED",
        )
    except Exception:
        logger.exception("recovery.restore.uncertainty_not_recorded restore=%s", restore_id)
