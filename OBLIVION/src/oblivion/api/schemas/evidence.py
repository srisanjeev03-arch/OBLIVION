"""Pydantic schemas for evidence."""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any


class BaselineCreate(BaseModel):
    operation_id: str
    target_id: str
    file_inventory: Optional[dict[str, Any]] = None
    hashes: Optional[dict[str, Any]] = None
    metadata_json: Optional[dict[str, Any]] = None


class BaselineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    target_id: str
    created_at: datetime


class RecoveryTestCreate(BaseModel):
    operation_id: str
    result_status: str
    evidence_json: Optional[dict[str, Any]] = None


class RecoveryTestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    result_status: str
    created_at: datetime


class ResidualFindingCreate(BaseModel):
    operation_id: str
    severity: str = Field(..., max_length=32)
    description: str
    artifact_path: Optional[str] = None
    evidence_json: Optional[dict[str, Any]] = None


class ResidualFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    severity: str
    description: str
    artifact_path: Optional[str] = None
    created_at: datetime


class AssuranceResultCreate(BaseModel):
    operation_id: str
    status: str
    confidence: str
    reasons: Optional[list[str]] = None
    limitations: Optional[list[str]] = None


class AssuranceResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    operation_id: str
    status: str
    confidence: str
    created_at: datetime
