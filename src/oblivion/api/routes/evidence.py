"""Evidence verification endpoints."""
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from oblivion.api.dependencies import require_permission
from oblivion.core.evidence.engine import EvidenceEngine
from oblivion.persistence.models.user import UserModel

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


class EvidenceVerificationRequest(BaseModel):
    evidence: dict[str, Any]
    signature: str
    public_key: str


class EvidenceVerificationResult(BaseModel):
    valid: bool


@router.post("/verify", response_model=EvidenceVerificationResult, status_code=status.HTTP_200_OK)
async def verify_evidence_endpoint(
    request: EvidenceVerificationRequest,
    current_user: UserModel = Depends(require_permission("evidence.verify")),
) -> EvidenceVerificationResult:
    """Verify raw evidence package signature against Ed25519 public key (requires evidence.verify permission)."""
    is_valid = EvidenceEngine.verify_evidence(
        request.evidence, request.signature, request.public_key
    )
    return EvidenceVerificationResult(valid=is_valid)
