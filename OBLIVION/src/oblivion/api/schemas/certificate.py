"""Pydantic schemas for certificates."""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


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
    evidence_id: Optional[str] = None
    evidence_digest: str = Field(..., min_length=64, max_length=64)
    signing_algorithm: str = "Ed25519"
    key_id: Optional[str] = None
    public_key: str
    signature: str
    claim: Optional[str] = None
    limitations: Optional[list[str]] = None


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    evidence_digest: str
    signing_algorithm: str
    key_id: Optional[str] = None
    public_key: str
    signature: str
    claim: Optional[str] = None
    issued_at: datetime
