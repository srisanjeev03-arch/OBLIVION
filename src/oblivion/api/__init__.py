"""FastAPI API package."""
from oblivion.api.app import app, create_app
from oblivion.api.routes.evidence import EvidenceVerificationRequest
from oblivion.api.routes.evidence import (
    EvidenceVerificationResult as VerificationResult,
)
from oblivion.api.schemas.target import TargetAnalyzeRequest, TargetProfile

__all__ = [
    "EvidenceVerificationRequest",
    "TargetAnalyzeRequest",
    "TargetProfile",
    "VerificationResult",
    "app",
    "create_app",
]

