"""Recovery object endpoints."""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from oblivion.api.dependencies import (
    get_recovery_vault,
    get_safe_validator,
    get_vault_key,
    require_permission,
)
from oblivion.api.schemas.recovery import (
    RecoveryObjectOut,
    RestoreRequest,
    RestoreResponse,
)
from oblivion.core.erasure.engine import ErasureEngine
from oblivion.core.erasure.events import EngineEventEmitter
from oblivion.core.erasure.vault import RecoveryVault
from oblivion.core.safety.paths import SafePathValidator
from oblivion.persistence.models.user import UserModel

router = APIRouter(prefix="/api/recovery-objects", tags=["recovery"])


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


@router.post("/{recovery_id}/restore", response_model=RestoreResponse, status_code=status.HTTP_202_ACCEPTED)
async def restore_recovery_object(
    recovery_id: str,
    request: RestoreRequest,
    current_user: UserModel = Depends(require_permission("recovery.execute")),
    validator: SafePathValidator = Depends(get_safe_validator),
    vault: RecoveryVault = Depends(get_recovery_vault),
    vault_key: bytes = Depends(get_vault_key),
) -> RestoreResponse:
    """
    Restore a controlled-recoverable object to a validated destination.
    Requires authenticated user with recovery.execute permission.
    Rejects existing destination files by default unless allow_overwrite=True.
    """
    # 1. Validate recovery object exists
    if not vault.exists(recovery_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "RECOVERY_OBJECT_NOT_FOUND", "message": f"Recovery object '{recovery_id}' not found"},
        )

    # 2. Check if destination already exists (Non-overwriting by default)
    dest_path = validator.canonicalize(request.destination)
    if os.path.exists(dest_path) and not request.allow_overwrite:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "RECOVERY_DESTINATION_EXISTS",
                "message": f"Destination '{dest_path}' already exists; overwrite denied by default",
            },
        )

    # 3. Validate destination path within allowed roots
    parent_dir = str(Path(dest_path).parent)
    if not validator.is_allowed(parent_dir):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "RECOVERY_DESTINATION_INVALID", "message": "Destination path is outside allowed roots"},
        )
    if validator.is_system_volume(dest_path):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "PROTECTED_PATH", "message": "Cannot restore onto protected system volume"},
        )

    # 4. Perform restoration via ErasureEngine restore primitive (Server-derived authorization)
    engine = ErasureEngine(validator=validator, event_emitter=EngineEventEmitter())
    engine.set_vault(vault, vault_key)

    restore_result = engine.restore_recovery_object(
        object_id=recovery_id,
        destination_path=dest_path,
        key=vault_key,
        authorized=True,
        allow_overwrite=request.allow_overwrite,
    )

    if restore_result.get("status") == "BLOCKED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "RECOVERY_DESTINATION_EXISTS", "message": restore_result.get("error", "Restore blocked")},
        )

    if restore_result.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "RECOVERY_TEST_FAILED", "message": restore_result.get("error", "Restoration failed")},
        )

    return RestoreResponse(
        status="COMPLETED",
        destination=restore_result["destination"],
        sha256=restore_result["sha256"],
        integrity_verified=restore_result.get("integrity_verified", True),
    )

