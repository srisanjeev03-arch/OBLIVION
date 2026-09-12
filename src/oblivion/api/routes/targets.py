"""Target endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from oblivion.api.dependencies import get_db, get_safe_validator, require_permission
from oblivion.api.schemas.target import TargetAnalyzeRequest, TargetOut, TargetProfile
from oblivion.core.discovery import StorageProfiler, TargetAnalyzer
from oblivion.core.safety.paths import PathSafetyError, SafePathValidator, encode_file_id
from oblivion.persistence.models.user import UserModel
from oblivion.persistence.repositories.operation_repo import OperationRepository

router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.post("/analyze", response_model=TargetProfile, status_code=status.HTTP_200_OK)
async def analyze_target(
    request: TargetAnalyzeRequest,
    current_user: UserModel = Depends(require_permission("evidence.hash")),
    validator: SafePathValidator = Depends(get_safe_validator),
    db: Session = Depends(get_db),
) -> TargetProfile:
    """Analyze a filesystem target without mutation (read-only, requires evidence.hash permission)."""
    validation = validator.validate_target(request.path)

    if not validation["valid"]:
        error_msg = "; ".join(validation.get("errors", ["Invalid path"]))
        error_code = "TARGET_INVALID"
        if any("system" in e.lower() or "protected" in e.lower() for e in validation.get("errors", [])):
            error_code = "PROTECTED_PATH"
        elif any("outside allowed" in e.lower() for e in validation.get("errors", [])):
            error_code = "TARGET_OUTSIDE_ALLOWED_SCOPE"

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": error_code, "message": error_msg},
        )

    try:
        analyzer = TargetAnalyzer(validator=validator)
        result = analyzer.analyze(request.path)
        profiler = StorageProfiler()
        profile = profiler.profile(request.path)
    except PathSafetyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "TARGET_INVALID", "message": str(e)},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "INTERNAL_ERROR", "message": "Failed to analyze target"},
        )

    target_id = result.get("id", f"tgt_{uuid.uuid4().hex[:12]}")
    canonical = result.get("canonical_path", request.path)
    target_type = result.get("type", "unknown")
    # The analyzer publishes the total under "size"; "size_bytes" exists only
    # inside `metadata`. Reading the wrong key here meant every analyzed target
    # was reported to the client as 0 bytes and persisted with total_size=0 -
    # an operator seeing "0 bytes" for the file they are about to erase. Both
    # spellings are accepted so the route survives either producer.
    size_bytes = result.get("size", result.get("size_bytes", 0)) or 0
    file_count = result.get("file_count", 0)
    sha256 = result.get("sha256")

    # Persist target in database for subsequent operations.
    #
    # The identity observed here is what every later destructive step is checked
    # against. It is recorded once, at analysis, and never rewritten: an identity
    # refreshed at execution time would be compared against itself and would
    # accept a substituted object, which is exactly audit finding A-2. An
    # existing row is therefore left alone rather than updated - its identity
    # predates any approval that may already reference it.
    observed_serial = validator.get_volume_serial(canonical)
    observed_file_id = validator._get_file_id(canonical)

    repo = OperationRepository(db)
    existing = repo.get_target(target_id)
    if not existing:
        repo.create_target(
            target_id=target_id,
            path=request.path,
            canonical_path=canonical,
            target_type=target_type if target_type in ("file", "directory") else "file",
            file_count=file_count,
            total_size=size_bytes,
            sha256=sha256,
            volume_serial=observed_serial,
            file_id=encode_file_id(observed_file_id),
        )

    return TargetProfile(
        id=target_id,
        path=canonical,
        canonical_path=canonical,
        type=target_type,
        size_bytes=size_bytes,
        file_count=file_count,
        sha256=sha256,
        storage_profile=profile,
        sensitivity={"level": "PUBLIC", "categories": [], "explanation": "Deterministic analysis (read-only)"},
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
    )


@router.get("/{target_id}", response_model=TargetOut, status_code=status.HTTP_200_OK)
async def get_target(
    target_id: str,
    current_user: UserModel = Depends(require_permission("case.view")),
    db: Session = Depends(get_db),
) -> TargetOut:
    """Retrieve an analyzed target by its ID (requires case.view permission)."""
    repo = OperationRepository(db)
    target = repo.get_target(target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "TARGET_NOT_FOUND", "message": f"Target '{target_id}' not found"},
        )
    return TargetOut.model_validate(target)

