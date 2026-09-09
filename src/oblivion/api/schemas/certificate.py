"""Pydantic schemas for certificates."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRecordCreate(BaseModel):
    operation_id: str
    evidence_digest: str = Field(..., min_length=64, max_length=64)
    payload: str
    schema_version: str = "1.0"


class EvidenceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    evidence_digest: str
    schema_version: str
    created_at: datetime


class CertificateCreate(BaseModel):
    operation_id: str
    evidence_id: str | None = None
    evidence_digest: str = Field(..., min_length=64, max_length=64)
    signing_algorithm: str = "Ed25519"
    key_id: str | None = None
    public_key: str
    signature: str
    claim: str | None = None
    limitations: list[str] | None = None


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    evidence_digest: str
    signing_algorithm: str
    key_id: str | None = None
    public_key: str
    signature: str
    claim: str | None = None
    issued_at: datetime


class DimensionResultOut(BaseModel):
    dimension: str
    result: str
    detail: str
    evidence_ref: str | None = None


class CertificateVerificationOut(BaseModel):
    certificate_id: str
    overall_status: str = Field(..., pattern="^(VALID|INVALID|INCONCLUSIVE)$")
    dimensions: list[DimensionResultOut]
    signature_valid: bool | None = None
    evidence_integrity: bool | None = None
    signer_trusted: bool | None = None
    cannot_prove: list[str] = Field(default_factory=list)


class VerificationResultOut(BaseModel):
    """Backward-compatible verification result for existing consumers."""
    valid: bool
    status: str
    evidence_integrity: bool = True
    signature_valid: bool = True
    reason: str = ""
    certificate_id: str | None = None
