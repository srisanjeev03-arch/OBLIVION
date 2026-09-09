"""FastAPI API endpoints."""
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from oblivion.core.discovery import TargetAnalyzer
from oblivion.core.discovery import StorageProfiler
from oblivion.core.safety.paths import SafePathValidator, PathSafetyError
from oblivion.core.evidence.engine import EvidenceEngine
from oblivion.certificate.signer import Ed25519SignerVerifier

app = FastAPI(title="Oblivion", version="0.1.0-slice1")

class TargetAnalyzeRequest(BaseModel):
    """Request to analyze a target."""
    path: str

class TargetProfile(BaseModel):
    """Profile of analyzed target."""
    id: str
    path: str
    type: str  # file, directory
    size_bytes: int
    file_count: int
    sha256: str
    storage_profile: Dict[str, Any]
    sensitivity: Optional[Dict[str, Any]] = None
    warnings: list[str] = []

class EvidenceVerificationRequest(BaseModel):
    evidence: Dict[str, Any]
    signature: str
    public_key: str

class VerificationResult(BaseModel):
    valid: bool

@app.post("/api/targets/analyze")
async def analyze_target(request: TargetAnalyzeRequest) -> TargetProfile:
    """Analyze a target without mutation (Slice 1)."""
    validator = SafePathValidator()
    validation = validator.validate_target(request.path)
    if not validation["valid"]:
        raise HTTPException(
            status_code=400,
            detail={"error_code": "TARGET_INVALID", "message": "; ".join(validation["errors"])},
        )
    analyzer = TargetAnalyzer(validator=validator)
    result = analyzer.analyze(request.path)
    profiler = StorageProfiler()
    profile = profiler.profile(request.path)
    return TargetProfile(
        id=result.get("id", ""),
        path=result.get("canonical_path", request.path),
        type=result.get("type", "unknown"),
        size_bytes=result.get("size_bytes", 0),
        file_count=result.get("file_count", 0),
        sha256=result.get("sha256", ""),
        storage_profile=profile,
        sensitivity={"classification": "unknown", "reason": "Slice 1 - advisory only"},
        warnings=result.get("warnings", []),
    )

@app.post("/api/evidence/verify")
async def verify_evidence(request: EvidenceVerificationRequest) -> VerificationResult:
    """Verify evidence package signature."""
    is_valid = EvidenceEngine.verify_evidence(
        request.evidence, request.signature, request.public_key
    )
    return VerificationResult(valid=is_valid)
